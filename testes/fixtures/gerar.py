"""Gerador de imagens de teste, com EXIF e GPS.

As fixtures sao sinteticas e tem tamanho pequeno, porque o orcamento de
memoria do ambiente de referencia e de 500 MiB e as imagens de teste nao
precisam de ser grandes para exercitar o codigo. O que o codigo tem de
enfrentar e a variety: com GPS, sem GPS, com EXIF incompleto, duplicadas
e quase duplicadas.

O uso e: `python testes/fixtures/gerar.py <directorio>`
"""

from __future__ import annotations

import datetime as _dt
import random
import sys
from pathlib import Path

import numpy as np
import piexif
from PIL import Image


def _padrao(largura: int, altura: int, semente: int) -> Image.Image:
    """Gera um padrao sintetico com textura, para a nitidez nao ser nula."""
    aleatorio = np.random.default_rng(semente)
    ruido = aleatorio.integers(0, 255, size=(altura, largura, 3), dtype=np.uint8)
    # Uma gradiente evita que a textura seja uniformemente aleatoria, que
    # daria uma nitidez enganadora.
    gradiente = np.linspace(0, 255, largura, dtype=np.uint8)
    ruido[:, :, 0] = (ruido[:, :, 0].astype(np.int16) + gradiente) % 256
    return Image.fromarray(ruido, mode="RGB")


def _graus_decimais(valor: float) -> tuple[int, int, int]:
    """Converte graus decimais para o DMS racional do EXIF.

    O DMS e sempre em valor absoluto: e a referencia (`N`, `S`, `E`, `W`) que
    carrega o sinal, e um numerador negativo nao e representavel no EXIF.
    """
    absoluto = abs(valor)
    graus = int(absoluto)
    resto = (absoluto - graus) * 60
    minutos = int(resto)
    segundos = round((resto - minutos) * 60, 6)
    return (
        (graus, 1),
        (minutos, 1),
        (int(segundos * 10000), 10000),
    )


def escrever(caminho: Path, imagem: Image.Image, exif: dict | None) -> None:
    """Escreve uma imagem JPEG com o EXIF indicado."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(caminho, "JPEG", quality=88)
    if exif is None:
        return
    dados = caminho.read_bytes()
    piexif.insert(piexif.dump(exif), dados, str(caminho))


def exif_com_gps(data: _dt.datetime, latitude: float, longitude: float) -> dict:
    """Constroi um EXIF completo, com GPS e data de captura."""
    zero = {}
    principal = {
        piexif.ImageIFD.Make: b"Khnumn",
        piexif.ImageIFD.Model: b"Fixture",
        piexif.ImageIFD.Software: b"khnumn-fixtures",
        piexif.ImageIFD.Orientation: 1,
        piexif.ImageIFD.DateTime: data.strftime("%Y:%m:%d %H:%M:%S").encode(),
    }
    exposicao = {
        piexif.ExifIFD.DateTimeOriginal: data.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.OffsetTimeOriginal: b"+01:00",
        piexif.ExifIFD.ExposureTime: (1, 500),
        piexif.ExifIFD.FNumber: (28, 10),
        piexif.ExifIFD.ISOSpeedRatings: 100,
        piexif.ExifIFD.FocalLength: (240, 10),
        piexif.ExifIFD.BodySerialNumber: b"FNX-0001",
    }
    gps = {
        piexif.GPSIFD.GPSVersionID: b"\x02\x03\x00\x00",
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: _graus_decimais(latitude),
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLongitude: _graus_decimais(longitude),
        piexif.GPSIFD.GPSAltitude: (int(120.5 * 100), 100),
        piexif.GPSIFD.GPSAltitudeRef: 0,
        piexif.GPSIFD.GPSDateStamp: data.strftime("%Y:%m:%d").encode(),
        piexif.GPSIFD.GPSTimeStamp: ((data.hour, 1), (data.minute, 1), (int(data.second), 1)),
        piexif.GPSIFD.GPSHPositioningError: (150, 100),
    }
    return {"0th": principal, "Exif": exposicao, "GPS": gps, "1st": zero, "thumbnail": None}


def exif_sem_gps(data: _dt.datetime) -> dict:
    """Constroi um EXIF sem posicao, para exercitar a ausencia de campos."""
    principal = {
        piexif.ImageIFD.Make: b"Khnumn",
        piexif.ImageIFD.Model: b"FixtureSemGPS",
        piexif.ImageIFD.DateTime: data.strftime("%Y:%m:%d %H:%M:%S").encode(),
    }
    exposicao = {
        piexif.ExifIFD.DateTimeOriginal: data.strftime("%Y:%m:%d %H:%M:%S").encode(),
        piexif.ExifIFD.ExposureTime: (1, 250),
    }
    zero = {}
    return {"0th": principal, "Exif": exposicao, "GPS": zero, "1st": zero, "thumbnail": None}


def gerar(directorio: Path) -> None:
    """Gera o conjunto de fixtures."""
    base = _dt.datetime(2026, 5, 12, 10, 24, 31)
    aleatorio = random.Random(7)

    for indice in range(4):
        imagem = _padrao(640, 480, semente=indice)
        escrever(
            directorio / f"com_gps_{indice:02d}.jpg",
            imagem,
            exif_com_gps(
                base + _dt.timedelta(seconds=indice * 7),
                43.2100 + indice * 0.0001,
                -1.2345 - indice * 0.0001,
            ),
        )

    for indice in range(2):
        imagem = _padrao(640, 480, semente=100 + indice)
        escrever(
            directorio / f"sem_gps_{indice:02d}.jpg",
            imagem,
            exif_sem_gps(base + _dt.timedelta(minutes=indice)),
        )

    # Uma copia exacta: o inventario tem de a reconhecer pelo hash.
    escrever(
        directorio / "duplicado_exacto.jpg",
        _padrao(640, 480, semente=0),
        exif_com_gps(base, 43.2100, -1.2345),
    )

    # Quase duplicado: a mesma cena, com uma alteracao pequena.
    imagem = _padrao(640, 480, semente=0)
    escrever(
        directorio / "quase_duplicado.jpg",
        imagem,
        exif_com_gps(base + _dt.timedelta(seconds=1), 43.2100, -1.2345),
    )

    # Um ficheiro que nao e imagem, para o inventario o registar sem o
    # inventar.
    (directorio / "notas.txt").write_text(
        "ficheiro de texto, para verificar que o inventario nao falha\n",
        encoding="utf-8",
    )

    print(f"fixtures geradas em {directorio} ({aleatorio.randint(0, 0) + 9} ficheiros)")


if __name__ == "__main__":
    alvo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("testes/fixtures/imagens")
    gerar(alvo)
