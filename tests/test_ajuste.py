import numpy as np
import pytest

from bombas.core.ajuste import ajustar, invertir
from bombas.core.modelos import Bomba, CurvaDigitalizada, Magnitud

# Curva H(Q) cúbica parecida a la de 738 mm de curvaBOMBA1.png (Q en m³/h, H en m).
COEF_H = np.array([-2.0e-9, -4.0e-6, -2.0e-3, 204.0])


def curva_h(n=40, ruido=0.0, diametro=738.0, semilla=0):
    q = np.linspace(0, 2750, n)
    h = np.polyval(COEF_H, q)
    if ruido:
        h = h + np.random.default_rng(semilla).normal(0, ruido, n)
    return CurvaDigitalizada(Magnitud.ALTURA, "Q", "H", q, h, diametro=diametro)


def test_recupera_coeficientes_exactos():
    c = ajustar(curva_h(), grado=3, unidad_x="m³/h", unidad_y="m")
    np.testing.assert_allclose(c.coeficientes, COEF_H, rtol=1e-6, atol=1e-9)
    assert c.r2 == pytest.approx(1.0)
    assert c.rmse == pytest.approx(0, abs=1e-8)
    assert c.grado == 3


def test_con_ruido_error_menor_al_1_por_ciento():
    datos = curva_h(ruido=0.5)
    c = ajustar(datos, grado=3)
    q = np.linspace(0, 2750, 200)
    error = np.abs(c.evaluar(q) - np.polyval(COEF_H, q))
    rango = np.ptp(np.polyval(COEF_H, q))
    assert error.max() < 0.01 * rango
    assert c.r2 > 0.99


def test_guarda_rango_unidades_y_diametro():
    c = ajustar(curva_h(), unidad_x="m³/h", unidad_y="m")
    assert (c.x_min, c.x_max) == (0, 2750)
    assert (c.unidad_x, c.unidad_y) == ("m³/h", "m")
    assert c.diametro == 738
    assert c.etiqueta == "H – 738 mm"
    assert c.en_rango(1000)
    assert not c.en_rango(3000)


@pytest.mark.parametrize("grado", [0, 5])
def test_grado_fuera_de_limites(grado):
    with pytest.raises(ValueError):
        ajustar(curva_h(), grado=grado)


def test_pocos_puntos():
    datos = CurvaDigitalizada(Magnitud.ALTURA, "Q", "H", np.array([0, 1, 2.0]), np.array([3, 2, 1.0]))
    with pytest.raises(ValueError):
        ajustar(datos, grado=3)


def test_invertir_dentro_del_rango():
    c = ajustar(curva_h())
    q_real = 1500.0
    h = float(np.polyval(COEF_H, q_real))
    assert invertir(c, h) == pytest.approx([q_real], rel=1e-6)


def test_invertir_fuera_del_rango_devuelve_vacio():
    c = ajustar(curva_h())
    assert invertir(c, 500.0) == []


def test_invertir_curva_con_maximo_devuelve_dos_raices():
    # Eficiencia parabólica con máximo de 87 % en 2100 m³/h.
    q = np.linspace(0, 2750, 30)
    eta = 87 - 87 * ((q - 2100) / 2100) ** 2
    c = ajustar(CurvaDigitalizada(Magnitud.EFICIENCIA, "Q", "η", q, eta), grado=2)
    raices = invertir(c, 80.0)
    assert len(raices) == 2
    np.testing.assert_allclose(c.evaluar(np.array(raices)), 80.0)


def test_bomba_busca_por_magnitud_y_diametro():
    h738 = ajustar(curva_h(diametro=738))
    h608 = ajustar(curva_h(diametro=608))
    q = np.linspace(0, 2750, 30)
    eta = ajustar(CurvaDigitalizada(Magnitud.EFICIENCIA, "Q", "η", q, 80 - (q - 2100) ** 2 / 1e5), grado=2)
    bomba = Bomba("ejemplo", [h738, h608, eta])
    assert bomba.curva(Magnitud.ALTURA, 608) is h608
    assert bomba.curva(Magnitud.ALTURA, 700) is None
    assert bomba.curva(Magnitud.EFICIENCIA, 738) is eta  # η común a todos los diámetros
    assert bomba.diametros() == [608, 738]
