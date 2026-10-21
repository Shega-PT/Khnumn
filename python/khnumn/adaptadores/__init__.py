"""Adaptadores de motores externos.

Cada adaptador vive atrás da mesma interface, a de `docs/Khnumn.md` §18.3, e
nenhum tipo do motor atravessa a fronteira. A fronteira é também a
fronteira de licença: um motor com copyleft forte é invocado por aqui, como
processo separado, e os seus resultados entram no sistema como dados com
proveniência.
"""

from .colmap import AdaptadorColmap, ErroAdaptador, ParametrosMotor, ResultadoMotor

__all__ = [
    "AdaptadorColmap",
    "ErroAdaptador",
    "ParametrosMotor",
    "ResultadoMotor",
]
