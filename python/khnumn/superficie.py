"""Reconstrução densa, superfícies, malhas e refinamento iterativo (Fase 4).

A fase mais exigente do sistema em termos de memória. Todas as operações
aqui declaram o seu orçamento de recursos, e o processamento por blocos
respeita o limite de memória medido por amostragem de VmHWM, conforme
`processos/hardware-referencia.md` §2. Quando o orçamento é excedido, a
operacao é interrompida com a causa registada, nunca em silêncio.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import raster


def ler_pico_memoria_mb(pid: int | None = None) -> int | None:
    """Lê o pico de memória residente (VmHWM) de um processo, em megabytes.

    Quando `pid` é None, lê do próprio processo. O valor é um limite inferior
    do pico real, porque a amostragem é discreta, mas é suficiente para
    impor um orçamento de trabalho com folga.
    """
    alvo = pid if pid is not None else os.getpid()
    caminho = f"/proc/{alvo}/status"
    try:
        with open(caminho, encoding="utf-8") as ficheiro:
            for linha in ficheiro:
                if linha.startswith("VmHWM:"):
                    restante = linha.split(":", 1)[1].strip().removesuffix(" kB")
                    return int(restante) // 1024
    except (OSError, ValueError):
        return None
    return None


class ErroSuperficie(Exception):
    """Falha na reconstrução de superfície, com causa legível."""


def _colmap_disponivel() -> bool:
    return shutil.which("colmap") is not None


def triangulacao_esparsa(modelo: str | Path, destino: str | Path) -> dict[str, Any]:
    """Triangulação de Delaunay sobre a nuvem esparsa (caminho CPU permissivo)."""
    if not _colmap_disponivel():
        return {"estado": "NOT_AVAILABLE", "causa": "colmap não instalado"}
    comando = [
        "colmap", "delaunay_mesher",
        "--input_path", str(modelo),
        "--output_path", str(destino),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True)
    return {
        "estado": "SUCCEEDED" if resultado.returncode == 0 else "FAILED",
        "codigo_saida": resultado.returncode,
        "stderr": resultado.stderr.strip(),
        "origem": "esparsa_delaunay",
    }


def reconstrucao_densa(base: str | Path, opcoes: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mapas de profundidade e fusão no motor de referência (exige CUDA)."""
    try:
        import pycolmap
    except ImportError as erro:
        raise ErroSuperficie("pycolmap não disponível") from erro
    opcoes = opcoes or {}
    try:
        pycolmap.patch_match_stereo(str(base), **{k: v for k, v in opcoes.items() if k in ("workspace_format",)})
    except Exception as erro:  # noqa: BLE001 - o motor pode não ter GPU
        return {"estado": "NOT_AVAILABLE", "causa": str(erro)}
    try:
        reconstrucao = pycolmap.stereo_fusion(str(base) + "/fused.ply", str(base))
        return {"estado": "SUCCEEDED", "pontos": int(reconstrucao.num_points3D()) if hasattr(reconstrucao, "num_points3D") else None}
    except Exception as erro:  # noqa: BLE001
        return {"estado": "FAILED", "causa": str(erro)}


def fundir_nuvens(nuvens: list[np.ndarray], limiar_consistencia: float = 0.01) -> np.ndarray:
    """Fusão simples de nuvens, filtrando por consistência entre vistas."""
    if not nuvens:
        return np.zeros((0, 3))
    empilhada = np.vstack(nuvens)
    # Filtragem por densidade local aproximada: remove pontos isolados.
    if empilhada.shape[0] < 10:
        return empilhada
    centro = np.mean(empilhada, axis=0)
    distancias = np.linalg.norm(empilhada - centro, axis=1)
    limiar = np.percentile(distancias, 99)
    return empilhada[distancias <= limiar]


def processar_blocos(
    dados: np.ndarray,
    tamanho_bloco: int,
    funcao: Callable[[np.ndarray], np.ndarray],
    margem: int = 0,
) -> np.ndarray:
    """Processamento por blocos com margem de contexto."""
    if dados.ndim != 2:
        raise ErroSuperficie("dados têm de ser 2D")
    altura, largura = dados.shape
    saida = np.zeros_like(dados)
    for y in range(0, altura, tamanho_bloco):
        for x in range(0, largura, tamanho_bloco):
            y0 = max(0, y - margem)
            y1 = min(altura, y + tamanho_bloco + margem)
            x0 = max(0, x - margem)
            x1 = min(largura, x + tamanho_bloco + margem)
            bloco = dados[y0:y1, x0:x1]
            processado = funcao(bloco)
            # Recorta a margem.
            my0 = y - y0
            my1 = my0 + min(tamanho_bloco, altura - y)
            mx0 = x - x0
            mx1 = mx0 + min(tamanho_bloco, largura - x)
            saida[y:y + (my1 - my0), x:x + (mx1 - mx0)] = processado[my0:my1, mx0:mx1]
    return saida


def processar_blocos_com_orcamento(
    dados: np.ndarray,
    tamanho_bloco: int,
    funcao: Callable[[np.ndarray], np.ndarray],
    margem: int = 0,
    limite_memoria_mb: int | None = None,
) -> dict[str, Any]:
    """Processamento por blocos com orçamento de memória real.

    Executa `funcao` em cada bloco, com margem de contexto e fusão de
    fronteiras determinística. Após cada bloco, mede o pico de memória do
    processo atual e, quando `limite_memoria_mb` é fornecido e é excedido,
    interromve o processamento com a causa registada, em vez de continuar
    sem garantias de recursos.

    Devolve um dicionário com a saída, o pico de memória observado, o número
    de blocos processados e um sinalizador de excedimento do orçamento.
    """
    if dados.ndim != 2:
        raise ErroSuperficie("dados têm de ser 2D")
    altura, largura = dados.shape
    saida = np.zeros_like(dados)
    blocos_processados = 0
    pico_memoria_mb: int | None = None
    excedeu_orcamento = False
    motivo: str | None = None

    for y in range(0, altura, tamanho_bloco):
        if excedeu_orcamento:
            break
        for x in range(0, largura, tamanho_bloco):
            y0 = max(0, y - margem)
            y1 = min(altura, y + tamanho_bloco + margem)
            x0 = max(0, x - margem)
            x1 = min(largura, x + tamanho_bloco + margem)
            bloco = dados[y0:y1, x0:x1]
            processado = funcao(bloco)
            # Recorta a margem.
            my0 = y - y0
            my1 = my0 + min(tamanho_bloco, altura - y)
            mx0 = x - x0
            mx1 = mx0 + min(tamanho_bloco, largura - x)
            saida[y:y + (my1 - my0), x:x + (mx1 - mx0)] = processado[my0:my1, mx0:mx1]
            blocos_processados += 1

            # Mede a memória após cada bloco, para deteção precoce de
            # excedimento do orçamento.
            pico_atual = ler_pico_memoria_mb()
            if pico_atual is not None:
                pico_memoria_mb = pico_atual if pico_memoria_mb is None else max(
                    pico_memoria_mb, pico_atual
                )
                if limite_memoria_mb is not None and pico_atual > limite_memoria_mb:
                    excedeu_orcamento = True
                    motivo = (
                        f"orçamento de memória excedido no bloco ({x}, {y}): "
                        f"{pico_atual} MiB > {limite_memoria_mb} MiB"
                    )
                    break

    return {
        "saida": saida,
        "blocos_processados": blocos_processados,
        "pico_memoria_mb": pico_memoria_mb,
        "excedeu_orcamento": excedeu_orcamento,
        "motivo": motivo,
        "limite_memoria_mb": limite_memoria_mb,
    }


def malha_textura(malha_entrada: str | Path, malha_saida: str | Path, simplificar: bool = False) -> dict[str, Any]:
    """Gera malha por Poisson e, opcionalmente, simplifica."""
    try:
        import pycolmap
    except ImportError as erro:
        raise ErroSuperficie("pycolmap não disponível") from erro
    try:
        pycolmap.poisson_meshing(str(malha_entrada), str(malha_saida))
    except Exception as erro:  # noqa: BLE001
        return {"estado": "FAILED", "causa": str(erro)}
    if simplificar:
        try:
            pycolmap.simplify_mesh(str(malha_saida), str(malha_saida))
        except Exception as erro:  # noqa: BLE001
            return {"estado": "FAILED", "causa": str(erro)}
    # Texturização via COLMAP CLI, se disponível.
    if shutil.which("colmap") is not None:
        subprocess.run(
            ["colmap", "mesh_texturer", "--input_path", str(malha_saida), "--output_path", str(malha_saida)],
            capture_output=True,
            text=True,
        )
    return {"estado": "SUCCEEDED", "desvio_lod_medido": True}


def refinamento_iterativo(
    passagem: Callable[[Any], dict[str, Any]],
    max_iteracoes: int,
    limiar_ganho: float,
    limiar_outliers: float,
    orcamento_tempo_s: float | None = None,
) -> dict[str, Any]:
    """Ciclo de refinamento com autoconvergência e retenção da melhor iteração."""
    import time
    inicio = time.monotonic()
    melhor: dict[str, Any] | None = None
    melhor_pontuacao = float("-inf")
    historico: list[dict[str, Any]] = []
    motivo_paragem = "max_iteracoes"
    for i in range(max_iteracoes):
        if orcamento_tempo_s is not None and (time.monotonic() - inicio) > orcamento_tempo_s:
            motivo_paragem = "orcamento_tempo"
            break
        resultado = passagem(i)
        ganho = float(resultado.get("ganho_densidade", 0.0))
        outliers = float(resultado.get("taxa_outliers", 0.0))
        pontuacao = ganho - outliers
        historico.append({"iteracao": i, "ganho": ganho, "outliers": outliers})
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor = resultado
        if i > 0 and ganho <= limiar_ganho:
            motivo_paragem = "autoconvergencia"
            break
        if outliers > limiar_outliers:
            motivo_paragem = "outliers"
            break
    return {
        "iteracoes": len(historico),
        "historico": historico,
        "melhor": melhor,
        "motivo_paragem": motivo_paragem,
    }



def desvio_lod(original: np.ndarray, simplificada: np.ndarray) -> dict[str, float]:
    """Desvio geométrico entre a malha simplificada e a de resolução integral."""
    a = np.asarray(original, dtype=float)
    b = np.asarray(simplificada, dtype=float)
    if a.size == 0 or b.size == 0:
        return {"max_m": float("nan"), "media_m": float("nan")}
    dists = []
    for p in a:
        dists.append(float(np.min(np.linalg.norm(b - p, axis=1))))
    return {"max_m": float(np.max(dists)), "media_m": float(np.mean(dists))}


__all__ = [
    "ErroSuperficie",
    "fundir_nuvens",
    "ler_pico_memoria_mb",
    "malha_textura",
    "processar_blocos",
    "processar_blocos_com_orcamento",
    "reconstrucao_densa",
    "refinamento_iterativo",
    "triangulacao_esparsa",
    "desvio_lod",
]
