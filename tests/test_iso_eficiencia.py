import numpy as np
import pytest

from bombas.core.iso_eficiencia import eficiencia_en
from bombas.core.modelos import CurvaAjustada, Magnitud, Rama


def rama(nivel, q, lado, h_min=100.0, h_max=250.0, pendiente=0.0):
    """Rama Q(H) = q + pendiente·(H - 100), válida en [h_min, h_max]."""
    return CurvaAjustada(
        magnitud=Magnitud.EFICIENCIA,
        coeficientes=np.array([pendiente, q - 100 * pendiente]),
        x_min=h_min,
        x_max=h_max,
        unidad_x="m³/h",
        unidad_y="m",
        r2=1.0,
        rmse=0.0,
        funcion_de="y",
        nivel=nivel,
        rama=lado,
    )


IZQ, DER = Rama.IZQUIERDA, Rama.DERECHA
# Colina: 60 / 70 / 80 % a la izquierda y 80 / 70 / 60 % a la derecha.
CURVAS = [
    rama(60, 300, IZQ),
    rama(70, 400, IZQ),
    rama(80, 500, IZQ),
    rama(80, 900, DER),
    rama(70, 1000, DER),
    rama(60, 1100, DER),
]


@pytest.mark.parametrize(
    "q, esperado",
    [(300, 60), (350, 65), (450, 75), (950, 75), (1050, 65), (1100, 60)],
)
def test_interpola_entre_ramas(q, esperado):
    r = eficiencia_en(CURVAS, q, 150)
    assert r.valor == pytest.approx(esperado)
    assert not r.cota_minima and r.aviso is None


def test_dentro_del_lazo_interno_es_cota_minima():
    r = eficiencia_en(CURVAS, 700, 150)
    assert r.valor == 80 and r.cota_minima


@pytest.mark.parametrize("q, h", [(200, 150), (1200, 150), (700, 300), (700, 50)])
def test_fuera_de_la_zona_no_extrapola(q, h):
    r = eficiencia_en(CURVAS, q, h)
    assert r.valor is None and r.aviso


def test_ramas_inclinadas_y_rangos_distintos():
    # El lazo de 80 % solo llega hasta H = 180: por encima, entre 70 izq. y 70 der.
    curvas = [
        rama(70, 400, IZQ, pendiente=0.5),
        rama(80, 500, IZQ, h_max=180),
        rama(80, 900, DER, h_max=180),
        rama(70, 1000, DER, pendiente=-0.5),
    ]
    assert eficiencia_en(curvas, 450, 100).valor == pytest.approx(75)
    r = eficiencia_en(curvas, 700, 200)  # 70 izq. en Q=450, 70 der. en Q=950
    assert r.valor == 70 and r.cota_minima


def test_exige_curvas_q_de_h():
    c = rama(60, 300, IZQ)
    c.funcion_de = "x"
    with pytest.raises(ValueError):
        eficiencia_en([c, rama(70, 400, IZQ)], 350, 150)
