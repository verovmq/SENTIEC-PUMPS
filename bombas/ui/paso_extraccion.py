"""Pestaña 3: digitalizar curvas con clics y registrar el punto de máximo rendimiento.

La imagen se muestra atenuada y las curvas ya digitalizadas se superponen en
negro: así se ve de un vistazo si el ajuste sigue el trazo original.
"""

from __future__ import annotations

from nicegui import ui

from bombas.core.ajuste import GRADO_MAXIMO, GRADO_MINIMO, GRADO_POR_DEFECTO
from bombas.core.modelos import Magnitud, Rama
from bombas.graficas.estilos import NEGRO
from bombas.ui import guia
from bombas.ui.lienzo import AYUDA, Lienzo
from bombas.ui.paso_calibracion import control_umbral, selector_panel

MAGNITUDES = {
    Magnitud.ALTURA: "H — altura manométrica",
    Magnitud.EFICIENCIA: "η — eficiencia",
    Magnitud.NPSH: "NPSH",
    Magnitud.POTENCIA: "P — potencia",
}
TIPO_FUNCION = "funcion"
TIPO_ISO = "iso"


def crear(ctx) -> None:
    from bombas.ui.app import proteger

    estado = {"semillas": [], "modo": "semillas"}  # modo: "semillas" o "maximo"

    guia.mostrar(guia.DIGITALIZAR, "Guía paso a paso: digitalizar curvas")
    with ui.row().classes("w-full no-wrap items-start gap-4"):
        with ui.column().classes("w-3/5"):
            ayuda = ui.label().classes("text-sm text-gray-700")
            lienzo = Lienzo(lambda x, y: al_clic(x, y), "lienzo-digitalizar")
        with ui.column().classes("w-2/5"):
            selector_panel(ctx)
            control_umbral(ctx, "umbral-digitalizar")
            with ui.card().classes("w-full"):
                ui.label("Nueva curva").classes("font-medium")
                magnitud = ui.select(MAGNITUDES, value=Magnitud.ALTURA, label="Magnitud").classes("w-full")
                tipo = ui.radio(
                    {TIPO_FUNCION: "η(Q) con su propio eje", TIPO_ISO: "Curva de igual rendimiento (sobre H–Q)"},
                    value=TIPO_FUNCION,
                ).props("dense")
                with ui.row().classes("items-end gap-2") as fila_iso:
                    nivel = ui.number("η de la curva (%)", value=None).classes("w-36")
                    rama = ui.select(
                        {Rama.IZQUIERDA: "rama izquierda", Rama.DERECHA: "rama derecha"},
                        value=Rama.IZQUIERDA, label="Rama",
                    ).classes("w-40")
                with ui.row().classes("items-end gap-2"):
                    diametro = ui.number("Diámetro impulsor (mm)", value=None).classes("w-48").mark("diametro").tooltip(
                        "Déjalo vacío si la curva no depende del diámetro."
                    )
                    grado = ui.select(
                        list(range(GRADO_MINIMO, GRADO_MAXIMO + 1)), value=GRADO_POR_DEFECTO, label="Grado"
                    ).classes("w-24")
                with ui.row().classes("items-center gap-2"):
                    contador = ui.label().classes("text-sm")
                    ui.button("Borrar clics", on_click=lambda: borrar_semillas()).props("flat dense")
                ui.button("Digitalizar curva", on_click=lambda: digitalizar()).classes("w-full").mark("digitalizar")
            with ui.card().classes("w-full") as tarjeta_maximo:
                ui.label("Punto de máximo rendimiento").classes("font-medium")
                ui.label(
                    "Si el gráfico marca el máximo como un punto (p. ej. «81»), regístralo para tener "
                    "valores reales dentro del lazo más interno."
                ).classes("text-sm text-gray-600")
                with ui.row().classes("items-end gap-2"):
                    eta_maximo = ui.number("η del punto (%)", value=None).classes("w-36")
                    ui.button("Marcar en la imagen", on_click=lambda: pedir_maximo()).props("outline dense")
            lista = ui.column().classes("w-full")

    def es_iso() -> bool:
        return magnitud.value == Magnitud.EFICIENCIA and tipo.value == TIPO_ISO

    def actualizar_formulario() -> None:
        tipo.set_visibility(magnitud.value == Magnitud.EFICIENCIA)
        fila_iso.set_visibility(es_iso())
        tarjeta_maximo.set_visibility(any(c.ajustada.es_iso_eficiencia for c in ctx.sesion.curvas))
        n = len(estado["semillas"])
        contador.text = f"{n} clic(s) sobre la curva" + (" — haz al menos 2" if n < 2 else "")
        if estado["modo"] == "maximo":
            ayuda.text = "Haz clic sobre el punto de máximo rendimiento del gráfico."
        elif ctx.panel_activo is None:
            ayuda.text = "Define y calibra primero un panel en «2. Calibrar»."
        else:
            eje = "Q (de abajo arriba)" if es_iso() else "Q (de izquierda a derecha)"
            ayuda.text = (
                f"Haz clic sobre la curva: al principio, al final y, si cruza otra curva casi "
                f"en paralelo, justo después del cruce. Se sigue en función de {eje}."
            )

    def dibujar() -> None:
        s = ctx.sesion
        lienzo.mostrar(s.imagen, atenuada=True)
        partes = []
        if ctx.panel_activo is not None:
            partes.append(lienzo.rect(s.paneles[ctx.panel_activo].recuadro))
        for c in s.curvas:
            partes.append(lienzo.polilinea(c.trazado, NEGRO))
        for i, (x, y) in enumerate(estado["semillas"], start=1):
            partes.append(lienzo.marca(x, y, AYUDA, str(i)))
        lienzo.dibujar("".join(partes))

    def borrar_semillas() -> None:
        estado["semillas"] = []
        actualizar_formulario()
        dibujar()

    def pedir_maximo() -> None:
        if ctx.panel_activo is None:
            ui.notify("Elige el panel donde está el punto.", type="warning")
            return
        estado["modo"] = "maximo"
        actualizar_formulario()

    @proteger
    def al_clic(x: float, y: float) -> None:
        if ctx.panel_activo is None:
            ui.notify("Define y calibra primero un panel en «2. Calibrar».", type="warning")
            return
        if estado["modo"] == "maximo":
            estado["modo"] = "semillas"
            if eta_maximo.value is None:
                actualizar_formulario()
                raise ValueError("Escribe primero el η del punto de máximo rendimiento.")
            p = ctx.sesion.agregar_punto_eficiencia(ctx.panel_activo, (x, y), eta_maximo.value, diametro.value)
            ui.notify(f"Punto de máximo registrado: Q={p.q:.4g}, H={p.h:.4g}, η={p.eta:g} %", type="positive")
            ctx.emitir("curvas")
            return
        estado["semillas"].append((x, y))
        actualizar_formulario()
        dibujar()

    @proteger
    def digitalizar() -> None:
        if ctx.panel_activo is None:
            raise ValueError("Define y calibra primero un panel en «2. Calibrar».")
        if len(estado["semillas"]) < 2:
            raise ValueError("Haz al menos 2 clics sobre la curva (inicio y fin).")
        iso = es_iso()
        if iso and nivel.value is None:
            raise ValueError("Escribe el η de la curva de igual rendimiento.")
        c = ctx.sesion.digitalizar_curva(
            ctx.panel_activo, estado["semillas"], magnitud.value, diametro.value, int(grado.value),
            nivel=nivel.value if iso else None, rama=rama.value if iso else None,
        )
        estado["semillas"] = []
        a = c.ajustada
        if c.avisos:
            ui.notify(f"{a.etiqueta}: revisa la curva. " + " ".join(c.avisos), type="warning", multi_line=True, timeout=12000)
        else:
            ui.notify(f"{a.etiqueta} digitalizada (R² = {a.r2:.4f}).", type="positive")
        ctx.emitir("curvas")

    @ui.refreshable
    def listado() -> None:
        s = ctx.sesion
        if not s.curvas and not s.puntos_eficiencia:
            return
        ui.label("Curvas digitalizadas").classes("font-medium")
        for i, c in enumerate(s.curvas):
            a = c.ajustada
            variable = "H" if a.funcion_de == "y" else "Q"
            unidad = a.unidad_y if a.funcion_de == "y" else a.unidad_x
            with ui.row().classes("w-full items-start no-wrap gap-2 border-b py-1"):
                with ui.column().classes("gap-0 flex-grow"):
                    ui.label(f"{a.etiqueta} · {s.paneles[c.panel].nombre}").classes("text-sm font-medium")
                    ui.label(
                        f"grado {a.grado} · R² = {a.r2:.4f} · válida en {variable} ∈ [{a.x_min:.4g}, {a.x_max:.4g}] {unidad}"
                    ).classes("text-xs text-gray-600")
                    for aviso in c.avisos:
                        ui.label(f"⚠ {aviso}").classes("text-xs text-amber-800")
                ui.button(icon="delete", on_click=lambda i=i: quitar(i)).props("flat dense round")
        for i, p in enumerate(s.puntos_eficiencia):
            with ui.row().classes("w-full items-center no-wrap gap-2 border-b py-1"):
                ui.label(f"Máximo η {p.eta:g} % en Q={p.q:.4g}, H={p.h:.4g}").classes("text-sm flex-grow")
                ui.button(icon="delete", on_click=lambda i=i: quitar_maximo(i)).props("flat dense round")

    def quitar(i: int) -> None:
        ctx.sesion.quitar_curva(i)
        ctx.emitir("curvas")

    def quitar_maximo(i: int) -> None:
        ctx.sesion.quitar_punto_eficiencia(i)
        ctx.emitir("curvas")

    def refrescar() -> None:
        listado.refresh()
        actualizar_formulario()
        dibujar()

    def al_cambiar_panel() -> None:
        estado.update(semillas=[], modo="semillas")
        refrescar()

    with lista:
        listado()
    magnitud.on_value_change(lambda: actualizar_formulario())
    tipo.on_value_change(lambda: actualizar_formulario())
    ctx.al("imagen", al_cambiar_panel)
    ctx.al("paneles", al_cambiar_panel)
    ctx.al("curvas", refrescar)
    refrescar()
