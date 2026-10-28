import cv2
import numpy as np

from bombas.core.calibracion import pixel_desde_valor
from bombas.core.preprocesado import grosor_tipico, preprocesar, reducir_mascara, vista_previa_mascara
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


def test_reducir_mascara_conserva_trazos_finos():
    m = np.zeros((7, 7), bool)
    m[0, 0] = m[3, 4] = m[6, 6] = True
    assert reducir_mascara(m, 3).tolist() == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_vista_previa_se_parece_a_la_mascara_completa():
    img = cv2.resize(grafico(), None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    recuadro = tuple(v * 3 for v in RECUADRO)
    previa, factor = vista_previa_mascara(img, recuadro, lado_max=700)
    assert factor == 4 and max(previa.shape) <= 700
    x0, y0, x1, y1 = recuadro
    completa = reducir_mascara(preprocesar(img, recuadro)[y0 : y1 + 1, x0 : x1 + 1], factor)
    # Casi todo el trazo de la vista previa está (±1 px) en la máscara completa reducida.
    cerca = cv2.dilate(completa.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    assert (previa & cerca).sum() / previa.sum() > 0.9


def test_vista_previa_responde_al_umbral():
    img = grafico()
    claro, _ = vista_previa_mascara(img, RECUADRO, umbral=60)
    oscuro, _ = vista_previa_mascara(img, RECUADRO, umbral=180)
    assert oscuro.sum() > claro.sum()
