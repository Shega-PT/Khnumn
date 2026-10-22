"""Registo de produtos no catalogo e esquema de produto (F9.E1).

O catalogo e o que torna o projecto recuperavel entre execucoes. Ate aqui a
tabela de produtos do catalogo era codigo morto: existia no esquema SQLite
mas nunca recebia um registo. A partir desta fase, a proveniencia deixa de
ser apenas uma capacidade do modelo de dados e passa a ser um registo que se
pode consultar.

Cada produto registado declara:
- identificador, tipo e formato em disco;
- sistema de coordenadas (ou a sua ausencia declarada);
- unidade e resolucao;
- campo escalar e legenda numerica (quando e um mapa);
- distincao entre dados medidos, estimados, interpolados e inferidos por modelo;
- incerteza (ou a sua ausencia declarada);
- proveniencia completa (operacoes, versoes, fontes).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ErroCatalogo(Exception):
    """Falha no registo ou consulta de produtos, com causa legivel."""


@dataclass
class RegistoProveniente:
    """Uma operacao de proveniencia associada a um produto."""

    task_id: str
    algoritmo: str
    versao: str
    entradas: list[str]


@dataclass
class IncertezaProduto:
    """Incerteza de um produto: estimada ou declarada ausente."""

    estimada: bool
    declaracao: str | None = None
    valor: float | None = None
    unidade: str | None = None
    metodo: str | None = None


@dataclass
class RegistoProduto:
    """Registo completo de um produto no catalogo."""

    product_id: str
    tipo: str
    formato: str
    source_uri: str
    sha256: str
    crs: str | None
    crs_declaracao: str | None
    unidades: dict[str, str]
    resolucao: dict[str, Any]
    campo: str | None = None
    legenda: list[dict[str, Any]] = field(default_factory=list)
    data_kind: str = "medido"
    incerteza: IncertezaProduto | None = None
    proveniencia: dict[str, Any] = field(default_factory=dict)


def hash_ficheiro(caminho: str | Path) -> str:
    """Calcula o hash SHA-256 de um ficheiro."""
    h = hashlib.sha256()
    with open(caminho, "rb") as ficheiro:
        for bloco in iter(lambda: ficheiro.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def validar_registo_produto(registo: RegistoProduto) -> list[str]:
    """Valida um registo de produto contra o esquema produto-v1.

    Devolve uma lista de mensagens de erro. Vazia quando o registo e valido.
    """
    erros: list[str] = []

    if not registo.product_id:
        erros.append("product_id e obrigatorio")
    if not registo.tipo:
        erros.append("tipo e obrigatorio")
    if not registo.formato:
        erros.append("format e obrigatorio")
    if not registo.source_uri:
        erros.append("source_uri e obrigatorio")
    if not registo.sha256:
        erros.append("sha256 e obrigatorio")
    elif len(registo.sha256) != 64:
        erros.append("sha256 deve ter 64 carateres hexadecimais")

    # CRS: quando nulo, a declaracao de ausencia e obrigatoria.
    if registo.crs is None and not registo.crs_declaracao:
        erros.append(
            "crs_declaracao e obrigatoria quando crs e nulo (ausencia declarada)"
        )

    # Incerteza: quando nao estimada, a declaracao e obrigatoria.
    if registo.incerteza is not None and not registo.incerteza.estimada:
        if not registo.incerteza.declaracao:
            erros.append(
                "incerteza.declaracao e obrigatoria quando a incerteza nao foi estimada"
            )

    # Mapas: quando tem campo, deve ter legenda.
    if registo.campo is not None and not registo.legenda:
        erros.append(
            "legenda e obrigatoria para produtos com campo escalar (mapa)"
        )

    # Unidades.
    if "horizontal" not in registo.unidades or "vertical" not in registo.unidades:
        erros.append("unidades deve conter horizontal e vertical")

    # Resolucao.
    if "horizontal" not in registo.resolucao or "vertical" not in registo.resolucao:
        erros.append("resolucao deve conter horizontal e vertical")

    # Data kind.
    validos_data_kind = {"medido", "estimado", "interpolado", "inferido_por_modelo"}
    if registo.data_kind not in validos_data_kind:
        erros.append(f"data_kind deve ser um de {sorted(validos_data_kind)}")

    return erros


def registo_para_dict(registo: RegistoProduto) -> dict[str, Any]:
    """Serializa um registo de produto para dicionario JSON."""
    incerteza_dict: dict[str, Any] | None = None
    if registo.incerteza is not None:
        incerteza_dict = {
            "estimated": registo.incerteza.estimada,
            "declaration": registo.incerteza.declaracao,
            "value": registo.incerteza.valor,
            "unit": registo.incerteza.unidade,
            "method": registo.incerteza.metodo,
        }

    return {
        "schema_version": "1.0.0",
        "product_id": registo.product_id,
        "type": registo.tipo,
        "format": registo.formato,
        "source_uri": registo.source_uri,
        "sha256": registo.sha256,
        "crs": registo.crs,
        "crs_declaration": registo.crs_declaracao,
        "units": registo.unidades,
        "resolution": registo.resolucao,
        "campo": registo.campo,
        "legenda": registo.legenda,
        "data_kind": registo.data_kind,
        "uncertainty": incerteza_dict or {
            "estimated": False,
            "declaration": "incerteza nao estimada",
            "value": None,
            "unit": None,
            "method": None,
        },
        "provenance": {
            "source_uri": registo.proveniencia.get("source_uri"),
            "operations": [
                {
                    "task_id": op.task_id,
                    "algorithm": op.algoritmo,
                    "version": op.versao,
                    "inputs": op.entradas,
                }
                for op in registo.proveniencia.get(
                    "operations", registo.proveniencia.get("operacoes", [])
                )
            ],
            "versions": registo.proveniencia.get(
                "versions", registo.proveniencia.get("versoes", {})
            ),
        },
    }


class Catalogo:
    """Catalogo local de produtos, sobre SQLite."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)
        self.ligacao: sqlite3.Connection | None = None

    def abrir(self) -> None:
        """Abre o catalogo, criando o esquema se necessario."""
        if self.caminho.parent and not self.caminho.parent.exists():
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.ligacao = sqlite3.connect(str(self.caminho))
        self.ligacao.execute("PRAGMA journal_mode = WAL")
        self.ligacao.execute("PRAGMA foreign_keys = ON")
        self._criar_esquema()

    def fechar(self) -> None:
        """Fecha a ligacao ao catalogo."""
        if self.ligacao is not None:
            self.ligacao.close()
            self.ligacao = None

    def _criar_esquema(self) -> None:
        assert self.ligacao is not None
        self.ligacao.executescript(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                product_id   TEXT PRIMARY KEY,
                tipo         TEXT NOT NULL,
                formato      TEXT NOT NULL,
                registo      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS produtos_tipo ON produtos(tipo);
            """
        )
        self.ligacao.commit()

    def gravar_produto(self, registo: RegistoProduto) -> None:
        """Grava um registo de produto no catalogo, substituindo se ja existir."""
        if self.ligacao is None:
            raise ErroCatalogo("catalogo nao esta aberto")
        erros = validar_registo_produto(registo)
        if erros:
            raise ErroCatalogo("registo invalido: " + "; ".join(erros))
        texto = json.dumps(registo_para_dict(registo), ensure_ascii=False)
        self.ligacao.execute(
            """
            INSERT INTO produtos(product_id, tipo, formato, registo)
            VALUES (?1, ?2, ?3, ?4)
            ON CONFLICT(product_id) DO UPDATE SET
                tipo = excluded.tipo,
                formato = excluded.formato,
                registo = excluded.registo
            """,
            (registo.product_id, registo.tipo, registo.formato, texto),
        )
        self.ligacao.commit()

    def produto(self, product_id: str) -> RegistoProduto | None:
        """Devolve um registo de produto pelo identificador."""
        if self.ligacao is None:
            raise ErroCatalogo("catalogo nao esta aberto")
        linha = self.ligacao.execute(
            "SELECT registo FROM produtos WHERE product_id = ?1",
            (product_id,),
        ).fetchone()
        if linha is None:
            return None
        dados = json.loads(linha[0])
        return _dict_para_registo(dados)

    def listar_produtos(self) -> list[RegistoProduto]:
        """Lista todos os produtos registados."""
        if self.ligacao is None:
            raise ErroCatalogo("catalogo nao esta aberto")
        cursor = self.ligacao.execute("SELECT registo FROM produtos")
        return [_dict_para_registo(json.loads(linha[0])) for linha in cursor]


def _dict_para_registo(dados: dict[str, Any]) -> RegistoProduto:
    """Constrói um RegistoProduto a partir de um dicionario JSON."""
    incerteza_dados = dados.get("uncertainty")
    incerteza: IncertezaProduto | None = None
    if incerteza_dados is not None:
        incerteza = IncertezaProduto(
            estimada=bool(incerteza_dados.get("estimated", False)),
            declaracao=incerteza_dados.get("declaration"),
            valor=incerteza_dados.get("value"),
            unidade=incerteza_dados.get("unit"),
            metodo=incerteza_dados.get("method"),
        )

    proveniencia = dados.get("provenance", {})
    # Aceita ambas as grafias (inglesa do esquema e portuguesa do codigo).
    operacoes_raw = proveniencia.get("operations", proveniencia.get("operacoes", []))
    operacoes = [
        RegistoProveniente(
            task_id=op.get("task_id", ""),
            algoritmo=op.get("algorithm", op.get("algoritmo", "")),
            versao=op.get("version", op.get("versao", "")),
            entradas=list(op.get("inputs", op.get("entradas", []))),
        )
        for op in operacoes_raw
    ]

    return RegistoProduto(
        product_id=dados["product_id"],
        tipo=dados["type"],
        formato=dados["format"],
        source_uri=dados["source_uri"],
        sha256=dados["sha256"],
        crs=dados.get("crs"),
        crs_declaracao=dados.get("crs_declaration", dados.get("crs_declaracao")),
        unidades=dados.get("units", dados.get("unidades", {})),
        resolucao=dados.get("resolution", dados.get("resolucao", {})),
        campo=dados.get("campo"),
        legenda=dados.get("legenda", []),
        data_kind=dados.get("data_kind", "medido"),
        incerteza=incerteza,
        proveniencia={
            "source_uri": proveniencia.get("source_uri"),
            "operacoes": operacoes,
            "versoes": proveniencia.get("versions", proveniencia.get("versoes", {})),
        },
    )


__all__ = [
    "ErroCatalogo",
    "RegistoProveniente",
    "IncertezaProduto",
    "RegistoProduto",
    "Catalogo",
    "hash_ficheiro",
    "validar_registo_produto",
    "registo_para_dict",
]
