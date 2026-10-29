"""Aplicación local: una página con cuatro pestañas que siguen el flujo de trabajo.

1. Cargar: PDF o imagen.
2. Calibrar: paneles (recuadro de trazado), umbral de oscuridad con vista previa
   en vivo y ejes con sus unidades originales.
3. Digitalizar: curvas con clics (semillas), curvas de igual rendimiento y
   punto de máximo rendimiento.
4. Gráficas y calculadoras: las tres gráficas únicas de la sesión y los cuadros 1–3.

Cada pestaña del navegador es una sesión independiente con su propio estado.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from functools import wraps

from nicegui import ui

from bombas.ui.sesion import Sesion

TITULO = "Digitalizador de curvas de bombas"

# Botones con su texto tal cual (Quasar los pone en mayúsculas): así coinciden con la guía.
ui.button.default_props("no-caps")


class Contexto:
    """Estado compartido por las pestañas de una sesión y avisos de cambios entre ellas.

    Eventos: "imagen" (se cargó o enderezó), "paneles" (panel nuevo, activo o ejes),
    "umbral" (cambió el umbral del panel activo), "curvas" (curvas o puntos de máximo).
    """

    def __init__(self):
        self.sesion = Sesion()
        self.panel_activo: int | None = None
        self._oyentes: dict[str, list[Callable[[], None]]] = defaultdict(list)

    def al(self, evento: str, funcion: Callable[[], None]) -> None:
        self._oyentes[evento].append(funcion)

    def emitir(self, evento: str) -> None:
        for funcion in list(self._oyentes[evento]):
            funcion()


def proteger(funcion):
    """Muestra los errores de validación como aviso en vez de romper la página."""

    @wraps(funcion)
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except ValueError as e:
            ui.notify(str(e), type="warning", multi_line=True)

    return envoltura


@ui.page("/")
def pagina() -> None:
    from bombas.ui import calculadoras, paso_calibracion, paso_carga, paso_extraccion

    ctx = Contexto()
    ui.query("body").style("background: white; color: black")
    with ui.header().classes("bg-white text-black border-b"):
        ui.label(TITULO).classes("text-lg font-medium")
    with ui.tabs().classes("w-full") as pestanas:
        t_carga = ui.tab("1. Cargar")
        t_calibrar = ui.tab("2. Calibrar")
        t_digitalizar = ui.tab("3. Digitalizar")
        t_graficas = ui.tab("4. Gráficas y calculadoras")
    with ui.tab_panels(pestanas, value=t_carga).classes("w-full"):
        with ui.tab_panel(t_carga):
            paso_carga.crear(ctx)
        with ui.tab_panel(t_calibrar):
            paso_calibracion.crear(ctx)
        with ui.tab_panel(t_digitalizar):
            paso_extraccion.crear(ctx)
        with ui.tab_panel(t_graficas):
            calculadoras.crear(ctx)


def main() -> None:
    # Solo accesible desde este equipo (por defecto NiceGUI escucha en toda la red local).
    ui.run(title=TITULO, language="es", host="127.0.0.1", port=8080, reload=False, show=True)
