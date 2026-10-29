"""Flujo completo de la interfaz con el simulador de usuario de NiceGUI (sin navegador).

Reproduce lo que haría la usuaria con curvaBOMBA1.png: cargar, crear un panel,
mover el deslizante del umbral, calibrar Q y H con clics, digitalizar la curva
de 738 mm y usar los tres cuadros de cálculo, agregando y quitando filas.
Los elementos se buscan por marcador (`.mark(...)`) para no depender de textos.
"""

import re
from pathlib import Path

import pytest
from nicegui import ElementFilter, ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import User

from bombas.core.calculadoras import calcular_caudal
from bombas.graficas.estilos import AZUL, CUADRO_CAUDAL, MORADO, NARANJA
from bombas.ui.app import pagina
from bombas.ui.calculadoras import lineas_resultado
from bombas_prueba import COEF_JOROBA, bomba_tipo_a

IMAGEN = Path(__file__).parent / "datos" / "curvaBOMBA1.png"


def elemento(user: User, marca: str):
    (e,) = user.find(marker=marca).elements
    return e


def clic(user: User, lienzo: str, x: float, y: float) -> None:
    user.find(marker=lienzo).trigger("mouse", {"mouse_event_type": "click", "image_x": x, "image_y": y})


async def calibrar(user: User, eje: str, titulo: str, unidad: str, punto1, valor1, punto2, valor2) -> None:
    # Se escriben los dos valores antes del segundo clic: así se comprueba que
    # colocar una marca no borra lo ya escrito en el formulario.
    user.find(marker=f"marca-{eje}-1").click()
    clic(user, "lienzo-calibrar", *punto1)
    elemento(user, f"valor-{eje}-1").value = valor1
    user.find(marker=f"marca-{eje}-2").click()
    clic(user, "lienzo-calibrar", *punto2)
    elemento(user, f"valor-{eje}-2").value = valor2
    assert elemento(user, f"valor-{eje}-1").value == valor1
    user.find(marker=f"guardar-{eje}").click()
    await user.should_see(f"Eje {eje} calibrado ({unidad})")
    await user.should_see(f"{titulo}  ✔ {unidad}")  # el formulario se redibuja (en segundo plano)


def visible(user: User, marca: str) -> bool:
    with user.client:  # user.find no ve los elementos ocultos
        (e,) = ElementFilter(marker=marca, only_visible=False)
    return e.visible


def resultado(user: User, marca: str) -> str:
    return " ".join(e.text for e in elemento(user, marca).descendants() if isinstance(e, ui.label))


def marcadores_altura(user: User) -> dict[str, str]:
    (altura,) = [g for g in user.find(ui.plotly).elements if g.figure.layout.title.text == "Altura y eficiencia"]
    return {t.meta: t.marker.color for t in altura.figure.data if t.mode == "markers" and t.yaxis == "y"}


@pytest.fixture
async def user_con_curva(user: User) -> User:
    """Hasta tener digitalizada la curva de 738 mm."""
    ui.page("/")(pagina)
    await user.open("/")
    subida = user.find(ui.upload).elements.pop()
    await subida.handle_uploads([SmallFileUpload("curvaBOMBA1.png", "image/png", IMAGEN.read_bytes())])
    await user.should_see("807 × 819 px")

    user.find(marker="nuevo-panel").click()
    clic(user, "lienzo-calibrar", 115, 239)
    clic(user, "lienzo-calibrar", 707, 758)
    await user.should_see("Panel creado")
    await user.should_see(marker="marca-Q-1")  # el formulario de ejes se dibuja en segundo plano
    await calibrar(user, "Q", "Q — Caudal (eje horizontal)", "m³/h", (115, 770), 0, (707, 770), 3500)
    await calibrar(user, "H", "H — Altura manométrica", "m", (100, 758), 0, (100, 239), 250)

    clic(user, "lienzo-digitalizar", 120, 334.5)
    clic(user, "lienzo-digitalizar", 577, 452)
    await user.should_see("2 clic(s) sobre la curva")
    elemento(user, "diametro").value = 738
    user.find(marker="digitalizar").click()
    await user.should_see("H – 738 mm · Panel 1")
    return user


async def test_deslizante_del_umbral_con_vista_previa_en_vivo(user_con_curva: User):
    user = user_con_curva
    mascara = elemento(user, "umbral-calibrar-mascara")
    antes = mascara.source
    assert antes.startswith("data:image/png")
    # Con 225 entra la cuadrícula gris (≈190–220): la máscara tiene que cambiar.
    user.find(marker="umbral-calibrar").trigger("update:modelValue", 225)
    assert mascara.source != antes  # la máscara se actualiza al mover el deslizante
    assert elemento(user, "umbral-digitalizar").value == 225  # el de la pestaña 3 se sincroniza
    await user.should_see("225")


async def test_calculadoras(user_con_curva: User):
    user = user_con_curva
    elemento(user, "c1-q-0").value = 2000
    # El diámetro empieza vacío: sin elegirlo no se calcula ni se dibuja nada.
    assert elemento(user, "c1-diametro-0").value is None
    assert "Elige el" in resultado(user, "c1-resultado-0") and "c1-f0" not in marcadores_altura(user)
    elemento(user, "c1-diametro-0").value = 738
    h = float(re.search(r"H = ([\d.]+)", resultado(user, "c1-resultado-0")).group(1))
    assert h == pytest.approx(175.26, abs=1)  # Excel V6: H(2000) = 175,26 m
    elemento(user, "c2-diametro-0").value = 738
    elemento(user, "c2-h-0").value = 175.3
    q = float(re.search(r"Q = ([\d.]+)", resultado(user, "c2-resultado-0")).group(1))
    assert q == pytest.approx(2000, abs=15)  # Excel V6: H(2000) = 175,26 m
    elemento(user, "c3-diametro-0").value = 738
    elemento(user, "c3-q-0").value = 1925
    elemento(user, "c3-h-0").value = 180
    assert "Por encima de la curva" in resultado(user, "c3-resultado-0")
    # Una sola figura de cada tipo, con los puntos en morado, azul y naranja.
    assert len(user.find(ui.plotly).elements) == 3
    assert marcadores_altura(user) == {"c1-f0": MORADO[0], "c2-f0": AZUL[0], "c3-f0": NARANJA[0]}

    # «Agregar» añade una fila con el siguiente tono; quitar una fila borra sus puntos.
    user.find(marker="agregar-c1").click()
    elemento(user, "c1-diametro-1").value = 738
    elemento(user, "c1-q-1").value = 1200
    assert marcadores_altura(user)["c1-f1"] == MORADO[1]
    user.find(marker="quitar-c1-0").click()
    assert "c1-f0" not in marcadores_altura(user) and "c1-f1" in marcadores_altura(user)


async def test_cuadro2_altura_inalcanzable(user_con_curva: User):
    user = user_con_curva
    elemento(user, "c2-diametro-0").value = 738
    elemento(user, "c2-h-0").value = 400
    assert "no se alcanza" in resultado(user, "c2-resultado-0")


def test_cuadro2_muestra_las_dos_soluciones_como_opciones():
    # Curva con joroba: H = 205,3 m se alcanza en Q ≈ 113 y Q ≈ 887 m³/h.
    r = calcular_caudal(bomba_tipo_a(coef_h738=COEF_JOROBA), 205.3, 738)
    textos = [t for t, _ in lineas_resultado(CUADRO_CAUDAL, r)]
    assert textos[0].startswith("2 caudales posibles")
    assert textos[1].startswith("Opción 1: Q = 112.7") and textos[2].startswith("Opción 2: Q = 887.3")
    assert not any(t.startswith("Q = ") for t in textos)  # no se elige una por defecto


async def test_errores_se_muestran_como_aviso(user_con_curva: User):
    user = user_con_curva
    user.find(marker="digitalizar").click()  # sin clics sobre la curva
    await user.should_see("Haz al menos 2 clics")


async def test_corregir_puntos_a_mano(user_con_curva: User):
    user = user_con_curva
    sesion_curva = lambda: elemento(user, "info-correccion").text  # noqa: E731
    user.find(marker="corregir-curva-0").click()
    await user.should_see("Corrigiendo puntos: H – 738 mm")
    assert visible(user, "tarjeta-correccion") and not visible(user, "tarjeta-nueva-curva")
    n_antes = int(sesion_curva().split()[0])
    # Borrar el final de la curva (x > 500) con dos clics en esquinas opuestas.
    clic(user, "lienzo-digitalizar", 500, 300)
    await user.should_see("esquina opuesta")
    clic(user, "lienzo-digitalizar", 600, 500)
    await user.should_see("borrado(s)")
    n_despues = int(sesion_curva().split()[0])
    assert 0 < n_despues < n_antes
    await user.should_see("corregida a mano")
    # «Deshacer» recupera los puntos; «Añadir punto» añade uno con un clic.
    user.find(marker="deshacer-correccion").click()
    assert int(sesion_curva().split()[0]) == n_antes
    elemento(user, "accion-correccion").value = "anadir"
    clic(user, "lienzo-digitalizar", 300, 370)
    assert int(sesion_curva().split()[0]) == n_antes + 1
    user.find(marker="terminar-correccion").click()
    assert not visible(user, "tarjeta-correccion") and visible(user, "tarjeta-nueva-curva")
