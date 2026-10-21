#!/usr/bin/env python3
"""Gera o manifesto de hashes das partições de dados.

O manifesto declara, por conjunto e por partição, a lista de ficheiros com o
seu hash e o seu tamanho. É a evidência de que duas execuções correm sobre
exactamente os mesmos ficheiros, que é a condição de comparabilidade do
protocolo de benchmark.

A partição é aplicada por regra determinística, e não por escolha de
operador: a partição de verificação tem de ser imposta pelo carregamento, e
isso só é verdade se a regra for mechanical e não uma decisão.

Uso: `python scripts/gerar-manifesto.py [--dados DIR] [--saida FILE]`
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import re
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent

#: Extensões que são imagens.
IMAGENS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def sha256(caminho: Path) -> str:
    """Hash SHA-256 de um ficheiro, em leitura encadeada."""
    calculo = hashlib.sha256()
    with caminho.open("rb") as ficheiro:
        for bloco in iter(lambda: ficheiro.read(1 << 20), b""):
            calculo.update(bloco)
    return calculo.hexdigest()


#: Tamanho do bloco de partição.
TAMANHO_BLOCO = 4


def particao_por_bloco(ordem: int) -> str:
    """Atribui um ficheiro a uma partição, pela regra declarada.

    A regra é a do manifesto: a sequência de captura é dividida em blocos de
    quatro imagens, e a primeira imagem de cada bloco vai para `verificacao`,
    as restantes para `ajuste`.

    A remoção de uma imagem de cada quatro, em vez de uma por bloco, partia
    a conectividade do grafo de vistas: a medição está em
    `processos/linha-base.md` §3.2. A partição por blocos preserva a
    conectividade local e mantém a verificação como um conjunto cujas
    imagens nunca entram no ajuste.
    """
    if ordem % TAMANHO_BLOCO == 0:
        return "verificacao"
    return "ajuste"


def inventariar(dados: Path) -> dict[str, Any]:
    """Inventaria os ficheiros de imagem presentes no directório de dados."""
    ajustes: list[dict[str, Any]] = []
    verificacoes: list[dict[str, Any]] = []
    outros: list[dict[str, Any]] = []

    imagens = sorted(
        caminho
        for caminho in dados.rglob("*")
        if caminho.is_file() and caminho.suffix.lower() in IMAGENS
    )

    for ordem, caminho in enumerate(imagens):
        if not caminho.is_file():
            continue
        if caminho.suffix.lower() not in IMAGENS:
            # A calibração e a nuvem de pontos de referência são registadas
            # à parte: não são imagens de entrada, e o seu papel é outro.
            outros.append(
                {
                    "ficheiro": str(caminho.relative_to(dados)),
                    "bytes": caminho.stat().st_size,
                    "papel": "referencia" if "calib" in caminho.name.lower() else "auxiliar",
                }
            )
            continue

        registo = {
            "ficheiro": str(caminho.relative_to(dados)),
            "sha256": sha256(caminho),
            "bytes": caminho.stat().st_size,
        }
        if particao_por_bloco(ordem) == "verificacao":
            verificacoes.append(registo)
        else:
            ajustes.append(registo)

    return {"ajuste": ajustes, "verificacao": verificacoes, "outros": outros}


def linha_yaml(valor: Any, nivel: int = 0) -> str:
    """Serializa um valor para YAML simples, sem dependências."""
    indentacao = "  " * nivel
    if isinstance(valor, dict):
        if not valor:
            return f"{indentacao}{{}}\n"
        texto = ""
        for chave, item in valor.items():
            if isinstance(item, (dict, list)):
                texto += f"{indentacao}{chave}:\n{linha_yaml(item, nivel + 1)}"
            else:
                texto += f"{indentacao}{chave}: {item}\n"
        return texto
    if isinstance(valor, list):
        if not valor:
            return f"{indentacao}[]\n"
        texto = ""
        for item in valor:
            if isinstance(item, dict):
                chaves = list(item)
                primeira = chaves[0]
                texto += f"{indentacao}- {primeira}: {item[primeira]}\n"
                for chave in chaves[1:]:
                    texto += f"{indentacao}  {chave}: {item[chave]}\n"
            else:
                texto += f"{indentacao}- {item}\n"
        return texto
    return f"{indentacao}{valor}\n"


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--dados", default=str(RAIZ / "datasets"), help="directório dos dados")
    analisador.add_argument("--saida", default=str(RAIZ / "manifests" / "hashes.yaml"), help="ficheiro de saída")
    argumentos = analisador.parse_args()

    dados = Path(argumentos.dados)
    if not dados.exists():
        print(f"directório de dados inexistente: {dados}")
        return 1

    conteudo = "# Gerado por scripts/gerar-manifesto.py. Não editar à mão.\n"
    conteudo += "gerado_utc: \"{}\"\n".format(
        _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
    )

    total = 0
    for subdirectorio in sorted(p for p in dados.iterdir() if p.is_dir()):
        inventario = inventariar(subdirectorio)
        if not any(inventario.values()):
            continue
        total += 1
        conteudo += f"conjunto_{subdirectorio.name.replace('-', '_')}:\n"
        conteudo += f"  raiz: \"{subdirectorio.relative_to(RAIZ)}\"\n"
        for chave in ("ajuste", "verificacao", "outros"):
            itens = inventario[chave]
            conteudo += f"  {chave}:\n"
            if not itens:
                conteudo += "    []\n"
                continue
            for item in itens:
                if "sha256" in item:
                    conteudo += f"    - ficheiro: \"{item['ficheiro']}\"\n"
                    conteudo += f"      sha256: \"{item['sha256']}\"\n"
                    conteudo += f"      bytes: {item['bytes']}\n"
                else:
                    conteudo += f"    - ficheiro: \"{item['ficheiro']}\"\n"
                    conteudo += f"      bytes: {item['bytes']}\n"
                    conteudo += f"      papel: {item['papel']}\n"

    saida = Path(argumentos.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(conteudo, encoding="utf-8")

    print(f"manifesto: {saida} ({total} conjunto(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
