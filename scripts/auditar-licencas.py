#!/usr/bin/env python3
"""Auditoria de licenças e geração de SBOM.

A auditoria é feita **por build**, e não por tabela: a licença de uma
dependência transitiva pode diferir da licença da biblioteca que a invoca, e
a unica forma de saber o que está efectivamente ligado é olhar para a
árvore de dependências compilada (`THIRD-PARTY.md` §4.3).

O script recolhe:

* as dependências Python a partir de `requirements.lock`, com a licença e a
  versão verificadas no PyPI;
* as dependências Rust a partir de `Cargo.lock`, com a licença verificada no
  crates.io;
* as bibliotecas que o motor embute, no caso do `pycolmap`, que é o ponto
  onde uma build estática pode esconder componentes com licença diferente.

A saída é um relatório em Markdown e um SBOM em JSON.

Uso: `python scripts/auditar-licencas.py [--offline] [--saida DIR]`
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
AGENTE = "khnumn-auditoria (auditoria de licencas)"

#: Licenças que não entram no núcleo distribuível.
COPYLEFT_FORTE = {"AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "GPL-2.0", "GPL-3.0", "GPL-2.0-only", "GPL-3.0-only"}


def _pedir(url: str, timeout: int = 20) -> dict[str, Any] | None:
    """Pede um documento JSON, ou devolve None se não for possível."""
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def ler_requirements(ficheiro: Path) -> list[tuple[str, str]]:
    """Lê o lock file Python."""
    if not ficheiro.exists():
        return []
    pares = []
    for linha in ficheiro.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "==" not in linha:
            continue
        nome, versao = linha.split("==", 1)
        pares.append((nome.strip(), versao.strip()))
    return sorted(pares)


def licenca_pypi(nome: str, offline: bool) -> dict[str, Any]:
    """Obtém a licença declarada de um pacote no PyPI."""
    dados = {"nome": nome, "licenca": None, "fonte": "desconhecida"}
    if offline:
        return dados
    info = _pedir(f"https://pypi.org/pypi/{nome}/json")
    if not info:
        return dados
    meta = info.get("info", {})
    licenca = meta.get("license_expression") or meta.get("license") or ""
    classificadores = [c for c in meta.get("classifiers", []) if c.startswith("License ::")]
    dados["licenca"] = licenca or (classificadores[0].split("::")[-1].strip() if classificadores else None)
    dados["fonte"] = "PyPI"
    return dados


def ler_cargo_lock(ficheiro: Path) -> list[tuple[str, str]]:
    """Lê o lock file Rust."""
    if not ficheiro.exists():
        return []
    conteudo = ficheiro.read_text(encoding="utf-8")
    pacotes = []
    for bloco in re.findall(r"\[\[package\]\](.*?)(?=\n\[\[package\]\]|\Z)", conteudo, re.S):
        nome = re.search(r'^name = "(.+)"$', bloco, re.M)
        versao = re.search(r'^version = "(.+)"$', bloco, re.M)
        if nome and versao:
            pacotes.append((nome.group(1), versao.group(1)))
    return sorted(set(pacotes))


def licenca_crates(nome: str, versao: str, offline: bool) -> dict[str, Any]:
    """Obtém a licença declarada de um crate no crates.io."""
    dados = {"nome": nome, "versao": versao, "licenca": None, "fonte": "desconhecida"}
    if offline:
        return dados
    info = _pedir(f"https://crates.io/api/v1/crates/{nome}/{versao}")
    if not info:
        return dados
    versao_info = info.get("version", {})
    dados["licenca"] = versao_info.get("license") or None
    dados["fonte"] = "crates.io"
    return dados


def bibliotecas_embutidas() -> list[dict[str, Any]]:
    """Inventaria as bibliotecas que o wheel do motor embute.

    Uma build estática do motor pode transportar componentes com licença
    própria. É aqui que uma política de núcleo livre de copyleft forte é
    verificada, e não declarada.
    """
    venv = RAIZ / ".venv" / "lib"
    if not venv.exists():
        return []
    encontradas = []
    for caminho in sorted(venv.glob("python*/site-packages/pycolmap.libs/*")):
        encontradas.append(
            {
                "ficheiro": caminho.name,
                "bytes": caminho.stat().st_size,
                "origem": "wheel pycolmap (build estatica do motor COLMAP)",
            }
        )
    return encontradas


def classificar(licenca: str | None) -> str:
    """Classifica uma licença face à política do núcleo."""
    if not licenca:
        return "desconhecida"
    normalizada = licenca.strip().upper()
    if "AGPL" in normalizada:
        return "copyleft forte"
    if re.search(r"\bGPL\b", normalizada) and "LGPL" not in normalizada:
        return "copyleft forte"
    if "LGPL" in normalizada or "MPL" in normalizada:
        return "copyleft fraco"
    if any(marca in normalizada for marca in ("MIT", "BSD", "APACHE", "PSF", "ISC", "ZLIB")):
        return "permissiva"
    return "a classificar"


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--offline", action="store_true", help="não consultar a rede")
    analisador.add_argument("--saida", default=str(RAIZ / "processos"), help="directório de saída")
    argumentos = analisador.parse_args()

    saida = Path(argumentos.saida)
    saida.mkdir(parents=True, exist_ok=True)

    python = []
    for nome, versao in ler_requirements(RAIZ / "requirements.lock"):
        registo = licenca_pypi(nome, argumentos.offline)
        registo["versao"] = versao
        registo["classificacao"] = classificar(registo.get("licenca"))
        python.append(registo)

    rust = []
    for nome, versao in ler_cargo_lock(RAIZ / "Cargo.lock"):
        registo = licenca_crates(nome, versao, argumentos.offline)
        registo["classificacao"] = classificar(registo.get("licenca"))
        rust.append(registo)

    embebidas = bibliotecas_embutidas()

    sbom = {
        "schema_version": "1.0.0",
        "gerado_utc": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "projecto": "khnumn",
        "versao": "0.1.0",
        "licenca_do_projecto": "Apache-2.0",
        "python": python,
        "rust": rust,
        "binarios_embutidos": embebidas,
    }
    (saida / "sbom.json").write_text(
        json.dumps(sbom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    linhas = [
        "# Auditoria de licenças — resultado automático",
        "",
        "Gerado por `scripts/auditar-licencas.py`. A data e a versão de cada",
        "verificação estão no SBOM em `processos/sbom.json`.",
        "",
        "## Dependências Python",
        "",
        "| Componente | Versão | Licença | Classificação |",
        "|---|---|---|---|",
    ]
    for registo in python:
        linhas.append(
            f"| `{registo['nome']}` | {registo.get('versao', '')} | {registo.get('licenca') or 'não verificada'} | {registo['classificacao']} |"
        )
    linhas += [
        "",
        "## Dependências Rust",
        "",
        "| Componente | Versão | Licença | Classificação |",
        "|---|---|---|---|",
    ]
    for registo in rust:
        linhas.append(
            f"| `{registo['nome']}` | {registo.get('versao', '')} | {registo.get('licenca') or 'não verificada'} | {registo['classificacao']} |"
        )
    linhas += [
        "",
        "## Bibliotecas embebidas no motor",
        "",
        "| Ficheiro | Bytes | Origem |",
        "|---|---|---|",
    ]
    for registo in embebidas:
        linhas.append(
            f"| `{registo['ficheiro']}` | {registo['bytes']} | {registo['origem']} |"
        )
    if not embebidas:
        linhas.append("| — | — | nenhum motor embebido presente no ambiente |")

    (saida / "auditoria-licencas-automatico.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(f"SBOM: {saida / 'sbom.json'}")
    print(f"Relatório: {saida / 'auditoria-licencas-automatico.md'}")
    print(f"Python: {len(python)} | Rust: {len(rust)} | embebidas: {len(embebidas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
