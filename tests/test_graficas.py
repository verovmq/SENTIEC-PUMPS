import pytest

from bombas.core.calculadoras import (
    GRAFICA_ALTURA,
    GRAFICA_NPSH,
    GRAFICA_POTENCIA,
    PuntoGrafico,
    calcular_altura,
    calcular_caudal,
    evaluar_punto,
)
from bombas.graficas.estilos import (
    AZUL,
    CUADRO_ALTURA,
    CUADRO_CAUDAL,
    CUADRO_PUNTO,
    MORADO,
    NARANJA,
    NEGRO,
    color_fila,
)
from bombas.graficas.figuras import META_CURVA, TIPOS, GestorGraficas
from bombas.core.modelos import PuntoEficiencia
from bombas_prueba import COEF_JOROBA, bomba_tipo_a, bomba_tipo_b


def trazas(fig, meta):
    return [t for t in fig.data if t.meta == meta]


@pytest.fixture
def gestor():
    return GestorGraficas(bomba_tipo_a())


# --- regla 6: una única gráfica por tipo ---------------------------------------------


def test_una_unica_figura_por_tipo(gestor):
    figuras = {tipo: gestor.figura(tipo) for tipo in TIPOS}
    gestor.dibujar_resultado(calcular_altura(gestor.bomba, 1500, 738), color_fila(1, 0), "c1-f0")
    gestor.dibujar_resultado(calcular_caudal(gestor.bomba, 180, 738), color_fila(2, 0), "c2-f0")
    gestor.dibujar_curvas()
    for tipo in TIPOS:
        assert gestor.figura(tipo) is figuras[tipo]
    assert len({id(f) for f in figuras.values()}) == 3


# --- reglas 3 y 5: curvas negras con su etiqueta ---------------------------------------


def test_curvas_ejes_y_textos_en_negro(gestor):
    for tipo in TIPOS:
        fig = gestor.figura(tipo)
        curvas = trazas(fig, META_CURVA)
        assert curvas and all(t.line.color == NEGRO for t in curvas)
        assert all(a.font.color == NEGRO for a in fig.layout.annotations)
        assert fig.layout.font.color == NEGRO and fig.layout.title.font.color == NEGRO
        for eje in (fig.layout.xaxis, fig.layout.yaxis):
            assert eje.linecolor == NEGRO and eje.tickfont.color == NEGRO and eje.title.font.color == NEGRO


def test_etiquetas_con_diametro_y_unidades_originales(gestor):
    fig = gestor.figura(GRAFICA_ALTURA)
    textos = {a.text for a in fig.layout.annotations}
    assert {"H – 738 mm", "H – 608 mm", "η"} <= textos
    assert fig.layout.xaxis.title.text == "Q [m³/h]" and fig.layout.yaxis.title.text == "H [m]"
    assert gestor.figura(GRAFICA_POTENCIA).layout.yaxis.title.text == "P [kW]"


def test_eficiencia_en_eje_secundario(gestor):
    fig = gestor.figura(GRAFICA_ALTURA)
    eta = [t for t in trazas(fig, META_CURVA) if t.name == "η"]
    assert eta[0].yaxis == "y2"
    assert fig.layout.yaxis2.side == "right" and fig.layout.yaxis2.title.text == "η [%]"


def test_tipo_b_curvas_de_igual_rendimiento_sin_eje_secundario():
    g = GestorGraficas(bomba_tipo_b())
    fig = g.figura(GRAFICA_ALTURA)
    iso = [t for t in trazas(fig, META_CURVA) if t.name.startswith("η")]
    assert len(iso) == 6 and all(t.yaxis == "y" and t.line.color == NEGRO for t in iso)
    assert "yaxis2" not in fig.to_dict()["layout"]
    assert "80 %" in {a.text for a in fig.layout.annotations}
    assert "η 80 % (izquierda)" in {t.name for t in iso}  # nombre completo al pasar el ratón
    assert g.figura(GRAFICA_POTENCIA).layout.yaxis.title.text == "P [C.V.]"


# --- regla 8: marcador y líneas punteadas hasta los ejes ---------------------------------


def test_punto_con_lineas_punteadas_hasta_los_ejes(gestor):
    gestor.agregar_punto(PuntoGrafico(GRAFICA_NPSH, 1500, 6.25), "#123456", "g")
    fig = gestor.figura(GRAFICA_NPSH)
    horizontal, vertical, marcador = trazas(fig, "g")
    assert marcador.mode == "markers" and marcador.marker.color == "#123456"
    for linea in (horizontal, vertical):
        assert linea.line.dash == "dot" and linea.line.color == "#123456"
    assert horizontal.x == (fig.layout.xaxis.range[0], 1500) and horizontal.y == (6.25, 6.25)
    assert vertical.x == (1500, 1500) and vertical.y == (fig.layout.yaxis.range[0], 6.25)


def test_punto_del_eje_secundario_va_al_eje_derecho(gestor):
    gestor.agregar_punto(PuntoGrafico(GRAFICA_ALTURA, 1500, 80, eje_y="y2"), "#123456", "g")
    horizontal, _, marcador = trazas(gestor.figura(GRAFICA_ALTURA), "g")
    assert marcador.yaxis == "y2"
    assert sorted(horizontal.x) == [1500, gestor.figura(GRAFICA_ALTURA).layout.xaxis.range[1]]


def test_punto_fuera_de_los_ejes_los_amplia(gestor):
    fig = gestor.figura(GRAFICA_POTENCIA)
    gestor.agregar_punto(PuntoGrafico(GRAFICA_POTENCIA, 5000, 3000), "#123456", "g")
    assert fig.layout.xaxis.range[1] > 5000 and fig.layout.yaxis.range[1] > 3000


# --- reglas 7 y 9: colores por cuadro, filas que se agregan y se reemplazan --------------


def test_colores_de_cada_cuadro():
    assert [color_fila(CUADRO_ALTURA, i) for i in range(len(MORADO))] == MORADO
    assert color_fila(CUADRO_CAUDAL, 0) in AZUL and color_fila(CUADRO_PUNTO, 0) in NARANJA
    assert color_fila(CUADRO_PUNTO, len(NARANJA)) == color_fila(CUADRO_PUNTO, 0)  # ciclo
    assert color_fila(CUADRO_ALTURA, 0) != color_fila(CUADRO_ALTURA, 1)  # cada fila, un tono


def test_varias_filas_y_recalcular_una_fila(gestor):
    b = gestor.bomba
    for fila, q in enumerate((1000, 1500, 2000)):  # botón "Agregar": filas nuevas
        gestor.dibujar_resultado(calcular_altura(b, q, 738), color_fila(1, fila), f"c1-f{fila}")
    fig = gestor.figura(GRAFICA_ALTURA)
    antes = len(fig.data)
    gestor.dibujar_resultado(calcular_altura(b, 1700, 738), color_fila(1, 1), "c1-f1")  # editar fila 1
    assert len(fig.data) == antes
    assert [t.x[0] for t in trazas(fig, "c1-f1") if t.mode == "markers"] == [1700, 1700]  # H y η
    gestor.quitar_grupo("c1-f1")
    assert trazas(fig, "c1-f1") == [] and trazas(fig, "c1-f0")


def test_cuadro2_con_dos_soluciones_dibuja_ambas():
    g = GestorGraficas(bomba_tipo_a(coef_h738=COEF_JOROBA))
    g.dibujar_resultado(calcular_caudal(g.bomba, 205.3, 738), color_fila(2, 0), "c2-f0")
    marcadores = [t for t in trazas(g.figura(GRAFICA_ALTURA), "c2-f0") if t.mode == "markers" and t.yaxis == "y"]
    assert sorted(round(t.x[0]) for t in marcadores) == [113, 887]
    assert all(t.marker.color in AZUL for t in marcadores)


def test_cuadro3_en_naranja(gestor):
    gestor.dibujar_resultado(evaluar_punto(gestor.bomba, 1500, 170, 738), color_fila(3, 0), "c3-f0")
    marcadores = [t for f in TIPOS for t in trazas(gestor.figura(f), "c3-f0") if t.mode == "markers"]
    assert len(marcadores) == 3 and all(t.marker.color in NARANJA for t in marcadores)


def test_punto_de_maximo_rendimiento_en_negro_sin_guias():
    b = bomba_tipo_b()
    b.puntos_eficiencia.append(PuntoEficiencia(q=700, h=175, eta=85))
    fig = GestorGraficas(b).figura(GRAFICA_ALTURA)
    (marcador,) = [t for t in trazas(fig, META_CURVA) if t.mode == "markers"]
    assert (marcador.x, marcador.y) == ((700,), (175,)) and marcador.marker.color == NEGRO
    assert "85 %" in {a.text for a in fig.layout.annotations}
    assert not [t for t in fig.data if t.line and t.line.dash == "dot"]  # sin líneas punteadas
