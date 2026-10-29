"""Las tres gráficas de la sesión y el dibujo de los puntos de las calculadoras.

`GestorGraficas` crea UNA sola vez las tres figuras (regla 6 de CLAUDE.md):
(a) H + η, (b) NPSH y (c) Potencia. Las calculadoras nunca crean figuras: añaden
y quitan trazas en estas mismas, identificadas por un grupo (p. ej. "c1-f0" =
cuadro 1, fila 0) para poder reemplazar una fila al recalcularla.

- Curvas, ejes y textos en negro (regla 5); cada curva lleva su etiqueta, con el
  diámetro si depende de él (regla 3).
- En (a), η(Q) va en un eje Y secundario si su unidad difiere de la de H. Si la
  bomba tiene curvas de igual rendimiento, se dibujan sobre H–Q con su valor de η.
- Cada punto: marcador y dos líneas punteadas hasta los ejes (regla 8). Para un
  punto del eje secundario, la línea horizontal va al eje de la derecha.
- Las unidades de los ejes son las del gráfico original (regla 4).
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from bombas.core.calculadoras import GRAFICA_ALTURA, GRAFICA_NPSH, GRAFICA_POTENCIA, PuntoGrafico
from bombas.core.modelos import Bomba, CurvaAjustada, Magnitud
from bombas.graficas.estilos import (
    ESTILO_GUIA,
    GRIS_CUADRICULA,
    GROSOR_CURVA,
    NEGRO,
    TAMANO_MARCADOR,
)

TIPOS = (GRAFICA_ALTURA, GRAFICA_NPSH, GRAFICA_POTENCIA)
TITULOS = {GRAFICA_ALTURA: "Altura y eficiencia", GRAFICA_NPSH: "NPSH", GRAFICA_POTENCIA: "Potencia"}
META_CURVA = "curva"
PUNTOS_CURVA = 120
MARGEN = 1.08  # los ejes llegan un 8 % más allá del máximo


def _muestrear(c: CurvaAjustada) -> tuple[np.ndarray, np.ndarray]:
    """Puntos (x, y) del gráfico a lo largo del rango válido de la curva."""
    t = np.linspace(c.x_min, c.x_max, PUNTOS_CURVA)
    v = c.evaluar(t)
    return (t, v) if c.funcion_de == "x" else (v, t)


def _maximo_bonito(valor: float) -> float:
    """Máximo de eje redondeado hacia arriba a un valor redondo (1; 1,2; 1,5; 2; 2,5; 3; 3,5; 4; 5; 6; 7; 8 × 10^k)."""
    objetivo = valor * MARGEN
    if objetivo <= 0:
        return 1.0
    potencia = 10 ** np.floor(np.log10(objetivo))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 10):
        if m * potencia >= objetivo:
            return float(m * potencia)
    return float(10 * potencia)


def _rotulo(c: CurvaAjustada) -> str:
    """Texto junto a la curva: corto en las de igual rendimiento ("80 %"), como en los catálogos."""
    return f"{c.nivel:g} %" if c.es_iso_eficiencia else c.etiqueta


def _titulo_eje(nombre: str, unidad: str) -> str:
    return f"{nombre} [{unidad}]" if unidad else nombre


class GestorGraficas:
    """Dueño de las tres figuras de la sesión. Crear uno por sesión y reutilizarlo."""

    def __init__(self, bomba: Bomba):
        self.bomba = bomba
        self._figuras: dict[str, go.Figure] = {tipo: self._crear(tipo) for tipo in TIPOS}
        self._eje_eta = False
        self.dibujar_curvas()

    def figura(self, tipo: str) -> go.Figure:
        """Siempre la misma figura para cada tipo (nunca una copia)."""
        return self._figuras[tipo]

    # --- creación y curvas ---------------------------------------------------

    @staticmethod
    def _crear(tipo: str) -> go.Figure:
        fig = go.Figure()
        eje = dict(
            color=NEGRO,
            linecolor=NEGRO,
            tickcolor=NEGRO,
            showline=True,
            mirror=False,
            ticks="outside",
            gridcolor=GRIS_CUADRICULA,
            zeroline=False,
            title_font=dict(color=NEGRO),
            tickfont=dict(color=NEGRO),
        )
        fig.update_layout(
            title=dict(text=TITULOS[tipo], font=dict(color=NEGRO)),
            font=dict(color=NEGRO),
            paper_bgcolor="white",
            plot_bgcolor="white",
            showlegend=False,
            margin=dict(l=70, r=70, t=50, b=60),
            xaxis=eje,
            yaxis=eje,
        )
        return fig

    def _curvas_de(self, tipo: str) -> list[tuple[CurvaAjustada, str]]:
        """(curva, eje Y) que van en cada gráfica."""
        b = self.bomba
        if tipo == GRAFICA_NPSH:
            return [(c, "y") for c in b.curvas if c.magnitud == Magnitud.NPSH]
        if tipo == GRAFICA_POTENCIA:
            return [(c, "y") for c in b.curvas if c.magnitud == Magnitud.POTENCIA]
        alturas = [c for c in b.curvas if c.magnitud == Magnitud.ALTURA]
        unidad_h = alturas[0].unidad_y if alturas else ""
        resultado = [(c, "y") for c in alturas]
        resultado += [(c, "y") for c in b.iso_eficiencia()]
        for c in b.curvas:
            if c.magnitud == Magnitud.EFICIENCIA and not c.es_iso_eficiencia:
                resultado.append((c, "y2" if c.unidad_y != unidad_h else "y"))
        return resultado

    def dibujar_curvas(self) -> None:
        """(Re)dibuja las curvas de la bomba en negro. Conserva los puntos de las calculadoras."""
        for tipo, fig in self._figuras.items():
            fig.data = tuple(t for t in fig.data if t.meta != META_CURVA)
            fig.layout.annotations = [a for a in fig.layout.annotations if a.name != META_CURVA]
            curvas = self._curvas_de(tipo)
            for c, eje in curvas:
                x, y = _muestrear(c)
                fig.add_trace(
                    go.Scatter(
                        x=x, y=y, mode="lines", name=c.etiqueta, meta=META_CURVA, yaxis=eje,
                        line=dict(color=NEGRO, width=GROSOR_CURVA),
                        hovertemplate=f"{c.etiqueta}<br>%{{x:.4g}}, %{{y:.4g}}<extra></extra>",
                    )
                )
                # Etiqueta junto al extremo superior/derecho de la curva.
                i = int(np.argmax(y)) if c.es_iso_eficiencia else -1
                fig.add_annotation(
                    x=x[i], y=y[i], yref=eje, text=_rotulo(c), name=META_CURVA, showarrow=False,
                    xanchor="left", yanchor="bottom", font=dict(color=NEGRO, size=11),
                )
            self._ejes(tipo, fig, curvas)
            if tipo == GRAFICA_ALTURA:
                self._eje_eta = any(eje == "y2" for _, eje in curvas)
                self._dibujar_puntos_eficiencia(fig)

    def _dibujar_puntos_eficiencia(self, fig: go.Figure) -> None:
        """Puntos de máximo rendimiento: dato del gráfico, en negro y sin líneas a los ejes."""
        for p in self.bomba.puntos_eficiencia:
            fig.add_trace(
                go.Scatter(
                    x=[p.q], y=[p.h], mode="markers", name=f"η máx. {p.etiqueta}", meta=META_CURVA,
                    marker=dict(color=NEGRO, size=7, symbol="circle"),
                    hovertemplate=f"η máx. {p.etiqueta}<br>%{{x:.4g}}, %{{y:.4g}}<extra></extra>",
                )
            )
            fig.add_annotation(
                x=p.q, y=p.h, text=p.etiqueta, name=META_CURVA, showarrow=False,
                xanchor="left", yanchor="bottom", font=dict(color=NEGRO, size=11),
            )

    def _ejes(self, tipo: str, fig: go.Figure, curvas) -> None:
        if not curvas:
            return
        primarias = [c for c, eje in curvas if eje == "y"]
        secundarias = [c for c, eje in curvas if eje == "y2"]
        xs = np.concatenate([_muestrear(c)[0] for c, _ in curvas])
        fig.update_xaxes(range=[0, _maximo_bonito(float(xs.max()))], title_text=_titulo_eje("Q", curvas[0][0].unidad_x))
        if primarias:
            ys = np.concatenate([_muestrear(c)[1] for c in primarias])
            ref = next((c for c in primarias if not c.es_iso_eficiencia), primarias[0])
            nombre = {GRAFICA_ALTURA: "H", GRAFICA_NPSH: "NPSH", GRAFICA_POTENCIA: "P"}[tipo]
            fig.update_yaxes(range=[0, _maximo_bonito(float(ys.max()))], title_text=_titulo_eje(nombre, ref.unidad_y))
        if secundarias:
            ys = np.concatenate([_muestrear(c)[1] for c in secundarias])
            fig.update_layout(
                yaxis2=dict(
                    overlaying="y", side="right", range=[0, _maximo_bonito(float(ys.max()))], tickmode="auto",
                    title_text=_titulo_eje("η", secundarias[0].unidad_y), color=NEGRO, linecolor=NEGRO,
                    tickcolor=NEGRO, showline=True, ticks="outside", showgrid=False, zeroline=False,
                    title_font=dict(color=NEGRO), tickfont=dict(color=NEGRO),
                )
            )

    # --- puntos de las calculadoras -------------------------------------------

    def _ampliar_rango(self, fig: go.Figure, eje: str, valor: float) -> None:
        objeto = fig.layout[eje]
        if objeto.range is not None and _maximo_bonito(valor) > objeto.range[1]:
            objeto.range = [objeto.range[0], _maximo_bonito(valor)]

    def agregar_punto(self, punto: PuntoGrafico, color: str, grupo: str) -> None:
        """Marcador + línea punteada horizontal y vertical hasta los ejes."""
        fig = self._figuras[punto.grafica]
        eje_y = punto.eje_y if (punto.eje_y == "y" or self._eje_eta) else "y"
        nombre_eje_y = "yaxis2" if eje_y == "y2" else "yaxis"
        self._ampliar_rango(fig, "xaxis", punto.x)
        self._ampliar_rango(fig, nombre_eje_y, punto.y)
        x_min, x_max = fig.layout.xaxis.range or (0, punto.x)
        y_min = (fig.layout[nombre_eje_y].range or (0, punto.y))[0]
        # Horizontal hacia su eje Y: el izquierdo, o el derecho si es el secundario.
        x_eje = x_max if eje_y == "y2" else x_min
        guia = dict(color=color, width=1.5, dash=ESTILO_GUIA)
        comun = dict(meta=grupo, yaxis=eje_y, hoverinfo="skip", showlegend=False)
        fig.add_trace(go.Scatter(x=[x_eje, punto.x], y=[punto.y, punto.y], mode="lines", line=guia, **comun))
        fig.add_trace(go.Scatter(x=[punto.x, punto.x], y=[y_min, punto.y], mode="lines", line=guia, **comun))
        fig.add_trace(
            go.Scatter(
                x=[punto.x], y=[punto.y], mode="markers", name=punto.etiqueta, meta=grupo, yaxis=eje_y,
                marker=dict(color=color, size=TAMANO_MARCADOR, line=dict(color=NEGRO, width=1)),
                hovertemplate=f"{punto.etiqueta}<br>%{{x:.4g}}, %{{y:.4g}}<extra></extra>",
                showlegend=False,
            )
        )

    def quitar_grupo(self, grupo: str) -> None:
        for fig in self._figuras.values():
            fig.data = tuple(t for t in fig.data if t.meta != grupo)

    def quitar_puntos(self) -> None:
        """Quita todos los puntos de las calculadoras (conserva las curvas)."""
        for fig in self._figuras.values():
            fig.data = tuple(t for t in fig.data if t.meta == META_CURVA)

    def dibujar_resultado(self, resultado, color: str, grupo: str) -> None:
        """Reemplaza los puntos del grupo por los del resultado de una calculadora."""
        self.quitar_grupo(grupo)
        for punto in resultado.puntos():
            self.agregar_punto(punto, color, grupo)
