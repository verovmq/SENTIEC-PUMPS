"""Regresión con el gráfico escaneado ER-3407 (tests/datos/er3407.png).

Gráfico de tipo B: la eficiencia son curvas de igual rendimiento sobre H–Q, la
potencia está en C.V. y el fondo es una cuadrícula verde.

Referencia: hoja "Polinomios" de viejo/Curvas_Bomba_ER-3407_D649.xlsx
(digitalización manual con precisión declarada de ±2 m y ±5 m³/h). La curva
Ø649 de ese Excel no se usa: no está en el gráfico del fabricante.
"""

from pathlib import Path

import numpy as np
import pytest

from bombas.core.ajuste import ajustar
from bombas.core.calibracion import pixel_desde_valor
from bombas.core.carga import cargar_archivo
from bombas.core.extraccion import digitalizar
from bombas.core.iso_eficiencia import eficiencia_en
from bombas.core.modelos import CurvaAjustada, Eje, Magnitud, Orientacion, Rama
from bombas.core.preprocesado import preprocesar

IMAGEN = Path(__file__).parent / "datos" / "er3407.png"
RECUADRO = (65, 15, 895, 504)
UMBRAL = 150  # escaneo con trazos claros; la cuadrícula verde se descarta por color

EJE_Q = Eje("Q", "m³/h", Orientacion.HORIZONTAL, 168.5, 200, 687.5, 1200)
EJE_H = Eje("H", "m", Orientacion.VERTICAL, 297.5, 50, 38.5, 300)
EJE_P = Eje("P", "C.V.", Orientacion.VERTICAL, 506, 0, 247, 1000)

# H(Q) = a0 + a1·Q + a2·Q² + a3·Q³ y Q máx, por diámetro.
H_XLS = {
    508: ([159.547722468647, -0.0177045711748838, 3.60864150370151e-05, -1.37788689032261e-07], 850),
    572: ([219.974820221592, -0.0269641689039294, 6.48042398034364e-05, -1.44310771396412e-07], 975),
    635: ([273.414469856574, -0.0387617226317104, 7.41496153237252e-05, -1.296561027524e-07], 1104),
}

# Q(H) = b0 + b1·H + b2·H² + b3·H³ en [H inicio, H fin], por (η, rama).
I, D = Rama.IZQUIERDA, Rama.DERECHA
ISO_XLS = {
    (60, I): ([304.035868454052, -0.395389430058174, 0.00231349040248594, 0], 153.83, 263.02),
    (65, I): ([416.790190923446, -0.78301506361222, 0.00312541150867823, 0], 150.97, 260.39),
    (70, I): ([408.77087466853, -0.147352905248097, 0.00196920964782289, 0], 147.66, 256.34),
    (75, I): ([506.59465291493, -0.577975276131964, 0.00359642064711191, 0], 142.72, 250),
    (78, I): ([570.607881221303, -0.670756845053609, 0.00417966770492042, 0], 137.05, 243.41),
    (79, I): ([687.059508739088, -1.27280411010191, 0.00556998434193858, 0], 130.16, 238.16),
    (80, I): ([7219.6971611609, -92.9009302825929, 0.438938673546252, -0.000685729563597033], 172, 234.31),
    (80, D): ([-2734.48605550721, 33.6869852916673, -0.0785111932180804, 0], 172, 209.06),
    (79, D): ([-2619.72263852367, 53.5269786387518, -0.284292701732359, 0.000525397093115], 124.84, 200.13),
    (78, D): ([-166.460468883866, 11.3482729350063, -0.0388720949945357, 5.19337254030965e-05], 116.12, 192.71),
    (75, D): ([4.87224028753664, 9.2358455686739, -0.0238923551065508, 1.87973412445899e-05], 108.5, 179.03),
    (70, D): ([-544.865889213216, 24.184078393271, -0.140184645286754, 0.000323939099449473], 99.52, 160.15),
    (65, D): ([602.73383917202, 0.910638514177, 0.0314465670198497, -9.76455978644601e-05], 85.79, 146.51),
}


def polinomio(coef_ascendente):
    return np.array(coef_ascendente[::-1])


def semilla(q, h):
    return float(pixel_desde_valor(EJE_Q, q)), float(pixel_desde_valor(EJE_H, h))


@pytest.fixture(scope="module")
def mascara():
    return preprocesar(cargar_archivo(IMAGEN), RECUADRO, umbral=UMBRAL)


@pytest.fixture(scope="module")
def iso(mascara):
    """Ramas digitalizadas: {(η, rama): (CurvaAjustada, avisos)}."""
    resultado = {}
    for (nivel, lado), (coef, h0, h1) in ISO_XLS.items():
        p = polinomio(coef)
        margen = 0.06 * (h1 - h0)  # clic cerca de los extremos, no exactamente en ellos
        semillas = [semilla(np.polyval(p, h), h) for h in (h0 + margen, h1 - margen)]
        curva, avisos = digitalizar(
            mascara, semillas, EJE_Q, EJE_H, Magnitud.EFICIENCIA, funcion_de="y", nivel=nivel, rama=lado
        )
        grado = 3 if (nivel, lado) == (80, I) else 2
        resultado[(nivel, lado)] = (ajustar(curva, grado, EJE_Q.unidad, EJE_H.unidad), avisos)
    return resultado


@pytest.mark.parametrize("diametro", list(H_XLS))
def test_altura_por_diametro(mascara, diametro):
    coef, q_max = H_XLS[diametro]
    p = polinomio(coef)
    semillas = [semilla(q, np.polyval(p, q)) for q in (5, q_max - 5)]
    curva, avisos = digitalizar(mascara, semillas, EJE_Q, EJE_H, Magnitud.ALTURA, diametro)
    assert avisos == []
    c = ajustar(curva, 3, EJE_Q.unidad, EJE_H.unidad)
    q = np.linspace(50, q_max - 50, 20)
    # ±2 m del Excel + ~1 m de la digitalización: < 1,2 % del eje de 300 m.
    np.testing.assert_allclose(c.evaluar(q), np.polyval(p, q), atol=3.5)
    assert c.etiqueta == f"H – {diametro} mm"


@pytest.mark.parametrize("clave", list(ISO_XLS), ids=lambda k: f"{k[0]}-{k[1].value}")
def test_ramas_de_igual_rendimiento(iso, clave):
    curva, avisos = iso[clave]
    assert avisos == []
    assert curva.funcion_de == "y" and curva.nivel == clave[0] and curva.rama == clave[1]
    p = polinomio(ISO_XLS[clave][0])
    h = np.linspace(curva.x_min, curva.x_max, 15)
    error = np.abs(curva.evaluar(h) - np.polyval(p, h))
    if clave[0] == 80:
        # Lazo interno: en su punta inferior Q(H) tiene pendiente casi infinita
        # y cualquier polinomio (también el del Excel) es inestable.
        assert np.median(error) < 8
    else:
        assert error.max() < 8  # ≈ 4 px; Excel declara ±5 m³/h


def test_eficiencia_en_puntos_frente_al_excel(iso):
    digitalizadas = [c for c, _ in iso.values()]
    referencia = [
        CurvaAjustada(Magnitud.EFICIENCIA, polinomio(coef), h0, h1, "m³/h", "m", 1, 0,
                      funcion_de="y", nivel=nivel, rama=lado)
        for (nivel, lado), (coef, h0, h1) in ISO_XLS.items()
    ]
    comparados = 0
    for q in range(400, 1001, 50):
        for h in range(120, 241, 10):
            a, b = eficiencia_en(digitalizadas, q, h), eficiencia_en(referencia, q, h)
            if a.valor is None or b.valor is None or a.cota_minima or b.cota_minima:
                continue
            assert abs(a.valor - b.valor) < 1.0, (q, h, a.valor, b.valor)
            comparados += 1
    assert comparados > 40


def test_punto_conocido_entre_78_y_79(iso):
    # A H = 150 m: rama izq. 78 % en Q ≈ 564 y 79 % en Q ≈ 621 (Excel) → η(600) ≈ 78,6 %.
    r = eficiencia_en([c for c, _ in iso.values()], 600, 150)
    assert r.valor == pytest.approx(78.6, abs=0.3) and not r.cota_minima


def test_dentro_del_lazo_de_80_es_cota_minima(iso):
    r = eficiencia_en([c for c, _ in iso.values()], 760, 185)
    assert r.valor == 80 and r.cota_minima


@pytest.mark.parametrize(
    "diametro, semillas, rango",
    [(635, [(67, 402), (637, 265)], (380, 420)), (508, [(67, 459), (503, 397)], (165, 205))],
)
def test_potencia_en_cv_sin_convertir(mascara, diametro, semillas, rango):
    curva, avisos = digitalizar(mascara, semillas, EJE_Q, EJE_P, Magnitud.POTENCIA, diametro)
    assert avisos == []
    c = ajustar(curva, 3, EJE_Q.unidad, EJE_P.unidad)
    assert c.unidad_y == "C.V."
    assert rango[0] <= c.evaluar(0) <= rango[1]  # potencia a caudal nulo leída en la imagen
    assert np.all(np.diff(c.evaluar(np.linspace(c.x_min, c.x_max, 20))) > 0)
