"""Pestaña 1: cargar un PDF o una imagen."""

from __future__ import annotations

from nicegui import ui

from bombas.ui import guia
from bombas.ui.lienzo import data_url
from bombas.ui.sesion import Sesion

DPI_OPCIONES = [150, 200, 300, 400]


def crear(ctx) -> None:
    from bombas.ui.app import proteger

    archivo = {"datos": None, "nombre": ""}

    guia.mostrar(guia.CARGAR, "Guía paso a paso: cargar el archivo", "guia-cargar")
    ui.label("Carga el PDF o la imagen con las curvas del fabricante.").classes("text-gray-700")
    with ui.row().classes("items-end gap-4"):
        subida = ui.upload(label="PDF o imagen", auto_upload=True, max_files=1)
        subida.props('accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff"')
        pagina = ui.number("Página (PDF)", value=1, min=1, precision=0).classes("w-32")
        dpi = ui.select(DPI_OPCIONES, value=300, label="Resolución PDF (DPI)").classes("w-48")
        boton = ui.button("Volver a cargar con esta página/DPI", on_click=lambda: cargar())
        boton.props("outline").bind_enabled_from(archivo, "nombre", backward=bool)
    info = ui.label().classes("text-gray-700")
    vista = ui.image().classes("max-w-4xl border")

    @proteger
    def cargar() -> None:
        if archivo["datos"] is None:
            return
        n = Sesion.paginas(archivo["datos"], archivo["nombre"])
        pagina.max = n
        p = min(max(1, int(pagina.value or 1)), n)
        ctx.sesion.cargar(archivo["datos"], archivo["nombre"], p - 1, int(dpi.value))
        ctx.panel_activo = None
        alto, ancho = ctx.sesion.imagen.shape[:2]
        paginas = f" · página {p} de {n}" if n > 1 else ""
        info.text = f"{archivo['nombre']}{paginas} · {ancho} × {alto} px. Sigue en «2. Calibrar»."
        vista.set_source(data_url(ctx.sesion.imagen))
        ctx.emitir("imagen")

    async def al_subir(e) -> None:
        archivo["datos"] = await e.file.read()
        archivo["nombre"] = e.file.name
        pagina.value = 1
        cargar()
        subida.reset()

    subida.on_upload(al_subir)
