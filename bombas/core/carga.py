"""Carga de PDF o imagen como matriz RGB (uint8, forma alto x ancho x 3).

Supuestos y límites:
- Los PDF se rasterizan con pypdfium2 (sin Poppler). 300 DPI es un buen
  compromiso; con menos de ~150 DPI las curvas pierden precisión.
- No se extraen trazos vectoriales del PDF: siempre se trabaja sobre la imagen.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

DPI_POR_DEFECTO = 300
EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def es_pdf(nombre: str) -> bool:
    return Path(nombre).suffix.lower() == ".pdf"


def paginas_pdf(datos: bytes) -> int:
    pdf = pdfium.PdfDocument(datos)
    try:
        return len(pdf)
    finally:
        pdf.close()


def rasterizar_pdf(datos: bytes, pagina: int = 0, dpi: int = DPI_POR_DEFECTO) -> np.ndarray:
    pdf = pdfium.PdfDocument(datos)
    try:
        if not 0 <= pagina < len(pdf):
            raise ValueError(f"El PDF tiene {len(pdf)} página(s); no existe la página {pagina + 1}.")
        imagen = pdf[pagina].render(scale=dpi / 72).to_pil().convert("RGB")
        return np.array(imagen)
    finally:
        pdf.close()


def decodificar_imagen(datos: bytes) -> np.ndarray:
    bgr = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("No se pudo leer la imagen (formato no soportado o archivo dañado).")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def cargar_bytes(datos: bytes, nombre: str, pagina: int = 0, dpi: int = DPI_POR_DEFECTO) -> np.ndarray:
    """Carga el contenido de un archivo subido. `nombre` solo se usa por su extensión."""
    if es_pdf(nombre):
        return rasterizar_pdf(datos, pagina, dpi)
    if Path(nombre).suffix.lower() not in EXTENSIONES_IMAGEN:
        raise ValueError(f"Extensión no soportada: {Path(nombre).suffix or '(ninguna)'}")
    return decodificar_imagen(datos)


def cargar_archivo(ruta: str | Path, pagina: int = 0, dpi: int = DPI_POR_DEFECTO) -> np.ndarray:
    ruta = Path(ruta)
    return cargar_bytes(ruta.read_bytes(), ruta.name, pagina, dpi)
