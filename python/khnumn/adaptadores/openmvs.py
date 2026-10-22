"""Adaptador do motor de MVS externo (OpenMVS).

O motor é executado como processo separado, conforme a fronteira de licença
de `docs/Khnumn.md` §18.3. O aviso de licença é emitido no primeiro uso.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import json


class ErroOpenMVS(Exception):
    """Falha no adaptador OpenMVS, com causa legível."""


class AdaptadorOpenMVS:
    def __init__(self, binario: str = "DensifyPointCloud") -> None:
        self.binario = binario
        self._aviso_emitido = False

    def instalado(self) -> bool:
        return shutil.which(self.binario) is not None

    def aviso_licenca(self) -> str:
        if self._aviso_emitido:
            return ""
        self._aviso_emitido = True
        return (
            "OpenMVS é AGPL-3.0 e é executado como processo separado; "
            "a sua licença não se aplica ao núcleo do Khnumn."
        )

    def executar(self, argumentos: list[str], entrada: str = "") -> dict[str, Any]:
        if not self.instalado():
            raise ErroOpenMVS(f"motor não instalado: {self.binario}")
        aviso = self.aviso_licenca()
        try:
            resultado = subprocess.run(
                [self.binario, *argumentos],
                input=entrada,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as erro:
            raise ErroOpenMVS(f"falha ao invocar {self.binario}: {erro}") from erro
        return {
            "codigo_saida": resultado.returncode,
            "stdout": resultado.stdout,
            "stderr": resultado.stderr,
            "aviso_licenca": aviso,
        }
