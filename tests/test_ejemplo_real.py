"""Regresión con una curva real de fabricante (tests/datos/curvaBOMBA1.png).

Las referencias de H 738 mm y η vienen de la digitalización manual
viejo/Curva_Bomba_Centrifuga_Digitalizada_738mm_V6.xlsx. Se comparan en
Q = 500..2700 m³/h: Q = 0 queda fuera del tramo digitalizado (la curva empieza
en Q ≈ 30 m³/h) y sería extrapolación.
"""

from pathlib import Path

import numpy as np
import pytest

from bombas.core.ajuste import ajustar
from bombas.core.carga import cargar_archivo
from bombas.core.extraccion import digitalizar
from bombas.core.modelos import Eje, Magnitud, Orientacion
from bombas.core.preprocesado import preprocesar

IMAGEN = Path(__file__).parent / "datos" / "curvaBOMBA1.png"

# Calibración leída de la imagen (píxeles de las líneas mayores de la cuadrícula).
EJE_Q = Eje("Q", "m³/h", Orientacion.HORIZONTAL, 115, 0, 707, 3500)
EJE_H = Eje("H", "m", Orientacion.VERTICAL, 758, 0, 239, 250)
EJE_ETA = Eje("η", "%", Orientacion.VERTICAL, 758, 0, 239, 100)
EJE_NPSH = Eje("NPSH", "m", Orientacion.VERTICAL, 654.5, 5, 550.5, 10)
EJE_P = Eje("P", "kW", Orientacion.VERTICAL, 217, 0, 31.5, 1500)
PANEL_H = (115, 239, 707, 758)
PANEL_P = (115, 31, 707, 217)

# (magnitud, diámetro, eje y, panel, semillas en px, grado)
CURVAS = {
    "H768": (Magnitud.ALTURA, 768, EJE_H, PANEL_H, [(118, 300.5), (600, 426)], 3),
    "H738": (Magnitud.ALTURA, 738, EJE_H, PANEL_H, [(120, 334.5), (577, 452)], 3),
    "H608": (Magnitud.ALTURA, 608, EJE_H, PANEL_H, [(118, 465.5), (489, 561)], 3),
    "eta": (Magnitud.EFICIENCIA, None, EJE_ETA, PANEL_H, [(118, 747), (578, 322)], 4),
    "npsh": (Magnitud.NPSH, None, EJE_NPSH, PANEL_H, [(272, 658.5), (578, 491.5)], 3),
    "pot": (Magnitud.POTENCIA, None, EJE_P, PANEL_P, [(118, 161.5), (578, 56.5)], 3),
}


@pytest.fixture(scope="module")
def ajustes():
    imagen = cargar_archivo(IMAGEN)
    mascaras = {panel: preprocesar(imagen, panel) for panel in (PANEL_H, PANEL_P)}
    resultado = {}
    for nombre, (magnitud, diametro, eje_y, panel, semillas, grado) in CURVAS.items():
        curva, avisos = digitalizar(mascaras[panel], semillas, EJE_Q, eje_y, magnitud, diametro)
        resultado[nombre] = (ajustar(curva, grado, EJE_Q.unidad, eje_y.unidad), avisos)
    return resultado


@pytest.mark.parametrize("nombre", list(CURVAS))
def test_todas_las_curvas_sin_avisos(ajustes, nombre):
    curva, avisos = ajustes[nombre]
    assert avisos == []
    assert curva.r2 > 0.999


Q_REF = np.array([500, 1000, 1500, 2000, 2500, 2700])


def test_h738_frente_a_referencia_manual(ajustes):
    h_ref = np.array([202.42, 196.93, 188.26, 175.26, 156.78, 147.60])
    curva, _ = ajustes["H738"]
    np.testing.assert_allclose(curva.evaluar(Q_REF), h_ref, atol=1.0)  # 0,4 % del eje
    assert curva.etiqueta == "H – 738 mm"
    assert (curva.unidad_x, curva.unidad_y) == ("m³/h", "m")


def test_eficiencia_frente_a_referencia_manual(ajustes):
    eta_ref = np.array([46.85, 72.30, 83.82, 87.02, 85.69, 84.39])
    curva, _ = ajustes["eta"]
    np.testing.assert_allclose(curva.evaluar(Q_REF), eta_ref, atol=1.0)


def test_orden_de_las_curvas_por_diametro(ajustes):
    q = np.linspace(100, 2200, 20)
    h768, h738, h608 = (ajustes[k][0].evaluar(q) for k in ("H768", "H738", "H608"))
    assert np.all(h768 > h738) and np.all(h738 > h608)


def test_valores_leidos_de_la_imagen(ajustes):
    eta, _ = ajustes["eta"]
    q = np.linspace(1500, 2700, 200)
    assert 85 <= eta.evaluar(q).max() <= 89  # máximo ≈ 87 % en la imagen
    assert 1900 <= q[np.argmax(eta.evaluar(q))] <= 2300
    pot, _ = ajustes["pot"]
    assert 430 <= pot.evaluar(20) <= 470  # ≈ 450 kW a caudal nulo
    assert 1270 <= pot.evaluar(2720) <= 1310  # ≈ 1300 kW al final
    npsh, _ = ajustes["npsh"]
    assert 4.5 <= npsh.evaluar(1000) <= 5.2 and 12.0 <= npsh.evaluar(2720) <= 12.8
