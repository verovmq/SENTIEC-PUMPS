import numpy as np
import pytest

from bombas.core.calculadoras import (
    GRAFICA_ALTURA,
    GRAFICA_NPSH,
    GRAFICA_POTENCIA,
    calcular_altura,
    calcular_caudal,
    evaluar_punto,
)
from bombas.core.modelos import PuntoEficiencia
from bombas_prueba import (
    COEF_ETA,
    COEF_H738,
    COEF_JOROBA,
    COEF_NPSH,
    COEF_P,
    bomba_tipo_a,
    bomba_tipo_b,
)

# --- Cuadro 1: Q → H ------------------------------------------------------------


def test_cuadro1_valores_y_unidades_originales():
    e = calcular_altura(bomba_tipo_a(), 1500, 738).estado
    assert e.h.valor == pytest.approx(np.polyval(COEF_H738, 1500)) and e.h.unidad == "m"
    assert e.eta.valor == pytest.approx(np.polyval(COEF_ETA, 1500)) and e.eta.unidad == "%"
    assert e.npsh.valor == pytest.approx(np.polyval(COEF_NPSH, 1500)) and e.npsh.unidad == "m"
    assert e.potencia.valor == pytest.approx(np.polyval(COEF_P, 1500)) and e.potencia.unidad == "kW"
    assert e.avisos == []


def test_cuadro1_avisa_de_extrapolacion():
    e = calcular_altura(bomba_tipo_a(), 2500, 608).estado  # H 608 solo llega a 2200
    assert e.h.valor is not None
    assert any("extrapolado" in a and "H" in a for a in e.avisos)


def test_cuadro1_npsh_fuera_de_rango_por_la_izquierda():
    e = calcular_altura(bomba_tipo_a(), 500, 738).estado  # NPSH empieza en 800
    assert any(a.startswith("NPSH") for a in e.avisos)


def test_cuadro1_diametro_no_digitalizado():
    with pytest.raises(ValueError, match="738"):
        calcular_altura(bomba_tipo_a(), 1000, 700)


def test_cuadro1_puntos_en_las_tres_graficas():
    puntos = calcular_altura(bomba_tipo_a(), 1500, 738).puntos()
    assert {(p.grafica, p.eje_y) for p in puntos} == {
        (GRAFICA_ALTURA, "y"), (GRAFICA_ALTURA, "y2"), (GRAFICA_NPSH, "y"), (GRAFICA_POTENCIA, "y")
    }


# --- Cuadro 2: H → Q ------------------------------------------------------------


def test_cuadro2_una_solucion():
    h = float(np.polyval(COEF_H738, 1800))
    r = calcular_caudal(bomba_tipo_a(), h, 738)
    assert [e.q for e in r.opciones] == pytest.approx([1800])
    assert r.opciones[0].eta.valor == pytest.approx(np.polyval(COEF_ETA, 1800))
    assert r.avisos == []


def test_cuadro2_dos_soluciones_se_muestran_ambas():
    r = calcular_caudal(bomba_tipo_a(coef_h738=COEF_JOROBA), 205.3, 738)
    assert [e.q for e in r.opciones] == pytest.approx([112.7017, 887.2983], rel=1e-5)
    assert r.avisos and "2 caudales" in r.avisos[0]
    marcadores_h = [p for p in r.puntos() if p.grafica == GRAFICA_ALTURA and p.eje_y == "y"]
    assert [p.etiqueta for p in marcadores_h] == ["H→Q (opción 1)", "H→Q (opción 2)"]


def test_cuadro2_altura_no_alcanzable():
    r = calcular_caudal(bomba_tipo_a(), 300, 738)
    assert r.opciones == [] and "no se alcanza" in r.avisos[0]
    assert r.puntos() == []


# --- Cuadro 3: punto conocido (Q, H) ----------------------------------------------


@pytest.mark.parametrize(
    "h, posicion",
    [(200.0, "por encima"), (150.0, "por debajo"), (None, "sobre la curva")],
)
def test_cuadro3_posicion_respecto_a_la_curva(h, posicion):
    h_bomba = float(np.polyval(COEF_H738, 1500))
    h = h_bomba + 0.1 if h is None else h
    r = evaluar_punto(bomba_tipo_a(), 1500, h, 738)
    assert r.posicion == posicion
    assert r.diferencia == pytest.approx(h - h_bomba)
    assert r.potencia.valor == pytest.approx(np.polyval(COEF_P, 1500))


def test_cuadro3_dibuja_el_punto_dado():
    puntos = evaluar_punto(bomba_tipo_a(), 1500, 170, 738).puntos()
    assert (puntos[0].grafica, puntos[0].x, puntos[0].y) == (GRAFICA_ALTURA, 1500, 170)


# --- Gráfico tipo B (curvas de igual rendimiento) ------------------------------------


def test_tipo_b_eficiencia_desde_el_mapa():
    # H(950) ≈ 196,8 m está dentro de las ramas (100..250 m); Q=950 cae entre
    # 80 % der. (Q=900) y 70 % der. (Q=1000) → η = 75 %.
    e = calcular_altura(bomba_tipo_b(), 950, 635).estado
    assert e.eta.valor == pytest.approx(75) and e.eta_de_mapa
    assert e.potencia.unidad == "C.V."
    assert e.npsh.valor is None and "No hay curva de NPSH" in e.npsh.avisos[0]
    assert all(p.eje_y == "y" for p in calcular_altura(bomba_tipo_b(), 950, 635).puntos())


def test_tipo_b_dentro_del_lazo_es_cota_minima():
    r = evaluar_punto(bomba_tipo_b(), 700, 180, 635)
    assert r.eta.valor == 80 and r.eta.cota_minima


def test_tipo_b_con_punto_de_maximo_rendimiento():
    b = bomba_tipo_b()
    b.puntos_eficiencia.append(PuntoEficiencia(q=700, h=175, eta=85))
    r = evaluar_punto(b, 700, 175, 635)
    assert r.eta.valor == pytest.approx(85) and not r.eta.cota_minima
