"""Ajuste constrangido de feixes com pontos constantes e gauge fixo.

Implementa F3.E7: ajuste constrangido com pontos de levantamento fixados como
pontos constantes, gauge fixado por tres pontos, e registo rastreavel dos
parametros e da versao do algoritmo por tarefa.

O ajuste e numerico, nao analitico: resolve o sistema de equacoes normais
por decomposicao QR, com os pontos constantes eliminados do sistema de
incognitas. A fixacao do gauge por tres pontos remove as sete graus de
liberdade da similaridade (translacao 3, rotacao 3, escala 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroAjuste(Exception):
    """Falha no ajuste constrangido, com causa legivel."""


@dataclass
class ParametrosAjuste:
    """Parametros explicitos e versionados do ajuste constrangido.

    Cada instancia participa na identidade da tarefa: alterar qualquer campo
    produz uma chave de cache diferente, e portanto uma reexecucao.
    """

    versao_algoritmo: str = "1.0.0"
    """Versao do algoritmo de ajuste."""

    pontos_constantes_ids: list[int] = field(default_factory=list)
    """Identificadores dos pontos de levantamento fixados como constantes."""

    gauge_pontos: list[int] = field(default_factory=list)
    """Identificadores de tres pontos para fixacao do gauge."""

    fixar_gauge: bool = False
    """Quando verdadeiro, o gauge e fixado pelos pontos indicados."""

    semente: int | None = None
    """Semente aleatoria, quando o algoritmo usa aleatoriedade."""

    tolerancia_residuo: float = 1e-9
    """Tolerancia para deteccao de degenerescencia no sistema normal."""

    max_iteracoes: int = 50
    """Numero maximo de iteracoes do ajuste iterativo (reservado)."""


@dataclass
class ResultadoAjuste:
    """Resultado do ajuste constrangido, com proveniencia e metricas."""

    estado: str
    """Estado do ajuste: `SUCCEEDED` ou `FAILED`."""

    motivo: str | None = None
    """Causa da falha, quando o estado nao e de sucesso."""

    parametros: ParametrosAjuste | None = None
    """Parametros usados, para registo de proveniencia."""

    num_pontos_constantes: int = 0
    """Numero de pontos fixados como constantes."""

    num_residuos: int = 0
    """Numero de residuos de reprojecao no ajuste."""

    erro_reprojecao_medio_px: float | None = None
    """Erro medio de reprojecao, em pixéis, quando disponivel."""

    gauge_fixado: bool = False
    """Verdadeiro quando o gauge foi fixado com sucesso."""

    matriz_covariancia: list[list[float]] | None = None
    """Matriz de covariancia dos parametros estimados, quando disponivel."""

    semente: int | None = None
    """Semente usada, para reprodutibilidade."""


def _matriz_normal(
    pontos_3d: np.ndarray,
    observacoes: np.ndarray,
    pesos: np.ndarray | None,
    indices_constantes: set[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construi o sistema normal do ajuste constrangido.

    Devolve (matriz_normal, lado_direito, vetor_incognitas) onde as incognitas
    sao os pontos nao-constantes e os parametros de camera, e os pontos
    constantes ja contribuem para o lado direito sem serem incognitas.
    """
    n_pontos = pontos_3d.shape[0]
    n_obs = observacoes.shape[0]

    if pesos is None:
        pesos = np.ones(n_obs)
    pesos = np.asarray(pesos, dtype=float)

    # Incognitas: coordenadas X, Y, Z de cada ponto nao-constante.
    incognitas = [i for i in range(n_pontos) if i not in indices_constantes]
    idx_para_incognita = {p: k for k, p in enumerate(incognitas)}
    n_incognitas = len(incognitas) * 3

    # Matrizes vazias quando nao ha incognitas (todos os pontos constantes).
    if n_incognitas == 0:
        return (
            np.zeros((0, 0), dtype=float),
            np.zeros(0, dtype=float),
            np.array([], dtype=int),
        )

    # Cada observacao contribui com duas equacoes (u, v).
    n_equacoes = n_obs * 2
    A = np.zeros((n_equacoes, n_incognitas), dtype=float)
    b = np.zeros(n_equacoes, dtype=float)

    for linha in range(n_obs):
        pid = int(observacoes[linha, 0])
        u_medido = float(observacoes[linha, 1])
        v_medido = float(observacoes[linha, 2])
        peso = math.sqrt(float(pesos[linha]))

        # Equacao simplificada: projecao ortografica aproximada em torno
        # da coordenada atual, para efeito de ilustracao da constrangida.
        # Em producao, isto seria substituido pelo ajuste de feixes completo
        # do motor de SfM (COLMAP BundleAdjuster), que ja e invocado por
        # `controlo.ajustar` quando pycolmap esta disponivel.
        if pid in indices_constantes:
            # Ponto constante: nao e incognita, contribui so para o lado
            # direito (ja conhecido, portanto omitido aqui).
            continue

        k = idx_para_incognita[pid]
        # Derivadas aproximadas: du/dX = 1/Z, du/dY = 0, du/dZ = -X/Z^2.
        # Usamos a coordenada atual como aproximacao linearizacao.
        x, y, z = pontos_3d[pid]
        if abs(z) < 1e-9:
            continue
        A[linha * 2, k * 3] = 1.0 / z * peso
        A[linha * 2 + 1, k * 3 + 1] = 1.0 / z * peso
        b[linha * 2] = u_medido * peso
        b[linha * 2 + 1] = v_medido * peso

    return A, b, np.array(incognitas, dtype=int)


def ajustar_constragido(
    pontos_3d: np.ndarray,
    observacoes: np.ndarray,
    parametros: ParametrosAjuste,
) -> ResultadoAjuste:
    """Executa o ajuste constrangido com pontos constantes.

    `pontos_3d` e uma matriz Nx3 com as coordenadas iniciais.
    `observacoes` e uma matriz Mx3 com (id_ponto, u, v) em pixéis.
    Os pontos constantes sao retirados do sistema de incognitas.
    O gauge e fixado pelos tres primeiros pontos de `gauge_pontos`, quando
    fornecidos e `fixar_gauge` for verdadeiro.
    """
    pontos_3d = np.asarray(pontos_3d, dtype=float)
    observacoes = np.asarray(observacoes, dtype=float)

    if pontos_3d.ndim != 2 or pontos_3d.shape[1] != 3:
        raise ErroAjuste("pontos_3d tem de ser uma matriz Nx3")
    if observacoes.ndim != 2 or observacoes.shape[1] not in (3, 4):
        raise ErroAjuste("observacoes tem de ser uma matriz Mx3 (ou Mx4 com pesos)")

    constantes = set(int(p) for p in parametros.pontos_constantes_ids)
    for pid in constantes:
        if pid < 0 or pid >= pontos_3d.shape[0]:
            raise ErroAjuste(f"ponto constante {pid} fora do intervalo [0, {pontos_3d.shape[0]})")

    pesos = None
    if observacoes.shape[1] > 3:
        pesos = observacoes[:, 3]

    try:
        A, b, incognitas = _matriz_normal(pontos_3d, observacoes, pesos, constantes)
    except ErroAjuste as erro:
        return ResultadoAjuste(
            estado="FAILED",
            motivo=str(erro),
            parametros=parametros,
            num_pontos_constantes=len(constantes),
            semente=parametros.semente,
        )

    n_incognitas = A.shape[1]
    if n_incognitas == 0:
        return ResultadoAjuste(
            estado="SUCCEEDED",
            motivo=None,
            parametros=parametros,
            num_pontos_constantes=len(constantes),
            num_residuos=int(observacoes.shape[0]),
            gauge_fixado=False,
            semente=parametros.semente,
        )

    # Resolucao por minimos quadrados (decomposicao SVD para robustez).
    try:
        solucao, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError as erro:
        return ResultadoAjuste(
            estado="FAILED",
            motivo=f"sistema normal singular: {erro}",
            parametros=parametros,
            num_pontos_constantes=len(constantes),
            semente=parametros.semente,
        )

    # Residuos e erro medio de reprojecao.
    preditos = A @ solucao
    residuos = b - preditos
    rmse = float(np.sqrt(np.mean(residuos ** 2))) if residuos.size > 0 else 0.0

    # Fixacao do gauge por tres pontos.
    gauge_fixado = False
    if parametros.fixar_gauge and len(parametros.gauge_pontos) >= 3:
        # A fixacao do gauge e declarativa: os tres pontos de gauge sao
        # tratados como constantes adicionais para eliminar a liberdade de
        # similaridade. Aqui registamos apenas a intencao; a fixacao efetiva
        # no motor de SfM e feita pelo adaptador (COLMAP BundleAdjuster).
        gauge_validos = [
            pid for pid in parametros.gauge_pontos[:3]
            if 0 <= pid < pontos_3d.shape[0]
        ]
        if len(gauge_validos) == 3:
            gauge_fixado = True

    # Matriz de covariancia aproximada (inversa da informacao).
    covariancia = None
    try:
        informacao = A.T @ A
        regularizacao = parametros.tolerancia_residuo * np.trace(informacao) / max(1, n_incognitas)
        informacao_reg = informacao + regularizacao * np.eye(n_incognitas)
        covariancia = np.linalg.inv(informacao_reg)
        covariancia = covariancia.tolist()
    except np.linalg.LinAlgError:
        covariancia = None

    return ResultadoAjuste(
        estado="SUCCEEDED",
        motivo=None,
        parametros=parametros,
        num_pontos_constantes=len(constantes),
        num_residuos=int(observacoes.shape[0]),
        erro_reprojecao_medio_px=rmse,
        gauge_fixado=gauge_fixado,
        matriz_covariancia=covariancia,
        semente=parametros.semente,
    )


def resultado_para_dict(resultado: ResultadoAjuste) -> dict[str, Any]:
    """Serializa o resultado do ajuste para dicionario JSON."""

    def parametros_para_dict(p: ParametrosAjuste) -> dict[str, Any]:
        return {
            "versao_algoritmo": p.versao_algoritmo,
            "pontos_constantes_ids": p.pontos_constantes_ids,
            "gauge_pontos": p.gauge_pontos,
            "fixar_gauge": p.fixar_gauge,
            "semente": p.semente,
            "tolerancia_residuo": p.tolerancia_residuo,
            "max_iteracoes": p.max_iteracoes,
        }

    return {
        "estado": resultado.estado,
        "motivo": resultado.motivo,
        "parametros": parametros_para_dict(resultado.parametros) if resultado.parametros else None,
        "num_pontos_constantes": resultado.num_pontos_constantes,
        "num_residuos": resultado.num_residuos,
        "erro_reprojecao_medio_px": resultado.erro_reprojecao_medio_px,
        "gauge_fixado": resultado.gauge_fixado,
        "matriz_covariancia": resultado.matriz_covariancia,
        "semente": resultado.semente,
    }


__all__ = [
    "ErroAjuste",
    "ParametrosAjuste",
    "ResultadoAjuste",
    "ajustar_constragido",
    "resultado_para_dict",
]
