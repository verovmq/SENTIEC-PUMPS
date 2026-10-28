"""Gráficos de bomba sintéticos con curvas de coeficientes conocidos."""

import cv2
import numpy as np

from bombas.core.calibracion import pixel_desde_valor
from bombas.core.modelos import Eje, Orientacion

RECUADRO = (80, 40, 860, 640)  # x0, y0, x1, y1
Q_MAX = 3000.0

EJE_Q = Eje("Q", "m³/h", Orientacion.HORIZONTAL, p1=80, v1=0, p2=860, v2=Q_MAX)
EJE_H = Eje("H", "m", Orientacion.VERTICAL, p1=640, v1=0, p2=40, v2=250)
EJE_ETA = Eje("η", "%", Orientacion.VERTICAL, p1=640, v1=0, p2=40, v2=100)

COEF_H = np.array([-2.0e-9, -4.0e-6, -2.0e-3, 204.0])  # H(Q), Q en 0..2750
COEF_ETA = np.polyfit([0, 2100, 4200], [0, 87, 0], 2)  # η(Q) parabólica, arranque empinado
Q_FIN = 2750.0

GRIS = (200, 200, 200)
NEGRO = (0, 0, 0)
ROJO = (230, 20, 20)


def a_pixeles(coef, eje_y, q_ini=0.0, q_fin=Q_FIN, n=400):
    q = np.linspace(q_ini, q_fin, n)
    x = pixel_desde_valor(EJE_Q, q)
    y = pixel_desde_valor(eje_y, np.polyval(coef, q))
    return np.stack([x, y], axis=1)


def semilla(coef, eje_y, q):
    return float(pixel_desde_valor(EJE_Q, q)), float(pixel_desde_valor(eje_y, np.polyval(coef, q)))


def dibujar_curva(img, puntos, grosor=3):
    pts = np.round(puntos * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [pts], False, NEGRO, grosor, cv2.LINE_AA, shift=4)


def grafico(con_ruido_visual=True, grosor=3):
    """Imagen RGB con cuadrícula, marco y las curvas H y η; opcionalmente caja de texto y marca roja."""
    img = np.full((700, 920, 3), 255, np.uint8)
    x0, y0, x1, y1 = RECUADRO
    for i in range(1, 30):  # cuadrícula menor gris
        x = int(x0 + (x1 - x0) * i / 30)
        cv2.line(img, (x, y0), (x, y1), GRIS, 1)
    for i in range(1, 25):
        y = int(y0 + (y1 - y0) * i / 25)
        cv2.line(img, (x0, y), (x1, y), GRIS, 1)
    for i in range(0, 7):  # cuadrícula mayor negra
        x = int(x0 + (x1 - x0) * i / 6)
        cv2.line(img, (x, y0), (x, y1), NEGRO, 2)
    for i in range(0, 6):
        y = int(y0 + (y1 - y0) * i / 5)
        cv2.line(img, (x0, y), (x1, y), NEGRO, 2)
    dibujar_curva(img, a_pixeles(COEF_H, EJE_H), grosor)
    dibujar_curva(img, a_pixeles(COEF_ETA, EJE_ETA), grosor)
    if con_ruido_visual:
        # Caja de texto con marco fino y fondo blanco, como en los catálogos.
        cv2.rectangle(img, (560, 520), (680, 545), (255, 255, 255), -1)
        cv2.rectangle(img, (560, 520), (680, 545), NEGRO, 1)
        cv2.putText(img, "738 mm Rated", (565, 538), cv2.FONT_HERSHEY_SIMPLEX, 0.4, NEGRO, 1)
        # Anotación roja.
        cv2.fillPoly(img, [np.array([[300, 560], [340, 560], [340, 600]])], ROJO)
    return img
