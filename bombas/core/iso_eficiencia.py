"""Eficiencia en un punto (Q, H) a partir de curvas de igual rendimiento.

Algunos fabricantes (p. ej. ER-3407) no dan η(Q) con su propio eje, sino una
familia de curvas de igual rendimiento (60, 65... 81 %) dibujadas sobre el
gráfico H–Q. Cada curva en U se digitaliza en dos ramas monótonas en H,
ajustadas como Q(H): en la rama izquierda η crece con Q y en la derecha decrece.

Para un punto (Q, H): a la altura H se evalúan todas las ramas cuyo rango de H
la contiene, se ordenan por Q y se interpola linealmente η entre las dos ramas
que rodean a Q.

Supuestos y límites:
- Fuera de la zona cubierta por las curvas (a la izquierda de la primera rama,
  a la derecha de la última, o por encima/debajo de todas) no hay valor: no se
  extrapola.
- Entre dos ramas del mismo nivel (dentro del lazo más interno, p. ej. 80 %),
  el gráfico solo dice que η es al menos ese nivel: se devuelve como cota mínima.
- La interpolación lineal en Q a H constante es una aproximación; el error es
  del orden de la separación entre curvas (unos pocos puntos de η).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from bombas.core.modelos import CurvaAjustada


@dataclass
class ResultadoEficiencia:
    valor: float | None  # η en %, o None si el punto está fuera de la zona cubierta
    cota_minima: bool = False  # True: η ≥ valor (dentro del lazo más interno)
    aviso: str | None = None


def eficiencia_en(curvas: list[CurvaAjustada], q: float, h: float) -> ResultadoEficiencia:
    """η en (q, h) interpolando entre las curvas de igual rendimiento."""
    iso = [c for c in curvas if c.es_iso_eficiencia]
    if not iso:
        raise ValueError("No hay curvas de igual rendimiento.")
    if any(c.funcion_de != "y" for c in iso):
        raise ValueError('Las curvas de igual rendimiento deben estar ajustadas como Q(H) (funcion_de="y").')

    cortes = sorted((float(c.evaluar(h)), float(c.nivel)) for c in iso if c.en_rango(h))
    if len(cortes) < 2 or not cortes[0][0] <= q <= cortes[-1][0]:
        return ResultadoEficiencia(
            None, aviso=f"El punto (Q={q:g}, H={h:g}) está fuera de la zona cubierta por las curvas de igual rendimiento."
        )
    qs = np.array([c[0] for c in cortes])
    i = int(np.clip(np.searchsorted(qs, q, side="right") - 1, 0, len(cortes) - 2))
    (qa, na), (qb, nb) = cortes[i], cortes[i + 1]
    if na == nb:
        return ResultadoEficiencia(na, cota_minima=True)
    t = 0.0 if qb == qa else (q - qa) / (qb - qa)
    return ResultadoEficiencia(na + t * (nb - na))
