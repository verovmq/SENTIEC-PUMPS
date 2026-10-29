"""Imagen interactiva: muestra el gráfico, recibe clics y dibuja superposiciones SVG.

Las coordenadas de los clics y del SVG son píxeles de la imagen original, así
que coinciden con las de la sesión (recuadros, marcas de calibración, semillas).

Colores de las superposiciones:
- Las curvas ya digitalizadas se dibujan en NEGRO (regla 5) sobre la imagen
  atenuada, para que se distingan del trazo original.
- Las ayudas de trabajo (recuadros, marcas, semillas) van en verde: no son
  curvas ni calculadoras, y así no se confunden con morado/azul/naranja.
"""

from __future__ import annotations

import base64
from collections.abc import Callable

import cv2
import numpy as np
from nicegui import ui

from bombas.graficas.estilos import NEGRO

AYUDA = "#2E7D32"  # verde de las ayudas de trabajo


def data_url(imagen: np.ndarray, formato: str = ".jpg") -> str:
    """Imagen RGB o máscara bool como data URL (JPEG para fotos, PNG para máscaras)."""
    if imagen.dtype == bool:
        imagen = np.where(imagen, 0, 255).astype(np.uint8)  # trazo negro sobre blanco
        formato = ".png"
    if imagen.ndim == 3:
        imagen = cv2.cvtColor(imagen, cv2.COLOR_RGB2BGR)
    parametros = [cv2.IMWRITE_JPEG_QUALITY, 90] if formato == ".jpg" else []
    ok, datos = cv2.imencode(formato, imagen, parametros)
    tipo = "jpeg" if formato == ".jpg" else "png"
    return f"data:image/{tipo};base64,{base64.b64encode(datos.tobytes()).decode()}"


def atenuar(imagen: np.ndarray, fuerza: float = 0.6) -> np.ndarray:
    """Aclara la imagen para que lo que se dibuje encima destaque."""
    return (imagen.astype(np.float32) * (1 - fuerza) + 255 * fuerza).astype(np.uint8)


class Lienzo:
    def __init__(self, al_hacer_clic: Callable[[float, float], None], marca: str = ""):
        self._al_hacer_clic = al_hacer_clic
        self._escala = 1.0
        self.imagen = ui.interactive_image(on_mouse=self._clic, events=["click"], cross=AYUDA).classes("w-full")
        if marca:
            self.imagen.mark(marca)

    def _clic(self, e) -> None:
        self._al_hacer_clic(e.image_x, e.image_y)

    def mostrar(self, imagen: np.ndarray | None, atenuada: bool = False) -> None:
        if imagen is None:
            self.imagen.set_source("")
            return
        self._escala = max(1.0, max(imagen.shape[:2]) / 800)  # grosor de las ayudas según el tamaño
        self.imagen.set_source(data_url(atenuar(imagen) if atenuada else imagen))

    def dibujar(self, svg: str) -> None:
        self.imagen.content = svg

    # --- piezas SVG ------------------------------------------------------------------

    def rect(self, recuadro, color: str = AYUDA, etiqueta: str = "") -> str:
        x0, y0, x1, y1 = recuadro
        w = 1.5 * self._escala
        texto = (
            f'<text x="{x0 + 4 * self._escala}" y="{y0 + 14 * self._escala}" fill="{color}" '
            f'font-size="{12 * self._escala}">{etiqueta}</text>'
            if etiqueta else ""
        )
        return (
            f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" '
            f'stroke="{color}" stroke-width="{w}" stroke-dasharray="{6 * self._escala}"/>' + texto
        )

    def marca(self, x: float, y: float, color: str = AYUDA, etiqueta: str = "") -> str:
        r = 4 * self._escala
        texto = (
            f'<text x="{x + r + 2}" y="{y - r}" fill="{color}" font-size="{12 * self._escala}">{etiqueta}</text>'
            if etiqueta else ""
        )
        return f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="{1.5 * self._escala}"/>' + texto

    def puntos(self, puntos: np.ndarray, color: str = AYUDA) -> str:
        """Puntos digitalizados como círculos rellenos pequeños (corrección manual)."""
        r = 2.5 * self._escala
        return "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}"/>' for x, y in puntos)

    def polilinea(self, puntos: np.ndarray, color: str = NEGRO) -> str:
        coordenadas = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
        return (
            f'<polyline points="{coordenadas}" fill="none" stroke="{color}" '
            f'stroke-width="{2 * self._escala}" stroke-linejoin="round"/>'
        )
