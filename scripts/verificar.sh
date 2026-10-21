#!/usr/bin/env bash
# Verificação completa do Khnumn.
#
# Executa, por ordem:
#   1. a formatação e a análise estática do Rust;
#   2. os testes unitários do Rust;
#   3. os testes da camada científica Python;
#   4. a auditoria de licenças, por build;
#   5. uma execução de fumo da CLI, de ponta a ponta.
#
# A execução de fumo cria um projecto temporário, ingere as fixtures e
# verifica que o inventário, a validação e o relatório de lacunas
# funcionam. É a prova de que as peças encaixam, e não de que são
# correctas: isso são os testes.
#
# Uso: scripts/verificar.sh [--rapido]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

VENV="$RAIZ/.venv"
PYTHON="$VENV/bin/python"
RAPIDO=0
[[ "${1:-}" == "--rapido" ]] && RAPIDO=1

echao() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
falhou() { printf '\n\033[31mFALHOU: %s\033[0m\n' "$1"; exit 1; }

echao "Ambiente"
"$PYTHON" --version || falhou "python da venv indisponivel"
cargo --version || falhou "cargo indisponivel"
[[ -f requirements.lock ]] || falhou "requirements.lock ausente"

echao "Formato e análise estática do Rust"
cargo fmt --all -- --check || falhou "cargo fmt"
cargo clippy --workspace --all-targets -- -D warnings || falhou "cargo clippy"

echao "Testes do Rust"
cargo test --workspace --quiet || falhou "cargo test"

echao "Testes da camada científica"
"$PYTHON" -m pytest testes/ -q || falhou "pytest"

if [[ $RAPIDO -eq 0 ]]; then
  echao "Auditoria de licenças (por build)"
  "$PYTHON" scripts/auditar-licencas.py --offline >/dev/null || falhou "auditoria de licenças"
  "$PYTHON" - <<'PY' || falhou "a auditoria encontrou copyleft forte"
import json, sys
from pathlib import Path
sbom = json.loads(Path("processos/sbom.json").read_text(encoding="utf-8"))
forte = [
    item for item in sbom["python"] + sbom["rust"]
    if item.get("classificacao") == "copyleft forte"
]
if forte:
    for item in forte:
        print(f"  copyleft forte: {item['nome']} {item.get('versao','')} {item.get('licenca')}")
    sys.exit(1)
print(f"  núcleo livre de copyleft forte ({len(sbom['python'])} python, {len(sbom['rust'])} rust)")
PY

  echao "Execução de fumo da CLI"
  PROJ="$(mktemp -d)"
  trap 'rm -rf "$PROJ"' EXIT
  cargo run --quiet --bin khnumn -- --project "$PROJ" init fumo >/dev/null || falhou "khnumn init"
  cargo run --quiet --bin khnumn -- --project "$PROJ" ingest testes/fixtures/imagens >/dev/null || falhou "khnumn ingest"
  cargo run --quiet --bin khnumn -- --project "$PROJ" validate >/dev/null || falhou "khnumn validate"
  cargo run --quiet --bin khnumn -- --project "$PROJ" report >/dev/null || falhou "khnumn report"
  cargo run --quiet --bin khnumn -- --project "$PROJ" run >/dev/null || falhou "khnumn run"
  echo "  fumo concluído"
fi

printf '\n\033[32mVerificação concluída.\033[0m\n'
