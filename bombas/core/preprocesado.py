"""Limpieza de la imagen: deja una máscara binaria con el trazo de las curvas.

Pasos (todos de visión clásica con OpenCV):
1. Umbral de oscuridad: solo el trazo oscuro; la cuadrícula gris clara queda fuera.
2. Descartar píxeles de color (anotaciones rojas, etc.): las curvas son negras.
3. Recortar al recuadro de trazado del panel.
4. Borrar líneas rectas largas horizontales y verticales (cuadrícula negra, marco).
5. Borrar cajas de texto rectangulares y los componentes muy pequeños.

Supuestos y límites:
- Las curvas son oscuras y casi negras; una curva de color claro no se detecta.
- Al borrar la cuadrícula se conservan los píxeles donde el trazo es más
  grueso que la línea (una curva que la cruza o va encima). Si la curva no es
  más gruesa que la cuadrícula, ese tramo se pierde; el seguidor de curvas
  (extraccion.py) salta huecos de hasta 60 px.
- Un tramo de curva recto y horizontal/vertical que ocupe más de
  `fraccion_linea` del recuadro se confundiría con la cuadrícula.
"""

from __future__ import annotations

import cv2
import numpy as np

UMBRAL_OSCURO = 100
SATURACION_MAXIMA = 80
FRACCION_SEGMENTO = 0.1
FRACCION_LINEA = 0.4


def mascara_oscura(
    imagen: np.ndarray, umbral: int = UMBRAL_OSCURO, saturacion_maxima: int = SATURACION_MAXIMA
) -> np.ndarray:
    """Píxeles oscuros y sin color (bool)."""
    gris = cv2.cvtColor(imagen, cv2.COLOR_RGB2GRAY)
    mascara = gris < umbral
    if saturacion_maxima is not None:
        hsv = cv2.cvtColor(imagen, cv2.COLOR_RGB2HSV)
        # La saturación de un píxel casi negro es ruidosa: se exige además algo de brillo.
        coloreado = (hsv[..., 1] > saturacion_maxima) & (hsv[..., 2] > 60)
        mascara &= ~coloreado
    return mascara


def lineas_rectas(
    mascara: np.ndarray,
    ancho: int,
    alto: int,
    fraccion_segmento: float = FRACCION_SEGMENTO,
    fraccion_linea: float = FRACCION_LINEA,
) -> tuple[np.ndarray, np.ndarray]:
    """Bandas (horizontales, verticales) que cubren las líneas de la cuadrícula y el marco.

    Se buscan segmentos rectos de al menos `fraccion_segmento` del panel y se
    conservan solo los de filas/columnas donde suman `fraccion_linea` del panel:
    una línea de la cuadrícula interrumpida por cajas de texto sigue sumando
    mucho, mientras que un tramo casi plano de una curva no.

    Se trabaja sobre la máscara dilatada 1 px porque el antialias reparte a veces
    una línea de la cuadrícula entre dos filas/columnas alternas.
    """
    m = cv2.dilate(mascara.astype(np.uint8), np.ones((3, 3), np.uint8))
    largo_h = max(5, int(fraccion_segmento * ancho))
    largo_v = max(5, int(fraccion_segmento * alto))
    horizontales = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((1, largo_h), np.uint8)).astype(bool)
    verticales = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((largo_v, 1), np.uint8)).astype(bool)
    horizontales &= (horizontales.sum(axis=1) >= fraccion_linea * ancho)[:, None]
    verticales &= (verticales.sum(axis=0) >= fraccion_linea * alto)[None, :]
    return horizontales, verticales


def borrar_cuadricula(
    mascara: np.ndarray, ancho: int, alto: int, fraccion_linea: float = FRACCION_LINEA
) -> np.ndarray:
    """Borra las líneas de la cuadrícula sin borrar las curvas que pasan por encima.

    Dentro de la banda de cada línea solo se borran los píxeles cuyo trazo, medido
    en perpendicular a la línea, no es más grueso que la propia línea. Donde una
    curva cruza o se superpone a la línea el trazo es más grueso y se conserva.
    """
    horizontales, verticales = lineas_rectas(mascara, ancho, alto, fraccion_linea=fraccion_linea)
    borrar = np.zeros_like(mascara)
    for banda, eje_perpendicular in ((horizontales, 0), (verticales, 1)):
        en_linea = mascara & banda
        if not en_linea.any():
            continue
        grosor = _longitud_tramos(mascara, eje_perpendicular)
        grosor_linea = np.median(grosor[en_linea])
        borrar |= en_linea & (grosor <= grosor_linea)
    return mascara & ~borrar


def cajas_texto(
    mascara: np.ndarray, lado_min: int = 12, lado_max: int = 250, margen: int = 2
) -> list[tuple[int, int, int, int]]:
    """Rectángulos (x0, y0, x1, y1) de cajas de texto con marco.

    Se detecta el hueco interior del marco (contorno hijo), que es un rectángulo
    aunque la caja toque una curva por fuera.
    """
    contornos, jerarquia = cv2.findContours(
        mascara.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    cajas = []
    if jerarquia is None:
        return cajas
    for contorno, (_, _, _, padre) in zip(contornos, jerarquia[0]):
        if padre < 0:
            continue  # solo huecos interiores
        x, y, w, h = cv2.boundingRect(contorno)
        if not (lado_min <= w <= lado_max and lado_min // 2 <= h <= lado_max) or w < h:
            continue
        # Hueco rectangular: ocupa casi todo su rectángulo envolvente.
        if cv2.contourArea(contorno) < 0.85 * w * h:
            continue
        cajas.append((x - margen, y - margen, x + w + margen, y + h + margen))
    return cajas


def _longitud_tramos(mascara: np.ndarray, eje: int) -> np.ndarray:
    """Para cada píxel True, longitud del tramo contiguo de True que lo contiene a lo largo de `eje`."""
    m = np.ascontiguousarray(np.moveaxis(mascara, eje, -1), dtype=bool)
    # Cada tramo recibe un identificador único (inicios acumulados) y se cuenta su tamaño.
    inicio = m.copy()
    inicio[..., 1:] &= ~m[..., :-1]
    ids = np.cumsum(inicio.ravel(), dtype=np.int32) * m.ravel()
    tamano = np.bincount(ids)
    tamano[0] = 0
    largo = tamano[ids].reshape(m.shape)
    return np.moveaxis(largo, -1, eje)


def _tramos_vh(mascara: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return _longitud_tramos(mascara, 0), _longitud_tramos(mascara, 1)


def grosor_tipico(mascara: np.ndarray, tramos=None) -> float:
    """Grosor mediano del trazo en píxeles (menor tramo horizontal/vertical por píxel)."""
    if not mascara.any():
        return 0.0
    vertical, horizontal = tramos if tramos is not None else _tramos_vh(mascara)
    return float(np.median(np.minimum(vertical, horizontal)[mascara]))


def quitar_trazos_finos(mascara: np.ndarray, grosor_min: int, tramos=None) -> np.ndarray:
    """Borra líneas finas alineadas con los ejes (marcos de cajas de texto, guías).

    Un píxel se borra si es más fino que `grosor_min` en una dirección y forma
    parte de un tramo recto largo en la otra. Los tramos inclinados de las
    curvas son cortos en ambas direcciones y se conservan, aunque sean finos.
    """
    if grosor_min <= 1:
        return mascara
    vertical, horizontal = tramos if tramos is not None else _tramos_vh(mascara)
    largo = 3 * grosor_min + 2
    fino_horizontal = (vertical < grosor_min) & (horizontal >= largo)
    fino_vertical = (horizontal < grosor_min) & (vertical >= largo)
    return mascara & ~(fino_horizontal | fino_vertical)


def quitar_componentes_pequenos(mascara: np.ndarray, lado_min: int) -> np.ndarray:
    """Quita componentes cuyo rectángulo envolvente mide menos de `lado_min` en ambos lados.

    Elimina letras y números sueltos; un trozo de curva entre dos líneas de la
    cuadrícula es más largo que eso.
    """
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), connectivity=8)
    lado = np.maximum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT])
    grandes = lado >= lado_min
    grandes[0] = False
    return grandes[etiquetas]


def limpiar(
    m: np.ndarray,
    fraccion_linea: float = FRACCION_LINEA,
    fraccion_texto: float = 0.025,
    grosor_min: int | None = None,
) -> np.ndarray:
    """Pasos 4 y 5 sobre la máscara oscura de un recuadro: cuadrícula, cajas, marcos y texto."""
    alto, ancho = m.shape
    m = borrar_cuadricula(m, ancho - 1, alto - 1, fraccion_linea)
    for cx0, cy0, cx1, cy1 in cajas_texto(m):
        m[max(cy0, 0) : cy1 + 1, max(cx0, 0) : cx1 + 1] = False
    tramos = _tramos_vh(m)
    if grosor_min is None:
        grosor_min = max(2, round(0.6 * grosor_tipico(m, tramos)))
    m = quitar_trazos_finos(m, grosor_min, tramos)
    lado_texto = max(6, int(fraccion_texto * (min(ancho, alto) - 1)))
    return quitar_componentes_pequenos(m, lado_texto)


def preprocesar(
    imagen: np.ndarray,
    recuadro: tuple[int, int, int, int],
    umbral: int = UMBRAL_OSCURO,
    fraccion_linea: float = FRACCION_LINEA,
    fraccion_texto: float = 0.025,
    grosor_min: int | None = None,
) -> np.ndarray:
    """Máscara (bool, mismo tamaño que la imagen) con el trazo de las curvas del panel.

    `fraccion_texto`: los componentes más pequeños que esa fracción del lado
    menor del recuadro se consideran texto y se borran.
    `grosor_min`: trazos más finos se borran (marcos de cajas, guías). Si es
    None se estima como el 60 % del grosor típico del trazo, con mínimo 2 px.
    """
    x0, y0, x1, y1 = recuadro
    # Se trabaja solo dentro del recuadro (bordes incluidos); fuera, la máscara es False.
    m = mascara_oscura(imagen[y0 : y1 + 1, x0 : x1 + 1], umbral)
    mascara = np.zeros(imagen.shape[:2], dtype=bool)
    mascara[y0 : y1 + 1, x0 : x1 + 1] = limpiar(m, fraccion_linea, fraccion_texto, grosor_min)
    return mascara


def reducir_mascara(mascara: np.ndarray, factor: int) -> np.ndarray:
    """Reduce la máscara `factor` veces: un píxel reducido es True si alguno de su bloque lo es.

    Así un trazo fino no desaparece al reducir (con un promedio se aclararía).
    """
    if factor <= 1:
        return mascara
    alto, ancho = mascara.shape
    a, b = -(-alto // factor) * factor, -(-ancho // factor) * factor
    relleno = np.zeros((a, b), dtype=np.uint8)
    relleno[:alto, :ancho] = mascara * np.uint8(255)  # 255: el promedio de un píxel en el bloque no se redondea a 0
    # INTER_AREA con factor entero promedia cada bloque: media > 0 ⇔ algún píxel True.
    return cv2.resize(relleno, (b // factor, a // factor), interpolation=cv2.INTER_AREA) > 0


def vista_previa_mascara(
    imagen: np.ndarray,
    recuadro: tuple[int, int, int, int],
    umbral: int = UMBRAL_OSCURO,
    lado_max: int = 700,
) -> tuple[np.ndarray, int]:
    """Máscara aproximada y rápida del recuadro, para ajustar el umbral en vivo.

    El umbral se aplica a resolución completa (así se comporta igual que en
    `preprocesar`) y la limpieza se hace sobre la máscara reducida para que el
    lado mayor no pase de `lado_max`. Devuelve la máscara del recuadro (no de la
    imagen entera) y el factor de reducción. Es solo para visualizar: la
    extracción usa siempre `preprocesar` a resolución completa.
    """
    x0, y0, x1, y1 = recuadro
    m = mascara_oscura(imagen[y0 : y1 + 1, x0 : x1 + 1], umbral)
    factor = max(1, -(-max(m.shape) // lado_max))
    return limpiar(reducir_mascara(m, factor)), factor
