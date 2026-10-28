import cv2
import numpy as np
import pytest

from bombas.core.calibracion import (
    enderezar_imagen,
    enderezar_puntos,
    estimar_inclinacion,
    pixel_desde_valor,
    valor_desde_pixel,
)
from bombas.core.modelos import Eje, Escala, Orientacion


def eje_x():
    # Como en curvaBOMBA1.png: 0 m³/h en x=117 px, 3500 m³/h en x=708 px.
    return Eje("Q", "m³/h", Orientacion.HORIZONTAL, p1=117, v1=0, p2=708, v2=3500)


def eje_y():
    # Eje vertical: el valor crece hacia arriba, el píxel hacia abajo.
    return Eje("H", "m", Orientacion.VERTICAL, p1=757, v1=0, p2=238, v2=250)


def test_lineal_extremos_y_punto_medio():
    e = eje_x()
    assert valor_desde_pixel(e, 117) == pytest.approx(0)
    assert valor_desde_pixel(e, 708) == pytest.approx(3500)
    assert valor_desde_pixel(e, (117 + 708) / 2) == pytest.approx(1750)


def test_eje_vertical_invertido():
    e = eje_y()
    assert valor_desde_pixel(e, 238) == pytest.approx(250)
    assert valor_desde_pixel(e, 757 - (757 - 238) * 0.4) == pytest.approx(100)


def test_ida_y_vuelta_lineal_y_log():
    lin = eje_x()
    log = Eje("Q", "GPM", Orientacion.HORIZONTAL, p1=100, v1=10, p2=500, v2=1000, escala=Escala.LOG)
    for e, valores in [(lin, [0, 123.4, 3500]), (log, [10, 50, 1000])]:
        px = pixel_desde_valor(e, np.array(valores))
        np.testing.assert_allclose(valor_desde_pixel(e, px), valores)


def test_log_decada_intermedia():
    e = Eje("Q", "GPM", Orientacion.HORIZONTAL, p1=100, v1=10, p2=500, v2=1000, escala=Escala.LOG)
    assert valor_desde_pixel(e, 300) == pytest.approx(100)


def test_la_unidad_no_se_altera():
    e = eje_x()
    valor_desde_pixel(e, 400)
    assert e.unidad == "m³/h"


@pytest.mark.parametrize(
    "eje",
    [
        Eje("Q", "L/s", Orientacion.HORIZONTAL, p1=10, v1=0, p2=10, v2=5),
        Eje("Q", "L/s", Orientacion.HORIZONTAL, p1=10, v1=5, p2=20, v2=5),
        Eje("Q", "L/s", Orientacion.HORIZONTAL, p1=10, v1=0, p2=20, v2=5, escala=Escala.LOG),
    ],
)
def test_ejes_invalidos(eje):
    with pytest.raises(ValueError):
        valor_desde_pixel(eje, 15)


def cuadricula(tamano=600, paso=50):
    img = np.full((tamano, tamano, 3), 255, np.uint8)
    for p in range(paso, tamano - paso + 1, paso):
        cv2.line(img, (paso, p), (tamano - paso, p), (0, 0, 0), 2)
        cv2.line(img, (p, paso), (p, tamano - paso), (0, 0, 0), 2)
    return img


def test_imagen_recta_sin_inclinacion():
    assert estimar_inclinacion(cuadricula()) == pytest.approx(0, abs=0.2)


@pytest.mark.parametrize("giro", [-3.0, -1.0, 2.0])
def test_estimar_y_corregir_inclinacion(giro):
    img = cuadricula()
    inclinada = enderezar_imagen(img, giro)  # rotar `giro` grados
    angulo = estimar_inclinacion(inclinada)
    assert angulo == pytest.approx(-giro, abs=0.2)
    assert estimar_inclinacion(enderezar_imagen(inclinada, angulo)) == pytest.approx(0, abs=0.2)


def test_enderezar_puntos_coincide_con_la_imagen():
    tam = (600, 600)
    p = np.array([[300.0, 300.0], [100.0, 300.0]])
    q = enderezar_puntos(p, 90, tam)
    # El centro no se mueve; un punto a su izquierda sube al rotar 90° antihorario.
    np.testing.assert_allclose(q[0], [300, 300], atol=1e-9)
    np.testing.assert_allclose(q[1], [300, 500], atol=1e-9)
