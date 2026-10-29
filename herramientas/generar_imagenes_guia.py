"""Genera las imágenes de ejemplo de la guía paso a paso (bombas/ui/imagenes_guia/).

Son recortes de los dos gráficos de prueba (tests/datos) con anotaciones en el
verde de las ayudas de la app: clics numerados, recuadros y valores a escribir.
Las curvas de ejemplo se digitalizan de verdad con la Sesion, así que si cambia
la extracción basta con volver a ejecutar:

    .venv\\Scripts\\python herramientas\\generar_imagenes_guia.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

from bombas.core.modelos import Magnitud, Rama  # noqa: E402
from bombas.core.preprocesado import vista_previa_mascara  # noqa: E402
from bombas.graficas.estilos import CUADRO_ALTURA, CUADRO_CAUDAL, CUADRO_PUNTO  # noqa: E402
from bombas.graficas.figuras import GRAFICA_ALTURA  # noqa: E402
from bombas.ui.lienzo import AYUDA, atenuar  # noqa: E402
from bombas.ui.sesion import Sesion  # noqa: E402
from test_er3407 import ISO_XLS, polinomio, semilla  # noqa: E402

DATOS = RAIZ / "tests" / "datos"
SALIDA = RAIZ / "bombas" / "ui" / "imagenes_guia"
VERDE = tuple(int(AYUDA[i : i + 2], 16) for i in (1, 3, 5))
GRIS = (120, 120, 120)
ANCHO = 760  # ancho de salida de cada imagen


def fuente(tamano: int, negrita: bool = False):
    nombre = "arialbd.ttf" if negrita else "arial.ttf"
    for ruta in (Path("C:/Windows/Fonts") / nombre, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamano)
    return ImageFont.load_default(tamano)


class Dibujo:
    """Recorte ampliado de una imagen, con anotaciones en coordenadas de la imagen original."""

    def __init__(self, imagen: np.ndarray, recorte=None, atenuada=False, ancho=ANCHO):
        x0, y0, x1, y1 = recorte or (0, 0, imagen.shape[1], imagen.shape[0])
        self.x0, self.y0 = x0, y0
        trozo = imagen[y0:y1, x0:x1]
        self.k = ancho / trozo.shape[1]
        trozo = cv2.resize(trozo, None, fx=self.k, fy=self.k, interpolation=cv2.INTER_CUBIC)
        self.img = Image.fromarray(atenuar(trozo) if atenuada else trozo).convert("RGB")
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y):
        return ((x - self.x0) * self.k, (y - self.y0) * self.k)

    def clic(self, x, y, numero=None, color=VERDE):
        cx, cy = self.p(x, y)
        r = 9
        self.d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=3)
        self.d.line((cx - 4, cy, cx + 4, cy), fill=color, width=2)
        self.d.line((cx, cy - 4, cx, cy + 4), fill=color, width=2)
        if numero is not None:
            f = fuente(15, True)
            bx, by = cx + 10, cy - 30
            self.d.ellipse((bx, by, bx + 22, by + 22), fill=color)
            self.d.text((bx + 11, by + 11), str(numero), font=f, fill="white", anchor="mm")

    def rotulo(self, x, y, texto, hacia=None, color=VERDE, tamano=16):
        """Caja de texto con su esquina superior izquierda en (x, y) (píxeles de salida) y flecha opcional."""
        f = fuente(tamano, True)
        caja = self.d.multiline_textbbox((x, y), texto, font=f, spacing=4)
        borde = (caja[0] - 6, caja[1] - 5, caja[2] + 6, caja[3] + 5)
        if hacia is not None:
            hx, hy = self.p(*hacia)
            ox = min(max(hx, borde[0]), borde[2])
            oy = min(max(hy, borde[1]), borde[3])
            self.d.line((ox, oy, hx, hy), fill=color, width=2)
        self.d.rounded_rectangle(borde, radius=5, fill="white", outline=color, width=2)
        self.d.multiline_text((x, y), texto, font=f, fill=color, spacing=4)

    def rect(self, recuadro, color=VERDE, texto=""):
        x0, y0 = self.p(*recuadro[:2])
        x1, y1 = self.p(*recuadro[2:])
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            largo = np.hypot(b[0] - a[0], b[1] - a[1])
            for t in np.arange(0, largo, 14):
                u, v = t / largo, min(t + 8, largo) / largo
                self.d.line((a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]),
                             a[0] + v * (b[0] - a[0]), a[1] + v * (b[1] - a[1])), fill=color, width=3)
        if texto:
            self.d.text((x0 + 6, y0 + 5), texto, font=fuente(16, True), fill=color)

    def linea_guia(self, x0, y0, x1, y1, color=VERDE):
        a, b = self.p(x0, y0), self.p(x1, y1)
        largo = np.hypot(b[0] - a[0], b[1] - a[1])
        for t in np.arange(0, largo, 10):
            u, v = t / largo, min(t + 5, largo) / largo
            self.d.line((a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]),
                         a[0] + v * (b[0] - a[0]), a[1] + v * (b[1] - a[1])), fill=color, width=2)

    def polilinea(self, puntos, color=(0, 0, 0), ancho=3):
        self.d.line([self.p(x, y) for x, y in puntos], fill=color, width=ancho, joint="curve")

    def guardar(self, nombre: str) -> None:
        self.img.save(SALIDA / nombre, optimize=True)
        print("  ", nombre, self.img.size)


def y_en(trazado: np.ndarray, x: float) -> float:
    orden = np.argsort(trazado[:, 0])
    return float(np.interp(x, trazado[orden, 0], trazado[orden, 1]))


def bomba1() -> tuple[Sesion, int]:
    s = Sesion()
    s.cargar((DATOS / "curvaBOMBA1.png").read_bytes(), "curvaBOMBA1.png")
    p = s.agregar_panel((115, 239), (707, 758))
    s.calibrar_eje(p, "Q", "m³/h", (115, 0), 0, (707, 0), 3500)
    s.calibrar_eje(p, "H", "m", (0, 758), 0, (0, 239), 250)
    for d, sem in ((768, [(118, 300.5), (600, 426)]), (738, [(120, 334.5), (577, 452)]), (608, [(118, 465.5), (489, 561)])):
        s.digitalizar_curva(p, sem, Magnitud.ALTURA, diametro=d)
    return s, p


def imagenes_calibrar(img: np.ndarray) -> None:
    # Paneles: dos clics en esquinas opuestas de la zona de trazado.
    d = Dibujo(img)
    d.rect((115, 31, 707, 217), GRIS, "Panel 2 (potencia): otro «Nuevo panel»")
    d.rect((115, 239, 707, 758), VERDE, "Panel 1")
    d.clic(115, 239, 1)
    d.clic(707, 758, 2)
    d.rotulo(150, 300, "Clic 1: esquina superior izquierda\nde la zona de trazado", hacia=(118, 242))
    d.rotulo(330, 690, "Clic 2: esquina inferior derecha", hacia=(704, 755))
    d.guardar("calibrar_panel.png")

    # Eje Q: solo cuenta la posición horizontal del clic.
    d = Dibujo(img, (40, 600, 807, 819))
    for x in (115, 707):
        d.linea_guia(x, 610, x, 770)
    d.clic(115, 770, 1)
    d.clic(707, 770, 2)
    d.rotulo(40, 25, "Marca 1 → clic en la raya del «0»\nValor 1 = 0", hacia=(115, 765))
    d.rotulo(390, 25, "Marca 2 → clic en la raya del «3500»\nValor 2 = 3500", hacia=(707, 765))
    d.rotulo(250, 225, "Unidad: m³/h (la del gráfico)", tamano=14)
    d.guardar("calibrar_eje_q.png")

    # Eje H (vertical): solo cuenta la altura del clic.
    d = Dibujo(img, (0, 220, 560, 790))
    for y in (758, 239):
        d.linea_guia(105, y, 540, y)
    d.clic(108, 758, 1)
    d.clic(108, 239, 2)
    d.rotulo(230, 600, "Marca 1 → clic en la raya del «0»\nValor 1 = 0", hacia=(108, 755))
    d.rotulo(300, 50, "Marca 2 → clic en la raya del «250»\nValor 2 = 250", hacia=(111, 242))
    d.rotulo(230, 690, "Unidad: m", tamano=14)
    d.guardar("calibrar_eje_h.png")

    # NPSH: un eje vertical con SUS propios números (no los de H).
    d = Dibujo(img, (380, 470, 807, 800))
    for y in (654.5, 550.5):
        d.linea_guia(560, y, 640, y)
    d.clic(640, 654.5, 1)
    d.clic(640, 550.5, 2)
    d.rotulo(20, 360, "Marca 1 → raya del «5» de NPSH\nValor 1 = 5", hacia=(637, 657))
    d.rotulo(20, 40, "Marca 2 → raya del «10» de NPSH\nValor 2 = 10", hacia=(637, 548))
    d.rotulo(20, 480,"No uses los números de H (izquierda)\nni los de η (derecha).", color=(160, 60, 0), tamano=14)
    d.guardar("calibrar_eje_npsh.png")

    # Umbral: demasiado bajo, bien y demasiado alto.
    recuadro = (115, 239, 707, 758)
    piezas = []
    for umbral, texto, color in ((45, "45: demasiado bajo\n(faltan tramos)", (160, 60, 0)),
                                 (140, "140: bien\n(curvas completas)", VERDE),
                                 (228, "228: demasiado alto\n(entra la cuadrícula)", (160, 60, 0))):
        m, _ = vista_previa_mascara(img, recuadro, umbral)
        rgb = np.where(m[..., None], 0, 255).astype(np.uint8).repeat(3, axis=2)
        d = Dibujo(rgb, ancho=ANCHO // 3 - 8)
        d.d.rectangle((0, 0, d.img.width - 1, d.img.height - 1), outline=GRIS, width=1)
        d.rotulo(10, 10, texto, color=color, tamano=13)
        piezas.append(d.img)
    lienzo = Image.new("RGB", (sum(p.width for p in piezas) + 8 * (len(piezas) - 1), piezas[0].height), "white")
    x = 0
    for p in piezas:
        lienzo.paste(p, (x, 0))
        x += p.width + 8
    lienzo.save(SALIDA / "calibrar_umbral.png", optimize=True)
    print("   calibrar_umbral.png", lienzo.size)


def imagenes_digitalizar(img: np.ndarray) -> None:
    s, _ = bomba1()
    trazados = {c.ajustada.diametro: c.trazado for c in s.curvas}

    # Dos clics: inicio y final de la curva de 738 mm.
    d = Dibujo(img, (60, 230, 720, 640))
    d.clic(120, 334.5, 1)
    d.clic(577, 452, 2)
    d.rotulo(25, 20, "Clic 1: al principio de la curva (izquierda)", hacia=(122, 331))
    d.rotulo(330, 330, "Clic 2: al final de la curva", hacia=(575, 455))
    d.guardar("digitalizar_clics.png")

    # Clic extra después de un cruce: la curva de 738 mm cruza la MCSF y la de eficiencia.
    x_extra = 300
    d = Dibujo(img, (100, 260, 460, 480))
    d.clic(120, 334.5, 1)
    d.clic(x_extra, y_en(trazados[738], x_extra), 2)
    d.rotulo(20, 330, "Clic 2 (extra): justo DESPUÉS del cruce,\nsobre la curva que quieres", hacia=(x_extra, y_en(trazados[738], x_extra) + 3))
    d.rotulo(350, 20, "Cruce con la MCSF\ny la curva de eficiencia", color=GRIS, tamano=14, hacia=(259, 348))
    d.rotulo(30, 20, "Clic 1: inicio", hacia=(122, 331))
    d.guardar("digitalizar_cruce.png")

    # Resultado: curvas digitalizadas en negro sobre la imagen atenuada.
    d = Dibujo(img, (60, 230, 720, 640), atenuada=True)
    for t in trazados.values():
        d.polilinea(t)
    d.rotulo(300, 20, "En negro: lo que digitalizó el programa.\nDebe ir justo encima del trazo original.", hacia=(400, y_en(trazados[768], 400)))
    d.guardar("digitalizar_resultado.png")


def imagenes_er3407(img: np.ndarray) -> None:
    # Curva de igual rendimiento de 75 %: dos ramas, cada una con clics de abajo arriba.
    d = Dibujo(img, (240, 30, 680, 290))
    for rama, texto, caja in ((Rama.IZQUIERDA, "Rama izquierda\nη = 75", (10, 130)), (Rama.DERECHA, "Rama derecha\nη = 75", (520, 330))):
        coef, h0, h1 = ISO_XLS[(75, rama)]
        margen = 0.06 * (h1 - h0)
        abajo, arriba = (semilla(np.polyval(polinomio(coef), h), h) for h in (h0 + margen, h1 - margen))
        d.clic(*abajo, 1)
        d.clic(*arriba, 2)
        d.rotulo(*caja, texto + "\n1 abajo → 2 arriba", hacia=abajo)
    d.guardar("digitalizar_iso.png")

    # Punto de máximo rendimiento (el «81»).
    d = Dibujo(img, (380, 60, 620, 200))
    d.clic(490.5, 121.4)
    d.rotulo(15, 15, "«Marcar en la imagen» → clic justo\nen el punto del 81\n(η del punto = 81)", hacia=(489, 119))
    d.guardar("digitalizar_maximo.png")


def imagen_calculadoras() -> None:
    """Gráfica de altura real (Plotly) con un punto de cada cuadro. Necesita kaleido."""
    s, p = bomba1()
    s.calibrar_eje(p, "η", "%", (0, 758), 0, (0, 239), 100)
    s.digitalizar_curva(p, [(118, 747), (578, 322)], Magnitud.EFICIENCIA, grado=4)
    s.calcular(CUADRO_ALTURA, 0, q=2000, diametro=738)
    s.calcular(CUADRO_CAUDAL, 0, h=160, diametro=738)
    s.calcular(CUADRO_PUNTO, 0, q=1000, h=215, diametro=738)
    s.gestor.figura(GRAFICA_ALTURA).write_image(SALIDA / "calculadoras_grafica.png", width=ANCHO, height=480)
    print("   calculadoras_grafica.png")


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    b1 = Sesion()
    b1.cargar((DATOS / "curvaBOMBA1.png").read_bytes(), "curvaBOMBA1.png")
    er = Sesion()
    er.cargar((DATOS / "er3407.png").read_bytes(), "er3407.png")
    imagenes_calibrar(b1.imagen)
    imagenes_digitalizar(b1.imagen)
    imagenes_er3407(er.imagen)
    imagen_calculadoras()


if __name__ == "__main__":
    main()
