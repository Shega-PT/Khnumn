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
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from . import metadados, qualidade
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
    resultado = adaptador.mapear(base)
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
