"""Quality gate de imagem.

As metricas de qualidade sao indicadores, nao veredictos. A variancia do
Laplaciano (`docs/Khnumn.md` §8.3) e sensivel ao conteudo, ao ruido e ao
processamento, e nao decide sozinha se uma imagem e utilizavel. Por isso o
gate produz varios sinais, e a sua conclusao e sempre um conjunto de
avisos com a sua causa, nunca um booleano isolado.

Todas as imagens sao reduzidas antes da analise. O orcamento de memoria do
ambiente de referencia e de 500 MiB, e a qualidade de uma imagem de 63
megapixeis nao cabe nele em precisao plena.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

#: Dimensao maxima da imagem analisada, em pixeis do lado maior.
DIMENSAO_MAXIMA = 1024

#: Distancia de Hamming maxima para considerar duas imagens quase iguais.
LIMIAR_QUASE_DUPLICADO = 6


class ErroQualidade(Exception):
    """Falha na avaliacao de qualidade, com causa legivel."""


def _carregar_reduzida(caminho: Path) -> np.ndarray:
    """Carrega a imagem em tons de cinza, reduzida ao limite de memoria."""
    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("L")
            largura, altura = imagem.size
            escala = min(1.0, DIMENSAO_MAXIMA / max(largura, altura))
            if escala < 1.0:
                novo = (max(1, int(largura * escala)), max(1, int(altura * escala)))
                imagem = imagem.resize(novo, Image.Resampling.BILINEAR)
            return np.asarray(imagem, dtype=np.uint8)
    except (OSError, ValueError) as erro:
        raise ErroQualidade(f"nao foi possivel ler a imagem {caminho}: {erro}") from erro


def _carregar_reduzida_cor(caminho: Path) -> np.ndarray:
    """Carrega a imagem em cor BGR, reduzida ao limite de memoria."""
    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGB")
            largura, altura = imagem.size
            escala = min(1.0, DIMENSAO_MAXIMA / max(largura, altura))
            if escala < 1.0:
                novo = (max(1, int(largura * escala)), max(1, int(altura * escala)))
                imagem = imagem.resize(novo, Image.Resampling.BILINEAR)
            rgb = np.asarray(imagem, dtype=np.uint8)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except (OSError, ValueError) as erro:
        raise ErroQualidade(f"nao foi possivel ler a imagem {caminho}: {erro}") from erro


def nitidez(caminho: Path) -> float:
    """Variancia do Laplaciano: um indicador aproximado de nitidez."""
    cinza = _carregar_reduzida(caminho)
    laplaciano = cv2.Laplacian(cinza, cv2.CV_64F)
    return float(np.var(laplaciano))


def exposicao(caminho: Path) -> dict[str, float]:
    """Fracao de pixeis pretos e brancos, e o brilho medio."""
    cinza = _carregar_reduzida(caminho)
    total = float(cinza.size)
    pretos = float(np.count_nonzero(cinza <= 2)) / total
    brancos = float(np.count_nonzero(cinza >= 253)) / total
    return {
        "fracao_pretos": pretos,
        "fracao_brancos": brancos,
        "brilho_medio": float(np.mean(cinza)) / 255.0,
        "contraste": float(np.std(cinza)) / 255.0,
    }


def saturacao(caminho: Path) -> dict[str, float]:
    """Saturacao media e fracao de pixeis com cor saturada."""
    cor = _carregar_reduzida_cor(caminho)
    hsv = cv2.cvtColor(cor, cv2.COLOR_BGR2HSV)
    canal_s = hsv[:, :, 1]
    return {
        "saturacao_media": float(np.mean(canal_s)) / 255.0,
        "fracao_saturada": float(np.count_nonzero(canal_s >= 250)) / float(canal_s.size),
    }


def ruido(caminho: Path) -> float:
    """Estimativa de ruido pelo desvio absoluto mediano do residuo.

    O residuo e a diferenca entre a imagem e a sua versao suavizada. A
    mediana e usada em vez da media porque a mediana nao e arrastada pelos
    outliers, que num residuo de imagem sao bordas, e nao ruido.
    """
    cinza = _carregar_reduzida(caminho).astype(np.float32)
    suave = cv2.GaussianBlur(cinza, (0, 0), 1.0)
    residuo = cinza - suave
    return float(np.median(np.abs(residuo))) / 255.0


def hash_perceptual(caminho: Path) -> int:
    """Hash perceptual dHash: 64 bits de diferencas de adjacencia.

    Duas imagens quase iguais produzem hashes quase iguais, e o numero de
    bits diferentes mede a distancia entre elas.
    """
    cinza = _carregar_reduzida(caminho)
    pequena = cv2.resize(cinza, (9, 8), interpolation=cv2.INTER_AREA)
    bits = pequena[:, 1:] > pequena[:, :-1]
    valor = 0
    for bit in bits.flatten():
        valor = (valor << 1) | int(bit)
    return valor


def distancia_hamming(a: int, b: int) -> int:
    """Distancia de Hamming entre dois hashes."""
    return bin(a ^ b).count("1")


def avaliar(caminho: Path) -> dict[str, Any]:
    """Avalia uma imagem e devolve metricas, criterios e avisos.

    O resumo que sai daqui nunca e um veredicto de usabilidade. E um
    conjunto de sinais, cada um com a sua razao, e a decisao de usar a
    imagem pertence a quem conhece a cena.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroQualidade(f"ficheiro inexistente: {caminho}")

    metricas: dict[str, float] = {}
    criterios: dict[str, str] = {}
    avisos: list[str] = []

    nitidez_valor = nitidez(caminho)
    metricas["nitidez_variancia_laplaciano"] = nitidez_valor
    if nitidez_valor < 20.0:
        criterios["nitidez"] = "suspeita"
        avisos.append(
            "nitidez baixa: a variancia do Laplaciano esta abaixo de 20, "
            "o que e consistente com desfoque ou movimento, mas tambem com "
            "uma cena sem textura"
        )
    else:
        criterios["nitidez"] = "aceitavel"

    exposicao_valores = exposicao(caminho)
    metricas.update({f"exposicao_{chave}": valor for chave, valor in exposicao_valores.items()})
    if exposicao_valores["fracao_pretos"] > 0.05:
        criterios["exposicao"] = "sombreada"
        avisos.append("mais de 5% dos pixeis estao pretos: a zona de sombras e grande")
    elif exposicao_valores["fracao_brancos"] > 0.05:
        criterios["exposicao"] = "sobre-exposta"
        avisos.append("mais de 5% dos pixeis estao brancos: houve saturacao")
    else:
        criterios["exposicao"] = "aceitavel"

    saturacao_valores = saturacao(caminho)
    metricas.update({f"saturacao_{chave}": valor for chave, valor in saturacao_valores.items()})
    if saturacao_valores["fracao_saturada"] > 0.02:
        criterios["saturacao"] = "saturada"
        avisos.append("mais de 2% dos pixeis tem cor saturada")
    else:
        criterios["saturacao"] = "aceitavel"

    ruido_valor = ruido(caminho)
    metricas["ruido_mediana_absoluta"] = ruido_valor
    if ruido_valor > 0.02:
        criterios["ruido"] = "elevado"
        avisos.append("ruido estimado acima de 0,02: pode afectar a correspondencia de pontos")
    else:
        criterios["ruido"] = "aceitavel"

    with Image.open(caminho) as imagem:
        largura, altura = imagem.size
    metricas["largura"] = float(largura)
    metricas["altura"] = float(altura)
    metricas["megapixeis"] = largura * altura / 1_000_000.0

    resumo = (
        f"imagem de {largura}x{altura}; sinais avaliados: "
        f"{len(criterios)}; avisos: {len(avisos)}"
    )

    return {
        "metrics": metricas,
        "criterios": criterios,
        "avisos": avisos,
        "resumo": resumo,
        "nota": (
            "Nenhuma metrica isolada decide a usabilidade de uma imagem. "
            "Estes sinais sao indicadores, e a sua interpretacao depende da cena."
        ),
    }


def quase_duplicados(caminhos: list[Path]) -> dict[str, Any]:
    """Agrupa imagens quase iguais, por distancia de Hamming.

    A comparacao e quadratico no numero de imagens, e por isso o numero de
    comparacoes e limitado: com o orcamento de memoria e de tempo do
    ambiente de referencia, um conjunto grande e podado e declarado, nao
    truncado em silencio.
    """
    hashes: list[tuple[str, int]] = []
    for caminho in caminhos:
        try:
            hashes.append((str(caminho), hash_perceptual(Path(caminho))))
        except ErroQualidade:
            continue

    grupos: list[dict[str, Any]] = []
    maximo_comparacoes = 20000
    comparacoes = 0
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            if comparacoes >= maximo_comparacoes:
                break
            comparacoes += 1
            distancia = distancia_hamming(hashes[i][1], hashes[j][1])
            if distancia <= LIMIAR_QUASE_DUPLICADO:
                grupos.append(
                    {
                        "a": hashes[i][0],
                        "b": hashes[j][0],
                        "distancia_hamming": distancia,
                    }
                )
    return {
        "grupos": grupos,
        "comparacoes": comparacoes,
        "truncado": comparacoes >= maximo_comparacoes,
    }


__all__ = [
    "ErroQualidade",
    "avaliar",
    "distancia_hamming",
    "exposicao",
    "hash_perceptual",
    "nitidez",
    "quase_duplicados",
    "ruido",
    "saturacao",
]
