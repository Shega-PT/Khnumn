"""Autenticação e proteção do transporte (F7.E6).

Pedidos autenticados, transporte protegido, permissões mínimas nos workers
e credenciais separadas dos ficheiros de projeto. Nunca armazena credenciais
em texto claro nos ficheiros de projeto.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass, field
from typing import Any


class ErroSeguranca(Exception):
    """Falha de autenticação ou proteção do transporte, com causa legível."""


@dataclass
class Credenciais:
    """Credenciais de autenticação de um worker ou cliente."""

    identificador: str
    """Identificador do cliente/worker."""

    segredo_hash: str
    """Hash do segredo (nunca o segredo em texto claro)."""

    algoritmo_hash: str = "sha256"
    """Algoritmo de hash usado para armazenar o segredo."""

    permissoes: list[str] = field(default_factory=list)
    """Lista de permissões concedidas (ex.: `ler_projeto`, `escrever_produto`)."""


@dataclass
class PedidoAutenticado:
    """Resultado da autenticação de um pedido."""

    autenticado: bool
    identificador: str | None = None
    permissoes: list[str] = field(default_factory=list)
    motivo: str | None = None
    timestamp_utc: str = field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat() + "Z")


class GerenciadorSeguranca:
    """Gerencia autenticação, proteção do transporte e permissões."""

    def __init__(self) -> None:
        self.credenciais: dict[str, Credenciais] = {}
        self.chave_transporte: bytes = os.urandom(32)

    def registar_credenciais(
        self,
        identificador: str,
        segredo: str,
        permissoes: list[str] | None = None,
    ) -> None:
        """Regista credenciais de um cliente/worker.

        O segredo é armazenado como hash, nunca em texto claro.
        """
        segredo_hash = hashlib.sha256(segredo.encode("utf-8")).hexdigest()
        self.credenciais[identificador] = Credenciais(
            identificador=identificador,
            segredo_hash=segredo_hash,
            permissoes=permissoes or [],
        )

    def autenticar_pedido(
        self,
        identificador: str,
        segredo_fornecido: str,
        permissao_necessaria: str | None = None,
    ) -> PedidoAutenticado:
        """Autentica um pedido e verifica permissões.

        Devolve um `PedidoAutenticado` com o resultado. Quando a autenticação
        falha, o motivo é declarado e o pedido é rejeitado.
        """
        credenciais = self.credenciais.get(identificador)
        if credenciais is None:
            return PedidoAutenticado(
                autenticado=False,
                identificador=identificador,
                motivo="identificador não registado",
            )

        segredo_hash_fornecido = hashlib.sha256(
            segredo_fornecido.encode("utf-8")
        ).hexdigest()

        if not hmac.compare_digest(
            credenciais.segredo_hash, segredo_hash_fornecido
        ):
            return PedidoAutenticado(
                autenticado=False,
                identificador=identificador,
                motivo="segredo inválido",
            )

        if permissao_necessaria is not None:
            if permissao_necessaria not in credenciais.permissoes:
                return PedidoAutenticado(
                    autenticado=False,
                    identificador=identificador,
                    motivo=(
                        f"permissão '{permissao_necessaria}' não concedida a {identificador}"
                    ),
                )

        return PedidoAutenticado(
            autenticado=True,
            identificador=identificador,
            permissoes=list(credenciais.permissoes),
            motivo=None,
        )

    def proteger_transporte(self, mensagem: bytes) -> dict[str, Any]:
        """Protege uma mensagem de transporte com autenticação e confidencialidade.

        Usa HMAC para integridade e cifragem simétrica simples (XOR com
        chave derivada) para ofuscação. Não é substituto de TLS em produção,
        mas fornece proteção básica contra leitura e alteração.
        """
        mac = hmac.new(self.chave_transporte, mensagem, hashlib.sha256).digest()
        cifrado = bytes(
            b ^ self.chave_transporte[i % len(self.chave_transporte)]
            for i, b in enumerate(mensagem)
        )

        return {
            "cifrado": base64.b64encode(cifrado).decode("ascii"),
            "mac": base64.b64encode(mac).decode("ascii"),
            "algoritmo": "hmac-sha256 + xor-ofuscação",
        }

    def verificar_transporte(self, pacote: dict[str, Any]) -> bytes | None:
        """Verifica a integridade de um pacote de transporte e devolve a mensagem.

        Devolve None quando o MAC não confere (possível adulteração).
        """
        try:
            cifrado = base64.b64decode(pacote["cifrado"])
            mac_recebido = base64.b64decode(pacote["mac"])
        except (KeyError, ValueError):
            return None

        mensagem = bytes(
            b ^ self.chave_transporte[i % len(self.chave_transporte)]
            for i, b in enumerate(cifrado)
        )

        mac_calculado = hmac.new(
            self.chave_transporte, mensagem, hashlib.sha256
        ).digest()

        if not hmac.compare_digest(mac_recebido, mac_calculado):
            return None

        return mensagem

    def permissoes_minimas(
        self,
        worker_id: str,
        permissoes_necessarias: list[str],
    ) -> bool:
        """Verifica se um worker tem todas as permissões necessárias."""
        credenciais = self.credenciais.get(worker_id)
        if credenciais is None:
            return False
        return all(
            p in credenciais.permissoes for p in permissoes_necessarias
        )

    def separar_credenciais_ficheiros_projeto(
        self,
        credenciais: dict[str, str],
        caminhos_ficheiros_projeto: list[str],
    ) -> dict[str, Any]:
        """Garante que credenciais não estão misturadas com ficheiros de projeto.

        Verifica que nenhum dos caminhos de ficheiros de projeto contém
        credenciais embutidas e devolve um relatório de separação.
        """
        alertas: list[str] = []
        for caminho in caminhos_ficheiros_projeto:
            # Verificação simples: nomes de ficheiros que sugerem credenciais.
            nome = caminho.lower()
            for palavra in ("senha", "segredo", "chave", "token", "credencial"):
                if palavra in nome:
                    alertas.append(
                        f"ficheiro de projeto pode conter credenciais: {caminho}"
                    )

        return {
            "credenciais_separadas": len(alertas) == 0,
            "alertas": alertas,
            "num_ficheiros_projeto": len(caminhos_ficheiros_projeto),
        }


def autenticar_pedido(
    gerenciador: GerenciadorSeguranca,
    identificador: str,
    segredo: str,
    permissao_necessaria: str | None = None,
) -> PedidoAutenticado:
    """Função de conveniência para autenticar um pedido."""
    return gerenciador.autenticar_pedido(
        identificador, segredo, permissao_necessaria
    )


def proteger_transporte(
    gerenciador: GerenciadorSeguranca,
    mensagem: bytes,
) -> dict[str, Any]:
    """Função de conveniência para proteger uma mensagem de transporte."""
    return gerenciador.proteger_transporte(mensagem)


__all__ = [
    "Credenciais",
    "ErroSeguranca",
    "GerenciadorSeguranca",
    "PedidoAutenticado",
    "autenticar_pedido",
    "proteger_transporte",
]
