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
  el gráfico solo dice que η es al menos ese nivel: se devuelve como cota mínima,
  salvo que se haya registrado el punto de máximo rendimiento (ver abajo).

Punto de máximo rendimiento (opcional, `PuntoEficiencia`):
- Define la "zona del máximo": la parte del lazo del nivel más interno visible
  desde el punto (cerrada, donde el lazo está abierto, por la envolvente convexa
  de ramas + punto). Dentro de esa zona, donde las ramas no dan un valor (cota
  mínima o fuera de las ramas), η baja linealmente desde el máximo hasta el
  nivel del lazo a lo largo de la recta que une el punto con el borde, como en
  una colina de rendimiento. El resultado queda entre ambos valores.
- Fuera de esa zona no cambia nada. Donde el borde es la envolvente y no una
  rama dibujada (lazo abierto), el valor en el borde es una aproximación.
- La interpolación lineal en Q a H constante es una aproximación; el error es
  del orden de la separación entre curvas (unos pocos puntos de η).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import ConvexHull, QhullError

from bombas.core.modelos import CurvaAjustada, PuntoEficiencia

MUESTRAS_POR_RAMA = 40


@dataclass
class ResultadoEficiencia:
    valor: float | None  # η en %, o None si el punto está fuera de la zona cubierta
    cota_minima: bool = False  # True: η ≥ valor (dentro del lazo más interno)
    aviso: str | None = None


def eficiencia_en(
    curvas: list[CurvaAjustada], q: float, h: float, puntos: list[PuntoEficiencia] = ()
) -> ResultadoEficiencia:
    """η en (q, h) interpolando entre las curvas de igual rendimiento.

    `puntos`: puntos de máximo rendimiento, para dar un valor dentro del lazo más interno.
    """
    iso = [c for c in curvas if c.es_iso_eficiencia]
    if not iso:
        raise ValueError("No hay curvas de igual rendimiento.")
    if any(c.funcion_de != "y" for c in iso):
        raise ValueError('Las curvas de igual rendimiento deben estar ajustadas como Q(H) (funcion_de="y").')
    resultado = _por_ramas(iso, q, h)
    if puntos and (resultado.valor is None or resultado.cota_minima):
        valor = _zona_del_maximo(iso, puntos, q, h)
        if valor is not None:
            return ResultadoEficiencia(valor)
    return resultado


def _cortes_rayo(origen: np.ndarray, direccion: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distancias s > 0 a las que el rayo origen + s·direccion corta los segmentos a[i]–b[i]."""
    e = b - a
    w = a - origen
    det = direccion[0] * (-e[:, 1]) - direccion[1] * (-e[:, 0])
    validos = np.abs(det) > 1e-12
    det = np.where(validos, det, 1.0)
    s = (w[:, 0] * (-e[:, 1]) - w[:, 1] * (-e[:, 0])) / det
    t = (direccion[0] * w[:, 1] - direccion[1] * w[:, 0]) / det
    ok = validos & (s > 1e-9) & (t >= -1e-9) & (t <= 1 + 1e-9)
    return s[ok]


def _zona_del_maximo(iso: list[CurvaAjustada], puntos: list[PuntoEficiencia], q: float, h: float) -> float | None:
    """η en la zona del punto de máximo rendimiento, o None fuera de ella.

    η baja linealmente desde el punto de máximo hasta el borde del lazo más
    interno a lo largo de la recta que pasa por (q, h). El borde lo forman las
    ramas de ese nivel y, donde el lazo está abierto (las ramas terminan en la
    curva del diámetro máximo), la envolvente convexa de ramas + punto.
    """
    nivel = max(c.nivel for c in iso)
    bajos = [p for p in puntos if p.eta <= nivel]
    if bajos:
        raise ValueError(
            f"El punto de máximo rendimiento ({bajos[0].eta:g} %) debe superar la curva más interna ({nivel:g} %)."
        )
    ramas = []
    for c in iso:
        if c.nivel == nivel:
            hh = np.linspace(c.x_min, c.x_max, MUESTRAS_POR_RAMA)
            ramas.append(np.column_stack([c.evaluar(hh), hh]))
    todos = np.vstack(ramas + [np.array([[p.q, p.h] for p in puntos], float)])
    # Normalizar para que las distancias no dependan de las unidades de Q y H.
    escala = np.array([np.ptp(todos[:, 0]) or 1.0, np.ptp(todos[:, 1]) or 1.0])
    todos = todos / escala
    try:
        envolvente = ConvexHull(todos)
    except (QhullError, ValueError):  # puntos insuficientes o alineados: no hay zona
        return None
    punto = np.array([q, h], float) / escala
    ecuaciones = envolvente.equations  # normal·x + d <= 0 dentro de la envolvente
    if np.any(ecuaciones[:, :2] @ punto + ecuaciones[:, 2] > 1e-9):
        return None

    maximo = min(puntos, key=lambda p: np.hypot(*((np.array([p.q, p.h]) / escala) - punto)))
    origen = np.array([maximo.q, maximo.h]) / escala
    distancia = float(np.hypot(*(punto - origen)))
    if distancia < 1e-12:
        return float(maximo.eta)
    direccion = (punto - origen) / distancia
    a = [r[:-1] / escala for r in ramas] + [todos[envolvente.simplices[:, 0]]]
    b = [r[1:] / escala for r in ramas] + [todos[envolvente.simplices[:, 1]]]
    cortes = _cortes_rayo(origen, direccion, np.vstack(a), np.vstack(b))
    if len(cortes) == 0:
        return None
    borde = float(cortes.min())
    if borde < distancia - 1e-9:
        return None  # el rayo sale del lazo antes de llegar al punto: no está en la zona
    return float(maximo.eta + (nivel - maximo.eta) * distancia / borde)


def _por_ramas(iso: list[CurvaAjustada], q: float, h: float) -> ResultadoEficiencia:
    """η interpolando, a la altura h, entre las dos ramas que rodean a q."""
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
