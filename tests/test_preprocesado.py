import numpy as np

from bombas.core.calibracion import pixel_desde_valor
from bombas.core.preprocesado import grosor_tipico, preprocesar
from sinteticos import COEF_H, EJE_H, EJE_Q, RECUADRO, grafico


def test_borra_cuadricula_caja_texto_y_color():
    m = preprocesar(grafico(), RECUADRO)
    assert not m[350:450, 465:476].any()  # línea mayor vertical (x=470), lejos de las curvas
    assert not m[395:405, 100:200].any()  # cuadrícula menor gris y línea mayor horizontal (y=400)
    assert not m[515:550, 555:685].any()  # caja de texto (marco y letras)
    assert not m[555:605, 295:345].any()  # anotación roja
    assert not m[:RECUADRO[1]].any() and not m[RECUADRO[3] + 1 :].any()  # fuera del recuadro


def test_conserva_la_curva():
    m = preprocesar(grafico(), RECUADRO)
    q = np.linspace(50, 2700, 200)
    xs = np.round(pixel_desde_valor(EJE_Q, q)).astype(int)
    ys = np.round(pixel_desde_valor(EJE_H, np.polyval(COEF_H, q))).astype(int)
    cerca = [m[y - 2 : y + 3, x].any() for x, y in zip(xs, ys)]
    # Solo se pierden los pocos píxeles donde la curva cruza la cuadrícula mayor.
    assert np.mean(cerca) > 0.9


def test_grosor_tipico():
    m = np.zeros((50, 50), bool)
    m[10:13, 5:45] = True  # trazo horizontal de 3 px
    assert grosor_tipico(m) == 3
