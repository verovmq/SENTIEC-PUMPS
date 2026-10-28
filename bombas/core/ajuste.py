"""Ajuste polinómico de curvas digitalizadas.

Supuestos y límites:
- El ajuste se hace en las unidades originales del gráfico (sin convertir).
- El polinomio solo es válido en el rango [x_min, x_max] de los puntos
  digitalizados; fuera de él es extrapolación y los resultados no son fiables.
- Grados altos (> 4) tienden a oscilar en los extremos; por eso se limita a 1..4.
"""

from __future__ import annotations

import numpy as np

from bombas.core.modelos import CurvaAjustada, CurvaDigitalizada

GRADO_MINIMO = 1
GRADO_MAXIMO = 4
GRADO_POR_DEFECTO = 3


def ajustar(
    curva: CurvaDigitalizada,
    grado: int = GRADO_POR_DEFECTO,
    unidad_x: str = "",
    unidad_y: str = "",
) -> CurvaAjustada:
    """Ajusta y(x) por mínimos cuadrados con numpy.polyfit."""
    if not GRADO_MINIMO <= grado <= GRADO_MAXIMO:
        raise ValueError(f"El grado debe estar entre {GRADO_MINIMO} y {GRADO_MAXIMO}.")
    x = np.asarray(curva.x, dtype=float)
    y = np.asarray(curva.y, dtype=float)
    if x.shape != y.shape:
        raise ValueError("x e y deben tener la misma longitud.")
    if len(np.unique(x)) <= grado:
        raise ValueError(f"Se necesitan al menos {grado + 1} valores distintos de x para grado {grado}.")

    coef = np.polyfit(x, y, grado)
    residuos = y - np.polyval(coef, x)
    ss_res = float(np.sum(residuos**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    rmse = float(np.sqrt(ss_res / len(x)))

    return CurvaAjustada(
        magnitud=curva.magnitud,
        coeficientes=coef,
        x_min=float(x.min()),
        x_max=float(x.max()),
        unidad_x=unidad_x,
        unidad_y=unidad_y,
        r2=r2,
        rmse=rmse,
        diametro=curva.diametro,
        unidad_diametro=curva.unidad_diametro,
    )


def invertir(curva: CurvaAjustada, y: float, tolerancia: float = 1e-9) -> list[float]:
    """Valores de x dentro del rango válido tales que curva(x) = y, ordenados.

    Lista vacía si y no se alcanza dentro del rango digitalizado.
    """
    coef = np.array(curva.coeficientes, dtype=float)
    coef[-1] -= y
    raices = np.roots(coef)
    margen = tolerancia * max(1.0, abs(curva.x_max - curva.x_min))
    reales = [
        float(r.real)
        for r in raices
        if abs(r.imag) <= margen and curva.x_min - margen <= r.real <= curva.x_max + margen
    ]
    return sorted(min(max(r, curva.x_min), curva.x_max) for r in reales)
