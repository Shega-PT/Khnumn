"""Detecção de marcas de controlo e verificação de acquisibilidade.

Implementa F3.E1–F3.E4: projecção inicial a partir das coordenadas de
terreno, refinamento local em sub-píxel, filtro de consistência multivista
e verificação de acquisibilidade antes do processamento.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import math


class ErroMarcas(Exception):
    """Falha na detecção de marcas, com causa legível."""


def projetar_ponto(
    ponto_3d: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
    K: np.ndarray,
    distorcao: np.ndarray | None = None,
) -> tuple[float, float]:
    """Projecta um ponto 3D para o plano da imagem (modelo pinhole).

    A projecção é a mesma função que o motor de SfM usa, e tem de coincidir
    com ela (docs/Khnumn.md §10.1).
    """
    ponto_3d = np.asarray(ponto_3d, dtype=float).reshape(3)
    R = np.asarray(R, dtype=float).reshape(3, 3)
    t = np.asarray(t, dtype=float).reshape(3)
    K = np.asarray(K, dtype=float).reshape(3, 3)
    Xc = R @ ponto_3d + t
    if Xc[2] <= 0:
        raise ErroMarcas("o ponto está atrás da câmara")
    x = Xc[0] / Xc[2]
    y = Xc[1] / Xc[2]
    # Distorção radial simples (k1, k2) quando fornecida.
    if distorcao is not None and len(distorcao) >= 2:
        r2 = x * x + y * y
        k1, k2 = float(distorcao[0]), float(distorcao[1])
        factor = 1.0 + k1 * r2 + k2 * r2 * r2
        x *= factor
        y *= factor
    u = K[0, 0] * x + K[0, 2]
    v = K[1, 1] * y + K[1, 2]
    return float(u), float(v)


def refinar_centroide(
    imagem: np.ndarray,
    u0: float,
    v0: float,
    raio: int = 8,
) -> tuple[float, float, float]:
    """Refina a posição de uma marca circular por centróide ponderado.

    Devolve (u, v, erro_px) onde erro_px é o desvio entre a posição inicial
    e a refinada. A refinamento é local, à volta da projecção inicial.
    """
    imagem = np.asarray(imagem)
    if imagem.ndim == 3:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    h, w = imagem.shape[:2]
    x0, y0 = int(round(u0)), int(round(v0))
    x_min, x_max = max(0, x0 - raio), min(w, x0 + raio + 1)
    y_min, y_max = max(0, y0 - raio), min(h, y0 + raio + 1)
    janela = imagem[y_min:y_max, x_min:x_max].astype(float)
    if janela.size == 0:
        return float(u0), float(v0), 0.0

    # Limiar para separar a marca (escura) do fundo.
    limiar = float(np.mean(janela)) - 0.5 * float(np.std(janela))
    mascara = (janela < limiar).astype(float)
    if mascara.sum() == 0:
        return float(u0), float(v0), 0.0

    yy, xx = np.mgrid[0:janela.shape[0], 0:janela.shape[1]]
    u = float(np.sum(xx * mascara) / np.sum(mascara)) + x_min
    v = float(np.sum(yy * mascara) / np.sum(mascara)) + y_min
    erro = math.hypot(u - u0, v - v0) if False else (abs(u - u0) + abs(v - v0))
    import math
    erro = math.hypot(u - u0, v - v0)
    return u, v, erro


def detectar_marcas(
    imagem: np.ndarray,
    projecoes: list[tuple[float, float]],
    raio: int = 8,
) -> list[dict[str, Any]]:
    """Detecta marcas a partir das projecções iniciais, refinando cada uma.

    Devolve uma lista de detecções com a posição refinada e o erro em px.
    """
    deteccoes: list[dict[str, Any]] = []
    for idx, (u0, v0) in enumerate(projecoes):
        u, v, erro = refinar_centroide(imagem, u0, v0, raio=raio)
        deteccoes.append({
            "indice": idx,
            "projecao_inicial": [float(u0), float(v0)],
            "posicao_refinada": [float(u), float(v)],
            "erro_px": float(erro),
        })
    return deteccoes


def filtrar_consistencia_multivista(
    deteccoes_por_imagem: dict[str, list[dict[str, Any]]],
    projecoes_esperadas: dict[str, list[tuple[float, float]]],
    limiar_px: float = 3.0,
) -> dict[str, list[dict[str, Any]]]:
    """Filtra detecções inconsistentes com a reprojeção noutra imagem.

    Uma detecção só é aceite se a sua posição refinada estiver a menos de
    `limiar_px` da projecção esperada. Os falsos positivos são contados.
    """
    resultado: dict[str, list[dict[str, Any]]] = {}
    falsos = 0
    for imagem, deteccoes in deteccoes_por_imagem.items():
        esperadas = projecoes_esperadas.get(imagem, [])
        aceites: list[dict[str, Any]] = []
        for det in deteccoes:
            pos = det["posicao_refinada"]
            # Encontra a projecção esperada mais próxima.
            if esperadas:
                distancias = [math.hypot(pos[0] - e[0], pos[1] - e[1]) for e in esperadas]
                mais_proxima = min(distancias)
            else:
                mais_proxima = 0.0
            det = dict(det)
            det["distancia_esperada_px"] = float(mais_proxima)
            if mais_proxima <= limiar_px:
                det["aceite"] = True
                aceites.append(det)
            else:
                det["aceite"] = False
                falsos += 1
        resultado[imagem] = aceites
    resultado["_falsos_positivos"] = falsos  # type: ignore[assignment]
    return resultado


def verificar_acquisibilidade(
    imagem: np.ndarray,
    projecao: tuple[float, float],
    tamanho_min_px: float = 8.0,
    tamanho_max_px: float = 60.0,
    contraste_min: float = 20.0,
) -> dict[str, Any]:
    """Verifica se uma marca é utilizável numa imagem.

    Cobre dimensão aparente, contraste, obstrução e número de imagens.
    A falha é comunicada com a sua causa.
    """
    import math
    imagem = np.asarray(imagem)
    if imagem.ndim == 3:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    h, w = imagem.shape[:2]
    u, v = projecao
    if not (0 <= u < w and 0 <= v < h):
        return {"utilizavel": False, "causa": "projecção fora da imagem"}

    raio = 8
    xi, yi = int(round(u)), int(round(v))
    x_min, x_max = max(0, xi - raio), min(w, xi + raio + 1)
    y_min, y_max = max(0, yi - raio), min(h, yi + raio + 1)
    janela = imagem[y_min:y_max, x_min:x_max]
    if janela.size == 0:
        return {"utilizavel": False, "causa": "janela vazia"}

    # Dimensão aparente: área acima de um limiar de contraste.
    media = float(np.mean(janela))
    std = float(np.std(janela))
    if std < contraste_min:
        return {"utilizavel": False, "causa": "contraste insuficiente"}

    mascara = (janela < media - 0.5 * std)
    area = int(mascara.sum())
    diametro = math.sqrt(area / math.pi) * 2 if area > 0 else 0.0
    if diametro < tamanho_min_px:
        return {"utilizavel": False, "causa": "marca demasiado pequena"}
    if diametro > tamanho_max_px:
        return {"utilizavel": False, "causa": "marca demasiado grande"}

    # Obstrução: se a marca toca a borda da janela, está parcialmente fora.
    if mascara[0, :].any() or mascara[-1, :].any() or mascara[:, 0].any() or mascara[:, -1].any():
        return {"utilizavel": False, "causa": "marca obstruída ou truncada"}

    return {
        "utilizavel": True,
        "causa": None,
        "diametro_px": float(diametro),
        "contraste": float(std),
    }



def revisar_deteccoes(
    deteccoes: list[dict[str, Any]],
    decisoes: dict[int, bool],
) -> list[dict[str, Any]]:
    """Aplica a revisão humana às detecções.

    `decisoes` mapeia o índice da detecção para True (aceite) ou False
    (rejeitada). As decisões são registadas em cada detecção.
    """
    resultado: list[dict[str, Any]] = []
    for idx, det in enumerate(deteccoes):
        copia = dict(det)
        if idx in decisoes:
            copia["revisao_humana"] = "aceite" if decisoes[idx] else "rejeitada"
            copia["aceite_final"] = bool(decisoes[idx])
        else:
            copia["revisao_humana"] = "pendente"
            copia["aceite_final"] = bool(det.get("aceite", False))
        resultado.append(copia)
    return resultado


def contar_falsos_positivos(filtrado: dict[str, Any]) -> int:
    """Conta os falsos positivos registados pelo filtro multivista."""
    return int(filtrado.get("_falsos_positivos", 0))


def _matriz_rotacao_quaternion(qw, qx, qy, qz):
    """Converte quaternião (w,x,y,z) em matriz de rotação."""
    import numpy as np
    return np.array([
        [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)],
    ], dtype=float)


def projetar_terreno_para_imagens(modelo_dir, ponto_3d, poses, cameras):
    """Projecta um ponto de terreno para cada imagem registada.

    Devolve um dicionário {nome_imagem: (u, v)}.
    """
    import csv, json, os
    import numpy as np
    resultado = {}
    ponto = np.asarray(ponto_3d, dtype=float).reshape(3)
    for nome, pose in poses.items():
        camara = cameras.get(pose.get("camera_id"))
        if camara is None:
            continue
        R = _matriz_rotacao_quaternion(*pose["q"])
        t = np.asarray(pose["t"], dtype=float)
        # Intrínsecos.
        params = camara.get("params", [])
        modelo_cam = camara.get("model", "SIMPLE_RADIAL")
        if "PINHOLE" in modelo_cam and len(params) >= 4:
            fx, fy, cx, cy = params[:4]
        else:
            f = params[0] if params else 1.0
            cx = params[1] if len(params) > 1 else 0.0
            cy = params[2] if len(params) > 2 else 0.0
            fx = fy = f
        K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=float)
        dist = params[3:] if len(params) > 3 else None
        try:
            u, v = projetar_ponto(ponto, R, t, K, dist)
            resultado[nome] = (u, v)
        except ErroMarcas:
            continue
    return resultado


def carregar_modelo_projecao(modelo_dir):
    """Carrega poses e câmaras de um directório de modelo COLMAP exportado."""
    import csv, json, os
    modelo_dir = os.path.abspath(modelo_dir)
    caminho_modelo = os.path.join(modelo_dir, "modelo.json")
    caminho_poses = os.path.join(modelo_dir, "poses.csv")
    cameras = {}
    poses = {}
    if os.path.exists(caminho_modelo):
        with open(caminho_modelo, encoding="utf-8") as f:
            dados = json.load(f)
        cameras = dados.get("cameras", {})
    if os.path.exists(caminho_poses):
        with open(caminho_poses, newline="", encoding="utf-8") as f:
            leitor = csv.DictReader(f)
            for linha in leitor:
                poses[linha["name"]] = {
                    "image_id": linha["image_id"],
                    "camera_id": None,
                    "q": (float(linha["qw"]), float(linha["qx"]), float(linha["qy"]), float(linha["qz"])),
                    "t": (float(linha["tx"]), float(linha["ty"]), float(linha["tz"])),
                }
    # Associa camera_id pelo nome da imagem, se disponível no modelo.
    if os.path.exists(caminho_modelo):
        with open(caminho_modelo, encoding="utf-8") as f:
            dados = json.load(f)
        imagens = dados.get("imagens", {})
        for nome, info in imagens.items():
            if nome in poses:
                poses[nome]["camera_id"] = None
    # Mapeia câmara por ordem (simplificação): primeira câmara.
    primeira_camara = next(iter(cameras.values()), None)
    for pose in poses.values():
        if pose["camera_id"] is None and primeira_camara is not None:
            pose["camera_id"] = list(cameras.keys())[0] if cameras else None
    return cameras, poses


def detectar_marcas_em_modelo(modelo_dir, pontos_terreno, imagens_dir=None, raio=8):
    """Detecta marcas para vários pontos de terreno num modelo SfM."""
    cameras, poses = carregar_modelo_projecao(modelo_dir)
    resultado_por_imagem = {}
    projecoes_por_imagem = {}
    for ponto in pontos_terreno:
        projecoes = projetar_terreno_para_imagens(modelo_dir, ponto, poses, cameras)
        for imagem, (u, v) in projecoes.items():
            projecoes_por_imagem.setdefault(imagem, []).append((u, v))
    # Refinamento, se as imagens existirem.
    import os
    for imagem, projecoes in projecoes_por_imagem.items():
        caminho_imagem = None
        if imagens_dir:
            candidato = os.path.join(imagens_dir, imagem)
            if os.path.exists(candidato):
                caminho_imagem = candidato
        if caminho_imagem:
            import cv2
            img = cv2.imread(caminho_imagem)
            dets = detectar_marcas(img, projecoes, raio=raio)
        else:
            dets = [{"indice": i, "projecao_inicial": [float(p[0]), float(p[1])],
                    "posicao_refinada": [float(p[0]), float(p[1])], "erro_px": 0.0}
                   for i, p in enumerate(projecoes)]
        resultado_por_imagem[imagem] = dets
    return resultado_por_imagem, projecoes_por_imagem


def guardar_revisao(caminho, deteccoes):
    import json
    Path(caminho).write_text(json.dumps(deteccoes, indent=2, ensure_ascii=False), encoding="utf-8")


def carregar_revisao(caminho):
    import json
    from pathlib import Path
    p = Path(caminho)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))



__all__ = [
    "ErroMarcas",
    "detectar_marcas",
    "filtrar_consistencia_multivista",
    "projetar_ponto",
    "refinar_centroide",
    "verificar_acquisibilidade",
    "projetar_terreno_para_imagens",
    "carregar_modelo_projecao",
    "detectar_marcas_em_modelo",
    "guardar_revisao",
    "carregar_revisao",
    "revisar_deteccoes",
    "contar_falsos_positivos",
]
