"""La guía paso a paso nombra botones y campos reales y sus imágenes existen."""

import re
from pathlib import Path

import pytest
from nicegui import ElementFilter, ui
from nicegui.testing import User

from bombas.ui import guia
from bombas.ui.app import pagina
from bombas.ui.paso_calibracion import EJES

UI = Path(guia.__file__).parent
TODAS = {"cargar": guia.CARGAR, "calibrar": guia.CALIBRAR, "digitalizar": guia.DIGITALIZAR, "calculadoras": guia.CALCULADORAS}
# Citas en negrita que no son literales del código (se construyen con f-strings).
NO_LITERALES = {"Opción 1", "Opción 2", "Ejes de Panel 1"}


def citas(pasos) -> set[str]:
    return {c for p in pasos for c in re.findall(r"\*\*«([^»]+)»\*\*", p.titulo + p.texto)}


def codigo_ui() -> str:
    """Código de la interfaz más los textos que se componen al ejecutarse (títulos de ejes, marcas)."""
    generados = [f"{n} — {d}" for n, d, _ in EJES] + [f"{t} {k}" for t in ("Marca", "Valor") for k in (1, 2)]
    return "\n".join([f.read_text(encoding="utf-8") for f in UI.glob("*.py") if f.name != "guia.py"] + generados)


@pytest.mark.parametrize("nombre", TODAS)
def test_los_botones_y_campos_citados_existen(nombre):
    codigo = codigo_ui()
    # Las comillas de los textos de la interfaz pueden ser "…" o '…'; basta con que el texto esté.
    faltan = [c for c in citas(TODAS[nombre]) - NO_LITERALES if c not in codigo]
    assert faltan == []


@pytest.mark.parametrize("nombre", TODAS)
def test_las_imagenes_existen(nombre):
    for paso in TODAS[nombre]:
        if paso.imagen:
            assert (guia.IMAGENES / paso.imagen).is_file(), paso.imagen
            assert paso.pie, f"{paso.imagen} sin pie de imagen"


async def test_cada_pestana_muestra_su_guia(user: User):
    ui.page("/")(pagina)
    await user.open("/")
    for titulo in ("cargar el archivo", "paneles, umbral y ejes", "digitalizar curvas", "gráficas y calculadoras"):
        await user.should_see(f"Guía paso a paso: {titulo}")
    await user.should_see("Nuevo panel")


async def test_cerrar_y_abrir_la_guia(user: User):
    ui.page("/")(pagina)
    await user.open("/")
    with user.client:  # user.find no ve los elementos ocultos
        (tarjeta,) = ElementFilter(marker="guia-calibrar", only_visible=False)
        (abrir,) = ElementFilter(marker="abrir-guia-calibrar", only_visible=False)
    assert tarjeta.visible and not abrir.visible  # abierta al empezar
    user.find(marker="cerrar-guia-calibrar").click()
    assert not tarjeta.visible and abrir.visible
    assert user.find(marker="guia-digitalizar").elements.pop().visible  # las demás pestañas no cambian
    user.find(marker="abrir-guia-calibrar").click()
    assert tarjeta.visible and not abrir.visible
