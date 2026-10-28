import cv2
import numpy as np
import pytest
from PIL import Image

from bombas.core.carga import cargar_archivo, cargar_bytes, paginas_pdf, rasterizar_pdf


def imagen_prueba():
    img = np.full((120, 200, 3), 255, np.uint8)
    img[40:80, 50:150] = (10, 20, 200)  # rectángulo azul (RGB)
    return img


def test_png_con_nombre_unicode(tmp_path):
    ruta = tmp_path / "curva bomba ñ.png"
    ok, datos = cv2.imencode(".png", cv2.cvtColor(imagen_prueba(), cv2.COLOR_RGB2BGR))
    ruta.write_bytes(datos.tobytes())
    np.testing.assert_array_equal(cargar_archivo(ruta), imagen_prueba())


def test_bytes_jpg_mantiene_orden_rgb():
    _, datos = cv2.imencode(".jpg", cv2.cvtColor(imagen_prueba(), cv2.COLOR_RGB2BGR))
    img = cargar_bytes(datos.tobytes(), "x.JPG")
    r, g, b = img[60, 100].astype(int)
    assert b > 150 and r < 60


def test_extension_no_soportada():
    with pytest.raises(ValueError):
        cargar_bytes(b"abc", "curva.docx")


def test_imagen_danada():
    with pytest.raises(ValueError):
        cargar_bytes(b"no es una imagen", "curva.png")


@pytest.fixture
def pdf_dos_paginas(tmp_path):
    ruta = tmp_path / "curvas.pdf"
    p1 = Image.fromarray(imagen_prueba())
    p2 = Image.fromarray(np.zeros((120, 200, 3), np.uint8))
    p1.save(ruta, save_all=True, append_images=[p2], resolution=72)
    return ruta


def test_pdf_paginas_y_dpi(pdf_dos_paginas):
    datos = pdf_dos_paginas.read_bytes()
    assert paginas_pdf(datos) == 2
    img = rasterizar_pdf(datos, pagina=0, dpi=144)  # 72 dpi de origen → doble de tamaño
    assert img.shape == (240, 400, 3)
    assert img[120, 200, 2] > 150  # centro azul
    assert rasterizar_pdf(datos, pagina=1, dpi=72).max() < 30  # segunda página negra


def test_pdf_pagina_inexistente(pdf_dos_paginas):
    with pytest.raises(ValueError):
        cargar_archivo(pdf_dos_paginas, pagina=5)
