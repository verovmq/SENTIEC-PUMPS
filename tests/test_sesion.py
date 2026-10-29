"""Flujo completo de una sesión, como lo hace la interfaz, sin NiceGUI."""

from pathlib import Path

import numpy as np
import pytest

from bombas.core.calculadoras import GRAFICA_ALTURA
from bombas.core.modelos import Escala, Magnitud, Rama
from bombas.graficas.estilos import AZUL, CUADRO_ALTURA, CUADRO_CAUDAL, CUADRO_PUNTO, MORADO
from bombas.graficas.figuras import META_CURVA, TIPOS
from bombas.ui.sesion import ANGULO_MINIMO, Sesion
from test_er3407 import ISO_XLS, polinomio, semilla

DATOS = Path(__file__).parent / "datos"


@pytest.fixture
def sesion():
    """curvaBOMBA1 cargada, con el panel inferior calibrado (Q, H, η) y la curva de 738 mm."""
    s = Sesion()
    s.cargar((DATOS / "curvaBOMBA1.png").read_bytes(), "curvaBOMBA1.png")
    p = s.agregar_panel((707, 758), (115, 239))  # esquinas en cualquier orden
    s.calibrar_eje(p, "Q", "m³/h", (115, 770), 0, (707, 770), 3500)
    s.calibrar_eje(p, "H", "m", (100, 758), 0, (100, 239), 250)
    s.calibrar_eje(p, "η", "%", (720, 758), 0, (720, 239), 100)
    s.digitalizar_curva(p, [(120, 334.5), (577, 452)], Magnitud.ALTURA, diametro=738)
    return s


def test_carga_reinicia_y_mantiene_las_mismas_figuras():
    s = Sesion()
    figuras = [s.gestor.figura(t) for t in TIPOS]
    s.cargar((DATOS / "curvaBOMBA1.png").read_bytes(), "curvaBOMBA1.png")
    assert s.imagen.shape == (819, 807, 3)
    s.cargar((DATOS / "er3407.png").read_bytes(), "er3407.png")
    assert s.paneles == [] and s.curvas == []
    assert [s.gestor.figura(t) for t in TIPOS] == figuras


def test_panel_normaliza_esquinas_y_rechaza_recuadros_minimos(sesion):
    assert sesion.paneles[0].recuadro == (115, 239, 707, 758)
    with pytest.raises(ValueError, match="pequeño"):
        sesion.agregar_panel((100, 100), (105, 300))


def test_calibracion_guarda_la_unidad_y_valida(sesion):
    eje = sesion.paneles[0].ejes["Q"]
    assert (eje.unidad, eje.p1, eje.p2) == ("m³/h", 115, 707)  # se usa la x del clic
    assert sesion.paneles[0].ejes["H"].p1 == 758  # y la y en los ejes verticales
    with pytest.raises(ValueError):
        sesion.calibrar_eje(0, "P", "kW", (10, 50), 0, (10, 50), 1500)  # mismo píxel
    with pytest.raises(ValueError, match="unidad"):
        sesion.calibrar_eje(0, "P", " ", (10, 50), 0, (10, 90), 1500)
    with pytest.raises(ValueError):
        sesion.calibrar_eje(0, "P", "GPM", (10, 50), 0, (10, 90), 100, escala=Escala.LOG)


def test_digitalizar_exige_el_eje_calibrado(sesion):
    with pytest.raises(ValueError, match="eje NPSH"):
        sesion.digitalizar_curva(0, [(272, 658.5), (578, 491.5)], Magnitud.NPSH)


def test_curva_digitalizada_va_a_las_graficas(sesion):
    c = sesion.curvas[0]
    assert c.avisos == [] and c.ajustada.etiqueta == "H – 738 mm"
    assert c.ajustada.evaluar(2000) == pytest.approx(175.3, abs=1.0)  # Excel V6: 175,26
    assert c.trazado.shape == (120, 2)
    nombres = [t.name for t in sesion.gestor.figura(GRAFICA_ALTURA).data if t.meta == META_CURVA]
    assert nombres == ["H – 738 mm"]
    sesion.quitar_curva(0)
    assert not [t for t in sesion.gestor.figura(GRAFICA_ALTURA).data if t.meta == META_CURVA]


def test_umbral_vista_previa_y_mascara(sesion):
    previa = sesion.vista_previa(0, umbral=150)
    assert previa.dtype == bool and previa.shape == (520, 593)
    completa = sesion.mascara(0)
    assert sesion.mascara(0) is completa  # se reutiliza mientras no cambie el umbral
    sesion.fijar_umbral(0, 120)
    assert sesion.mascara(0) is not completa


def test_calculadoras_dibujan_con_el_tono_de_cada_fila(sesion):
    sesion.digitalizar_curva(0, [(118, 747), (578, 322)], Magnitud.EFICIENCIA, grado=4)
    r1 = sesion.calcular(CUADRO_ALTURA, 0, q=2000, diametro=738)
    assert r1.estado.eta.valor == pytest.approx(87.0, abs=1.0)  # Excel V6: 87,02
    r2 = sesion.calcular(CUADRO_CAUDAL, 3, h=175.3, diametro=738)
    assert [round(o.q, -2) for o in r2.opciones] == [2000]
    sesion.calcular(CUADRO_PUNTO, 0, q=1925, h=180, diametro=738)
    fig = sesion.gestor.figura(GRAFICA_ALTURA)
    colores = {t.meta: t.marker.color for t in fig.data if t.mode == "markers" and t.meta != META_CURVA}
    assert colores["c1-f0"] == MORADO[0] and colores["c2-f3"] == AZUL[3]
    sesion.quitar_fila(CUADRO_CAUDAL, 3)
    assert not [t for t in fig.data if t.meta == "c2-f3"]


def test_diametro_obligatorio_si_hay_varios(sesion):
    sesion.digitalizar_curva(0, [(118, 465.5), (489, 561)], Magnitud.ALTURA, diametro=608)
    assert sesion.diametros() == [608, 738]
    with pytest.raises(ValueError, match="diámetro"):
        sesion.calcular(CUADRO_ALTURA, 0, q=1000, diametro=None)


def test_er3407_igual_rendimiento_y_punto_de_maximo():
    s = Sesion()
    s.cargar((DATOS / "er3407.png").read_bytes(), "er3407.png")
    p = s.agregar_panel((65, 15), (895, 504))
    s.fijar_umbral(p, 150)
    s.calibrar_eje(p, "Q", "m³/h", (168.5, 0), 200, (687.5, 0), 1200)
    s.calibrar_eje(p, "H", "m", (0, 297.5), 50, (0, 38.5), 300)
    s.digitalizar_curva(p, [(67.3, 66.2), (635.1, 195.7)], Magnitud.ALTURA, diametro=635)
    # Ramas del lazo de 80 %, con clics cerca de sus extremos.
    for rama, grado in ((Rama.IZQUIERDA, 3), (Rama.DERECHA, 2)):
        coef, h0, h1 = ISO_XLS[(80, rama)]
        margen = 0.06 * (h1 - h0)
        semillas = [semilla(np.polyval(polinomio(coef), h), h) for h in (h0 + margen, h1 - margen)]
        s.digitalizar_curva(p, semillas, Magnitud.EFICIENCIA, nivel=80, rama=rama, grado=grado)
    assert all(c.avisos == [] for c in s.curvas)
    with pytest.raises(ValueError, match="superar"):
        s.agregar_punto_eficiencia(p, (490.5, 121.4), 79)
    bep = s.agregar_punto_eficiencia(p, (490.5, 121.4), 81)  # el "81" del gráfico
    assert bep.q == pytest.approx(820, abs=5) and bep.h == pytest.approx(220, abs=2)
    r = s.calcular(CUADRO_PUNTO, 0, q=bep.q, h=bep.h, diametro=635)
    assert r.eta.valor == pytest.approx(81)
    with pytest.raises(ValueError, match="igual rendimiento"):
        s.digitalizar_curva(p, [(100, 100), (200, 120)], Magnitud.ALTURA, nivel=70)


def test_enderezar_antes_de_los_paneles(sesion):
    with pytest.raises(ValueError, match="antes"):
        sesion.enderezar()
    s = Sesion()
    s.cargar((DATOS / "curvaBOMBA1.png").read_bytes(), "curvaBOMBA1.png")
    original = s.imagen.copy()
    assert abs(s.enderezar()) < ANGULO_MINIMO  # imagen recta: no se toca
    assert s.angulo == 0 and np.array_equal(s.imagen, original)


# --- corrección manual de puntos ----------------------------------------------------------


def test_quitar_puntos_que_se_fueron_por_otra_curva(sesion):
    original = sesion.curvas[0].ajustada
    px = sesion.puntos_curva(0)
    xs = np.array([380, 400, 420, 440])
    y_738 = np.interp(xs, px[:, 0], px[:, 1])
    # Simula un tramo mal seguido: puntos 40 px por encima, como si se hubiera ido por otra curva.
    for x, y in zip(xs, y_738 - 40):
        sesion.agregar_punto_curva(0, (x, y))
    mala = sesion.curvas[0].ajustada
    assert mala.r2 < original.r2 and sesion.curvas[0].editada
    # Un rectángulo alrededor de esos puntos (sin tocar la curva buena) los quita y el ajuste vuelve a ser el original.
    assert sesion.quitar_puntos_curva(0, (375, y_738.min() - 45), (445, y_738.max() - 32)) == 4
    np.testing.assert_allclose(sesion.curvas[0].ajustada.evaluar([500, 1500, 2500]), original.evaluar([500, 1500, 2500]), atol=0.05)


def test_quitar_un_extremo_acorta_el_rango_valido_y_se_puede_deshacer(sesion):
    c = sesion.curvas[0]
    q_max = c.ajustada.x_max
    n = sesion.quitar_puntos_curva(0, (500, 300), (600, 500))  # el final de la curva (Q > ~2300)
    assert n > 0 and c.ajustada.x_max < q_max - 300
    assert len(c.trazado) and c.trazado[:, 0].max() < 500  # el dibujo sobre la imagen también se acorta
    sesion.deshacer_edicion(0)
    assert c.ajustada.x_max == q_max and not c.editada
    with pytest.raises(ValueError, match="deshacer"):
        sesion.deshacer_edicion(0)


def test_quitar_puntos_zona_vacia_o_sin_puntos_suficientes(sesion):
    c = sesion.curvas[0]
    antes = c.ajustada
    with pytest.raises(ValueError, match="No hay puntos"):
        sesion.quitar_puntos_curva(0, (600, 700), (700, 750))
    with pytest.raises(ValueError, match="No se puede ajustar"):
        sesion.quitar_puntos_curva(0, (100, 200), (710, 760))  # toda la curva
    assert c.ajustada is antes and c.historial == []  # nada cambió


def test_puntos_curva_en_pixeles_sobre_el_trazo(sesion):
    px = sesion.puntos_curva(0)
    assert px.shape[1] == 2 and len(px) >= 20
    assert px[:, 0].min() == pytest.approx(120, abs=3) and px[:, 0].max() == pytest.approx(577, abs=3)


# --- borrar paneles -----------------------------------------------------------------------


def test_quitar_panel_borra_sus_curvas_y_conserva_las_de_otros(sesion):
    arriba = sesion.agregar_panel((115, 31), (707, 217))  # panel de potencia
    sesion.calibrar_eje(arriba, "Q", "m³/h", (115, 0), 0, (707, 0), 3500)
    sesion.calibrar_eje(arriba, "P", "kW", (0, 217), 0, (0, 31.5), 1500)
    sesion.digitalizar_curva(arriba, [(118, 161.5), (578, 56.5)], Magnitud.POTENCIA)
    assert [p.nombre for p in sesion.paneles] == ["Panel 1", "Panel 2"]

    assert sesion.quitar_panel(0) == 1  # el panel 1 tenía la curva de 738 mm
    assert [p.nombre for p in sesion.paneles] == ["Panel 2"]
    (potencia,) = sesion.curvas
    assert potencia.panel == 0 and potencia.ajustada.magnitud == Magnitud.POTENCIA
    assert len(sesion.puntos_curva(0)) > 0  # sigue usando los ejes de su panel
    # Un panel nuevo no repite el nombre de uno existente.
    assert sesion.paneles[sesion.agregar_panel((115, 239), (707, 758))].nombre == "Panel 3"


def test_quitar_panel_de_igual_rendimiento_borra_los_puntos_de_maximo():
    s = Sesion()
    s.cargar((DATOS / "er3407.png").read_bytes(), "er3407.png")
    p = s.agregar_panel((65, 15), (895, 504))
    s.fijar_umbral(p, 150)
    s.calibrar_eje(p, "Q", "m³/h", (168.5, 0), 200, (687.5, 0), 1200)
    s.calibrar_eje(p, "H", "m", (0, 297.5), 50, (0, 38.5), 300)
    coef, h0, h1 = ISO_XLS[(80, Rama.DERECHA)]
    margen = 0.06 * (h1 - h0)
    semillas = [semilla(np.polyval(polinomio(coef), h), h) for h in (h0 + margen, h1 - margen)]
    s.digitalizar_curva(p, semillas, Magnitud.EFICIENCIA, nivel=80, rama=Rama.DERECHA, grado=2)
    s.agregar_punto_eficiencia(p, (490.5, 121.4), 81)
    assert s.quitar_panel(p) == 1
    assert s.paneles == [] and s.curvas == [] and s.puntos_eficiencia == []
