"""Extracción guiada de curvas a partir de semillas (clics del usuario).

Como en los gráficos de fabricante todas las curvas suelen ser negras, no se
pueden separar por color. El usuario marca 2 o más puntos sobre una curva
(inicio, fin y, si hace falta, puntos intermedios cerca de los cruces) y un
seguidor recorre la máscara entre cada par de semillas.

El seguidor avanza a pasos cortos en la dirección de la curva: mira los píxeles
de la máscara en un anillo alrededor del punto actual, solo dentro de un cono
centrado en la dirección actual, y se mueve al centro del grupo de píxeles más
alineado. Así, en un cruce, la otra curva queda fuera del cono. Si no hay
píxeles (hueco por la cuadrícula o una caja de texto borradas), alarga el paso
estrechando el cono hasta `HUECO_MAXIMO`. Todas las distancias se escalan con
el grosor del trazo, para que funcione igual a cualquier resolución.

Las curvas casi verticales (p. ej. las de igual rendimiento) se describen como
x(y): con `funcion_de="y"` se recorre la máscara traspuesta, avanzando por filas.

Supuestos y límites:
- La curva es función de x (o de y con `funcion_de="y"`): un único punto por
  columna (o por fila).
- Solo se digitaliza entre la primera y la última semilla: no se extrapola.
- En cruces casi tangentes el seguidor puede saltar de curva. Se detecta si el
  trazado no llega a la semilla siguiente (aviso) y se corrige añadiendo una
  semilla intermedia justo después del cruce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from scipy.ndimage import median_filter

from bombas.core.calibracion import valor_desde_pixel
from bombas.core.modelos import CurvaDigitalizada, Eje, Magnitud, Rama
from bombas.core.preprocesado import grosor_tipico

# Valores para un trazo de referencia de 2 px de grosor; se escalan con el grosor real.
GROSOR_REFERENCIA = 2.0
PASO = 3  # px por paso
CONO = np.radians(40)  # semiapertura del cono de búsqueda en pasos normales
CONO_INICIAL = np.radians(80)  # primer paso: la tangente puede diferir de la recta entre semillas
CONO_HUECO = np.radians(20)  # semiapertura al saltar huecos cortos
HUECO_CORTO = 25  # px: hasta aquí se usa CONO_HUECO
CONO_HUECO_LARGO = np.radians(8)  # semiapertura para huecos largos (curva tangente a la cuadrícula)
HUECO_MAXIMO = 60  # px máximos que se salta sin encontrar trazo
PASOS_DIRECCION = 4  # pasos usados para estimar la dirección
RADIO_AJUSTE_SEMILLA = 6  # px para llevar una semilla al centro del trazo
TOLERANCIA_LLEGADA = 8  # px: más lejos de la semilla siguiente = posible salto de curva
PUNTOS_POR_DEFECTO = 50


@dataclass(frozen=True)
class Parametros:
    """Distancias del seguidor en píxeles, proporcionales al grosor del trazo."""

    paso: int
    hueco_corto: int
    hueco_maximo: int
    radio_semilla: int
    tolerancia: float
    ancho_cruce: float  # un grupo más ancho que esto en el anillo es un cruce de curvas

    @classmethod
    def para_grosor(cls, grosor: float) -> Parametros:
        e = max(1.0, grosor / GROSOR_REFERENCIA)
        paso = max(PASO, round(PASO * e))
        return cls(
            paso=paso,
            hueco_corto=round(HUECO_CORTO * e),
            hueco_maximo=round(HUECO_MAXIMO * e),
            radio_semilla=round(RADIO_AJUSTE_SEMILLA * e),
            tolerancia=TOLERANCIA_LLEGADA * e,
            ancho_cruce=3 * paso + 2,
        )


@dataclass
class Seguimiento:
    x: np.ndarray  # coordenadas de píxel, x creciente
    y: np.ndarray
    avisos: list[str] = field(default_factory=list)


@lru_cache(maxsize=None)
def _anillo(radio: int) -> np.ndarray:
    r = np.arange(-radio - 1, radio + 2)
    dx, dy = np.meshgrid(r, r)
    d = np.hypot(dx, dy)
    sel = (d >= radio - 0.5) & (d < radio + 0.5)
    return np.stack([dx[sel], dy[sel]], axis=1).astype(float)


def grosor_local(mascara: np.ndarray, semillas, margen: int = 40) -> float:
    """Grosor típico del trazo en la zona que abarcan las semillas."""
    xs = [x for x, _ in semillas]
    ys = [y for _, y in semillas]
    alto, ancho = mascara.shape
    x0, x1 = max(0, int(min(xs)) - margen), min(ancho, int(max(xs)) + margen + 1)
    y0, y1 = max(0, int(min(ys)) - margen), min(alto, int(max(ys)) + margen + 1)
    return grosor_tipico(mascara[y0:y1, x0:x1]) or GROSOR_REFERENCIA


def ajustar_semilla(mascara: np.ndarray, x: float, y: float, radio: int = RADIO_AJUSTE_SEMILLA):
    """Lleva un clic al centro del trazo más cercano (o lo deja igual si no hay trazo)."""
    alto, ancho = mascara.shape
    x0, x1 = max(0, int(x) - radio), min(ancho, int(x) + radio + 1)
    y0, y1 = max(0, int(y) - radio), min(alto, int(y) + radio + 1)
    ys, xs = np.nonzero(mascara[y0:y1, x0:x1])
    if len(xs) == 0:
        return float(x), float(y)
    xs, ys = xs + x0, ys + y0
    cerca = np.hypot(xs - x, ys - y) <= np.hypot(xs - x, ys - y).min() + 2
    return float(xs[cerca].mean()), float(ys[cerca].mean())


def _paso(
    mascara: np.ndarray, p: np.ndarray, direccion: float, radio: int, cono: float, ancho_cruce: float
):
    """Siguiente punto sobre el trazo a distancia `radio`, o None si no hay trazo en el cono."""
    alto, ancho = mascara.shape
    cand = p + _anillo(radio)
    xi, yi = np.round(cand[:, 0]).astype(int), np.round(cand[:, 1]).astype(int)
    dentro = (xi >= 0) & (xi < ancho) & (yi >= 0) & (yi < alto)
    cand, xi, yi = cand[dentro], xi[dentro], yi[dentro]
    cand = cand[mascara[yi, xi]]
    if len(cand) == 0:
        return None
    ang = np.arctan2(cand[:, 1] - p[1], cand[:, 0] - p[0])
    desvio = (ang - direccion + np.pi) % (2 * np.pi) - np.pi
    en_cono = np.abs(desvio) <= cono
    if not en_cono.any():
        return None
    desvio, cand = desvio[en_cono], cand[en_cono]
    # Agrupar por ángulo: cada grupo es el corte del anillo con un trazo.
    orden = np.argsort(desvio)
    desvio, cand = desvio[orden], cand[orden]
    cortes = np.flatnonzero(np.diff(desvio) > 1.5 / radio) + 1
    grupos = np.split(np.arange(len(desvio)), cortes)
    mejor = min(grupos, key=lambda g: abs(desvio[g].mean()))
    ancho_grupo = (desvio[mejor[-1]] - desvio[mejor[0]]) * radio
    if ancho_grupo > ancho_cruce:
        # Grupo demasiado ancho: cruce con otra curva. Se sigue recto.
        return p + radio * np.array([np.cos(direccion), np.sin(direccion)])
    return cand[mejor].mean(axis=0)


def _recorrer(mascara: np.ndarray, inicio, fin, par: Parametros) -> tuple[list[np.ndarray], bool]:
    """Recorre el trazo desde `inicio` hacia `fin` (en x creciente o decreciente).

    Devuelve los puntos y si llegó a la columna de `fin` sin perderse.
    """
    p = np.array(inicio, dtype=float)
    fin = np.array(fin, dtype=float)
    sentido = 1.0 if fin[0] >= p[0] else -1.0
    puntos = [p]
    direccion = np.arctan2(fin[1] - p[1], fin[0] - p[0])
    cono = CONO_INICIAL
    max_pasos = int(4 * np.hypot(*(fin - p)) / par.paso) + 10
    for _ in range(max_pasos):
        if sentido * (p[0] - fin[0]) >= 0:
            break
        siguiente = None
        for radio in range(par.paso, par.hueco_maximo + 1):
            if radio == par.paso:
                cono_radio = cono
            elif radio <= par.hueco_corto:
                cono_radio = min(cono, CONO_HUECO)
            else:
                cono_radio = CONO_HUECO_LARGO
            siguiente = _paso(mascara, p, direccion, radio, cono_radio, par.ancho_cruce)
            if siguiente is not None:
                break
        # En tramos casi verticales un paso puede no avanzar en x; solo retroceder es perderse.
        if siguiente is None or sentido * (siguiente[0] - p[0]) < -1:
            return puntos, False  # perdido: sin trazo hacia delante
        p = siguiente
        puntos.append(p)
        ref = puntos[max(0, len(puntos) - 1 - PASOS_DIRECCION)]
        direccion = np.arctan2(p[1] - ref[1], p[0] - ref[0])
        cono = CONO
    return puntos, True


def _error_llegada(puntos: list[np.ndarray], completo: bool, destino, tolerancia: float) -> float:
    """Distancia en px entre el recorrido y la semilla de destino (inf si se perdió lejos)."""
    destino = np.asarray(destino, dtype=float)
    ultimo = puntos[-1]
    if not completo:
        d = float(np.hypot(*(destino - ultimo)))
        return d if d <= tolerancia else np.inf
    xs = np.array([q[0] for q in puntos])
    ys = np.array([q[1] for q in puntos])
    orden = np.argsort(xs)
    return float(abs(np.interp(destino[0], xs[orden], ys[orden]) - destino[1]))


def _seguir_tramo(
    mascara: np.ndarray, inicio, fin, par: Parametros, eje: str = "x"
) -> tuple[list[np.ndarray], str | None]:
    """Recorre de `inicio` a `fin`; si no llega bien, prueba en sentido contrario.

    Si ninguno de los dos recorridos une las semillas, se combinan: la ida a la
    izquierda del punto donde se perdió la vuelta y la vuelta a su derecha
    (cada recorrido es fiable cerca de su semilla de partida).

    Devuelve los puntos en x creciente y un aviso (None si el tramo es fiable).
    """
    ida, ok_ida = _recorrer(mascara, inicio, fin, par)
    if _error_llegada(ida, ok_ida, fin, par.tolerancia) <= par.tolerancia:
        return ida, None
    vuelta, ok_vuelta = _recorrer(mascara, fin, inicio, par)
    if _error_llegada(vuelta, ok_vuelta, inicio, par.tolerancia) <= par.tolerancia:
        return vuelta[::-1], None

    vuelta = vuelta[::-1]
    x_corte = vuelta[0][0]
    izquierda = [q for q in ida if q[0] < x_corte]
    puntos = izquierda + vuelta
    xs_ida = np.array([q[0] for q in ida])
    if xs_ida.max() >= x_corte:
        ys_ida = np.array([q[1] for q in ida])
        orden = np.argsort(xs_ida)
        y_ida = np.interp(x_corte, xs_ida[orden], ys_ida[orden])
        if abs(y_ida - vuelta[0][1]) <= par.tolerancia:
            return puntos, None  # ida y vuelta coinciden en la unión
        return puntos, (
            f"el seguimiento no une las semillas sin ambigüedad cerca de {eje}={x_corte:.0f} px "
            "(posible cruce con otra curva). Revisa ese tramo o añade una semilla tras el cruce."
        )
    return puntos, (
        f"hay un hueco sin trazo entre {eje}={xs_ida.max():.0f} y {eje}={x_corte:.0f} px. "
        "Revisa ese tramo o añade una semilla dentro del hueco."
    )


def seguir_curva(
    mascara: np.ndarray, semillas, grosor: float | None = None, funcion_de: str = "x"
) -> Seguimiento:
    """Recorre la curva que pasa por las semillas.

    Con `funcion_de="x"` devuelve un y por columna de píxel (x creciente); con
    "y", un x por fila (y creciente). Las coordenadas devueltas son siempre (x, y)
    de la imagen.
    `grosor`: grosor del trazo en px; si es None se estima alrededor de las semillas.
    """
    if funcion_de not in ("x", "y"):
        raise ValueError('funcion_de debe ser "x" o "y".')
    if funcion_de == "x":
        return _seguir(mascara, semillas, grosor, "x")
    seg = _seguir(mascara.T, [(y, x) for x, y in semillas], grosor, "y")
    return Seguimiento(seg.y, seg.x, seg.avisos)


def _seguir(mascara: np.ndarray, semillas, grosor: float | None, eje: str) -> Seguimiento:
    """Seguimiento con la variable independiente en la primera coordenada (columna)."""
    s = sorted((float(x), float(y)) for x, y in semillas)
    if len(s) < 2:
        raise ValueError("Se necesitan al menos 2 semillas (inicio y fin de la curva).")
    if len({round(x) for x, _ in s}) != len(s):
        linea = "columna" if eje == "x" else "fila"
        raise ValueError(f"Dos semillas están en la misma {linea}; la curva debe ser función de {eje}.")
    par = Parametros.para_grosor(grosor if grosor is not None else grosor_local(mascara, s))
    s = [ajustar_semilla(mascara, x, y, par.radio_semilla) for x, y in s]

    avisos = []
    puntos = []
    for i, (inicio, fin) in enumerate(zip(s[:-1], s[1:])):
        tramo, aviso = _seguir_tramo(mascara, inicio, fin, par, eje)
        if aviso:
            avisos.append(f"Tramo {i + 1}: {aviso}")
        puntos += [q for q in tramo if inicio[0] <= q[0] <= fin[0]]

    xy = np.array(puntos)
    # Un valor por columna (media de los puntos que caen en ella).
    columnas = np.round(xy[:, 0]).astype(int)
    xu, inversa = np.unique(columnas, return_inverse=True)
    yu = np.bincount(inversa, weights=xy[:, 1]) / np.bincount(inversa)
    return Seguimiento(xu.astype(float), yu, avisos)


def quitar_atipicos(x: np.ndarray, y: np.ndarray, ventana: int = 9, k: float = 4.0):
    """Elimina puntos que se apartan de la mediana móvil más de k·MAD (mín. 1.5 px)."""
    if len(y) < ventana:
        return x, y
    suave = median_filter(y, size=ventana, mode="nearest")
    residuo = np.abs(y - suave)
    mad = np.median(residuo)
    limite = max(k * 1.4826 * mad, 1.5)
    ok = residuo <= limite
    return x[ok], y[ok]


def remuestrear(x: np.ndarray, y: np.ndarray, n: int = PUNTOS_POR_DEFECTO):
    """n puntos equiespaciados en x por interpolación lineal (x creciente)."""
    orden = np.argsort(x)
    x, y = x[orden], y[orden]
    xn = np.linspace(x[0], x[-1], n)
    return xn, np.interp(xn, x, y)


def digitalizar(
    mascara: np.ndarray,
    semillas,
    eje_x: Eje,
    eje_y: Eje,
    magnitud: Magnitud,
    diametro: float | None = None,
    n: int = PUNTOS_POR_DEFECTO,
    grosor: float | None = None,
    funcion_de: str = "x",
    nivel: float | None = None,
    rama: Rama | None = None,
) -> tuple[CurvaDigitalizada, list[str]]:
    """Sigue la curva, la limpia, la remuestrea y la pasa a unidades de los ejes.

    Para una curva de igual rendimiento: `funcion_de="y"`, `nivel` = η de la
    curva y `rama` izquierda/derecha.
    Devuelve la curva y los avisos del seguimiento (vacío si todo fue bien).
    """
    seg = seguir_curva(mascara, semillas, grosor, funcion_de)
    if funcion_de == "x":
        px, py = quitar_atipicos(seg.x, seg.y)
        px, py = remuestrear(px, py, n)
    else:
        py, px = quitar_atipicos(seg.y, seg.x)
        py, px = remuestrear(py, px, n)
    curva = CurvaDigitalizada(
        magnitud=magnitud,
        eje_x=eje_x.nombre,
        eje_y=eje_y.nombre,
        x=np.asarray(valor_desde_pixel(eje_x, px), dtype=float),
        y=np.asarray(valor_desde_pixel(eje_y, py), dtype=float),
        diametro=diametro,
        funcion_de=funcion_de,
        nivel=nivel,
        rama=rama,
    )
    return curva, seg.avisos
