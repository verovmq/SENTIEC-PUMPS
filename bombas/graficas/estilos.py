"""Colores y estilos fijos del proyecto (reglas 5 y 7 de CLAUDE.md).

- Curvas digitalizadas, ejes y textos: NEGRO.
- Cuadro 1 (cálculo de altura): tonos de MORADO.
- Cuadro 2 (cálculo de caudal): tonos de AZUL.
- Cuadro 3 (puntos de operación): tonos de NARANJA.
Cada fila de un cuadro usa un tono distinto de su paleta (se repiten en ciclo).
"""

NEGRO = "#000000"
GRIS_CUADRICULA = "#E5E5E5"  # cuadrícula de fondo, no es un eje ni una curva

MORADO = ["#6A0DAD", "#9B59B6", "#4B0082", "#B57EDC", "#7D3C98", "#8E44AD"]
AZUL = ["#1F5FBF", "#5DADE2", "#0B3D91", "#3498DB", "#1B4F72", "#85C1E9"]
NARANJA = ["#E67E22", "#F5B041", "#BA4A00", "#EB984E", "#D35400", "#F8C471"]

CUADRO_ALTURA = 1
CUADRO_CAUDAL = 2
CUADRO_PUNTO = 3
PALETAS = {CUADRO_ALTURA: MORADO, CUADRO_CAUDAL: AZUL, CUADRO_PUNTO: NARANJA}

GROSOR_CURVA = 2
TAMANO_MARCADOR = 10
ESTILO_GUIA = "dot"  # líneas punteadas del punto a los ejes


def color_fila(cuadro: int, fila: int) -> str:
    """Tono de la fila `fila` (desde 0) del cuadro 1, 2 o 3."""
    paleta = PALETAS[cuadro]
    return paleta[fila % len(paleta)]
