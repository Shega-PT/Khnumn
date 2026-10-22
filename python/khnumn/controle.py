"""Controlo, georreferenciação e validação independente.

Implementa as etapas da Fase 3 do roadmap: ingestão de pontos de controlo
com covariância obrigatória, exclusão de checkpoints do ajuste, similaridade
de sete parâmetros ponderada, ajuste constrangido e propagação por ensemble.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from . import geo

#: Papéis válidos para um ponto de controlo.
PAPEIS_VALIDOS = {"control", "checkpoint"}

#: Número mínimo de pontos de controlo para uma similaridade de 7 parâmetros.
MINIMO_PONTOS_SIMILARIDADE = 3


class ErroControle(Exception):
    """Falha no controlo, com causa legível."""


def _validar_ponto(ponto: dict[str, Any]) -> None:
    """Valida um ponto de controlo, recusando o que não tem covariância."""
    if not isinstance(ponto, dict):
        raise ErroControle("ponto de controlo tem de ser um objecto")
    for campo in ("id", "role", "crs", "coordinates", "units", "covariance", "method", "instrument", "measured_utc", "operator"):
        if campo not in ponto:
            raise ErroControle(f"ponto {ponto.get('id', '?')!r}: campo obrigatório ausente: {campo}")
    if ponto["role"] not in PAPEIS_VALIDOS:
        raise ErroControle(f"ponto {ponto['id']!r}: papel inválido {ponto['role']!r}")
    coords = ponto["coordinates"]
    if not isinstance(coords, list) or len(coords) != 3:
        raise ErroControle(f"ponto {ponto['id']!r}: coordinates tem de ter 3 valores")
    cov = ponto["covariance"]
    if not isinstance(cov, dict) or "matrix" not in cov:
        raise ErroControle(f"ponto {ponto['id']!r}: covariância em falta")
    matriz = cov["matrix"]
    if not isinstance(matriz, list) or len(matriz) != 3 or any(not isinstance(l, list) or len(l) != 3 for l in matriz):
        raise ErroControle(f"ponto {ponto['id']!r}: a covariância tem de ser 3x3")
    if cov.get("units") != "m2":
        raise ErroControle(f"ponto {ponto['id']!r}: a covariância tem de estar em m2")




def validar_ponto_schema(ponto: dict[str, Any]) -> None:
    """Valida um ponto contra o esquema controlo-v1, se disponível."""
    try:
        import jsonschema
        import json
        from pathlib import Path
        esquema_path = Path(__file__).resolve().parents[2] / "schemas" / "controlo-v1.schema.json"
        if esquema_path.exists():
            esquema = json.loads(esquema_path.read_text(encoding="utf-8"))
            jsonschema.validate(ponto, esquema)
    except ImportError:
        pass
    except Exception as erro:  # noqa: BLE001
        raise ErroControle(f"ponto inválido contra o esquema: {erro}") from erro


def ingerir_pontos(caminho: Path) -> list[dict[str, Any]]:
    """Lê e valida pontos de controlo de um ficheiro JSON.

    A ausência de covariância é erro de configuração, não omissão tolerada.
    Devolve a lista validada, preservando o papel de cada ponto.
    """
    caminho = Path(caminho)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ErroControle(f"não foi possível ler {caminho}: {erro}") from erro

    if isinstance(dados, dict):
        dados = dados.get("points", dados.get("pontos", []))
    if not isinstance(dados, list):
        raise ErroControle("o ficheiro de pontos tem de conter uma lista")

    pontos: list[dict[str, Any]] = []
    for ponto in dados:
        _validar_ponto(ponto)
        validar_ponto_schema(ponto)
        pontos.append(ponto)
    return pontos


def separar_papeis(pontos: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa pontos de controlo dos pontos de verificação."""
    controlo = [p for p in pontos if p["role"] == "control"]
    checkpoints = [p for p in pontos if p["role"] == "checkpoint"]
    return controlo, checkpoints


def pontos_para_ajuste(pontos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Devolve apenas os pontos de controlo, excluindo os checkpoints.

    A exclusão é imposta aqui, por código, e não por convenção do operador.
    """
    controlo, _ = separar_papeis(pontos)
    return controlo


def coordenadas_enu(ponto: dict[str, Any]) -> np.ndarray:
    """Converte as coordenadas de um ponto para ENU em metros."""
    coords = ponto["coordinates"]
    crs_origem = ponto["crs"]
    return np.asarray(geo.para_enu(list(coords), crs_origem, crs_origem), dtype=float)


def covariancia_matriz(ponto: dict[str, Any]) -> np.ndarray:
    """Devolve a covariância 3x3 de um ponto."""
    return np.asarray(ponto["covariance"]["matrix"], dtype=float)


def similaridade_7_parametros(
    origem: np.ndarray,
    destino: np.ndarray,
    pesos: np.ndarray | None = None,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Estima uma transformação de similaridade (R, t, s) por mínimos quadrados.

    `origem` e `destino` são matrizes Nx3. `pesos` são pesos por ponto
    (inversos à variância). Devolve (R 3x3, escala, t 3).
    Usa a solução de Umeyama, com ponderação quando fornecida.
    """
    origem = np.asarray(origem, dtype=float)
    destino = np.asarray(destino, dtype=float)
    if origem.shape != destino.shape or origem.ndim != 2 or origem.shape[1] != 3:
        raise ErroControle("origem e destino têm de ser matrizes Nx3")
    n = origem.shape[0]
    if n < MINIMO_PONTOS_SIMILARIDADE:
        raise ErroControle(f"são necessários pelo menos {MINIMO_PONTOS_SIMILARIDADE} pontos")

    if pesos is None:
        pesos = np.ones(n)
    pesos = np.asarray(pesos, dtype=float)
    pesos = pesos / pesos.sum()

    # Centroides ponderados.
    mu_o = np.sum(origem * pesos[:, None], axis=0)
    mu_d = np.sum(destino * pesos[:, None], axis=0)
    oc = origem - mu_o
    dc = destino - mu_d

    # Covariância cruzada ponderada.
    sigma = (oc * pesos[:, None]).T @ dc / np.sum(pesos)
    u, s, vt = np.linalg.svd(sigma)
    d = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        d[2, 2] = -1.0
    r = vt.T @ d @ u.T

    # Escala.
    var_o = np.sum(pesos * np.sum(oc ** 2, axis=1))
    escala = (np.sum(pesos * np.sum(oc * (r @ oc.T).T, axis=1)) / var_o) if var_o > 0 else 1.0

    t = mu_d - escala * (r @ mu_o)
    return r, float(escala), t


def ransac_similaridade(
    origem: np.ndarray,
    destino: np.ndarray,
    covariancias: np.ndarray | None = None,
    limiar_px: float = 3.0,
    iteracoes: int = 200,
    semente: int = 0,
) -> dict[str, Any]:
    """Estimador robusto de similaridade, com limiar escalado pela incerteza.

    O limiar é escalado pela raiz da variância quando as covariâncias são
    fornecidas, de modo que um ponto mais incerto tem um limiar mais largo.
    """
    origem = np.asarray(origem, dtype=float)
    destino = np.asarray(destino, dtype=float)
    n = origem.shape[0]
    if covariancias is None:
        covariancias = np.ones((n, 3, 3))
    covariancias = np.asarray(covariancias, dtype=float)

    rng = np.random.default_rng(semente)
    melhor_inliers: np.ndarray = np.zeros(n, dtype=bool)
    melhor_modelo: tuple[np.ndarray, float, np.ndarray] | None = None
    melhor_contagem = 0

    if n < MINIMO_PONTOS_SIMILARIDADE:
        raise ErroControle("pontos insuficientes para RANSAC")

    for _ in range(iteracoes):
        indices = rng.choice(n, size=MINIMO_PONTOS_SIMILARIDADE, replace=False)
        try:
            # Pesos inversos à variância, quando existem covariâncias.
            pesos_local = None
            if covariancias is not None:
                tracos = np.array([max(1e-12, float(np.trace(covariancias[i]))) for i in indices])
                pesos_local = 1.0 / tracos
            r, s, t = similaridade_7_parametros(origem[indices], destino[indices], pesos=pesos_local)
        except ErroControle:
            continue
        # Resíduos.
        transformados = s * (origem @ r.T) + t
        residuos = np.linalg.norm(transformados - destino, axis=1)
        # Limiar por ponto, escalado pela incerteza.
        limiares = np.array([
            limiar_px * max(1.0, math.sqrt(float(np.trace(covariancias[i])) / 3.0))
            for i in range(n)
        ])
        inliers = residuos <= limiares
        contagem = int(inliers.sum())
        if contagem > melhor_contagem:
            melhor_contagem = contagem
            melhor_inliers = inliers
            melhor_modelo = (r, s, t)

    if melhor_modelo is None:
        raise ErroControle("RANSAC não encontrou um modelo válido")

    r, s, t = melhor_modelo
    # Re-estimativa com todos os inliers.
    if melhor_inliers.sum() >= MINIMO_PONTOS_SIMILARIDADE:
        pesos_inliers = None
        if covariancias is not None:
            tracos = np.array([max(1e-12, float(np.trace(covariancias[i]))) for i in range(n) if melhor_inliers[i]])
            pesos_inliers = 1.0 / tracos
        r, s, t = similaridade_7_parametros(origem[melhor_inliers], destino[melhor_inliers], pesos=pesos_inliers)

    return {
        "R": r,
        "escala": s,
        "t": t,
        "inliers": melhor_inliers,
        "num_inliers": int(melhor_inliers.sum()),
        "num_total": n,
    }


def perturbar_coordenadas(ponto: dict[str, Any], rng: np.random.Generator) -> np.ndarray:
    """Sorteia coordenadas perturbadas pela covariância do ponto."""
    cov = covariancia_matriz(ponto)
    media = coordenadas_enu(ponto)
    try:
        return rng.multivariate_normal(media, cov)
    except np.linalg.LinAlgError:
        return media + rng.normal(scale=np.sqrt(np.diag(cov)))


def propagar_ensemble(
    pontos: list[dict[str, Any]],
    funcao_ajuste: Any,
    n_amostras: int,
    semente: int = 0,
) -> dict[str, Any]:
    """Executa a etapa final N vezes, perturbando as coordenadas dos pontos.

    `funcao_ajuste` recebe a lista de pontos perturbados e devolve um
    resultado (qualquer). A dispersão dos resultados é a incerteza do
    controlo propagada.
    """
    if n_amostras < 1:
        raise ErroControle("o número de amostras do ensemble tem de ser positivo")
    rng = np.random.default_rng(semente)
    resultados: list[Any] = []
    for _ in range(n_amostras):
        perturbados = []
        for ponto in pontos:
            copia = json.loads(json.dumps(ponto))
            novas = perturbar_coordenadas(ponto, rng)
            copia["coordinates"] = [float(v) for v in novas]
            perturbados.append(copia)
        resultados.append(funcao_ajuste(perturbados))
    return {
        "n_amostras": n_amostras,
        "resultados": resultados,
        "dispersao": _dispersao(resultados),
    }


def _dispersao(resultados: list[Any]) -> dict[str, Any]:
    """Calcula a dispersão de uma lista de resultados numéricos."""
    if not resultados:
        return {"n": 0}
    # Se os resultados forem arrays, calcula desvio padrão por componente.
    try:
        arr = np.asarray(resultados, dtype=float)
    except (ValueError, TypeError):
        return {"n": len(resultados), "tipo": "nao_numerico"}
    if arr.ndim == 1:
        return {"n": len(resultados), "std": float(np.std(arr)), "mean": float(np.mean(arr))}
    return {
        "n": len(resultados),
        "std_por_componente": [float(v) for v in np.std(arr, axis=0).ravel()],
        "mean_por_componente": [float(v) for v in np.mean(arr, axis=0).ravel()],
    }



def escrever_prior_gnss(
    base_dados: str,
    posicao: list[float],
    covariancia: list[list[float]],
    coordinate_system: str = "CARTESIAN",
) -> int:
    """Escreve um prior de pose GNSS na base de dados do motor.

    Devolve o identificador do prior. A associação à imagem é feita pelo
    chamador, via `corr_data_id`, conforme a versão do motor.
    """
    import pycolmap
    import numpy as np
    db = pycolmap.Database.open(base_dados)
    prior = pycolmap.PosePrior()
    prior.position = np.asarray(posicao, dtype=float)
    prior.position_covariance = np.asarray(covariancia, dtype=float)
    cs = getattr(pycolmap.PosePriorCoordinateSystem, coordinate_system, None)
    if cs is None:
        raise ErroControle(f"sistema de coordenadas desconhecido: {coordinate_system}")
    prior.coordinate_system = cs
    pid = db.write_pose_prior(prior)
    db.close()
    return int(pid)


def triangulacao_local(reconstrucao: Any, observacoes: list[tuple[int, float, float]]) -> list[float] | None:
    """Triangula um ponto de controlo a partir das suas observações.

    `observacoes` é uma lista de (image_id, x, y). Devolve [X, Y, Z] ou None.
    """
    try:
        import pycolmap
        import numpy as np
    except ImportError:
        return None
    try:
        cameras = []
        rays = []
        for image_id, x, y in observacoes:
            imagem = reconstrucao.image(int(image_id))
            camara = reconstrucao.camera(imagem.camera_id)
            # Matriz cam_from_world 3x4.
            pose = imagem.cam_from_world()
            R = np.asarray(pose.rotation.matrix(), dtype=float)
            t = np.asarray(pose.translation, dtype=float)
            M = np.hstack([R, t.reshape(3, 1)])
            cameras.append(M)
            # Raio em coordenadas da câmara (normalizado).
            ray = np.array([ (x - camara.principal_point_x) / camara.focal_length_x,
                            (y - camara.principal_point_y) / camara.focal_length_y,
                            1.0], dtype=float)
            ray = ray / np.linalg.norm(ray)
            rays.append(ray)
        if len(cameras) < 2:
            return None
        xyz = pycolmap.triangulate_multi_view_point(cameras, np.asarray(rays, dtype=float))
        if xyz is None:
            return None
        return [float(v) for v in np.asarray(xyz).ravel()[:3]]
    except Exception:
        return None


def aplicar_priors_gnss(base: str, priors: list[dict[str, Any]]) -> int:
    """Escreve priors de pose GNSS na base de dados do motor.

    Devolve o número de priors escritos. A aplicação no ajuste é feita com
    `use_prior_position=True` no mapeamento.
    """
    try:
        import pycolmap
        import numpy as np
    except ImportError:
        return 0
    base_path = base
    db_path = base_path + "/database.db" if not base_path.endswith(".db") else base_path
    try:
        db = pycolmap.Database.open(db_path)
    except Exception:
        return 0
    escritos = 0
    for prior in priors:
        try:
            imagem = db.read_image_with_name(prior.get("imagem", ""))
        except Exception:
            continue
        # Garante rig/frame.
        rig_id = 1
        try:
            rig = pycolmap.Rig()
            rig.rig_id = rig_id
            rig.add_ref_sensor(pycolmap.sensor_t(pycolmap.SensorType.CAMERA, imagem.camera_id))
            db.write_rig(rig)
        except Exception:
            pass
        try:
            frame = pycolmap.Frame()
            frame.frame_id = imagem.image_id
            frame.rig_id = rig_id
            frame.add_data_id(imagem.data_id)
            frame.finalize_data_ids()
            db.write_frame(frame)
            imagem.frame_id = imagem.image_id
            db.update_image(imagem)
        except Exception:
            pass
        pp = pycolmap.PosePrior()
        posicao = prior.get("posicao", [0.0, 0.0, 0.0])
        pp.position = np.asarray(posicao, dtype=float)
        cov = prior.get("covariancia", [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        pp.position_covariance = np.asarray(cov, dtype=float)
        sistema = prior.get("coordinate_system", "CARTESIAN")
        pp.coordinate_system = getattr(pycolmap.PosePriorCoordinateSystem, sistema, pycolmap.PosePriorCoordinateSystem.CARTESIAN)
        pp.corr_data_id = imagem.data_id
        try:
            db.write_pose_prior(pp)
            escritos += 1
        except Exception:
            continue
    db.close()
    return escritos



__all__ = [
    "ErroControle",
    "MINIMO_PONTOS_SIMILARIDADE",
    "PAPEIS_VALIDOS",
    "coordenadas_enu",
    "covariancia_matriz",
    "ingerir_pontos",
    "perturbar_coordenadas",
    "pontos_para_ajuste",
    "propagar_ensemble",
    "ransac_similaridade",
    "separar_papeis",
    "similaridade_7_parametros",
    "triangulacao_local",
    "aplicar_priors_gnss",
    "escrever_prior_gnss",
]
