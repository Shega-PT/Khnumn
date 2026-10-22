"""Detecção de cenário e correção manual (Fase 5)."""

from __future__ import annotations

from typing import Any

CLASSES = [
    "aerial_nadir", "aerial_oblique", "urban_facade", "indoor",
    "natural_terrain", "vegetation", "satellite_optical", "multispectral",
    "thermal", "sar", "mixed", "unknown",
]


class ErroCenario(Exception):
    """Falha na detecção de cenário, com causa legível."""


def classificar_cenario(metadados: dict[str, Any], qualidade: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classifica o cenário a partir de sinais observáveis."""
    razoes: list[str] = []
    classe = "unknown"
    confianca = 0.3

    captura = metadados.get("capture", {}) if isinstance(metadados, dict) else {}
    posicao = captura.get("position")
    if posicao and posicao.get("source") == "GNSS_EXIF":
        classe = "aerial_nadir"
        confianca = 0.6
        razoes.append("posição GNSS presente nos metadados")
    orientacao = captura.get("orientation", {})
    if isinstance(orientacao, dict) and orientacao.get("source") not in (None, "unknown"):
        razoes.append("orientação declarada")
    media_type = metadados.get("media_type", "")
    if "tiff" in str(media_type):
        razoes.append("imagem TIFF")
    if qualidade and qualidade.get("metrics", {}).get("megapixeis", 0) > 50:
        razoes.append("imagem de alta resolução")

    if not razoes:
        classe = "unknown"
        confianca = 0.1
    return {
        "classe": classe,
        "confianca": float(confianca),
        "razoes": razoes,
        "classes_candidatas": [(classe, confianca)],
    }


def corrigir_cenario(classificacao: dict[str, Any], correcao: str, motivo: str) -> dict[str, Any]:
    """Aplica correção manual, com prioridade sobre a sugestão."""
    resultado = dict(classificacao)
    resultado["classe_final"] = correcao
    resultado["correcao_manual"] = True
    resultado["motivo"] = motivo
    resultado["classe_original"] = classificacao.get("classe")
    return resultado


__all__ = ["CLASSES", "ErroCenario", "classificar_cenario", "corrigir_cenario"]
