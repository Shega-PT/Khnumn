"""Leitura de metadados de imagem: EXIF, XMP e campos ausentes.

Duas regras de `docs/Khnumn.md` governam este modulo.

**Os metadados do fornecedor sao lidos, nao acreditados.** Um valor
declarado pelo fabricante ou pelo receptor e um valor *declarado*: fica
registado com a sua origem e com a marca de nao verificado. A diferenca
entre um valor declarado e um valor verificado e a diferenca entre um
levantamento e uma opiniao.

**A ausencia e um dado.** Um campo que o ficheiro nao traz e registado como
ausente, com a sua ausencia contada. Nunca e substituido por um valor
inventado, e nunca desaparece do registo.

O carimbo temporal do ficheiro nao e tempo de captura (`docs/Khnumn.md`
§5.6): a data que o utilizador atribui a uma pasta pode divergir do tempo
real em horas. Por isso, quando nada mais existe, o instante de captura
fica nulo e a ausencia e declarada, em vez de se chamar "mtime" a tempo de
captura.
"""

from __future__ import annotations

import datetime as _dt
import xml.etree.ElementTree as _ElementTree
from pathlib import Path
from typing import Any

import piexif
from PIL import Image, ExifTags

from . import geo

#: Tipos de media reconhecidos, por extensao.
_TIPOS_MEDIA = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".dng": "image/x-adobe-dng",
    ".nef": "image/x-nikon-nef",
    ".cr2": "image/x-canon-cr2",
    ".arw": "image/x-sony-arw",
    ".raf": "image/x-fujifilm-raf",
    ".pcd": "image/x-phaseone-pcd",
    ".rw2": "image/x-panasonic-rw2",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}

#: Campos cuja ausencia e registada, com o nome do campo no registo.
_CAMPOS_RELEVANTES = (
    "capture_time_utc",
    "position",
    "orientation",
    "exposure_time_s",
    "focal_length_mm",
    "iso",
    "sensor_id",
)

#: Elementos XMP de interesse, por nome local.
_ELEMENTOS_XMP = {
    "AbsoluteAltitude",
    "RelativeAltitude",
    "GPSLatitude",
    "GPSLongitude",
    "GPSAltitude",
    "GpsStatus",
    "FlightTimestamp",
    "CameraSerialNumber",
    "LensModel",
    "Make",
    "Model",
    "AerialOrientation",
    "CameraPitchDegree",
    "CameraYawDegree",
    "CameraRollDegree",
    "GimbalPitchDegree",
    "GimbalYawDegree",
    "GimbalRollDegree",
    "HomeLongitude",
    "HomeLatitude",
    "HomeAltitude",
}


class ErroMetadados(Exception):
    """Falha na leitura de metadados, com causa legivel."""


def extrair(caminho: Path) -> dict[str, Any]:
    """Extrai os metadados de um ficheiro.

    Devolve um dicionario com a forma que o registo de activo espera:
    `media_type`, `width`, `height`, `capture`, `exposure`,
    `campos_ausentes` e `vendor_metadata`.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroMetadados(f"ficheiro inexistente: {caminho}")

    tipo = _tipo_media(caminho)
    largura, altura = _dimensoes(caminho)

    exif = _ler_exif(caminho)
    xmp = _ler_xmp(caminho)

    captura = _construir_captura(exif, xmp)
    exposicao = _construir_exposicao(exif, xmp)

    presentes = {
        "capture_time_utc": captura["capture_time_utc"] is not None,
        "position": captura["position"] is not None,
        "orientation": captura["orientation"] is not None,
        "exposure_time_s": exposicao["exposure_time_s"] is not None,
        "focal_length_mm": exposicao["focal_length_mm"] is not None,
        "iso": exposicao["iso"] is not None,
        "sensor_id": captura["sensor_id"] is not None,
    }
    ausentes = [campo for campo in _CAMPOS_RELEVANTES if not presentes[campo]]
    if largura is None or altura is None:
        ausentes.append("imagem")

    return {
        "media_type": tipo,
        "width": largura,
        "height": altura,
        "capture": captura,
        "exposure": exposicao,
        "campos_ausentes": ausentes,
        "vendor_metadata": {
            "confianca": "declarado_nao_verificado",
            "exif": exif,
            "xmp": xmp,
        },
    }


def _tipo_media(caminho: Path) -> str:
    """Determina o tipo de media pela extensao e pelos bytes magicos."""
    extensao = caminho.suffix.lower()
    tipo = _TIPOS_MEDIA.get(extensao)
    if tipo is not None:
        return tipo
    try:
        with caminho.open("rb") as ficheiro:
            cabecalho = ficheiro.read(16)
    except OSError:
        return "application/octet-stream"
    if cabecalho.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if cabecalho.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if cabecalho[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if cabecalho.startswith(b"RIFF") and cabecalho[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _dimensoes(caminho: Path) -> tuple[int | None, int | None]:
    """Le as dimensoes sem descodificar a imagem inteira.

    Um ficheiro que nao e uma imagem legivel devolve dimensoes nulas, e
    nao um erro: o inventario existe para registar o que ha, e um ficheiro
    nao-imagem registado e mais honesto do que um ficheiro nao-imagem
    falhado em silencio.
    """
    try:
        with Image.open(caminho) as imagem:
            return imagem.width, imagem.height
    except (OSError, ValueError):
        return None, None


def _nome_tag(etiqueta: int, ifd: str) -> str:
    """Devolve o nome legivel de uma etiqueta EXIF.

    As etiquetas do IFD GPS tem numeracao relativa, e por isso tem uma
    tabela propria; as dos outros IFDs aparecem na tabela global.
    """
    if ifd == "GPS":
        return ExifTags.GPSTAGS.get(etiqueta, f"gps_tag_{etiqueta}")
    nome = ExifTags.TAGS.get(etiqueta)
    if isinstance(nome, str):
        return nome
    if isinstance(nome, dict):
        return str(nome.get("name", f"tag_{etiqueta}"))
    return f"tag_{etiqueta}"


def _ler_exif(caminho: Path) -> dict[str, Any]:
    """Le o EXIF com o piexif, que cobre GPS e os IFDs de exposicao."""
    try:
        exif = piexif.load(str(caminho))
    except Exception:
        # Ficheiros sem EXIF, ou com EXIF truncado, nao sao um erro fatal:
        # a ausencia de metadados e um dado, e nao uma falha de leitura.
        return {}

    resultado: dict[str, Any] = {}
    for nome, ifd in (
        ("0th", exif.get("0th", {})),
        ("Exif", exif.get("Exif", {})),
        ("GPS", exif.get("GPS", {})),
    ):
        for etiqueta, valor in ifd.items():
            legivel = _nome_tag(etiqueta, nome)
            resultado[legivel] = _serializavel(valor)
    return resultado


def _serializavel(valor: Any) -> Any:
    """Converte um valor EXIF em algo que se possa serializar em JSON.

    Os bytes que sao texto legivel viram texto; os que sao binarios ficam
    em hexadecimal. Um EXIF legivel e um EXIF que se pode auditar.
    """
    if isinstance(valor, bytes):
        try:
            texto = valor.decode("utf-8")
        except UnicodeDecodeError:
            return valor.hex()
        if all(caractere.isprintable() or caractere in "\r\n\t" for caractere in texto):
            return texto.rstrip("\x00")
        return valor.hex()
    if isinstance(valor, tuple):
        return [_serializavel(item) for item in valor]
    if isinstance(valor, (int, float, str, bool)) or valor is None:
        return valor
    return str(valor)


def _racional(valor: Any) -> float | None:
    """Converte um racional EXIF, que pode ser par, tupla ou numero."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, (tuple, list)) and len(valor) == 2:
        try:
            numerador, denominador = valor
            if denominador == 0:
                return None
            return float(numerador) / float(denominador)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def _ler_xmp(caminho: Path) -> dict[str, Any]:
    """Le o XMP: do lado XMP ou de uma etiqueta embebida na imagem."""
    lado = caminho.with_suffix(caminho.suffix + ".xmp")
    conteudo: bytes | None = None
    if lado.is_file():
        try:
            conteudo = lado.read_bytes()
        except OSError:
            conteudo = None
    if conteudo is None:
        try:
            with Image.open(caminho) as imagem:
                bruto = imagem.info.get("xmp")
                if isinstance(bruto, bytes):
                    conteudo = bruto
        except (OSError, ValueError):
            conteudo = None
    if conteudo is None:
        return {}

    try:
        # defusedxml evita expansao de entidades externas num ficheiro que
        # vem de fora (`docs/Khnumn.md` §20).
        from defusedxml import ElementTree

        raiz = ElementTree.fromstring(conteudo)
    except Exception:
        return {}

    resultado: dict[str, Any] = {}
    for elemento in raiz.iter():
        nome = elemento.tag.split("}")[-1]
        if nome in _ELEMENTOS_XMP and elemento.text and elemento.text.strip():
            resultado[nome] = elemento.text.strip()
    return resultado


def _construir_captura(exif: dict[str, Any], xmp: dict[str, Any]) -> dict[str, Any]:
    """Constroi o bloco de captura.

    A precedencia e: carimbo GNSS, depois EXIF, depois XMP. O carimbo GNSS
    tem resolucao de um segundo e vem do receptor, e por isso e mais fiavel
    do que o relogio da camara; o EXIF e o que o utilizador ou o sistema
    configurou; o XMP e o ultimo recurso.
    """
    instante: str | None = None
    origem = "ausente"
    confianca = "nenhuma"

    gnss = _instante_gnss(exif)
    if gnss is not None:
        instante, origem, confianca = gnss, "gnss_timestamp", "alta"

    if instante is None:
        exif_dt = exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized")
        if exif_dt:
            deslocamento = exif.get("OffsetTimeOriginal") or exif.get("OffsetTime")
            instante, fuso_declarado = _instante_utc_de_exif(str(exif_dt), deslocamento)
            if instante is not None:
                origem = "exif_datetime_original"
                # Sem fuso declarado, o carimbo e uma hora de relogio e nao um
                # instante. A confianca baixa e a suposicao fica registada.
                confianca = "media" if fuso_declarado else "baixa"

    if instante is None and xmp.get("FlightTimestamp"):
        instante, _fuso_declarado = _instante_utc_de_exif(str(xmp["FlightTimestamp"]), None)
        if instante is not None:
            origem, confianca = "exif_datetime_original", "baixa"

    posicao = _construir_posicao(exif, xmp)
    orientacao = _construir_orientacao(exif, xmp)

    return {
        "capture_time_utc": instante,
        "clock_source": origem,
        "clock_confidence": confianca,
        "sensor_id": _sensor_id(exif),
        "position": posicao,
        "orientation": orientacao,
    }


def _instante_gnss(exif: dict[str, Any]) -> str | None:
    """Constroi o instante UTC a partir do carimbo GNSS."""
    data = exif.get("GPSDateStamp")
    hora = exif.get("GPSTimeStamp")
    if not data or not hora:
        return None
    if isinstance(hora, (tuple, list)):
        partes = [_racional(item) for item in hora]
        if any(parte is None for parte in partes):
            return None
        hora = f"{int(partes[0]):02d}:{int(partes[1]):02d}:{int(partes[2]):02d}"
    try:
        data_hora = _dt.datetime.strptime(f"{data} {hora}", "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return data_hora.replace(tzinfo=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _instante_utc_de_exif(valor: str, deslocamento: Any) -> tuple[str | None, bool]:
    """Converte um carimbo EXIF local em instante UTC.

    Devolve tambem se o fuso foi declarado. Sem fuso declarado, o carimbo e
    lido como UTC e a operacao e declarada como tal: um carimbo sem fuso e
    uma hora de relogio, nao um instante, e a diferenca entre os dois e
    precisamente a que produz erros de posicao silenciosos.
    """
    texto = valor.strip().rstrip("\x00")
    for formato in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            data_hora = _dt.datetime.strptime(texto.split(".")[0].split("+")[0], formato)
        except ValueError:
            continue
        fuso = _dt.timezone.utc
        fuso_declarado = False
        if deslocamento:
            try:
                texto_fuso = str(deslocamento).strip().replace(":", "")
                sinal = 1 if texto_fuso[0] != "-" else -1
                horas = int(texto_fuso[1:3])
                minutos = int(texto_fuso[3:5])
                fuso = _dt.timezone(sinal * _dt.timedelta(hours=horas, minutes=minutos))
                fuso_declarado = True
            except (ValueError, IndexError):
                fuso = _dt.timezone.utc
        instante = (
            data_hora.replace(tzinfo=fuso)
            .astimezone(_dt.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        return instante, fuso_declarado
    return None, False


def _construir_posicao(exif: dict[str, Any], xmp: dict[str, Any]) -> dict[str, Any] | None:
    """Constroi a posicao a partir do GPS ou do XMP."""
    latitude = _graus_decimais(exif.get("GPSLatitude"))
    longitude = _graus_decimais(exif.get("GPSLongitude"))

    # A referencia carrega o sinal: o DMS e sempre em valor absoluto.
    if latitude is not None and str(exif.get("GPSLatitudeRef", "N")).upper() in ("S",):
        latitude = -latitude
    if longitude is not None and str(exif.get("GPSLongitudeRef", "E")).upper() in ("W",):
        longitude = -longitude

    if latitude is None and xmp.get("GPSLatitude") and xmp.get("GPSLongitude"):
        try:
            latitude = float(xmp["GPSLatitude"])
            longitude = float(xmp["GPSLongitude"])
        except (TypeError, ValueError):
            latitude = longitude = None

    if latitude is None or longitude is None:
        return None

    altitude = None
    datum_vertical = None
    referencia = exif.get("GPSAltitudeRef")
    if exif.get("GPSAltitude") is not None:
        altitude = _racional(exif["GPSAltitude"])
        if referencia in (1, b"\x01"):
            datum_vertical = "geoidico_nao_declarado"
        else:
            datum_vertical = "elipsoidal_wgs84"

    return {
        "crs": "EPSG:4979",
        "coordinates": [float(longitude), float(latitude), altitude if altitude is not None else 0.0],
        "units": {"horizontal": "deg", "vertical": "m"},
        # O DOP do receptor e um factor de diluicao, nao uma incerteza. Declarar
        # uma incerteza a partir dele seria inventar a que nao existe, e por
        # isso a incerteza fica nula e a ausencia declarada em `vendor_metadata`.
        "uncertainty_horizontal": None,
        "uncertainty_vertical": None,
        "source": "GNSS_EXIF",
        "vertical_datum": datum_vertical,
    }


def _graus_decimais(valor: Any) -> float | None:
    """Converte o DMS racional do EXIF em graus decimais."""
    if valor is None:
        return None
    if isinstance(valor, (tuple, list)) and len(valor) == 3:
        componentes = [_racional(item) for item in valor]
        if any(componente is None for componente in componentes):
            return None
        graus, minutos, segundos = componentes
        return float(graus) + float(minutos) / 60.0 + float(segundos) / 3600.0
    return _racional(valor)


def _construir_orientacao(exif: dict[str, Any], xmp: dict[str, Any]) -> dict[str, Any] | None:
    """Constroi a orientacao, quando algum sinal existe.

    A orientacao e o campo que mais vezes se presume. Um valor declarado
    pelo fabricante ou pelo sistema de voo e registado como declarado e nao
    verificado, porque nao ha referencia com que verificar.
    """
    angulo = exif.get("Orientation")
    if angulo is not None:
        return {"source": "exif_orientation", "status": "declared"}
    for chave in ("CameraYawDegree", "GimbalYawDegree"):
        if xmp.get(chave) is not None:
            return {"source": f"xmp:{chave}", "status": "declared"}
    return None


def _sensor_id(exif: dict[str, Any]) -> str | None:
    """Constroi um identificador de sensor a partir do numero de serie."""
    serie = exif.get("BodySerialNumber") or exif.get("SerialNumber")
    if serie:
        return str(serie)
    marca = exif.get("Make")
    modelo = exif.get("Model")
    if marca and modelo:
        return f"{marca} {modelo}".strip()
    return None


def _construir_exposicao(exif: dict[str, Any], xmp: dict[str, Any]) -> dict[str, Any]:
    """Constroi o bloco de exposicao."""
    tempo = _racional(exif.get("ExposureTime"))
    abertura = _racional(exif.get("FNumber"))
    iso = exif.get("ISOSpeedRatings") or exif.get("ISO")
    if isinstance(iso, (list, tuple)):
        iso = iso[0] if iso else None
    if iso is not None:
        try:
            iso = int(iso)
        except (TypeError, ValueError):
            iso = None
    focal = _racional(exif.get("FocalLength"))

    return {
        "shutter_speed_s": tempo,
        "aperture": abertura,
        "iso": iso,
        "focal_length_mm": focal,
        "exposure_time_s": tempo,
    }


__all__ = ["ErroMetadados", "extrair", "geo"]
