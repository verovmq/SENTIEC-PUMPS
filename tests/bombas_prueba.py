"""Bombas de prueba con curvas de coeficientes conocidos (sin digitalizar)."""

import numpy as np

from bombas.core.modelos import Bomba, CurvaAjustada, Magnitud, Rama

COEF_H738 = np.array([-2.0e-9, -4.0e-6, -2.0e-3, 204.0])
COEF_H608 = np.array([-2.0e-9, -4.0e-6, -2.0e-3, 140.0])
COEF_ETA = np.polyfit([0, 2100, 4200], [0, 87, 0], 2)
COEF_NPSH = np.array([1.0e-6, 0.0, 4.0])
COEF_P = np.array([0.35, 450.0])
# Curva con joroba: máximo de 205,75 m en Q = 500 → H = 205,3 se alcanza dos veces.
COEF_JOROBA = np.array([-3.0e-6, 3.0e-3, 205.0])


def curva(magnitud, coef, x_min, x_max, unidad_y, diametro=None, **extra):
    return CurvaAjustada(
        magnitud=magnitud, coeficientes=np.asarray(coef, float), x_min=x_min, x_max=x_max,
        unidad_x="m³/h", unidad_y=unidad_y, r2=1.0, rmse=0.0, diametro=diametro, **extra,
    )


def bomba_tipo_a(coef_h738=COEF_H738):
    """Como curvaBOMBA1: H por diámetro, η(Q), NPSH y P comunes."""
    return Bomba(
        "Tipo A",
        [
            curva(Magnitud.ALTURA, coef_h738, 0, 2750, "m", 738),
            curva(Magnitud.ALTURA, COEF_H608, 0, 2200, "m", 608),
            curva(Magnitud.EFICIENCIA, COEF_ETA, 0, 2750, "%"),
            curva(Magnitud.NPSH, COEF_NPSH, 800, 2750, "m"),
            curva(Magnitud.POTENCIA, COEF_P, 0, 2750, "kW"),
        ],
    )


def rama(nivel, q, lado, h_min=100.0, h_max=250.0):
    """Rama de igual rendimiento vertical Q(H) = q."""
    return curva(Magnitud.EFICIENCIA, [0.0, q], h_min, h_max, "m", funcion_de="y", nivel=nivel, rama=lado)


def bomba_tipo_b():
    """Como la ER-3407: H por diámetro, curvas de igual rendimiento y P en C.V."""
    i, d = Rama.IZQUIERDA, Rama.DERECHA
    return Bomba(
        "Tipo B",
        [
            curva(Magnitud.ALTURA, COEF_H738, 0, 2750, "m", 635),
            rama(60, 300, i), rama(70, 400, i), rama(80, 500, i),
            rama(80, 900, d), rama(70, 1000, d), rama(60, 1100, d),
            curva(Magnitud.POTENCIA, COEF_P, 0, 2750, "C.V.", 635),
        ],
    )
