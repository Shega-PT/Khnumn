#!/usr/bin/env python3
"""Linha de base manual: reconstrução pela via directa do motor.

A linha de base é o resultado de referência contra o qual a implementação do
Khnumn é comparada. É obtida pela via mais directa que existe: o motor é
chamado directamente, sem o Khnumn no meio, e o resultado é registado no
formato do relatório de `processos/protocolo-benchmark.md` §9.

A separação importa. Se a linha de base fosse produzida pelo próprio código
que se está a validar, uma falha comum aos dois seria invisível: os dois
números concordariam, e o concordar não diria nada.

Uso:
    python scripts/linha-base.py --imagens DIR --saida DIR [--mapeador incremental|global]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pycolmap

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))


def pico_memoria_mb(pid: int) -> int:
    """Lê o pico de memória residente de um processo, em megabytes."""
    try:
        for linha in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if linha.startswith("VmHWM:"):
                return int(linha.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def executar_com_medicao(funcao, *argumentos, **opcoes):
    """Executa uma função e mede o seu tempo e o seu pico de memória."""
    inicio = time.monotonic()
    resultado = funcao(*argumentos, **opcoes)
    duracao = time.monotonic() - inicio
    return resultado, duracao


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--imagens", required=True, help="directório com as imagens")
    analisador.add_argument("--saida", required=True, help="directório de saída")
    analisador.add_argument("--mapeador", default="incremental", choices=["incremental", "global"])
    analisador.add_argument("--max-image-size", type=int, default=1600)
    analisador.add_argument("--threads", type=int, default=2)
    analisador.add_argument("--max-features", type=int, default=4096)
    analisador.add_argument("--limite-memoria-mb", type=int, default=500)
    argumentos = analisador.parse_args()

    imagens = Path(argumentos.imagens).resolve()
    saida = Path(argumentos.saida).resolve()
    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True, exist_ok=True)

    base = saida / "colmap"
    base.mkdir(parents=True, exist_ok=True)
    base_imagens = saida / "imagens"
    base_imagens.mkdir(parents=True, exist_ok=True)

    nomes = sorted(p.name for p in imagens.iterdir() if p.is_file())
    for nome in nomes:
        destino = base_imagens / nome
        if not destino.exists():
            destino.symlink_to(imagens / nome)

    base_dados = base / "database.db"

    extracao = pycolmap.FeatureExtractionOptions()
    extracao.max_image_size = argumentos.max_image_size
    extracao.num_threads = argumentos.threads
    extracao.use_gpu = False
    extracao.sift.max_num_features = argumentos.max_features

    instantes: dict[str, float] = {}

    def medir(nome):
        def embrulho(*args, **kwargs):
            inicio = time.monotonic()
            resultado = args[0](*args[1:], **kwargs) if args else None
            instantes[nome] = time.monotonic() - inicio
            return resultado

        return embrulho

    print(f"[1/3] extraccao de features ({len(nomes)} imagens, max_image_size={argumentos.max_image_size})", flush=True)
    _, instantes["extracao"] = executar_com_medicao(
        pycolmap.extract_features,
        str(base_dados),
        str(base_imagens),
        nomes,
        pycolmap.CameraMode.AUTO,
        pycolmap.ImageReaderOptions(),
        extracao,
    )

    print("[2/3] correspondencia exaustiva", flush=True)
    correspondencia = pycolmap.FeatureMatchingOptions()
    correspondencia.sift.cpu_brute_force_matcher = True
    _, instantes["correspondencia"] = executar_com_medicao(
        pycolmap.match_exhaustive,
        str(base_dados),
        correspondencia,
        pycolmap.ExhaustivePairingOptions(),
        pycolmap.TwoViewGeometryOptions(),
    )

    print(f"[3/3] mapeamento {argumentos.mapeador}", flush=True)
    # O gauge e declarado, e nao escolhido pelo motor: o par inicial e as
    # duas primeiras imagens por ordem, e a primeira camara e mantida
    # constante. A comparacao com a implementacao so e justa com a mesma
    # declaracao.
    import sqlite3

    ligacao = sqlite3.connect(f"file:{base_dados}?mode=ro", uri=True)
    ids = dict(ligacao.execute("SELECT name, image_id FROM images").fetchall())
    cameras = ligacao.execute("SELECT camera_id FROM cameras ORDER BY camera_id").fetchall()
    ligacao.close()
    par_inicial = (ids[nomes[0]], ids[nomes[1]]) if len(nomes) > 1 else None
    camera_constante = cameras[0][0] if cameras else None

    if argumentos.mapeador == "global":
        opcoes = pycolmap.GlobalPipelineOptions()
    else:
        opcoes = pycolmap.IncrementalPipelineOptions()
        opcoes.random_seed = 0
        opcoes.init_num_trials = 1 if par_inicial else 10
        if par_inicial:
            opcoes.init_image_id1 = par_inicial[0]
            opcoes.init_image_id2 = par_inicial[1]
        if camera_constante is not None:
            opcoes.constant_cameras = {camera_constante}
    _, instantes["mapeamento"] = executar_com_medicao(
        pycolmap.incremental_mapping if argumentos.mapeador == "incremental" else pycolmap.global_mapping,
        str(base_dados),
        str(base_imagens),
        str(base / "sparse"),
        opcoes,
    )

    from khnumn.adaptadores.colmap import componentes_conectadas, pasta_do_modelo

    modelo_pasta = pasta_do_modelo(base / "sparse")
    reconstrucao = pycolmap.Reconstruction(str(modelo_pasta))
    if argumentos.mapeador == "global":
        reconstrucoes = pycolmap.global_mapping(str(base_dados), str(base_imagens), str(base / "sparse"), opcoes)
        reconstrucao = max(reconstrucoes.values(), key=lambda r: r.num_reg_images())

    resumo = reconstrucao.summary()

    # Erro de reprojecção: o motor sabe calculá-lo sobre as observações
    # registadas, e é esse o número que interessa, e não uma média de
    # resíduos por imagem.
    erro_medio = reconstrucao.compute_mean_reprojection_error()
    num_observacoes = reconstrucao.compute_num_observations()
    comprimento_medio = reconstrucao.compute_mean_track_length()
    observacoes_por_imagem = reconstrucao.compute_mean_observations_per_reg_image()

    relatorio = {
        "schema_version": "1.0.0",
        "identificador": "linha-base-eth3d-terrace",
        "data": _dt.datetime.now(_dt.timezone.utc).date().isoformat(),
        "questao": "A reconstrucao esparsa pela via directa do motor e reprodutivel dentro das tolerancias?",
        "hipotese": "A cena de 23 imagens, com boa sobreposicao e textura, reconstroi-se de forma consistente.",
        "variavel_alterada": "nenhuma: esta e a execucao de referencia",
        "dados": {
            "conjunto": "eth3d-terrace",
            "particao": "ajuste",
            "imagens": len(nomes),
            "hashes": "manifests/hashes.yaml",
        },
        "ambiente": {
            "maquina": "Intel Core i3-5005U, 4 threads, 3826 MiB RAM, sem acelerador",
            "software": {
                "pycolmap": pycolmap.__version__,
                "colmap": "embebido no wheel pycolmap",
            },
            "semente": "N/A",
        },
        "configuracao": {
            "max_image_size": argumentos.max_image_size,
            "max_num_features": argumentos.max_features,
            "threads": argumentos.threads,
            "use_gpu": False,
            "mapeador": argumentos.mapeador,
            "limite_memoria_mb": argumentos.limite_memoria_mb,
            "par_inicial": list(nomes[:2]),
            "camera_constante": camera_constante,
        },
        "resultados": {
            "camera_registadas": reconstrucao.num_reg_images(),
            "cameras_no_modelo": len(reconstrucao.cameras),
            "pontos_3d": reconstrucao.num_points3D(),
            "observacoes": num_observacoes,
            "erro_reprojecao_medio_px": erro_medio,
            "comprimento_medio_de_rastro": comprimento_medio,
            "observacoes_por_imagem_media": observacoes_por_imagem,
            "componentes_conectadas": componentes_conectadas(reconstrucao),
        },
        "tempo": {chave: round(valor, 2) for chave, valor in instantes.items()},
        "estado": "NOT_VALIDATED",
        "causa": (
            "Sem referencia geodetica independente: este conjunto valida a consistencia "
            "interna e a forma da superficie, nao a exactidao posicional absoluta."
        ),
        "resumo_do_modelo": resumo,
    }

    (saida / "relatorio.json").write_text(
        json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(relatorio["resultados"], indent=2, ensure_ascii=False))
    print(f"tempo: {relatorio['tempo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
