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
ACCION_BORRAR = "borrar"
ACCION_ANADIR = "anadir"


def crear(ctx) -> None:
    from bombas.ui.app import proteger

    # modo: "semillas", "maximo" o "corregir" (corrección manual de la curva `corrigiendo`).
    estado = {"semillas": [], "modo": "semillas", "corrigiendo": None, "esquina": None}

    guia.mostrar(guia.DIGITALIZAR, "Guía paso a paso: digitalizar curvas", "guia-digitalizar")
    with ui.row().classes("w-full no-wrap items-start gap-4"):
        with ui.column().classes("w-3/5"):
            ayuda = ui.label().classes("text-sm text-gray-700")
            lienzo = Lienzo(lambda x, y: al_clic(x, y), "lienzo-digitalizar")
        with ui.column().classes("w-2/5"):
            selector_panel(ctx)
            control_umbral(ctx, "umbral-digitalizar")
            with ui.card().classes("w-full").style(f"border: 2px solid {AYUDA}").mark("tarjeta-correccion") as tarjeta_correccion:
                titulo_correccion = ui.label().classes("font-medium")
                ui.label(
                    "Los puntos digitalizados se ven en verde. Quita los que se fueron por otra curva "
                    "o añade puntos sobre el trazo correcto; la curva se vuelve a ajustar en cada cambio."
                ).classes("text-sm text-gray-600")
                accion = ui.toggle(
                    {ACCION_BORRAR: "Borrar puntos (zona)", ACCION_ANADIR: "Añadir punto"}, value=ACCION_BORRAR,
                    on_change=lambda: cambiar_accion(),
                ).mark("accion-correccion")
                info_correccion = ui.label().classes("text-sm").mark("info-correccion")
                with ui.row().classes("gap-2"):
                    ui.button("Deshacer", icon="undo", on_click=lambda: deshacer()).props("outline dense").mark(
                        "deshacer-correccion"
                    )
                    ui.button("Terminar corrección", icon="check", on_click=lambda: terminar_correccion()).props(
                        "dense"
                    ).mark("terminar-correccion")
            with ui.card().classes("w-full").mark("tarjeta-nueva-curva") as tarjeta_nueva:
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
        corrigiendo = estado["modo"] == "corregir"
        tarjeta_correccion.set_visibility(corrigiendo)
        tarjeta_nueva.set_visibility(not corrigiendo)
        if corrigiendo:
            c = ctx.sesion.curvas[estado["corrigiendo"]]
            a = c.ajustada
            titulo_correccion.text = f"Corrigiendo puntos: {a.etiqueta}"
            info_correccion.text = f"{len(c.digitalizada.x)} puntos · R² = {a.r2:.4f}"
            if accion.value == ACCION_ANADIR:
                ayuda.text = "Haz clic sobre el trazo correcto de la curva para añadir un punto."
            elif estado["esquina"] is None:
                ayuda.text = "Haz clic en una esquina de la zona con los puntos que quieres borrar."
            else:
                ayuda.text = "Ahora haz clic en la esquina opuesta de la zona: se borran los puntos que queden dentro."
        elif estado["modo"] == "maximo":
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
        if estado["modo"] == "corregir":
            partes.append(lienzo.puntos(s.puntos_curva(estado["corrigiendo"])))
            if estado["esquina"] is not None:
                partes.append(lienzo.marca(*estado["esquina"], AYUDA, "esquina 1"))
        lienzo.dibujar("".join(partes))

    def corregir(i: int) -> None:
        c = ctx.sesion.curvas[i]
        if ctx.panel_activo != c.panel:
            ctx.panel_activo = c.panel
            ctx.emitir("paneles")  # reinicia el modo; después se entra en corrección
        estado.update(modo="corregir", corrigiendo=i, esquina=None, semillas=[])
        accion.value = ACCION_BORRAR
        refrescar()

    def terminar_correccion() -> None:
        estado.update(modo="semillas", corrigiendo=None, esquina=None)
        refrescar()

    def cambiar_accion() -> None:
        estado["esquina"] = None
        if estado["modo"] == "corregir":
            actualizar_formulario()
            dibujar()

    @proteger
    def deshacer() -> None:
        ctx.sesion.deshacer_edicion(estado["corrigiendo"])
        ctx.emitir("curvas")

    def clic_correccion(x: float, y: float) -> None:
        i = estado["corrigiendo"]
        if accion.value == ACCION_ANADIR:
            q, v = ctx.sesion.agregar_punto_curva(i, (x, y))
            ui.notify(f"Punto añadido: Q = {q:.4g}, {v:.4g}.", type="positive")
        elif estado["esquina"] is None:
            estado["esquina"] = (x, y)
            actualizar_formulario()
            dibujar()
            return
        else:
            esquina, estado["esquina"] = estado["esquina"], None
            try:
                n = ctx.sesion.quitar_puntos_curva(i, esquina, (x, y))
            finally:
                actualizar_formulario()
                dibujar()
            ui.notify(f"{n} punto(s) borrado(s). La curva se ha vuelto a ajustar.", type="positive")
        ctx.emitir("curvas")

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
        if estado["modo"] == "corregir":
            clic_correccion(x, y)
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
                        + (" · corregida a mano" if c.editada else "")
                    ).classes("text-xs text-gray-600")
                    for aviso in c.avisos:
                        ui.label(f"⚠ {aviso}").classes("text-xs text-amber-800")
                ui.button(icon="edit", on_click=lambda i=i: corregir(i)).props("flat dense round").tooltip(
                    "Corregir puntos"
                ).mark(f"corregir-curva-{i}")
                ui.button(icon="delete", on_click=lambda i=i: quitar(i)).props("flat dense round").tooltip(
                    "Borrar curva"
                )
        for i, p in enumerate(s.puntos_eficiencia):
            with ui.row().classes("w-full items-center no-wrap gap-2 border-b py-1"):
                ui.label(f"Máximo η {p.eta:g} % en Q={p.q:.4g}, H={p.h:.4g}").classes("text-sm flex-grow")
                ui.button(icon="delete", on_click=lambda i=i: quitar_maximo(i)).props("flat dense round")

    def quitar(i: int) -> None:
        ctx.sesion.quitar_curva(i)
        if estado["modo"] == "corregir":  # los índices cambian: se termina la corrección
            estado.update(modo="semillas", corrigiendo=None, esquina=None)
        ctx.emitir("curvas")

    def quitar_maximo(i: int) -> None:
        ctx.sesion.quitar_punto_eficiencia(i)
        ctx.emitir("curvas")

    def refrescar() -> None:
        listado.refresh()
        actualizar_formulario()
        dibujar()

    def al_cambiar_panel() -> None:
        estado.update(semillas=[], modo="semillas", corrigiendo=None, esquina=None)
        refrescar()

    with lista:
        listado()
    magnitud.on_value_change(lambda: actualizar_formulario())
    tipo.on_value_change(lambda: actualizar_formulario())
    ctx.al("imagen", al_cambiar_panel)
    ctx.al("paneles", al_cambiar_panel)
    ctx.al("curvas", refrescar)
    refrescar()
