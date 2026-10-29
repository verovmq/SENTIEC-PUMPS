"""Pestaña 2: paneles, umbral de oscuridad (con vista previa en vivo) y calibración de ejes."""

from __future__ import annotations

import cv2
from nicegui import ui

from bombas.core.modelos import UNIDADES_SUGERIDAS, Escala
from bombas.ui import guia
from bombas.ui.lienzo import AYUDA, Lienzo, data_url

# (nombre del eje, descripción, tipo de unidad)
EJES = [
    ("Q", "Caudal (eje horizontal)", "caudal"),
    ("H", "Altura manométrica", "altura"),
    ("η", "Eficiencia (solo si tiene eje propio)", "eficiencia"),
    ("NPSH", "NPSH", "npsh"),
    ("P", "Potencia", "potencia"),
]
UMBRAL_MIN, UMBRAL_MAX = 30, 230


def selector_panel(ctx):
    """Desplegable del panel activo, compartido por las pestañas."""
    selector = ui.select({}, label="Panel activo").classes("w-48")

    def refrescar() -> None:
        selector.options = {i: p.nombre for i, p in enumerate(ctx.sesion.paneles)}
        selector.update()
        selector.value = ctx.panel_activo

    def cambiar(e) -> None:
        if e.value is not None and e.value != ctx.panel_activo:
            ctx.panel_activo = e.value
            ctx.emitir("paneles")

    selector.on_value_change(cambiar)
    ctx.al("paneles", refrescar)
    ctx.al("imagen", refrescar)
    return selector


def control_umbral(ctx, marca: str = "umbral") -> None:
    """Deslizante del umbral siempre visible, con el original y la máscara lado a lado.

    Mientras se mueve se usa la vista previa rápida (copia reducida); la máscara
    completa a resolución real solo se calcula al digitalizar.
    """
    with ui.card().classes("w-full"):
        ui.label("Umbral de oscuridad").classes("font-medium")
        ui.label(
            "Mueve el deslizante hasta que en la máscara (derecha) aparezcan las curvas completas "
            "con la menor cantidad posible de cuadrícula y texto. Más alto = admite trazos más claros. "
            "Algún corte corto (donde se cruzan curvas o pasa una etiqueta) no importa: al digitalizar "
            "se salta; si falta un tramo largo, haz un clic extra sobre la curva después del corte."
        ).classes("text-sm text-gray-600")
        sin_panel = ui.label("Define primero un panel en «2. Calibrar».").classes("text-sm text-gray-500")
        with ui.column().classes("w-full") as contenido:
            with ui.row().classes("w-full items-center gap-3"):
                deslizante = ui.slider(min=UMBRAL_MIN, max=UMBRAL_MAX, step=1, value=100).classes("flex-grow").mark(marca)
                valor = ui.label().classes("w-10 text-right font-mono")
            with ui.row().classes("w-full no-wrap gap-2"):
                original = ui.image().classes("w-1/2 border")
                mascara = ui.image().classes("w-1/2 border").mark(f"{marca}-mascara")

    def vista(umbral: int) -> None:
        sesion, i = ctx.sesion, ctx.panel_activo
        previa = sesion.vista_previa(i, umbral)
        x0, y0, x1, y1 = sesion.paneles[i].recuadro
        recorte = cv2.resize(sesion.imagen[y0 : y1 + 1, x0 : x1 + 1], previa.shape[::-1], interpolation=cv2.INTER_AREA)
        original.set_source(data_url(recorte))
        mascara.set_source(data_url(previa))
        valor.text = str(umbral)

    def al_mover(e) -> None:
        if ctx.panel_activo is None:
            return
        umbral = int(e.args if not isinstance(e.args, (list, tuple)) else e.args[0])
        ctx.sesion.fijar_umbral(ctx.panel_activo, umbral)
        vista(umbral)
        ctx.emitir("umbral")

    def refrescar() -> None:
        hay_panel = ctx.panel_activo is not None
        sin_panel.set_visibility(not hay_panel)
        contenido.set_visibility(hay_panel)
        if hay_panel:
            umbral = ctx.sesion.paneles[ctx.panel_activo].umbral
            deslizante.value = umbral
            vista(umbral)

    deslizante.on("update:model-value", al_mover, throttle=0.15)
    for evento in ("paneles", "imagen", "umbral"):
        ctx.al(evento, refrescar)
    refrescar()


def crear(ctx) -> None:
    from bombas.ui.app import proteger

    estado = {"modo": None, "esquinas": [], "marcas": {}}  # marcas[eje] = {1: (x, y), 2: (x, y)}
    etiquetas_marca = {}  # (eje, k) → etiqueta con la posición de la marca en el formulario

    guia.mostrar(guia.CALIBRAR, "Guía paso a paso: paneles, umbral y ejes", "guia-calibrar")
    with ui.row().classes("w-full no-wrap items-start gap-4"):
        with ui.column().classes("w-3/5"):
            ayuda = ui.label("Carga primero un archivo.").classes("text-sm text-gray-700")
            lienzo = Lienzo(lambda x, y: al_clic(x, y), "lienzo-calibrar")
        with ui.column().classes("w-2/5"):
            with ui.row().classes("items-end gap-2"):
                selector_panel(ctx)
                ui.button("Nuevo panel", on_click=lambda: iniciar_panel()).props("outline").mark("nuevo-panel")
                ui.button("Enderezar imagen", on_click=lambda: enderezar()).props("flat").tooltip(
                    "Detecta y corrige una inclinación pequeña de la cuadrícula. Hazlo antes de crear paneles."
                )
            control_umbral(ctx, "umbral-calibrar")
            ejes_ui = ui.column().classes("w-full")

    def dibujar() -> None:
        s = ctx.sesion
        lienzo.mostrar(s.imagen)
        partes = []
        for i, p in enumerate(s.paneles):
            partes.append(lienzo.rect(p.recuadro, AYUDA if i == ctx.panel_activo else "#9E9E9E", p.nombre))
        if ctx.panel_activo is not None:
            x0, y0, x1, y1 = s.paneles[ctx.panel_activo].recuadro
            for nombre, eje in s.paneles[ctx.panel_activo].ejes.items():
                for p in (eje.p1, eje.p2):
                    x, y = (p, y1) if nombre == "Q" else (x0, p)
                    partes.append(lienzo.marca(x, y, etiqueta=nombre))
        for nombre, marcas in estado["marcas"].items():
            for k, (x, y) in marcas.items():
                partes.append(lienzo.marca(x, y, etiqueta=f"{nombre}{k}"))
        for x, y in estado["esquinas"]:
            partes.append(lienzo.marca(x, y))
        lienzo.dibujar("".join(partes))

    def indicar(texto: str) -> None:
        ayuda.text = texto

    def iniciar_panel() -> None:
        if ctx.sesion.imagen is None:
            ui.notify("Carga primero un archivo.", type="warning")
            return
        estado.update(modo="recuadro", esquinas=[])
        indicar("Haz clic en dos esquinas opuestas de la zona de trazado del panel (dentro de los ejes).")

    @proteger
    def enderezar() -> None:
        angulo = ctx.sesion.enderezar()
        ui.notify(f"Inclinación corregida: {angulo:.2f}°" if abs(angulo) >= 0.05 else "La imagen ya está recta.")
        ctx.emitir("imagen")

    @proteger
    def al_clic(x: float, y: float) -> None:
        modo = estado["modo"]
        if modo == "recuadro":
            estado["esquinas"].append((x, y))
            if len(estado["esquinas"]) == 2:
                try:
                    ctx.panel_activo = ctx.sesion.agregar_panel(*estado["esquinas"])
                finally:
                    estado.update(modo=None, esquinas=[])
                indicar("Panel creado. Ajusta el umbral y calibra sus ejes.")
                ctx.emitir("paneles")
            dibujar()
        elif isinstance(modo, tuple):  # ("marca", eje, 1 | 2)
            _, eje, k = modo
            estado["marcas"].setdefault(eje, {})[k] = (x, y)
            estado["modo"] = None
            indicar(f"Marca {k} del eje {eje} colocada. Escribe su valor y pulsa «Guardar eje».")
            # Solo se actualiza el texto de la marca: reconstruir el formulario borraría los valores escritos.
            if (eje, k) in etiquetas_marca:
                etiquetas_marca[(eje, k)].text = f"({x:.0f}, {y:.0f}) px"
            dibujar()

    def pedir_marca(eje: str, k: int) -> None:
        estado["modo"] = ("marca", eje, k)
        direccion = "horizontal" if eje == "Q" else "vertical"
        indicar(f"Haz clic sobre una marca conocida del eje {eje} ({direccion}): marca {k}.")

    @ui.refreshable
    def ejes_formulario() -> None:
        i = ctx.panel_activo
        if i is None:
            return
        panel = ctx.sesion.paneles[i]
        etiquetas_marca.clear()
        ui.label(f"Ejes de {panel.nombre}").classes("font-medium mt-2")
        ui.label(
            "Para cada eje: dos clics en marcas conocidas (lo más separadas posible), sus valores "
            "y la unidad tal como aparece en el gráfico. Calibra solo los ejes que tenga el panel."
        ).classes("text-sm text-gray-600")
        for nombre, descripcion, tipo in EJES:
            eje = panel.ejes.get(nombre)
            marcas = estado["marcas"].get(nombre, {})
            titulo = f"{nombre} — {descripcion}" + (f"  ✔ {eje.unidad}" if eje else "")
            with ui.expansion(titulo).classes("w-full border rounded"):
                with ui.row().classes("items-end gap-2"):
                    unidad = ui.select(
                        UNIDADES_SUGERIDAS[tipo], label="Unidad", new_value_mode="add-unique",
                        value=eje.unidad if eje else UNIDADES_SUGERIDAS[tipo][0],
                    ).classes("w-28")
                    escala = ui.select(
                        {Escala.LINEAL: "lineal", Escala.LOG: "logarítmica"}, label="Escala",
                        value=eje.escala if eje else Escala.LINEAL,
                    ).classes("w-36")
                valores = {}
                for k in (1, 2):
                    with ui.row().classes("items-end gap-2"):
                        ui.button(f"Marca {k}", on_click=lambda n=nombre, k=k: pedir_marca(n, k)).props(
                            "outline dense"
                        ).mark(f"marca-{nombre}-{k}")
                        estado_marca = f"({marcas[k][0]:.0f}, {marcas[k][1]:.0f}) px" if k in marcas else "sin marcar"
                        etiquetas_marca[(nombre, k)] = ui.label(estado_marca).classes("text-sm w-28")
                        defecto = (eje.v1 if k == 1 else eje.v2) if eje else None
                        valores[k] = ui.number(f"Valor {k}", value=defecto).classes("w-28").mark(f"valor-{nombre}-{k}")
                ui.button(
                    "Guardar eje",
                    on_click=lambda n=nombre, u=unidad, e=escala, v=valores: guardar_eje(n, u.value, e.value, v),
                ).props("dense").mark(f"guardar-{nombre}")

    @proteger
    def guardar_eje(nombre: str, unidad: str, escala: Escala, valores) -> None:
        marcas = estado["marcas"].get(nombre, {})
        if 1 not in marcas or 2 not in marcas:
            raise ValueError(f"Marca los dos puntos del eje {nombre} sobre la imagen.")
        if valores[1].value is None or valores[2].value is None:
            raise ValueError(f"Escribe los valores de las dos marcas del eje {nombre}.")
        ctx.sesion.calibrar_eje(
            ctx.panel_activo, nombre, unidad or "", marcas[1], valores[1].value, marcas[2], valores[2].value, escala
        )
        estado["marcas"].pop(nombre, None)
        ui.notify(f"Eje {nombre} calibrado ({unidad}).", type="positive")
        ctx.emitir("paneles")

    def al_cambiar_imagen() -> None:
        estado.update(modo=None, esquinas=[], marcas={})
        indicar("Pulsa «Nuevo panel» y marca la zona de trazado." if ctx.sesion.imagen is not None else "Carga primero un archivo.")
        refrescar()

    def refrescar() -> None:
        ejes_formulario.refresh()
        dibujar()

    with ejes_ui:
        ejes_formulario()
    ctx.al("imagen", al_cambiar_imagen)
    ctx.al("paneles", refrescar)
