"""Conversión píxel ↔ valor y corrección de inclinación.

Supuestos y límites:
- Los ejes son ortogonales entre sí; solo se corrige una rotación pequeña
  (|ángulo| <= 10°), no la perspectiva.
- Cada eje se calibra con dos marcas; la precisión depende de lo separadas
  que estén (conviene usar las marcas extremas del eje).
"""

from __future__ import annotations

import cv2
import numpy as np

from bombas.core.modelos import Eje, Escala

ANGULO_MAXIMO = 10.0


def validar_eje(eje: Eje) -> None:
    if eje.p1 == eje.p2:
        raise ValueError(f"Eje {eje.nombre}: las dos marcas están en el mismo píxel.")
    if eje.v1 == eje.v2:
        raise ValueError(f"Eje {eje.nombre}: las dos marcas tienen el mismo valor.")
    if eje.escala == Escala.LOG and (eje.v1 <= 0 or eje.v2 <= 0):
        raise ValueError(f"Eje {eje.nombre}: una escala logarítmica requiere valores > 0.")


def _a_lineal(eje: Eje, valor):
    return np.log10(valor) if eje.escala == Escala.LOG else np.asarray(valor, dtype=float)


def _desde_lineal(eje: Eje, valor):
    return 10.0**valor if eje.escala == Escala.LOG else valor


def valor_desde_pixel(eje: Eje, pixel):
    """Valor (en la unidad del eje) que corresponde a una coordenada de píxel."""
    validar_eje(eje)
    a1, a2 = _a_lineal(eje, eje.v1), _a_lineal(eje, eje.v2)
    t = (np.asarray(pixel, dtype=float) - eje.p1) / (eje.p2 - eje.p1)
    return _desde_lineal(eje, a1 + t * (a2 - a1))


def pixel_desde_valor(eje: Eje, valor):
    """Coordenada de píxel que corresponde a un valor del eje."""
    validar_eje(eje)
    a1, a2 = _a_lineal(eje, eje.v1), _a_lineal(eje, eje.v2)
    t = (_a_lineal(eje, valor) - a1) / (a2 - a1)
    return eje.p1 + t * (eje.p2 - eje.p1)


def matriz_rotacion(angulo_grados: float, centro: tuple[float, float]) -> np.ndarray:
    """Matriz afín 2x3 que corrige una inclinación de `angulo_grados` alrededor de `centro`."""
    return cv2.getRotationMatrix2D(centro, angulo_grados, 1.0)


def enderezar_imagen(imagen: np.ndarray, angulo_grados: float) -> np.ndarray:
    """Rota la imagen para anular su inclinación (fondo blanco)."""
    if angulo_grados == 0:
        return imagen
    alto, ancho = imagen.shape[:2]
    m = matriz_rotacion(angulo_grados, (ancho / 2, alto / 2))
    return cv2.warpAffine(
        imagen, m, (ancho, alto), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255)
    )


def enderezar_puntos(puntos, angulo_grados: float, tamano: tuple[int, int]) -> np.ndarray:
    """Aplica a puntos (N, 2) de la imagen original la misma rotación que `enderezar_imagen`."""
    alto, ancho = tamano
    m = matriz_rotacion(angulo_grados, (ancho / 2, alto / 2))
    p = np.asarray(puntos, dtype=float).reshape(-1, 2)
    return p @ m[:, :2].T + m[:, 2]


def estimar_inclinacion(imagen: np.ndarray) -> float:
    """Estima en grados la inclinación de la cuadrícula con la transformada de Hough.

    Devuelve el ángulo a pasar a `enderezar_imagen` (positivo = rotar en sentido
    antihorario). Usa las líneas casi horizontales y casi verticales, que en un
    gráfico de curvas son la cuadrícula y los ejes. Devuelve 0 si no encuentra líneas.
    """
    gris = imagen if imagen.ndim == 2 else cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY)
    bordes = cv2.Canny(gris, 50, 150)
    lado = min(gris.shape)
    lineas = cv2.HoughLinesP(
        bordes, 1, np.pi / 1800, threshold=lado // 4, minLineLength=lado // 3, maxLineGap=5
    )
    if lineas is None:
        return 0.0
    angulos = []
    for x1, y1, x2, y2 in lineas.reshape(-1, 4):
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Llevar verticales y horizontales al mismo intervalo (-45°, 45°].
        a = (a + 45) % 90 - 45
        if abs(a) <= ANGULO_MAXIMO:
            angulos.append(a)
    if not angulos:
        return 0.0
    # En coordenadas de imagen (y hacia abajo), una línea con ángulo +a está
    # girada en sentido horario; se corrige rotando +a en sentido antihorario.
    return float(np.median(angulos))
