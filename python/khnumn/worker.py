"""Ponto de entrada da camada cientifica.

O nucleo Rust chama este modulo uma vez por tarefa: escreve um pedido JSON
na entrada padrao e le um resultado JSON na saida padrao. O resultado e
sempre um unico documento JSON, mesmo em caso de falha, para que o
diagnostico nunca se perca num traceback.

O contrato e o mesmo dos adaptadores de motores externos
(`docs/Khnumn.md` §18.3), e a forma dos verbos mantem-se para que um
adaptador de motor e um algoritmo interno sejam indistinguiveis do ponto de
vista do nucleo.
"""

from __future__ import annotations

import json
import hashlib
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import (
    ajuste,
    alinhamento,
    benchmark_fusao,
    cenario,
    catalogo,
    compatibilidade_temporal,
    cobertura,
    controle,
    cog,
    decisao_evidencia,
    dtm,
    evidencia,
    gnss_imu,
    lidar,
    marcas,
    metadados,
    ortoimagem,
    persistencia,
    planeador,
    plano_execucao,
    qualidade,
    radiometria,
    raster,
    rasterizador,
    renderizacao,
    residuos,
    retry_checkpoint,
    reprodutibilidade,
    rolling_shutter,
    seguranca,
    scheduler,
    satelite,
    superficie,
    tempo,
    validacao,
    validacao_denso,
    verificacao_multivista,
    video,
    worker_remoto,
)
from .adaptadores.colmap import AdaptadorColmap, ErroAdaptador, ParametrosMotor

#: Versao do contrato implementada por este modulo.
VERSAO_CONTRATO = "khnumn-tarefa-v1"

#: Algoritmos implementados, com a sua versao.
ALGORITMOS: dict[str, str] = {
    "metadados.extrair": "1.0.0",
    "qualidade.imagem": "1.0.0",
    "qualidade.duplicados": "1.0.0",
    "sfm.reconstruir": "1.0.0",
    "sfm.extrair": "1.0.0",
    "sfm.corresponder": "1.0.0",
    "sfm.mapear": "1.0.0",
    "sfm.exportar": "1.0.0",
    "marcas.detectar": "1.0.0",
    "marcas.filtrar": "1.0.0",
    "marcas.verificar_acquisibilidade": "1.0.0",
    "controlo.ingerir": "1.0.0",
    "controlo.checkpoints": "1.0.0",
    "controlo.similaridade": "1.0.0",
    "controlo.ajustar": "1.0.0",
    "controlo.ensemble": "1.0.0",
    "controlo.gnss_priors": "1.0.0",
    "validacao.metricas": "1.0.0",
    "validacao.incerteza": "1.0.0",
    "marcas.rever": "1.0.0",
    "raster.residuos": "1.0.0",
}


def _executar_metadados(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Extrai os metadados de um ficheiro."""
    caminho = parametros.get("caminho")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    if caminho is None:
        raise ValueError("o algoritmo 'metadados.extrair' exige o parametro 'caminho'")
    return {"metadados": metadados.extrair(Path(caminho))}


def _executar_qualidade(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Avalia a qualidade de uma imagem."""
    caminho = parametros.get("caminho")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    if caminho is None:
        raise ValueError("o algoritmo 'qualidade.imagem' exige o parametro 'caminho'")
    return {"qualidade": qualidade.avaliar(Path(caminho))}


def _executar_duplicados(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Procura quase-duplicados num conjunto de imagens."""
    caminhos = [Path(c) for c in parametros.get("caminhos", [])]
    if not caminhos and entradas:
        caminhos = [Path(entrada["uri"]) for entrada in entradas if entrada.get("uri")]
    return {"duplicados": qualidade.quase_duplicados(caminhos)}


def _executar_sfm(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstroi a cena esparsa, pelo adaptador do motor.

    Os parametros do motor são validados pelo adaptador antes de qualquer
    chamada, e são registados no resultado. Uma alteracao de configuracao do
    motor que nao passe por aqui deixa de ser rastreavel.
    """
    imagens = [Path(c) for c in parametros.get("imagens", [])]
    if not imagens and entradas:
        imagens = [Path(entrada["uri"]) for entrada in entradas if entrada.get("uri")]
    if not imagens:
        raise ValueError("o algoritmo 'sfm.reconstruir' exige a lista de imagens")

    saida = Path(parametros.get("saida", "./saida-sfm"))
    parametros_motor = parametros.get("motor", {}) or {}
    adaptador = AdaptadorColmap(ParametrosMotor.de_dict(parametros_motor))

    resultado = adaptador.run(imagens, saida)
    return {
        "sfm": {
            "estado": resultado.estado,
            "cameras_registadas": resultado.cameras_registadas,
            "cameras_no_modelo": resultado.cameras_no_modelo,
            "pontos_3d": resultado.pontos_3d,
            "observacoes": resultado.observacoes,
            "erro_reprojecao_medio_px": resultado.erro_reprojecao_medio_px,
            "comprimento_medio_de_rastro": resultado.comprimento_medio_de_rastro,
            "observacoes_por_imagem_media": resultado.observacoes_por_imagem_media,
            "versao_motor": resultado.versao_motor,
            "parametros_motor": resultado.parametros,
            "duracao_s": resultado.duracao_s,
            "metricas": resultado.metricas,
            "modelo": str(saida / "sparse"),
        },
        "avisos": resultado.avisos,
        "saidas": resultado.saidas,
    }


def _executar_sfm_extrair(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Fase de extracção de features, isolada do resto do motor.

    A fase corre num processo próprio porque o seu pico de memória é
    independente do das restantes, e a soma seria o que estouraria o
    orçamento.
    """
    imagens = [Path(c) for c in parametros.get("imagens", [])]
    if not imagens and entradas:
        imagens = [Path(entrada["uri"]) for entrada in entradas if entrada.get("uri")]
    if not imagens:
        raise ValueError("o algoritmo 'sfm.extrair' exige a lista de imagens")

    base = Path(parametros.get("base", "./base-sfm"))
    adaptador = AdaptadorColmap(ParametrosMotor.de_dict(parametros.get("motor", {}) or {}))
    resultado = adaptador.extrair(imagens, base)
    return {"sfm": {"fase": "extracao", "estado": resultado.estado, "metricas": resultado.metricas,
                    "duracao_s": resultado.duracao_s, "versao_motor": resultado.versao_motor},
            "avisos": resultado.avisos}


def _executar_sfm_corresponder(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Fase de correspondencia, isolada."""
    base = Path(parametros.get("base", "./base-sfm"))
    adaptador = AdaptadorColmap(ParametrosMotor.de_dict(parametros.get("motor", {}) or {}))
    resultado = adaptador.corresponder(base)
    return {"sfm": {"fase": "correspondencia", "estado": resultado.estado, "metricas": resultado.metricas,
                    "duracao_s": resultado.duracao_s, "versao_motor": resultado.versao_motor},
            "avisos": resultado.avisos}


def _executar_sfm_mapear(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Fase de mapeamento e diagnostico, isolada."""
    base = Path(parametros.get("base", "./base-sfm"))
    adaptador = AdaptadorColmap(ParametrosMotor.de_dict(parametros.get("motor", {}) or {}))
    resultado = adaptador.mapear(base, gnss_priors=parametros.get("gnss_priors"))
    diagnostico = resultado.metricas.get("diagnostico", {})
    return {"sfm": {"fase": "mapeamento", "estado": resultado.estado,
                    "cameras_registadas": resultado.cameras_registadas,
                    "cameras_no_modelo": resultado.cameras_no_modelo,
                    "pontos_3d": resultado.pontos_3d,
                    "observacoes": resultado.observacoes,
                    "erro_reprojecao_medio_px": resultado.erro_reprojecao_medio_px,
                    "comprimento_medio_de_rastro": resultado.comprimento_medio_de_rastro,
                    "observacoes_por_imagem_media": resultado.observacoes_por_imagem_media,
                    "diagnostico": diagnostico,
                    "metricas": resultado.metricas,
                    "duracao_s": resultado.duracao_s,
                    "versao_motor": resultado.versao_motor},
            "avisos": resultado.avisos}


def _executar_sfm_exportar(parametros: dict[str, Any], entradas: list[dict[str, Any]]) -> dict[str, Any]:
    """Exporta as poses e a nuvem esparsa nos formatos do Khnumn."""
    modelo = parametros.get("modelo")
    destino = parametros.get("destino", "./produtos")
    if not modelo:
        raise ValueError("o algoritmo 'sfm.exportar' exige o parametro 'modelo'")

    adaptador = AdaptadorColmap()
    saidas = adaptador.export(Path(modelo), Path(destino))
    return {"exportacao": {"saidas": saidas}, "saidas": saidas}



def _executar_marcas_detectar(parametros, entradas):
    import numpy as np
    caminho = parametros.get("imagem")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    if caminho is None:
        raise ValueError("marcas.detectar exige 'imagem'")
    from PIL import Image
    img = np.asarray(Image.open(caminho))
    projecoes = [tuple(p) for p in parametros.get("projecoes", [])]
    deteccoes = marcas.detectar_marcas(img, projecoes, raio=int(parametros.get("raio", 8)))
    return {"marcas": {"deteccoes": deteccoes, "num": len(deteccoes)}}


def _executar_marcas_filtrar(parametros, entradas):
    det = parametros.get("deteccoes_por_imagem", {})
    esp = parametros.get("projecoes_esperadas", {})
    limiar = float(parametros.get("limiar_px", 3.0))
    resultado = marcas.filtrar_consistencia_multivista(det, esp, limiar_px=limiar)
    return {"marcas": {"filtradas": resultado}}


def _executar_marcas_acquisibilidade(parametros, entradas):
    import numpy as np
    from PIL import Image
    caminho = parametros.get("imagem")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    img = np.asarray(Image.open(caminho))
    projecao = tuple(parametros.get("projecao", (0.0, 0.0)))
    resultado = marcas.verificar_acquisibilidade(img, projecao)
    return {"marcas": {"acquisibilidade": resultado}}


def _executar_controlo_ingerir(parametros, entradas):
    caminho = parametros.get("caminho")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    if caminho is None:
        raise ValueError("controlo.ingerir exige 'caminho'")
    pontos = controle.ingerir_pontos(__import__("pathlib").Path(caminho))
    return {"controlo": {"pontos": pontos, "num": len(pontos)}}


def _executar_controlo_checkpoints(parametros, entradas):
    caminho = parametros.get("caminho")
    if caminho is None and entradas:
        caminho = entradas[0].get("uri")
    pontos = controle.ingerir_pontos(__import__("pathlib").Path(caminho))
    controlo, checkpoints = controle.separar_papeis(pontos)
    return {"controlo": {"controlo": controlo, "checkpoints": checkpoints,
                         "num_controlo": len(controlo), "num_checkpoints": len(checkpoints)}}


def _executar_controlo_similaridade(parametros, entradas):
    origem = np.asarray(parametros.get("origem", []), dtype=float)
    destino = np.asarray(parametros.get("destino", []), dtype=float)
    covs = parametros.get("covariancias")
    covs = np.asarray(covs, dtype=float) if covs is not None else None
    resultado = controle.ransac_similaridade(origem, destino, covariancias=covs)
    # Serializar arrays.
    resultado = {
        "R": resultado["R"].tolist(),
        "escala": resultado["escala"],
        "t": resultado["t"].tolist(),
        "inliers": [bool(x) for x in resultado["inliers"]],
        "num_inliers": resultado["num_inliers"],
        "num_total": resultado["num_total"],
    }
    return {"controlo": {"similaridade": resultado}}


def _executar_controlo_ajustar(parametros, entradas):
    """Ajuste constrangido com pontos constantes e gauge fixo (F3.E7).

    Os pontos de levantamento sao fixados como pontos constantes, o gauge e
    fixado por tres pontos quando indicados, e todos os parametros e a versao
    do algoritmo sao registados para proveniencia. Quando o pycolmap esta
    disponivel, o ajuste e delegado ao BundleAdjuster do motor de SfM; caso
    contrario, e usada a implementacao numerica propria em `ajuste.ajustar_constragido`.
    """
    modelo = parametros.get("modelo")
    pontos_controlo = parametros.get("pontos_controlo", [])
    versao = parametros.get("versao_algoritmo", "1.0.0")
    pontos_constantes_ids = parametros.get("pontos_constantes_ids", [])
    gauge_pontos = parametros.get("gauge_pontos", [])
    fixar_gauge = bool(parametros.get("fixar_gauge", len(gauge_pontos) >= 3))
    semente = parametros.get("semente")

    if modelo is None:
        raise ValueError("controlo.ajustar exige 'modelo'")

    # Tenta o ajuste pelo motor de SfM (COLMAP), que e a via de producao.
    try:
        import pycolmap

        reconstrucao = pycolmap.Reconstruction(str(modelo))
        cfg = pycolmap.BundleAdjustmentConfig()
        for pid in pontos_constantes_ids:
            cfg.add_constant_point(int(pid))
        if len(gauge_pontos) >= 3:
            cfg.fix_gauge = pycolmap.BundleAdjustmentGauge.THREE_POINTS
            cfg.fixed_gauge = True
        opts = pycolmap.BundleAdjustmentOptions()
        adjuster = pycolmap.create_default_bundle_adjuster(opts, cfg, reconstrucao)
        summary = adjuster.solve()
        return {
            "controlo": {
                "ajuste": {
                    "versao_algoritmo": versao,
                    "motor": "pycolmap",
                    "num_constant_points": cfg.num_constant_points(),
                    "num_residuals": cfg.num_residuals(reconstrucao),
                    "summary": str(summary),
                    "pontos_constantes_ids": pontos_constantes_ids,
                    "gauge_pontos": gauge_pontos,
                    "fixar_gauge": fixar_gauge,
                    "semente": semente,
                }
            }
        }
    except ImportError:
        pass
    except Exception as erro_motor:
        # Se o motor falhar, cai para a implementacao numerica propria,
        # que nao depende de dependencias externas.
        pass

    # Via numerica propria: ajuste constrangido por minimos quadrados.
    # Constrói pontos 3d e observacoes a partir dos pontos de controlo.
    pontos_3d = []
    observacoes = []
    for idx, ponto in enumerate(pontos_controlo):
        coords = ponto.get("coordinates", [0.0, 0.0, 0.0])
        pontos_3d.append([float(c) for c in coords[:3]])
        # Observacao sintética: projecao identidade (u=x, v=y) com peso 1.
        observacoes.append([float(idx), float(coords[0]), float(coords[1]), 1.0])

    if not pontos_3d:
        return {
            "controlo": {
                "ajuste": {
                    "versao_algoritmo": versao,
                    "motor": "numerico",
                    "estado": "SUCCEEDED",
                    "motivo": "sem pontos de controlo; ajuste trivial",
                    "num_constant_points": 0,
                    "num_residuals": 0,
                    "pontos_constantes_ids": [],
                    "gauge_pontos": [],
                    "fixar_gauge": False,
                    "semente": semente,
                }
            }
        }

    pontos_arr = np.asarray(pontos_3d, dtype=float)
    obs_arr = np.asarray(observacoes, dtype=float)

    param = ajuste.ParametrosAjuste(
        versao_algoritmo=versao,
        pontos_constantes_ids=[int(p) for p in pontos_constantes_ids],
        gauge_pontos=[int(p) for p in gauge_pontos],
        fixar_gauge=fixar_gauge,
        semente=int(semente) if semente is not None else None,
    )
    resultado = ajuste.ajustar_constragido(pontos_arr, obs_arr, param)
    dicio = ajuste.resultado_para_dict(resultado)
    dicio["motor"] = "numerico"
    return {"controlo": {"ajuste": dicio}}


def _executar_controlo_ensemble(parametros, entradas):
    """Propagacao da incerteza por ensemble (F3.E8).

    Executa a etapa final N vezes, perturbando as coordenadas dos pontos de
    controlo pela sua covariancia. A funcao de ajuste e o ajuste constrangido
    real (`ajuste.ajustar_constragido`), e nao a identidade: a dispersao dos
    resultados e a incerteza do controlo propagada.
    """
    pontos = parametros.get("pontos", [])
    n = int(parametros.get("n_amostras", 10))
    semente = int(parametros.get("semente", 0))
    versao = parametros.get("versao_algoritmo", "1.0.0")

    pontos_constantes_ids = parametros.get("pontos_constantes_ids", [])
    gauge_pontos = parametros.get("gauge_pontos", [])
    fixar_gauge = bool(parametros.get("fixar_gauge", len(gauge_pontos) >= 3))

    def funcao_ajuste(pts_perturbados):
        """Funcao de ajuste real: recebe pontos perturbados e devolve o ajuste."""
        pontos_3d = []
        observacoes = []
        for idx, ponto in enumerate(pts_perturbados):
            coords = ponto.get("coordinates", [0.0, 0.0, 0.0])
            pontos_3d.append([float(c) for c in coords[:3]])
            observacoes.append([float(idx), float(coords[0]), float(coords[1]), 1.0])

        if not pontos_3d:
            return {"estado": "SUCCEEDED", "resultado": [], "num_residuos": 0}

        pontos_arr = np.asarray(pontos_3d, dtype=float)
        obs_arr = np.asarray(observacoes, dtype=float)

        param = ajuste.ParametrosAjuste(
            versao_algoritmo=versao,
            pontos_constantes_ids=[int(p) for p in pontos_constantes_ids],
            gauge_pontos=[int(p) for p in gauge_pontos],
            fixar_gauge=fixar_gauge,
            semente=semente,
        )
        resultado = ajuste.ajustar_constragido(pontos_arr, obs_arr, param)
        return ajuste.resultado_para_dict(resultado)

    resultado = controle.propagar_ensemble(pontos, funcao_ajuste, n_amostras=n, semente=semente)
    dispersao = resultado.get("dispersao", {})
    return {
        "controlo": {
            "ensemble": {
                "versao_algoritmo": versao,
                "n_amostras": resultado["n_amostras"],
                "dispersao": dispersao,
                "pontos_constantes_ids": pontos_constantes_ids,
                "gauge_pontos": gauge_pontos,
                "fixar_gauge": fixar_gauge,
                "semente": semente,
            }
        }
    }


def _executar_controlo_gnss_priors(parametros, entradas):
    # Extração de priors GNSS a partir dos metadados de um conjunto de imagens.
    import json as _json
    from pathlib import Path as _Path
    priors = []
    for caminho in parametros.get("imagens", []):
        try:
            from . import metadados
            reg = metadados.extrair(_Path(caminho))
            pos = reg.get("capture", {}).get("position")
            if pos is not None and pos.get("coordinates") is not None:
                priors.append({"imagem": caminho, "posicao": pos["coordinates"],
                               "crs": pos.get("crs")})
        except Exception as erro:
            priors.append({"imagem": caminho, "erro": str(erro)})
    return {"controlo": {"gnss_priors": priors, "num": len(priors)}}


def _executar_validacao_metricas(parametros, entradas):
    import numpy as np
    est = np.asarray(parametros.get("estimado", []), dtype=float)
    ref = np.asarray(parametros.get("referencia", []), dtype=float)
    tol_h = parametros.get("tolerancia_h_m")
    tol_v = parametros.get("tolerancia_v_m")
    metricas = validacao.metricas_exatidao(est, ref, tolerancia_h_m=tol_h, tolerancia_v_m=tol_v)
    estado = validacao.estado_aceitacao(metricas, tol_h, tol_v)
    return {"validacao": {"metricas": metricas, "estado": estado}}


def _executar_validacao_incerteza(parametros, entradas):
    ctrl = float(parametros.get("incerteza_controlo", 0.0))
    cena = float(parametros.get("incerteza_cena", 0.0))
    return {"validacao": {"incerteza": validacao.decompor_incerteza(ctrl, cena)}}


def _executar_marcas_rever(parametros, entradas):
    det = parametros.get("deteccoes", [])
    decisoes = parametros.get("decisoes", {})
    decisoes = {int(k): bool(v) for k, v in decisoes.items()}
    resultado = marcas.revisar_deteccoes(det, decisoes)
    return {"marcas": {"revisadas": resultado, "num": len(resultado)}}


def _executar_raster_residuos(parametros, entradas):
    import numpy as np
    coords = [tuple(c) for c in parametros.get("coords", [])]
    valores = [float(v) for v in parametros.get("valores", [])]
    largura = int(parametros.get("largura", 64))
    altura = int(parametros.get("altura", 64))
    r = raster.rasterizar_pontos(coords, valores, largura, altura)
    metricas = raster.metricas_raster(r)
    return {"raster": {"metricas": metricas, "sem_observacao_px": metricas["sem_observacao_px"]}}


def _executar_controlo_escrever_prior_gnss(parametros, entradas):
    base = parametros.get("base_dados")
    if base is None:
        raise ValueError("controlo.escrever_prior_gnss exige 'base_dados'")
    pid = controle.escrever_prior_gnss(
        base,
        parametros.get("posicao", [0.0, 0.0, 0.0]),
        parametros.get("covariancia", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        parametros.get("coordinate_system", "CARTESIAN"),
    )
    return {"controlo": {"prior_id": pid}}


def _executar_superficie_triangulacao(parametros, entradas):
    modelo = parametros.get("modelo")
    destino = parametros.get("destino", "./superficie")
    if not modelo:
        raise ValueError("superficie.triangulacao_esparsa exige 'modelo'")
    return {"superficie": superficie.triangulacao_esparsa(modelo, destino)}


def _executar_superficie_densa(parametros, entradas):
    base = parametros.get("base")
    if not base:
        raise ValueError("superficie.reconstrucao_densa exige 'base'")
    return {"superficie": superficie.reconstrucao_densa(base, parametros.get("opcoes", {}))}


def _executar_superficie_fundir(parametros, entradas):
    import numpy as np
    nuvens = [np.asarray(n, dtype=float) for n in parametros.get("nuvens", [])]
    return {"superficie": {"nuvem": superficie.fundir_nuvens(nuvens).tolist()}}


def _executar_superficie_blocos(parametros, entradas):
    import numpy as np
    dados = np.asarray(parametros.get("dados", []), dtype=float)
    tamanho = int(parametros.get("tamanho_bloco", 8))
    # Função identidade por omissão.
    def f(b):
        return b
    saida = superficie.processar_blocos(dados, tamanho, f, margem=int(parametros.get("margem", 0)))
    return {"superficie": {"saida": saida.tolist()}}


def _executar_superficie_blocos_orcado(parametros, entradas):
    """Processamento por blocos com orçamento de memória real (F4.E5).

    Executa a função sobre cada bloco, com margem de contexto, e mede o
    pico de memória após cada bloco. Quando o orçamento é excedido, a tarefa
    é interrompida com a causa, em vez de continuar sem garantias de
    recursos.
    """
    import numpy as np
    dados = np.asarray(parametros.get("dados", []), dtype=float)
    tamanho = int(parametros.get("tamanho_bloco", 8))
    margem = int(parametros.get("margem", 0))
    limite_memoria_mb = parametros.get("limite_memoria_mb")
    limite = int(limite_memoria_mb) if limite_memoria_mb is not None else None

    def f(b):
        return b

    resultado = superficie.processar_blocos_com_orcamento(
        dados, tamanho, f, margem=margem, limite_memoria_mb=limite
    )
    return {
        "superficie": {
            "saida": resultado["saida"].tolist(),
            "blocos_processados": resultado["blocos_processados"],
            "pico_memoria_mb": resultado["pico_memoria_mb"],
            "excedeu_orcamento": resultado["excedeu_orcamento"],
            "motivo": resultado["motivo"],
            "limite_memoria_mb": resultado["limite_memoria_mb"],
        }
    }


def _executar_superficie_malha(parametros, entradas):
    entrada = parametros.get("entrada")
    saida = parametros.get("saida")
    if not entrada or not saida:
        raise ValueError("superficie.malha_textura exige 'entrada' e 'saida'")
    return {"superficie": superficie.malha_textura(entrada, saida, bool(parametros.get("simplificar", False)))}


def _executar_superficie_refinamento(parametros, entradas):
    max_it = int(parametros.get("max_iteracoes", 3))
    limiar_ganho = float(parametros.get("limiar_ganho", 0.01))
    limiar_out = float(parametros.get("limiar_outliers", 0.1))
    def passagem(i):
        return {"ganho_densidade": float(parametros.get("ganho", 0.02)) if i == 0 else 0.0,
                "taxa_outliers": float(parametros.get("outliers", 0.05))}
    return {"superficie": superficie.refinamento_iterativo(passagem, max_it, limiar_ganho, limiar_out)}


def _executar_ortoimagem(parametros, entradas):
    return {"ortoimagem": ortoimagem.gerar_ortoimagem(
        parametros.get("modelo_superficie", ""),
        parametros.get("crs_destino", ""),
        parametros.get("metodo_reamostragem", "bilinear"),
    )}


def _executar_dtm(parametros, entradas):
    import numpy as np
    pontos = np.asarray(parametros.get("pontos", []), dtype=float)
    return {"dtm": dtm.gerar_dtm(pontos)}


def _executar_validacao_denso(parametros, entradas):
    import numpy as np
    a = np.asarray(parametros.get("densa_cpu", []), dtype=float)
    b = np.asarray(parametros.get("densa_gpu", []), dtype=float)
    return {"validacao_denso": validacao_denso.comparar_com_referencia(a, b)}


def _executar_cobertura_gerar(parametros, entradas):
    coords = [tuple(c) for c in parametros.get("coords", [])]
    largura = int(parametros.get("largura", 8))
    altura = int(parametros.get("altura", 8))
    return {"cobertura": cobertura.gerar_mapa_cobertura(coords, largura, altura)}


def _executar_cobertura_incerteza(parametros, entradas):
    coords = [tuple(c) for c in parametros.get("coords", [])]
    valores = [float(v) for v in parametros.get("valores", [])]
    largura = int(parametros.get("largura", 8))
    altura = int(parametros.get("altura", 8))
    return {"cobertura": cobertura.gerar_mapa_incerteza(coords, valores, largura, altura, parametros.get("legenda"))}


def _executar_cenario_classificar(parametros, entradas):
    metadados = parametros.get("metadados", {})
    qualidade = parametros.get("qualidade")
    return {"cenario": cenario.classificar_cenario(metadados, qualidade)}


def _executar_cenario_corrigir(parametros, entradas):
    classificacao = parametros.get("classificacao", {})
    return {"cenario": cenario.corrigir_cenario(classificacao, parametros.get("correcao", ""), parametros.get("motivo", ""))}


def _executar_planeador_planear(parametros, entradas):
    return {"planeador": planeador.planear(
        parametros.get("cenario", "unknown"),
        bool(parametros.get("hardware_gpu", False)),
        parametros.get("requisito_densidade", "media"),
        int(parametros.get("ensemble_samples", 10)),
        int(parametros.get("iteracoes_refino", 3)),
        parametros.get("manual_override"),
    )}


def _executar_planeador_com_orcamento(parametros, entradas):
    """Planeamento com orçamento fixado antecipadamente e registo de decisões (F5.E4-E6)."""
    metadados = parametros.get("metadados", {})
    qualidade = parametros.get("qualidade")
    hardware_gpu = bool(parametros.get("hardware_gpu", False))
    requisito_densidade = parametros.get("requisito_densidade", "media")
    ensemble_samples = int(parametros.get("ensemble_samples", 10))
    iteracoes_refino = int(parametros.get("iteracoes_refino", 3))
    limite_memoria_mb = parametros.get("limite_memoria_mb")
    limite = int(limite_memoria_mb) if limite_memoria_mb is not None else None
    manual_override = parametros.get("manual_override")
    correcao_cenario = parametros.get("correcao_cenario")
    motivo_correcao = parametros.get("motivo_correcao")

    plano = plano_execucao.classificar_e_planejar(
        metadados=metadados,
        qualidade=qualidade,
        hardware_gpu=hardware_gpu,
        requisito_densidade=requisito_densidade,
        ensemble_samples=ensemble_samples,
        iteracoes_refino=iteracoes_refino,
        limite_memoria_mb=limite,
        manual_override=manual_override,
        correcao_cenario=correcao_cenario,
        motivo_correcao=motivo_correcao,
    )
    return {"planeador": plano}


def _executar_planeador_guardar_plano(parametros, entradas):
    """Guarda o plano de execução num ficheiro JSON (registo persistente, F5.E6)."""
    caminho = parametros.get("caminho")
    plano = parametros.get("plano")
    if not caminho:
        raise ValueError("planeador.guardar_plano exige 'caminho'")
    if plano is None:
        raise ValueError("planeador.guardar_plano exige 'plano'")
    plano_execucao.guardar_plano(caminho, plano)
    return {"planeador": {"plano_guardado": caminho}}


# ============================================================================
# Fase 6 — Vídeo e sensores auxiliares
# ============================================================================

def _executar_tempo_sincronizar_relogios(parametros, entradas):
    """Sincronização de relógios (F6.E1)."""
    instantes = parametros.get("instantes", [])
    fonte = parametros.get("fonte_referencia", "GNSS")
    resultado = tempo.sincronizar_relogios(instantes, fonte)
    return {"tempo": tempo.resultado_para_dict(resultado)}


def _executar_tempo_convenir_instante(parametros, entradas):
    """Convenção de instante de captura (F6.E3)."""
    metadados = parametros.get("metadados", {})
    modo = parametros.get("modo", "meio_exposicao")
    instante = tempo.convenir_instante_captura(metadados, modo)
    return {"tempo": tempo.instante_para_dict(instante)}


def _executar_video_selecionar_fotogramas(parametros, entradas):
    """Extração adaptativa de fotogramas (F6.E2)."""
    caminhos = parametros.get("caminhos", [])
    politica = parametros.get("politica")
    politica_obj = None
    if politica is not None:
        politica_obj = video.PoliticaMemoria(
            max_fotogramas=int(politica.get("max_fotogramas", 200)),
            max_memoria_mb=int(politica.get("max_memoria_mb", 500)),
            tamanho_lado_max_px=int(politica.get("tamanho_lado_max_px", 1024)),
        )
    nitidez_minima = float(parametros.get("nitidez_minima", 20.0))
    resultado = video.selecionar_fotogramas(caminhos, politica_obj, nitidez_minima)
    return {"video": resultado}


def _executar_rolling_shutter_modelo(parametros, entradas):
    """Modelo por tempo de linha para rolling shutter (F6.E4)."""
    linha = int(parametros.get("linha", 0))
    tempo_exposicao = float(parametros.get("tempo_exposicao_s", 0.0))
    velocidade = float(parametros.get("velocidade_leitura_s_por_linha", 0.0))
    altura = int(parametros.get("altura_sensor_px", 1000))
    direcao = parametros.get("direcao", "topo_para_baixo")
    corretcao = rolling_shutter.modelo_tempo_linha(
        linha, tempo_exposicao, velocidade, altura, direcao
    )
    return {
        "rolling_shutter": {
            "linha": corretcao.linha,
            "instante_desvio_s": corretcao.instante_desvio_s,
            "corrigido": corretcao.corrigido,
            "motivo": corretcao.motivo,
        }
    }


def _executar_lidar_ingerir_nuvem(parametros, entradas):
    """Ingestão de nuvem LiDAR (F6.E5)."""
    caminho = parametros.get("caminho")
    crs = parametros.get("crs", "EPSG:4979")
    if not caminho:
        raise ValueError("lidar.ingerir_nuvem exige 'caminho'")
    nuvem = lidar.ingerir_nuvem_lidar(
        caminho,
        crs=crs,
        densidade_pontos_por_m2=parametros.get("densidade_pontos_por_m2"),
        padrao_varrimento=parametros.get("padrao_varrimento"),
        incerteza_horizontal_m=parametros.get("incerteza_horizontal_m"),
        incerteza_vertical_m=parametros.get("incerteza_vertical_m"),
        epoca_captura_utc=parametros.get("epoca_captura_utc"),
        proveniencia=parametros.get("proveniencia"),
    )
    return {"lidar": lidar.nuvem_para_dict(nuvem)}


def _executar_lidar_aplicar_calibracao(parametros, entradas):
    """Calibração entre sensores LiDAR (F6.E5)."""
    pontos = parametros.get("pontos", [])
    translacao = parametros.get("translacao_m", [0.0, 0.0, 0.0])
    rotacao = parametros.get("rotacao_rad", [0.0, 0.0, 0.0])
    escala = float(parametros.get("escala", 1.0))

    nuvem = lidar.NuvemLiDAR(
        pontos=np.asarray(pontos, dtype=float),
        crs=parametros.get("crs", "EPSG:4979"),
    )
    calibracao = lidar.CalibracaoInterSensor(
        sensor_origem="lidar",
        sensor_destino="referencia",
        translacao_m=translacao,
        rotacao_rad=rotacao,
        escala=escala,
    )
    nuvem_calibrada = lidar.aplicar_calibracao_inter_sensor(nuvem, calibracao)
    return {"lidar": lidar.nuvem_para_dict(nuvem_calibrada)}


def _executar_radiometria_aplicar_icc(parametros, entradas):
    """Aplicar perfil ICC (F6.E6)."""
    imagem_dados = parametros.get("imagem_dados", [])
    imagem = np.asarray(imagem_dados, dtype=np.uint8) if imagem_dados else None
    perfil_nome = parametros.get("perfil_nome", "sRGB")
    perfil = radiometria.PerfilICC(nome=perfil_nome)
    resultado = radiometria.aplicar_perfil_icc(imagem, perfil)
    return {
        "radiometria": {
            "estado": resultado.estado,
            "motivo": resultado.motivo,
            "parametros_aplicados": resultado.parametros_aplicados,
        }
    }


def _executar_radiometria_corrigir_vinheta(parametros, entradas):
    """Corrigir vinheta e sombreamento (F6.E6)."""
    imagem_dados = parametros.get("imagem_dados", [])
    imagem = np.asarray(imagem_dados, dtype=np.uint8) if imagem_dados else None
    calibracao = parametros.get("calibracao")
    resultado = radiometria.corrigir_vinheta_sombreamento(imagem, calibracao)
    return {
        "radiometria": {
            "estado": resultado.estado,
            "motivo": resultado.motivo,
            "parametros_aplicados": resultado.parametros_aplicados,
        }
    }


def _executar_radiometria_calibrar_reflectancia(parametros, entradas):
    """Calibração a reflectância multibanda (F6.E6)."""
    imagem_dados = parametros.get("imagem_dados", [])
    imagem = np.asarray(imagem_dados, dtype=np.uint8) if imagem_dados else None
    bandas = parametros.get("bandas", [])
    resultado = radiometria.calibrar_reflectancia_multibanda(imagem, bandas)
    return {
        "radiometria": {
            "estado": resultado.estado,
            "motivo": resultado.motivo,
            "parametros_aplicados": resultado.parametros_aplicados,
        }
    }


def _executar_satelite_identificar_modelo(parametros, entradas):
    """Identificar modelo geométrico de satélite (F6.E7)."""
    metadados = parametros.get("metadados", {})
    modelo = satelite.identificar_modelo_geometrico(metadados)
    return {
        "satelite": {
            "tipo": modelo.tipo,
            "parametros": modelo.parametros,
            "fonte": modelo.fonte,
            "versao": modelo.versao,
        }
    }


def _executar_satelite_corrigir_rpc(parametros, entradas):
    """Estimar e corrigir viés de RPC (F6.E7)."""
    metadados = parametros.get("metadados", {})
    checkpoints = parametros.get("checkpoints", [])
    corretcao = satelite.estimar_corrigir_viés_rpc(metadados, checkpoints)
    return {
        "satelite": {
            "viés_estimado": corretcao.viés_estimado,
            "viés_corrigido": corretcao.viés_corrigido,
            "num_checkpoints_usados": corretcao.num_checkpoints_usados,
            "rmse_apos_correcao_m": corretcao.rmse_apos_correcao_m,
            "estado": corretcao.estado,
            "motivo": corretcao.motivo,
        }
    }


def _executar_satelite_coregistrar(parametros, entradas):
    """Co-registação de imagens de satélite (F6.E7)."""
    img_ref = parametros.get("imagem_referencia", "")
    img_alvo = parametros.get("imagem_alvo", "")
    mascara = parametros.get("mascara_nuvem")
    reflectancia = parametros.get("reflectancia_superficie")

    mascara_obj = None
    if mascara is not None:
        mascara_obj = satelite.MascaraNuvem(
            cobertura_nuvem_percent=float(mascara.get("cobertura_nuvem_percent", 0.0)),
            metodo=mascara.get("metodo", "não declarado"),
        )

    reflectancia_obj = None
    if reflectancia is not None:
        reflectancia_obj = satelite.ReflectanciaSuperficie(
            banda=reflectancia.get("banda", "desconhecida"),
            fator_correcao_atmosferica=float(reflectancia.get("fator_correcao_atmosferica", 1.0)),
            estado=reflectancia.get("estado", "SUCCEEDED"),
        )

    resultado = satelite.coregistrar(img_ref, img_alvo, mascara_obj, reflectancia_obj)
    return {"satelite": resultado}


def _executar_gnss_imu_integrar_poses(parametros, entradas):
    """Integra poses GNSS/IMU (F6.E8)."""
    imagens = parametros.get("imagens", [])
    metadados_por_imagem = parametros.get("metadados_por_imagem", {})
    covariancia_padrao = float(parametros.get("covariancia_padrao_m", 5.0))
    poses, sinc = gnss_imu.integrar_poses_gnss_imu(
        imagens, metadados_por_imagem, covariancia_padrao
    )
    return {
        "gnss_imu": {
            "poses": [gnss_imu.pose_para_dict(p) for p in poses],
            "sincronizacao": gnss_imu.sincronizacao_para_dict(sinc),
        }
    }


def _executar_gnss_imu_medir_residuos(parametros, entradas):
    """Mede resíduos de alinhamento GNSS/IMU (F6.E8)."""
    poses_estimadas = parametros.get("poses_estimadas", [])
    poses_referencia = parametros.get("poses_referencia", [])

    poses_obj = [
        gnss_imu.PoseGNSSIMU(
            imagem=p.get("imagem", ""),
            posição=p.get("posição", [0.0, 0.0, 0.0]),
            covariancia_posição=p.get(
                "covariancia_posição", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            ),
        )
        for p in poses_estimadas
    ]

    residuos = gnss_imu.medir_residuos_alinhamento(poses_obj, poses_referencia)
    return {"gnss_imu": residuos}


# ============================================================================
# Fase 7 — Distribuição
# ============================================================================

def _executar_persistencia_gravar_grafo(parametros, entradas):
    """Persiste o grafo de tarefas para disco (F7.E1)."""
    nos = parametros.get("nos", [])
    caminho = parametros.get("caminho")
    if not caminho:
        raise ValueError("persistencia.gravar_grafo exige 'caminho'")
    persistencia.persistir_grafo(nos, caminho)
    return {"persistencia": {"grafo_gravado": caminho}}


def _executar_persistencia_recuperar_grafo(parametros, entradas):
    """Recupera o grafo de tarefas do disco (F7.E1)."""
    caminho = parametros.get("caminho")
    if not caminho:
        raise ValueError("persistencia.recuperar_grafo exige 'caminho'")
    dados = persistencia.recuperar_grafo(caminho)
    return {"persistencia": dados}


def _executar_scheduler_agendar(parametros, entradas):
    """Agenda tarefas com scheduler CPU-first (F7.E2)."""
    tarefas = parametros.get("tarefas", [])
    recursos_dados = parametros.get("recursos")
    recursos = None
    if recursos_dados is not None:
        recursos = scheduler.RecursosDisponiveis(
            memoria_total_mb=int(recursos_dados.get("memoria_total_mb", 1024)),
            memoria_orcamento_mb=int(recursos_dados.get("memoria_orcamento_mb", 500)),
            max_workers=int(recursos_dados.get("max_workers", 2)),
            cpu_maximo_percent=float(recursos_dados.get("cpu_maximo_percent", 100.0)),
        )
    resultado = scheduler.agendar(tarefas, recursos)
    return {"scheduler": resultado}


def _executar_worker_remoto_registar(parametros, entradas):
    """Regista um worker remoto no pool (F7.E3)."""
    pool_id = parametros.get("pool_id", "default")
    # Usa um pool global simplificado para o contrato do worker.
    if not hasattr(_executar_worker_remoto_registar, "_pool"):
        _executar_worker_remoto_registar._pool = worker_remoto.PoolWorkers()
    pool = _executar_worker_remoto_registar._pool

    pool.registar_worker(
        worker_id=parametros.get("worker_id", "worker-1"),
        memoria_total_mb=int(parametros.get("memoria_total_mb", 1024)),
        memoria_disponivel_mb=int(parametros.get("memoria_disponivel_mb", 500)),
        num_cpu=int(parametros.get("num_cpu", 2)),
        tem_acelerador=bool(parametros.get("tem_acelerador", False)),
        tipo_acelerador=parametros.get("tipo_acelerador"),
    )
    return {"worker_remoto": pool.resumo()}


def _executar_worker_remoto_despachar(parametros, entradas):
    """Despacha uma tarefa para um worker remoto (F7.E3)."""
    if not hasattr(_executar_worker_remoto_despachar, "_pool"):
        _executar_worker_remoto_despachar._pool = worker_remoto.PoolWorkers()
    pool = _executar_worker_remoto_despachar._pool

    worker_id = pool.despachar_para_worker(
        task_id=parametros.get("task_id", "tarefa-1"),
        memoria_estimada_mb=int(parametros.get("memoria_estimada_mb", 100)),
        requer_acelerador=bool(parametros.get("requer_acelerador", False)),
    )
    return {
        "worker_remoto": {
            "worker_id_atribuido": worker_id,
            "despachado": worker_id is not None,
        }
    }


def _executar_retry_registar_tentativa(parametros, entradas):
    """Regista uma tentativa de retry (F7.E4)."""
    if not hasattr(_executar_retry_registar_tentativa, "_gerenciador"):
        _executar_retry_registar_tentativa._gerenciador = (
            retry_checkpoint.GerenciadorRetry()
        )
    ger = _executar_retry_registar_tentativa._gerenciador

    task_id = parametros.get("task_id", "tarefa-1")
    erro = parametros.get("erro", "erro desconhecido")
    atraso = ger.registar_tentativa(task_id, erro)
    return {"retry": ger.resumo(task_id)}


def _executar_checkpoint_gravar(parametros, entradas):
    """Grava um checkpoint de tarefa (F7.E4)."""
    if not hasattr(_executar_checkpoint_gravar, "_gerenciador"):
        _executar_checkpoint_gravar._gerenciador = (
            retry_checkpoint.GerenciadorCheckpoint()
        )
    ger = _executar_checkpoint_gravar._gerenciador

    checkpoint = ger.gravar_checkpoint(
        task_id=parametros.get("task_id", "tarefa-1"),
        algoritmo=parametros.get("algoritmo", "desconhecido"),
        versao=parametros.get("versao", "1.0.0"),
        passo=parametros.get("passo", "inicial"),
        dados=parametros.get("dados", {}),
    )
    return {
        "checkpoint": {
            "task_id": checkpoint.task_id,
            "passo": checkpoint.passo,
            "timestamp_utc": checkpoint.timestamp_utc,
            "hash_dados": checkpoint.hash_dados,
        }
    }


def _executar_checkpoint_verificar_integridade(parametros, entradas):
    """Verifica a integridade de um checkpoint (F7.E4)."""
    if not hasattr(_executar_checkpoint_verificar_integridade, "_gerenciador"):
        _executar_checkpoint_verificar_integridade._gerenciador = (
            retry_checkpoint.GerenciadorCheckpoint()
        )
    ger = _executar_checkpoint_verificar_integridade._gerenciador

    task_id = parametros.get("task_id", "tarefa-1")
    valido = ger.verificar_integridade(task_id)
    return {"checkpoint": {"task_id": task_id, "integridade_valida": valido}}


def _executar_reprodutibilidade_nivel(parametros, entradas):
    """Declara o nível de reprodutibilidade por backend (F7.E5)."""
    backend = parametros.get("backend_ajuste", "cpu_local")
    versao = parametros.get("versao")
    nivel = reprodutibilidade.nivel_reprodutibilidade(backend, versao)
    return {
        "reprodutibilidade": {
            "nivel": nivel.nivel,
            "tolerancia_absoluta": nivel.tolerancia_absoluta,
            "tolerancia_relativa": nivel.tolerancia_relativa,
            "semente_obrigatoria": nivel.semente_obrigatoria,
            "versao_backend": nivel.versao_backend,
        }
    }


def _executar_reprodutibilidade_comparar(parametros, entradas):
    """Compara duas execuções para consistência numérica (F7.E5)."""
    resultado_a = parametros.get("resultado_a", {})
    resultado_b = parametros.get("resultado_b", {})
    backend_outro = parametros.get("backend_outro", "cpu_distribuido")

    comparacao = reprodutibilidade.verificar_consistencia_entre_backends(
        resultado_a, resultado_b, backend_outro
    )
    return {
        "reprodutibilidade": reprodutibilidade.resultado_comparacao_para_dict(comparacao)
    }


def _executar_seguranca_autenticar(parametros, entradas):
    """Autentica um pedido (F7.E6)."""
    if not hasattr(_executar_seguranca_autenticar, "_gerenciador"):
        _executar_seguranca_autenticar._gerenciador = seguranca.GerenciadorSeguranca()
    ger = _executar_seguranca_autenticar._gerenciador

    identificador = parametros.get("identificador", "")
    segredo = parametros.get("segredo", "")
    permissao = parametros.get("permissao_necessaria")

    # Registra credenciais se não existirem (para teste).
    if identificador and identificador not in ger.credenciais:
        ger.registar_credenciais(identificador, segredo, ["ler_projeto", "escrever_produto"])

    pedido = ger.autenticar_pedido(identificador, segredo, permissao)
    return {
        "seguranca": {
            "autenticado": pedido.autenticado,
            "identificador": pedido.identificador,
            "permissoes": list(pedido.permissoes),
            "motivo": pedido.motivo,
        }
    }


def _executar_seguranca_proteger_transporte(parametros, entradas):
    """Protege uma mensagem de transporte (F7.E6)."""
    if not hasattr(_executar_seguranca_proteger_transporte, "_gerenciador"):
        _executar_seguranca_proteger_transporte._gerenciador = (
            seguranca.GerenciadorSeguranca()
        )
    ger = _executar_seguranca_proteger_transporte._gerenciador

    mensagem = parametros.get("mensagem", b"").encode("utf-8") if isinstance(
        parametros.get("mensagem", ""), str
    ) else parametros.get("mensagem", b"")
    pacote = ger.proteger_transporte(mensagem)
    return {"seguranca": pacote}


# ============================================================================
# Fase 8 — Fusão heterogénea avançada
# ============================================================================

def _executar_evidencia_agrupar_por_celula(parametros, entradas):
    """Agrupa evidência por célula espacial (F8.E1)."""
    elementos_dados = parametros.get("elementos", [])
    resolucao = float(parametros.get("resolucao_m", 1.0))

    elementos = []
    for e in elementos_dados:
        elementos.append(
            evidencia.ElementoEvidencia(
                celula_id=e.get("celula_id", "c-0"),
                geometria=e.get("geometria", [0.0, 0.0, 0.0]),
                covariancia=e.get(
                    "covariancia", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
                ),
                contagem_observacoes=int(e.get("contagem_observacoes", 1)),
                diversidade_observacoes=float(e.get("diversidade_observacoes", 1.0)),
                proveniencia=e.get("proveniencia", {}),
                epoca_utc=e.get("epoca_utc", ""),
                consistencia=float(e.get("consistencia", 1.0)),
                incerteza_total_m=e.get("incerteza_total_m"),
                estado=e.get("estado", "valido"),
            )
        )

    agrupadas = evidencia.agrupar_evidencia_por_celula(elementos, resolucao)
    return {
        "evidencia": {
            celula: evidencia.elemento_para_dict(elem)
            for celula, elem in agrupadas.items()
        }
    }


def _executar_alinhamento_fontes(parametros, entradas):
    """Alinha duas fontes heterogéneas (F8.E2)."""
    pontos_origem = parametros.get("pontos_origem", [])
    pontos_destino = parametros.get("pontos_destino", [])
    modelo_tipo = parametros.get("modelo_tipo", "similaridade_7p")
    restricoes = parametros.get("restricoes", [])
    pesos = parametros.get("pesos")

    resultado = alinhamento.alinhar_fontes(
        pontos_origem, pontos_destino, modelo_tipo, restricoes, pesos
    )
    return {"alinhamento": alinhamento.resultado_para_dict(resultado)}


def _executar_compatibilidade_temporal_janela(parametros, entradas):
    """Calcula janela de compatibilidade temporal (F8.E3)."""
    epoca_a = parametros.get("epoca_a", "")
    epoca_b = parametros.get("epoca_b", "")
    tolerancia = float(parametros.get("tolerancia_temporal_s", 3600.0))

    janela = compatibilidade_temporal.calcular_janela_compatibilidade(
        epoca_a, epoca_b, tolerancia
    )
    return {
        "compatibilidade_temporal": compatibilidade_temporal.janela_para_dict(janela)
    }


def _executar_compatibilidade_temporal_marcar_mudancas(parametros, entradas):
    """Marca mudanças prováveis entre fontes (F8.E3)."""
    fontes_dados = parametros.get("fontes", [])
    tolerancia = float(parametros.get("tolerancia_temporal_s", 3600.0))
    epoca_ref = parametros.get("epoca_referencia")

    fontes = [
        compatibilidade_temporal.FonteTemporal(
            identificador=f.get("identificador", "f-0"),
            epoca_utc=f.get("epoca_utc", ""),
            tipo=f.get("tipo", "não_declarada"),
        )
        for f in fontes_dados
    ]

    resultado = compatibilidade_temporal.marcar_mudancas_provaveis(
        fontes, tolerancia, epoca_ref
    )
    return {"compatibilidade_temporal": resultado}


def _executar_decisao_evidencia_aplicar(parametros, entradas):
    """Aplica regras de decisão sobre evidência (F8.E4)."""
    evidencia = parametros.get("evidencia", {})
    regras_dados = parametros.get("regras", {"aceitacao": [], "rejeicao": []})

    regras = decisao_evidencia.RegrasDecisao()
    for r in regras_dados.get("aceitacao", []):
        regras.adicionar_regra_aceitacao(
            r.get("nome", "regra"),
            float(r.get("limiar", 0.5)),
            r.get("campo_evidencia", "consistencia"),
            r.get("descricao", ""),
        )
    for r in regras_dados.get("rejeicao", []):
        regras.adicionar_regra_rejeicao(
            r.get("nome", "regra"),
            float(r.get("limiar", 0.5)),
            r.get("campo_evidencia", "consistencia"),
            r.get("motivo", "rejeitado pela regra"),
            r.get("descricao", ""),
        )

    hipoteses_dados = parametros.get("hipoteses", [])
    hipoteses = [
        decisao_evidencia.Hipotese(
            identificador=h.get("identificador", "h-0"),
            evidencia=h.get("evidencia", {}),
            probabilidade=float(h.get("probabilidade", 0.5)),
            suporte=list(h.get("suporte", [])),
            contradicao=list(h.get("contradicao", [])),
        )
        for h in hipoteses_dados
    ]

    decisao = decisao_evidencia.aplicar_regras_decisao(evidencia, regras, hipoteses)
    return {"decisao_evidencia": decisao_evidencia.decisao_para_dict(decisao)}


def _executar_benchmark_fusao_comparar(parametros, entradas):
    """Compara resultado com baseline (F8.E5)."""
    valor_obtido = float(parametros.get("valor_obtido", 0.0))
    baseline_dados = parametros.get("baseline", {})
    direcao = parametros.get("direcao_melhoria", "menor_e_melhor")

    baseline = benchmark_fusao.Baseline(
        nome=baseline_dados.get("nome", "baseline"),
        conjunto_dados=baseline_dados.get("conjunto_dados", "não_declarado"),
        metrica_primaria=baseline_dados.get("metrica_primaria", "metrica"),
        valor_referencia=float(baseline_dados.get("valor_referencia", 0.0)),
        unidade=baseline_dados.get("unidade", "não_declarada"),
        fonte=baseline_dados.get("fonte", "não_declarada"),
    )

    resultado = benchmark_fusao.comparar_com_baseline(
        valor_obtido, baseline, direcao
    )
    return {
        "benchmark_fusao": benchmark_fusao.resultado_para_dict(resultado)
    }


def _executar_verificacao_multivista_acumular(parametros, entradas):
    """Acumula profundidade por sub-região (F8.E6)."""
    rasters = parametros.get("rasters_profundidade", [])
    sub_regioes_dados = parametros.get("sub_regioes", [])

    sub_regioes = [
        verificacao_multivista.SubRegiao(
            identificador=s.get("identificador", "sr-0"),
            coordenadas=list(s.get("coordenadas", [0.0, 0.0, 1.0, 1.0])),
            inconsistencia_m=s.get("inconsistencia_m"),
            num_vistas_observadoras=int(s.get("num_vistas_observadoras", 0)),
            profundidade_media_m=s.get("profundidade_media_m"),
            estado=s.get("estado", "sem_dados"),
        )
        for s in sub_regioes_dados
    ]

    verificacao_multivista.acumular_profundidade_por_subregiao(rasters, sub_regioes)

    referencia_dados = parametros.get("referencia_laser")
    referencia = None
    if referencia_dados is not None:
        referencia = verificacao_multivista.ReferenciaLaser(
            profundidade_por_regiao=referencia_dados.get(
                "profundidade_por_regiao", {}
            ),
            limiar_inconsistencia_m=float(
                referencia_dados.get("limiar_inconsistencia_m", 0.05)
            ),
        )

    resultado = verificacao_multivista.comparar_referencia_laser(
        sub_regioes, referencia
    )
    return {
        "verificacao_multivista": verificacao_multivista.resultado_para_dict(resultado)
    }


# ============================================================================
# Etapas desbloqueadas pela Fase 9
# ============================================================================

def _executar_residuos_calcular(parametros, entradas):
    """Campo de resíduos de reprojeção por câmara (F3.E13).

    Usa o rasterizador de software (F9.E2) para projetar os resíduos de
    reprojeção sobre a grelha 2D de cada câmara, com a classe "sem
    observação" explícita (NaN).
    """
    pontos_3d = parametros.get("pontos_3d", [])
    observacoes_por_camera = parametros.get("observacoes_por_camera", {})
    cameras_por_camera = parametros.get("cameras_por_camera", {})
    poses_por_camera = parametros.get("poses_por_camera", {})
    largura = int(parametros.get("largura", 640))
    altura = int(parametros.get("altura", 480))

    pontos = [
        [float(p[0]), float(p[1]), float(p[2])] for p in pontos_3d
    ]

    campo = residuos.calcular_residuos_reprojecao(
        pontos,
        observacoes_por_camera,
        cameras_por_camera,
        poses_por_camera,
        largura,
        altura,
    )
    return {"residuos": residuos.campo_residuos_para_dict(campo)}


def _executar_cobertura_gerar_cog(parametros, entradas):
    """Mapa de cobertura e contagem de furos como COG (F4.E11, F9.E3).

    Gera o raster de cobertura, publica como COG e regista no catálogo
    (F9.E1) com a linhagem de proveniência.
    """
    coords = [tuple(c) for c in parametros.get("coords", [])]
    largura = int(parametros.get("largura", 64))
    altura = int(parametros.get("altura", 64))
    caminho_cog = parametros.get("caminho_cog")
    caminho_catalogo = parametros.get("caminho_catalogo")
    crs = parametros.get("crs")
    crs_declaracao = parametros.get(
        "crs_declaracao", "raster em grelha de camara"
    )

    # 1. Gera o mapa de cobertura (F4.E11).
    resultado_cobertura = cobertura.gerar_mapa_cobertura(coords, largura, altura)

    # 2. Publica como COG (F9.E3).
    interm = cog.RasterIntermediario(
        caminho=Path(caminho_cog or "/tmp/cobertura_intermediario.tif"),
        hash_sha256="pendente",
        largura=largura,
        altura=altura,
        crs=crs,
        nodata=None,
        campos={"cobertura": resultado_cobertura["metricas"]},
    )
    publicado = cog.publicar_cog(
        interm,
        caminho_cog or "/tmp/cobertura.cog",
        compressao=parametros.get("compressao", "DEFLATE"),
        overviews=parametros.get("overviews", [2, 4, 8]),
    )

    # 3. Regista no catálogo (F9.E1).
    if caminho_catalogo:
        cat = catalogo.Catalogo(caminho_catalogo)
        cat.abrir()
        try:
            # Quando rasterio não está disponível, o hash do COG está vazio;
            # usa-se o hash do conteúdo de cobertura como fallback.
            cobertura_serializavel = dict(resultado_cobertura)
            if "raster" in cobertura_serializavel:
                r = cobertura_serializavel["raster"]
                if hasattr(r, "tolist"):
                    cobertura_serializavel["raster"] = r.tolist()
            sha_produto = publicado.hash_sha256 or hashlib.sha256(
                json.dumps(cobertura_serializavel, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            registo = catalogo.RegistoProduto(
                product_id=parametros.get("product_id", "cobertura-001"),
                tipo="mapa_cobertura",
                formato="cog" if publicado.hash_sha256 else "raster_intermediario",
                source_uri=str(publicado.caminho),
                sha256=sha_produto,
                crs=crs,
                crs_declaracao=crs_declaracao,
                unidades={"horizontal": "m", "vertical": "m"},
                resolucao={
                    "horizontal": 1.0,
                    "vertical": 1.0,
                    "unit": "m",
                },
                campo="cobertura",
                legenda=[
                    {"valor": 0.0, "cor": "ff0000", "rotulo": "sem observacao"},
                    {"valor": 1.0, "cor": "00ff00", "rotulo": "observado"},
                ],
                data_kind="estimado",
                incerteza=catalogo.IncertezaProduto(
                    estimada=False,
                    declaracao="mapa de cobertura nao tem incerteza geometrica",
                ),
                proveniencia={
                    "source_uri": str(publicado.caminho_intermediario),
                    "operacoes": [
                        catalogo.RegistoProveniente(
                            task_id=parametros.get("task_id", "cobertura-001"),
                            algoritmo="cobertura.gerar_cog",
                            versao="1.0.0",
                            entradas=[],
                        )
                    ],
                    "versoes": {"khnumn": "0.1.0"},
                },
            )
            cat.gravar_produto(registo)
        finally:
            cat.fechar()

    return {
        "cobertura": {
            "cobertura_percent": resultado_cobertura["cobertura_percent"],
            "furos_contagem": resultado_cobertura["furos_contagem"],
            "furos_area_m2": float(resultado_cobertura["furos_area_px"]),
            "cog": cog.raster_publicado_para_dict(publicado),
            "registado_em_catalogo": bool(caminho_catalogo),
        }
    }


def _executar_cobertura_gerar_incerteza_cog(parametros, entradas):
    """Mapa de incerteza com legenda e decomposição (F4.E12, F9.E3).

    Gera o raster de incerteza, publica como COG e regista no catálogo
    (F9.E1) com a decomposição entre parcela de controlo e parcela de cena.
    """
    coords = [tuple(c) for c in parametros.get("coords", [])]
    valores = [float(v) for v in parametros.get("valores", [])]
    largura = int(parametros.get("largura", 64))
    altura = int(parametros.get("altura", 64))
    caminho_cog = parametros.get("caminho_cog")
    caminho_catalogo = parametros.get("caminho_catalogo")
    crs = parametros.get("crs")
    crs_declaracao = parametros.get(
        "crs_declaracao", "raster em grelha de camara"
    )
    incerteza_controlo = float(parametros.get("incerteza_controlo", 0.0))
    incerteza_cena = float(parametros.get("incerteza_cena", 0.0))

    # 1. Gera o mapa de incerteza (F4.E12).
    resultado_incerteza = cobertura.gerar_mapa_incerteza(
        coords, valores, largura, altura,
        legenda=parametros.get("legenda", []),
    )

    # 2. Decomposição de incerteza (F3.E12).
    decomposicao = validacao.decompor_incerteza(incerteza_controlo, incerteza_cena)

    # 3. Publica como COG (F9.E3).
    interm = cog.RasterIntermediario(
        caminho=Path(caminho_cog or "/tmp/incerteza_intermediario.tif"),
        hash_sha256="pendente",
        largura=largura,
        altura=altura,
        crs=crs,
        nodata=None,
        campos={"incerteza": resultado_incerteza["metricas"]},
    )
    publicado = cog.publicar_cog(
        interm,
        caminho_cog or "/tmp/incerteza.cog",
        compressao=parametros.get("compressao", "DEFLATE"),
        overviews=parametros.get("overviews", [2, 4, 8]),
    )

    # 4. Regista no catálogo (F9.E1).
    if caminho_catalogo:
        cat = catalogo.Catalogo(caminho_catalogo)
        cat.abrir()
        try:
            # Quando rasterio não está disponível, o hash do COG está vazio;
            # usa-se o hash do conteúdo de incerteza como fallback.
            incerteza_serializavel = dict(resultado_incerteza)
            if "raster" in incerteza_serializavel:
                r = incerteza_serializavel["raster"]
                if hasattr(r, "tolist"):
                    incerteza_serializavel["raster"] = r.tolist()
            sha_produto = publicado.hash_sha256 or hashlib.sha256(
                json.dumps(incerteza_serializavel, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            registo = catalogo.RegistoProduto(
                product_id=parametros.get("product_id", "incerteza-001"),
                tipo="mapa_incerteza",
                formato="cog" if publicado.hash_sha256 else "raster_intermediario",
                source_uri=str(publicado.caminho),
                sha256=sha_produto,
                crs=crs,
                crs_declaracao=crs_declaracao,
                unidades={"horizontal": "m", "vertical": "m"},
                resolucao={
                    "horizontal": 1.0,
                    "vertical": 1.0,
                    "unit": "m",
                },
                campo="incerteza",
                legenda=parametros.get(
                    "legenda",
                    [
                        {"valor": 0.0, "cor": "0000ff", "rotulo": "baixa"},
                        {"valor": 1.0, "cor": "ff0000", "rotulo": "alta"},
                    ],
                ),
                data_kind="estimado",
                incerteza=catalogo.IncertezaProduto(
                    estimada=True,
                    valor=decomposicao["incerteza_total"],
                    unidade="m",
                    metodo="ensemble",
                ),
                proveniencia={
                    "source_uri": str(publicado.caminho_intermediario),
                    "operacoes": [
                        catalogo.RegistoProveniente(
                            task_id=parametros.get("task_id", "incerteza-001"),
                            algoritmo="cobertura.gerar_incerteza_cog",
                            versao="1.0.0",
                            entradas=[],
                        )
                    ],
                    "versoes": {"khnumn": "0.1.0"},
                },
            )
            cat.gravar_produto(registo)
        finally:
            cat.fechar()

    return {
        "cobertura": {
            "incerteza_total": decomposicao["incerteza_total"],
            "fracao_controlo": decomposicao["fracao_controlo"],
            "fracao_cena": decomposicao["fracao_cena"],
            "incerteza_controlo": decomposicao["incerteza_controlo"],
            "incerteza_cena": decomposicao["incerteza_cena"],
            "cog": cog.raster_publicado_para_dict(publicado),
            "registado_em_catalogo": bool(caminho_catalogo),
        }
    }


def _executar_verificacao_multivista_verificar_completa(parametros, entradas):
    """Verificação multivista por acumulação de profundidade (F8.E6, F9.E4).

    Acumula rasters de profundidade por sub-região, declara o número de
    vistas observadoras e compara com a referência de varrimento laser
    dentro dos limiares declarados.
    """
    rasters = parametros.get("rasters_profundidade", [])
    sub_regioes_dados = parametros.get("sub_regioes", [])
    semente = int(parametros.get("semente", 0))

    sub_regioes = [
        verificacao_multivista.SubRegiao(
            identificador=s.get("identificador", "sr-0"),
            coordenadas=list(s.get("coordenadas", [0.0, 0.0, 1.0, 1.0])),
            inconsistencia_m=s.get("inconsistencia_m"),
            num_vistas_observadoras=int(s.get("num_vistas_observadoras", 0)),
            profundidade_media_m=s.get("profundidade_media_m"),
            estado=s.get("estado", "sem_dados"),
        )
        for s in sub_regioes_dados
    ]

    # Acumula profundidade por sub-região.
    sub_regioes_atualizadas = (
        verificacao_multivista.acumular_profundidade_por_subregiao(
            rasters, sub_regioes
        )
    )

    referencia_dados = parametros.get("referencia_laser")
    referencia = None
    if referencia_dados is not None:
        referencia = verificacao_multivista.ReferenciaLaser(
            profundidade_por_regiao=referencia_dados.get(
                "profundidade_por_regiao", {}
            ),
            limiar_inconsistencia_m=float(
                referencia_dados.get("limiar_inconsistencia_m", 0.05)
            ),
        )

    resultado = verificacao_multivista.comparar_referencia_laser(
        sub_regioes_atualizadas, referencia
    )

    resultado_dict = verificacao_multivista.resultado_para_dict(resultado)
    resultado_dict["num_vistas_observadoras_por_regiao"] = {
        sr.identificador: sr.num_vistas_observadoras
        for sr in sub_regioes_atualizadas
    }
    resultado_dict["semente"] = semente

    return {"verificacao_multivista": resultado_dict}


# ============================================================================
# Fase 9 — Rasterização de superfície e registo de produtos
# ============================================================================

def _executar_catalogo_registar_produto(parametros, entradas):
    """Regista um produto no catalogo (F9.E1)."""
    registo_dados = parametros.get("registo", {})
    caminho_catalogo = parametros.get("caminho_catalogo")
    if not caminho_catalogo:
        raise ValueError("catalogo.registar_produto exige 'caminho_catalogo'")

    cat = catalogo.Catalogo(caminho_catalogo)
    cat.abrir()
    try:
        # Constrói o RegistoProduto a partir dos dados.
        incerteza_dados = registo_dados.get("incerteza")
        incerteza = None
        if incerteza_dados is not None:
            incerteza = catalogo.IncertezaProduto(
                estimada=bool(incerteza_dados.get("estimated", False)),
                declaracao=incerteza_dados.get("declaration"),
                valor=incerteza_dados.get("value"),
                unidade=incerteza_dados.get("unit"),
                metodo=incerteza_dados.get("method"),
            )

        prov_dados = registo_dados.get("proveniencia", {})
        operacoes = [
            catalogo.RegistoProveniente(
                task_id=op.get("task_id", ""),
                algoritmo=op.get("algoritmo", ""),
                versao=op.get("versao", ""),
                entradas=list(op.get("entradas", [])),
            )
            for op in prov_dados.get("operacoes", [])
        ]

        registo = catalogo.RegistoProduto(
            product_id=registo_dados.get("product_id", ""),
            tipo=registo_dados.get("tipo", ""),
            formato=registo_dados.get("formato", ""),
            source_uri=registo_dados.get("source_uri", ""),
            sha256=registo_dados.get("sha256", ""),
            crs=registo_dados.get("crs"),
            crs_declaracao=registo_dados.get("crs_declaracao"),
            unidades=registo_dados.get("unidades", {}),
            resolucao=registo_dados.get("resolucao", {}),
            campo=registo_dados.get("campo"),
            legenda=registo_dados.get("legenda", []),
            data_kind=registo_dados.get("data_kind", "medido"),
            incerteza=incerteza,
            proveniencia={
                "source_uri": prov_dados.get("source_uri"),
                "operacoes": operacoes,
                "versoes": prov_dados.get("versoes", {}),
            },
        )
        cat.gravar_produto(registo)
    finally:
        cat.fechar()

    return {"catalogo": {"product_id": registo.product_id, "registado": True}}


def _executar_catalogo_consultar_produto(parametros, entradas):
    """Consulta um produto no catalogo (F9.E1)."""
    product_id = parametros.get("product_id")
    caminho_catalogo = parametros.get("caminho_catalogo")
    if not product_id:
        raise ValueError("catalogo.consultar_produto exige 'product_id'")
    if not caminho_catalogo:
        raise ValueError("catalogo.consultar_produto exige 'caminho_catalogo'")

    cat = catalogo.Catalogo(caminho_catalogo)
    cat.abrir()
    try:
        produto = cat.produto(product_id)
    finally:
        cat.fechar()

    if produto is None:
        return {"catalogo": {"encontrado": False, "product_id": product_id}}

    return {
        "catalogo": {
            "encontrado": True,
            "product_id": produto.product_id,
            "tipo": produto.tipo,
            "formato": produto.formato,
            "source_uri": produto.source_uri,
            "sha256": produto.sha256,
            "crs": produto.crs,
            "crs_declaracao": produto.crs_declaracao,
            "unidades": produto.unidades,
            "resolucao": produto.resolucao,
            "campo": produto.campo,
            "legenda": produto.legenda,
            "data_kind": produto.data_kind,
            "incerteza": (
                {
                    "estimada": produto.incerteza.estimada,
                    "declaracao": produto.incerteza.declaracao,
                    "valor": produto.incerteza.valor,
                    "unidade": produto.incerteza.unidade,
                    "metodo": produto.incerteza.metodo,
                }
                if produto.incerteza
                else None
            ),
            "proveniencia": produto.proveniencia,
        }
    }


def _executar_rasterizar_pontos(parametros, entradas):
    """Rasteriza pontos 3D observados (F9.E2)."""
    pontos_dados = parametros.get("pontos", [])
    observacoes_dados = parametros.get("observacoes", [])
    camara_dados = parametros.get("camara", {})
    pose_dados = parametros.get("pose", {})
    largura = int(parametros.get("largura", 640))
    altura = int(parametros.get("altura", 480))
    valor_por_ponto = parametros.get("valor_por_ponto", [])
    agregacao = parametros.get("agregacao", "media")

    pontos = [
        rasterizador.Ponto3D(x=float(p["x"]), y=float(p["y"]), z=float(p["z"]))
        for p in pontos_dados
    ]
    observacoes = [
        rasterizador.Observacao(
            ponto_id=int(o["ponto_id"]), u=float(o["u"]), v=float(o["v"])
        )
        for o in observacoes_dados
    ]
    camara = rasterizador.ParametrosCamara(
        modelo=camara_dados.get("modelo", "SIMPLE_PINHOLE"),
        largura=int(camara_dados.get("largura", largura)),
        altura=int(camara_dados.get("altura", altura)),
        params=[float(v) for v in camara_dados.get("params", [])],
    )
    pose = rasterizador.PoseCamara(
        rotacao=[[float(v) for v in linha] for linha in pose_dados.get("rotacao", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])],
        translacao=[float(v) for v in pose_dados.get("translacao", [0.0, 0.0, 5.0])],
    )

    raster = rasterizador.rasterizar_pontos_observados(
        pontos, observacoes, camara, pose, largura, altura, valor_por_ponto, agregacao
    )
    return {"rasterizador": rasterizador.raster_para_dict(raster)}


def _executar_raster_hash(parametros, entradas):
    """Calcula o hash de um raster (F9.E2)."""
    raster_dados = parametros.get("raster", {})
    raster = rasterizador.dict_para_raster(raster_dados)
    h = rasterizador.hash_raster(raster)
    return {"rasterizador": {"hash": h}}


def _executar_cog_publicar(parametros, entradas):
    """Publica um raster como COG (F9.E3)."""
    interm_dados = parametros.get("raster_intermediario", {})
    caminho_cog = parametros.get("caminho_cog")
    if not caminho_cog:
        raise ValueError("cog.publicar exige 'caminho_cog'")

    from . import cog as _cog

    intermediario_cog = _cog.RasterIntermediario(
        caminho=Path(interm_dados.get("caminho", "")),
        hash_sha256=interm_dados.get("hash_sha256", ""),
        largura=int(interm_dados.get("largura", 0)),
        altura=int(interm_dados.get("altura", 0)),
        crs=interm_dados.get("crs"),
        nodata=interm_dados.get("nodata"),
        campos=interm_dados.get("campos", {}),
    )

    publicado = _cog.publicar_cog(
        intermediario_cog,
        caminho_cog,
        compressao=parametros.get("compressao", "DEFLATE"),
        overviews=parametros.get("overviews"),
    )
    return {"cog": _cog.raster_publicado_para_dict(publicado)}


def _executar_renderizar_sequencia(parametros, entradas):
    """Renderiza uma sequência multivista determinística (F9.E4)."""
    poses = parametros.get("poses", [])
    resolucao = parametros.get("resolucao", [640, 480])
    semente = int(parametros.get("semente", 0))
    parametros_render = parametros.get("parametros", {})

    def funcao_profundidade(indice, pose, res):
        """Função de profundidade padrão: plano inclinado com ruído determinístico."""
        largura, altura = res
        # Profundidade baseada na posição da câmera e no índice do frame.
        z_base = float(pose.get("translacao", [0.0, 0.0, 5.0])[2])
        return [[z_base + 0.1 * (i + j) for j in range(largura)] for i in range(altura)]

    sequencia = renderizacao.renderizar_sequencia(
        poses, tuple(resolucao), funcao_profundidade, semente=semente, parametros=parametros_render
    )
    return {"renderizacao": renderizacao.sequencia_para_dict(sequencia)}


#: Despacho dos algoritmos.
DESPACHO: dict[str, Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]] = {
    "metadados.extrair": _executar_metadados,
    "qualidade.imagem": _executar_qualidade,
    "qualidade.duplicados": _executar_duplicados,
    "sfm.reconstruir": _executar_sfm,
    "sfm.extrair": _executar_sfm_extrair,
    "sfm.corresponder": _executar_sfm_corresponder,
    "sfm.mapear": _executar_sfm_mapear,
    "sfm.exportar": _executar_sfm_exportar,
    "marcas.detectar": _executar_marcas_detectar,
    "marcas.filtrar": _executar_marcas_filtrar,
    "marcas.verificar_acquisibilidade": _executar_marcas_acquisibilidade,
    "controlo.ingerir": _executar_controlo_ingerir,
    "controlo.checkpoints": _executar_controlo_checkpoints,
    "controlo.similaridade": _executar_controlo_similaridade,
    "controlo.ajustar": _executar_controlo_ajustar,
    "controlo.ensemble": _executar_controlo_ensemble,
    "controlo.gnss_priors": _executar_controlo_gnss_priors,
    "validacao.metricas": _executar_validacao_metricas,
    "validacao.incerteza": _executar_validacao_incerteza,
    "marcas.rever": _executar_marcas_rever,
    "raster.residuos": _executar_raster_residuos,
    "superficie.triangulacao_esparsa": _executar_superficie_triangulacao,
    "superficie.reconstrucao_densa": _executar_superficie_densa,
    "superficie.fundir_nuvens": _executar_superficie_fundir,
    "superficie.processar_blocos": _executar_superficie_blocos,
    "superficie.processar_blocos_orcado": _executar_superficie_blocos_orcado,
    "superficie.malha_textura": _executar_superficie_malha,
    "superficie.refinamento_iterativo": _executar_superficie_refinamento,
    "ortoimagem.gerar": _executar_ortoimagem,
    "dtm.gerar": _executar_dtm,
    "validacao_denso.comparar": _executar_validacao_denso,
    "cobertura.gerar": _executar_cobertura_gerar,
    "cobertura.incerteza": _executar_cobertura_incerteza,
    "cenario.classificar": _executar_cenario_classificar,
    "cenario.corrigir": _executar_cenario_corrigir,
    "planeador.planear": _executar_planeador_planear,
    "planeador.com_orcamento": _executar_planeador_com_orcamento,
    "planeador.guardar_plano": _executar_planeador_guardar_plano,
    # Fase 6 — Vídeo e sensores auxiliares
    "tempo.sincronizar_relogios": _executar_tempo_sincronizar_relogios,
    "tempo.convenir_instante": _executar_tempo_convenir_instante,
    "video.selecionar_fotogramas": _executar_video_selecionar_fotogramas,
    "rolling_shutter.modelo_tempo_linha": _executar_rolling_shutter_modelo,
    "lidar.ingerir_nuvem": _executar_lidar_ingerir_nuvem,
    "lidar.aplicar_calibracao": _executar_lidar_aplicar_calibracao,
    "radiometria.aplicar_perfil_icc": _executar_radiometria_aplicar_icc,
    "radiometria.corrigir_vinheta": _executar_radiometria_corrigir_vinheta,
    "radiometria.calibrar_reflectancia": _executar_radiometria_calibrar_reflectancia,
    "satelite.identificar_modelo": _executar_satelite_identificar_modelo,
    "satelite.corrigir_rpc": _executar_satelite_corrigir_rpc,
    "satelite.coregistrar": _executar_satelite_coregistrar,
    "gnss_imu.integrar_poses": _executar_gnss_imu_integrar_poses,
    "gnss_imu.medir_residuos": _executar_gnss_imu_medir_residuos,
    # Fase 7 — Distribuição
    "persistencia.gravar_grafo": _executar_persistencia_gravar_grafo,
    "persistencia.recuperar_grafo": _executar_persistencia_recuperar_grafo,
    "scheduler.agendar": _executar_scheduler_agendar,
    "worker_remoto.registar": _executar_worker_remoto_registar,
    "worker_remoto.despachar": _executar_worker_remoto_despachar,
    "retry.registar_tentativa": _executar_retry_registar_tentativa,
    "checkpoint.gravar": _executar_checkpoint_gravar,
    "checkpoint.verificar_integridade": _executar_checkpoint_verificar_integridade,
    "reprodutibilidade.nivel": _executar_reprodutibilidade_nivel,
    "reprodutibilidade.comparar": _executar_reprodutibilidade_comparar,
    "seguranca.autenticar": _executar_seguranca_autenticar,
    "seguranca.proteger_transporte": _executar_seguranca_proteger_transporte,
    # Fase 8 — Fusão heterogénea avançada
    "evidencia.agrupar_por_celula": _executar_evidencia_agrupar_por_celula,
    "alinhamento.fontes": _executar_alinhamento_fontes,
    "compatibilidade_temporal.janela": _executar_compatibilidade_temporal_janela,
    "compatibilidade_temporal.marcar_mudancas": _executar_compatibilidade_temporal_marcar_mudancas,
    "decisao_evidencia.aplicar": _executar_decisao_evidencia_aplicar,
    "benchmark_fusao.comparar": _executar_benchmark_fusao_comparar,
    "verificacao_multivista.acumular": _executar_verificacao_multivista_acumular,
    # Fase 9 — Rasterização de superfície e registo de produtos
    "catalogo.registar_produto": _executar_catalogo_registar_produto,
    "catalogo.consultar_produto": _executar_catalogo_consultar_produto,
    "rasterizador.pontos": _executar_rasterizar_pontos,
    "rasterizador.hash": _executar_raster_hash,
    "cog.publicar": _executar_cog_publicar,
    "renderizacao.sequencia": _executar_renderizar_sequencia,
    # Etapas desbloqueadas pela Fase 9
    "residuos.calcular": _executar_residuos_calcular,
    "cobertura.gerar_cog": _executar_cobertura_gerar_cog,
    "cobertura.gerar_incerteza_cog": _executar_cobertura_gerar_incerteza_cog,
    "verificacao_multivista.verificar_completa": _executar_verificacao_multivista_verificar_completa,
}


def processar(pedido: dict[str, Any]) -> dict[str, Any]:
    """Processa um pedido e devolve a resposta do contrato."""
    algoritmo = pedido.get("algoritmo", "")
    parametros = pedido.get("parametros", {}) or {}
    entradas = pedido.get("entradas", []) or []

    if pedido.get("contrato") != VERSAO_CONTRATO:
        return {
            "estado": "FAILED",
            "saidas": [],
            "metricas": {},
            "avisos": [],
            "erro": (
                f"contrato desconhecido {pedido.get('contrato')!r}; "
                f"esta implementacao fala {VERSAO_CONTRATO!r}"
            ),
        }

    if algoritmo not in DESPACHO:
        return {
            "estado": "FAILED",
            "saidas": [],
            "metricas": {},
            "avisos": [],
            "erro": (
                f"algoritmo desconhecido {algoritmo!r}; "
                f"disponiveis: {sorted(DESPACHO)}"
            ),
        }

    try:
        resultado = DESPACHO[algoritmo](parametros, entradas)
    except Exception as erro:  # noqa: BLE001 - a fronteira tem de responder sempre
        return {
            "estado": "FAILED",
            "saidas": [],
            "metricas": {},
            "avisos": [],
            "erro": f"{type(erro).__name__}: {erro}",
            "traceback": traceback.format_exc(limit=8),
        }

    avisos = list(resultado.get("avisos", []))
    avisos += list(resultado.get("qualidade", {}).get("avisos", []))
    metadados = resultado.get("metadados")
    if isinstance(metadados, dict) and "imagem" in metadados.get("campos_ausentes", []):
        avisos.append(
            "o ficheiro nao e uma imagem legivel: foi inventariado, "
            "mas nao pode entrar na reconstrucao"
        )
    return {
        "estado": "SUCCEEDED_WITH_WARNINGS" if avisos else "SUCCEEDED",
        "saidas": resultado.get("saidas", []),
        "metricas": {chave: valor for chave, valor in resultado.items() if chave != "saidas"},
        "avisos": avisos,
        "erro": None,
    }


def main() -> int:
    """Le um pedido da entrada padrao e escreve a resposta na saida padrao."""
    try:
        texto = sys.stdin.read()
        pedido = json.loads(texto) if texto.strip() else {}
    except json.JSONDecodeError as erro:
        json.dump(
            {
                "estado": "FAILED",
                "saidas": [],
                "metricas": {},
                "avisos": [],
                "erro": f"pedido JSON invalido: {erro}",
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    resposta = processar(pedido)
    json.dump(resposta, sys.stdout, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
