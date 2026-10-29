"""Pestaña 4: las tres gráficas únicas de la sesión y los cuadros de cálculo.

- Las gráficas son SIEMPRE las mismas figuras del `GestorGraficas` de la sesión;
  aquí solo se muestran y se refrescan (regla 6).
- Cuadro 1 (morado): Q → H, η, NPSH, P. Cuadro 2 (azul): H → Q; si hay dos
  caudales válidos se muestran los dos como opciones. Cuadro 3 (naranja): punto
  conocido (Q, H) respecto a la curva de la bomba.
- Cada cuadro tiene un botón «Agregar» que añade filas; cada fila tiene su tono.
"""

from __future__ import annotations

from nicegui import ui

from bombas.core.calculadoras import Estado, Valor
from bombas.core.modelos import Magnitud
from bombas.graficas.estilos import CUADRO_ALTURA, CUADRO_CAUDAL, CUADRO_PUNTO, PALETAS, color_fila
from bombas.graficas.figuras import TIPOS
from bombas.ui import guia

TITULOS = {
    CUADRO_ALTURA: "Cuadro 1 · Cálculo de altura (Q → H)",
    CUADRO_CAUDAL: "Cuadro 2 · Cálculo de caudal (H → Q)",
    CUADRO_PUNTO: "Cuadro 3 · Puntos de operación (Q, H)",
}


def _numero(v: float) -> str:
    return f"{v:.4g}"


def _valor(nombre: str, v: Valor) -> str:
    if v.valor is None:
        return f"{nombre} = —"
    signo = "≥ " if v.cota_minima else ""
    return f"{nombre} = {signo}{_numero(v.valor)} {v.unidad}".rstrip()


def _estado(e: Estado) -> str:
    return " · ".join(_valor(n, v) for n, v in (("H", e.h), ("η", e.eta), ("NPSH", e.npsh), ("P", e.potencia)))


def _unidades(sesion) -> tuple[str, str]:
    """Unidades de Q y H de la bomba (las del gráfico original)."""
    h = next((c for c in sesion.bomba.curvas if c.magnitud == Magnitud.ALTURA), None)
    return (h.unidad_x, h.unidad_y) if h else ("", "")


def lineas_resultado(cuadro: int, r) -> list[tuple[str, str]]:
    """Texto del resultado de una fila: (línea, clases CSS). Sin elementos de UI, para poder probarlo."""
    lineas: list[tuple[str, str]] = []
    if cuadro == CUADRO_ALTURA:
        lineas.append((_estado(r.estado), "text-black"))
        avisos = r.estado.avisos
    elif cuadro == CUADRO_CAUDAL:
        if len(r.opciones) > 1:  # nunca se elige una por defecto: se muestran todas
            lineas.append((f"{len(r.opciones)} caudales posibles con esa altura — elige el de tu instalación:", "font-medium"))
            for i, e in enumerate(r.opciones, start=1):
                lineas.append((f"Opción {i}: Q = {_numero(e.q)} · " + _estado(e), "text-black"))
        elif r.opciones:
            e = r.opciones[0]
            lineas.append((f"Q = {_numero(e.q)} · " + _estado(e), "text-black"))
        avisos = [a for a in r.avisos if not a.startswith("Hay ")]  # el aviso de 2 caudales ya se muestra arriba
        avisos += [a for e in r.opciones for a in e.avisos]
    else:
        if r.posicion:
            signo = "+" if r.diferencia >= 0 else "−"
            lineas.append(
                (f"{r.posicion.capitalize()} de la curva ({signo}{_numero(abs(r.diferencia))} {r.h_bomba.unidad})", "font-medium")
            )
        lineas.append((" · ".join([_valor("H curva", r.h_bomba), _valor("η", r.eta), _valor("NPSH", r.npsh), _valor("P", r.potencia)]), "text-black"))
        avisos = r.avisos
    lineas += [(f"⚠ {a}", "text-xs text-amber-800") for a in dict.fromkeys(avisos)]
    return lineas


class Fila:
    def __init__(self, cuadro: "Cuadro", indice: int):
        self.cuadro, self.indice = cuadro, indice
        ctx = cuadro.ctx
        color = color_fila(cuadro.numero, indice)
        with cuadro.filas:
            with ui.row().classes("w-full items-start no-wrap gap-2 border-b py-1") as self.contenedor:
                ui.element("div").classes("w-3 h-3 mt-5 rounded-full shrink-0").style(f"background:{color}")
                with ui.column().classes("gap-1 flex-grow"):
                    with ui.row().classes("items-end gap-2"):
                        q_u, h_u = _unidades(ctx.sesion)
                        self.q = self.h = None
                        if cuadro.numero in (CUADRO_ALTURA, CUADRO_PUNTO):
                            self.q = ui.number(f"Q ({q_u})" if q_u else "Q").classes("w-28").mark(f"c{cuadro.numero}-q-{indice}")
                        if cuadro.numero in (CUADRO_CAUDAL, CUADRO_PUNTO):
                            self.h = ui.number(f"H ({h_u})" if h_u else "H").classes("w-28").mark(f"c{cuadro.numero}-h-{indice}")
                        self.diametro = ui.select({}, label="Diámetro").classes("w-32").mark(
                            f"c{cuadro.numero}-diametro-{indice}"
                        )
                    self.resultado = ui.column().classes("gap-0").mark(f"c{cuadro.numero}-resultado-{indice}")
                ui.button(icon="close", on_click=self.quitar).props("flat dense round").mark(
                    f"quitar-c{cuadro.numero}-{indice}"
                )
        for entrada in (self.q, self.h, self.diametro):
            if entrada is not None:
                entrada.on_value_change(lambda: self.calcular())
        self.actualizar_diametros()

    def actualizar_diametros(self) -> None:
        diametros = self.cuadro.ctx.sesion.diametros()
        self.diametro.options = {d: f"{d:g} mm" for d in diametros}
        self.diametro.update()
        self.diametro.set_visibility(bool(diametros))
        if self.diametro.value not in diametros:
            # Empieza vacío: el usuario elige el diámetro de su impulsor (no se supone ninguno).
            self.diametro.value = None

    def _mostrar(self, lineas: list[tuple[str, str]]) -> None:
        self.resultado.clear()
        with self.resultado:
            for texto, clase in lineas:
                ui.label(texto).classes(f"text-sm {clase}")

    def calcular(self) -> None:
        ctx, n = self.cuadro.ctx, self.cuadro.numero
        q = self.q.value if self.q else None
        h = self.h.value if self.h else None
        falta_diametro = bool(ctx.sesion.diametros()) and self.diametro.value is None
        if (self.q and q is None) or (self.h and h is None) or falta_diametro:
            ctx.sesion.quitar_fila(n, self.indice)
            hay_datos = (self.q is None or q is not None) and (self.h is None or h is not None)
            self._mostrar([("Elige el «Diámetro» de esta fila.", "text-amber-800")] if hay_datos else [])
            self.cuadro.refrescar_graficas()
            return
        try:
            r = ctx.sesion.calcular(n, self.indice, q=q, h=h, diametro=self.diametro.value)
        except ValueError as e:
            self._mostrar([(str(e), "text-amber-800")])
            return
        lineas = lineas_resultado(n, r)
        self._mostrar(lineas)
        self.cuadro.refrescar_graficas()

    def quitar(self) -> None:
        self.cuadro.ctx.sesion.quitar_fila(self.cuadro.numero, self.indice)
        self.cuadro.filas_activas.remove(self)
        self.contenedor.delete()
        self.cuadro.refrescar_graficas()


class Cuadro:
    def __init__(self, ctx, numero: int, refrescar_graficas):
        self.ctx, self.numero, self.refrescar_graficas = ctx, numero, refrescar_graficas
        self.filas_activas: list[Fila] = []
        self._siguiente = 0
        color = PALETAS[numero][0]
        with ui.card().classes("w-full").style(f"border-top: 4px solid {color}"):
            ui.label(TITULOS[numero]).classes("font-medium").style(f"color:{color}")
            self.filas = ui.column().classes("w-full gap-0")
            # Quasar pinta los botones con su color primario; !important impone el del cuadro.
            ui.button("Agregar", icon="add", on_click=self.agregar).props("outline dense").style(
                f"color:{color} !important"
            ).mark(f"agregar-c{numero}")
        self.agregar()

    def agregar(self) -> None:
        self.filas_activas.append(Fila(self, self._siguiente))
        self._siguiente += 1  # cada fila conserva su índice (y su tono) aunque se borren otras

    def recalcular(self) -> None:
        for fila in self.filas_activas:
            fila.actualizar_diametros()
            fila.calcular()


def crear(ctx) -> None:
    graficas = []

    guia.mostrar(guia.CALCULADORAS, "Guía paso a paso: gráficas y calculadoras", "guia-calculadoras")
    def refrescar_graficas() -> None:
        for g in graficas:
            g.update()

    with ui.row().classes("w-full no-wrap items-start gap-4"):
        with ui.column().classes("w-3/5"):
            sin_curvas = ui.label("Digitaliza curvas en «3. Digitalizar» para verlas aquí.").classes("text-gray-600")
            for tipo in TIPOS:
                graficas.append(ui.plotly(ctx.sesion.gestor.figura(tipo)).classes("w-full h-96"))
        with ui.column().classes("w-2/5"):
            cuadros = [Cuadro(ctx, n, refrescar_graficas) for n in (CUADRO_ALTURA, CUADRO_CAUDAL, CUADRO_PUNTO)]

    def al_cambiar_curvas() -> None:
        sin_curvas.set_visibility(not ctx.sesion.curvas)
        for c in cuadros:
            c.recalcular()
        refrescar_graficas()

    ctx.al("curvas", al_cambiar_curvas)
    ctx.al("imagen", al_cambiar_curvas)
    al_cambiar_curvas()
