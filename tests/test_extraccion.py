import cv2
import numpy as np
import pytest

from bombas.core.ajuste import ajustar
from bombas.core.extraccion import digitalizar, seguir_curva
from bombas.core.modelos import Eje, Magnitud
from bombas.core.preprocesado import preprocesar
from sinteticos import (
    COEF_ETA,
    COEF_H,
    EJE_ETA,
    EJE_H,
    EJE_Q,
    Q_FIN,
    RECUADRO,
    grafico,
    semilla,
)

Q_PRUEBA = np.linspace(20, Q_FIN - 20, 100)


@pytest.fixture(scope="module")
def mascara():
    return preprocesar(grafico(), RECUADRO)


def error_maximo(curva_ajustada, coef):
    return np.abs(curva_ajustada.evaluar(Q_PRUEBA) - np.polyval(coef, Q_PRUEBA)).max()


def test_altura_con_dos_semillas(mascara):
    semillas = [semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)]
    curva, avisos = digitalizar(mascara, semillas, EJE_Q, EJE_H, Magnitud.ALTURA, diametro=738)
    assert avisos == []
    assert curva.diametro == 738
    c = ajustar(curva, 3)
    assert error_maximo(c, COEF_H) < 0.01 * 250  # < 1 % del eje
    assert c.x_min < 30 and c.x_max > Q_FIN - 30


def test_eficiencia_empinada_que_cruza_la_altura(mascara):
    semillas = [semilla(COEF_ETA, EJE_ETA, 5), semilla(COEF_ETA, EJE_ETA, Q_FIN)]
    curva, avisos = digitalizar(mascara, semillas, EJE_Q, EJE_ETA, Magnitud.EFICIENCIA)
    assert avisos == []
    assert error_maximo(ajustar(curva, 2), COEF_ETA) < 0.01 * 100


def test_semillas_imprecisas_se_ajustan_al_trazo(mascara):
    (xa, ya), (xb, yb) = semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)
    curva, avisos = digitalizar(mascara, [(xa + 1, ya + 3), (xb - 1, yb - 3)], EJE_Q, EJE_H, Magnitud.ALTURA)
    assert avisos == []
    assert error_maximo(ajustar(curva, 3), COEF_H) < 0.01 * 250


def test_salta_un_hueco(mascara):
    m = mascara.copy()
    xa, _ = semilla(COEF_H, EJE_H, 1200)
    m[:, int(xa) : int(xa) + 40] = False  # 40 px sin trazo
    curva, avisos = digitalizar(
        m, [semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)], EJE_Q, EJE_H, Magnitud.ALTURA
    )
    assert avisos == []
    assert error_maximo(ajustar(curva, 3), COEF_H) < 0.01 * 250


def test_avisa_si_las_semillas_no_estan_en_la_misma_curva(mascara):
    # H y η no se cruzan antes de Q≈1330: no hay camino entre estas semillas.
    semillas = [semilla(COEF_H, EJE_H, 0), semilla(COEF_ETA, EJE_ETA, 800)]
    assert seguir_curva(mascara, semillas).avisos


def test_avisa_si_el_hueco_es_demasiado_largo(mascara):
    m = mascara.copy()
    xa, _ = semilla(COEF_H, EJE_H, 1200)
    m[:, int(xa) : int(xa) + 250] = False  # mucho más que el salto máximo para este grosor
    s = seguir_curva(m, [semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)])
    assert any("hueco" in a for a in s.avisos)


def test_un_valor_por_columna_y_x_creciente(mascara):
    s = seguir_curva(mascara, [semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)])
    assert np.all(np.diff(s.x) > 0)


def test_independiente_de_la_resolucion():
    """La misma imagen a 3× (trazos de ~9 px, como un PDF a 300 DPI) da el mismo resultado."""
    k = 3
    img = cv2.resize(grafico(), None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    recuadro = tuple(v * k for v in RECUADRO)
    escalar = lambda e: Eje(e.nombre, e.unidad, e.orientacion, e.p1 * k, e.v1, e.p2 * k, e.v2)
    m = preprocesar(img, recuadro)
    for coef, eje_y, grado, q0 in ((COEF_H, EJE_H, 3, 0), (COEF_ETA, EJE_ETA, 2, 5)):
        semillas = [tuple(v * k for v in semilla(coef, eje_y, q)) for q in (q0, Q_FIN)]
        curva, avisos = digitalizar(m, semillas, escalar(EJE_Q), escalar(eje_y), Magnitud.ALTURA)
        assert avisos == []
        assert error_maximo(ajustar(curva, grado), coef) < 0.01 * (eje_y.v2 - eje_y.v1)


@pytest.mark.parametrize("semillas", [[(100, 200)], [(100, 200), (100, 300)]])
def test_semillas_invalidas(mascara, semillas):
    with pytest.raises(ValueError):
        seguir_curva(mascara, semillas)


def test_funcion_de_y_equivale_a_trasponer(mascara):
    semillas = [semilla(COEF_H, EJE_H, 0), semilla(COEF_H, EJE_H, Q_FIN)]
    por_columnas = seguir_curva(mascara, semillas)
    por_filas = seguir_curva(mascara.T, [(y, x) for x, y in semillas], funcion_de="y")
    np.testing.assert_allclose(por_filas.y, por_columnas.x)
    np.testing.assert_allclose(por_filas.x, por_columnas.y)
    assert np.all(np.diff(por_filas.y) > 0)
