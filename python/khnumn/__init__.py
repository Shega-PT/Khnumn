"""Camada cientifica do Khnumn.

Este pacote contem o que o nucleo Rust deliberadamente nao sabe: ler uma
imagem, medir a sua nitidez, projectar uma coordenada e conversar com um
motor de reconstrucao.

O acesso a esta camada faz-se pelo contrato `khnumn-tarefa-v1`, que e
identico na forma ao contrato de adaptadores de motores externos
(`docs/Khnumn.md` §18.3). A fronteira e unica e estreita de proposito: um
sistema com muitas fronteiras temmany inconsistencias, e a incoerencia
entre o que o nucleo acredita e o que a camada produz e a pior delas.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
