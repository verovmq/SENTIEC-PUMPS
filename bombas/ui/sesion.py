"""Estado y operaciones de una sesión de trabajo, sin dependencias de la UI.

La interfaz solo muestra y llama a estos métodos; así la lógica se puede probar
con pytest. Una sesión tiene:
- la imagen cargada (enderezada si se corrigió la inclinación),
- paneles: recuadro de trazado, umbral de oscuridad y ejes calibrados,
- curvas digitalizadas y ajustadas, y puntos de máximo rendimiento,
- un único `GestorGraficas` para toda la sesión (regla 6 de CLAUDE.md).

Convenciones de ejes por panel: "Q" es el eje horizontal (caudal); "H", "η",
"NPSH" y "P" son verticales. Las unidades son las que elige el usuario al
calibrar (las del gráfico original) y no se convierten.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from bombas.core.ajuste import GRADO_POR_DEFECTO, ajustar
from bombas.core.calculadoras import calcular_altura, calcular_caudal, evaluar_punto
from bombas.core.calibracion import (
    enderezar_imagen,
    estimar_inclinacion,
    pixel_desde_valor,
    validar_eje,
    valor_desde_pixel,
)
from bombas.core.carga import cargar_bytes, es_pdf, paginas_pdf
from bombas.core.extraccion import digitalizar
from bombas.core.modelos import (
    Bomba,
    CurvaAjustada,
    CurvaDigitalizada,
    Eje,
    Escala,
    Magnitud,
    Orientacion,
    PuntoEficiencia,
    Rama,
)
from bombas.core.preprocesado import UMBRAL_OSCURO, preprocesar, vista_previa_mascara
from bombas.graficas.estilos import CUADRO_ALTURA, CUADRO_CAUDAL, CUADRO_PUNTO, color_fila
from bombas.graficas.figuras import GestorGraficas

EJE_CAUDAL = "Q"
EJES_VERTICALES = ("H", "η", "NPSH", "P")
EJE_DE_MAGNITUD = {
    Magnitud.ALTURA: "H",
    Magnitud.EFICIENCIA: "η",
    Magnitud.NPSH: "NPSH",
    Magnitud.POTENCIA: "P",
}
ANGULO_MINIMO = 0.05  # grados: por debajo no se endereza la imagen
PUNTOS_TRAZADO = 120


@dataclass
class Panel:
    nombre: str
    recuadro: tuple[int, int, int, int]  # x0, y0, x1, y1 en píxeles de la imagen
    umbral: int = UMBRAL_OSCURO
    ejes: dict[str, Eje] = field(default_factory=dict)
    _cache: tuple[int, np.ndarray] | None = field(default=None, repr=False)


@dataclass
class CurvaRegistrada:
    panel: int
    semillas: list[tuple[float, float]]
    digitalizada: CurvaDigitalizada
    ajustada: CurvaAjustada
    avisos: list[str]
    trazado: np.ndarray  # (N, 2) píxeles del polinomio ajustado, para superponerlo a la imagen
    editada: bool = False  # se quitaron o añadieron puntos a mano
    historial: list[tuple] = field(default_factory=list, repr=False)  # estados anteriores, para deshacer


def _trazado(ajustada: CurvaAjustada, eje_x: Eje, eje_y: Eje) -> np.ndarray:
    """Polinomio ajustado en píxeles de la imagen, para dibujarlo sobre el original."""
    t = np.linspace(ajustada.x_min, ajustada.x_max, PUNTOS_TRAZADO)
    v = ajustada.evaluar(t)
    q, y = (t, v) if ajustada.funcion_de == "x" else (v, t)
    return np.column_stack([pixel_desde_valor(eje_x, q), pixel_desde_valor(eje_y, y)])


def _grupo(cuadro: int, fila: int) -> str:
    return f"c{cuadro}-f{fila}"


class Sesion:
    def __init__(self):
        self.imagen: np.ndarray | None = None
        self.nombre_archivo = ""
        self.angulo = 0.0
        self.paneles: list[Panel] = []
        self.curvas: list[CurvaRegistrada] = []
        self.puntos_eficiencia: list[PuntoEficiencia] = []
        self.gestor = GestorGraficas(Bomba())

    # --- carga ------------------------------------------------------------------

    @staticmethod
    def paginas(datos: bytes, nombre: str) -> int:
        return paginas_pdf(datos) if es_pdf(nombre) else 1

    def cargar(self, datos: bytes, nombre: str, pagina: int = 0, dpi: int = 300) -> None:
        """Carga un PDF o una imagen y empieza de cero (las gráficas se conservan, vacías)."""
        self.imagen = cargar_bytes(datos, nombre, pagina, dpi)
        self.nombre_archivo = nombre
        self.angulo = 0.0
        self.paneles, self.curvas, self.puntos_eficiencia = [], [], []
        self.gestor.quitar_puntos()
        self.actualizar_graficas()

    def _exigir_imagen(self) -> np.ndarray:
        if self.imagen is None:
            raise ValueError("Primero carga un PDF o una imagen.")
        return self.imagen

    def enderezar(self) -> float:
        """Detecta la inclinación de la cuadrícula y endereza la imagen. Devuelve el ángulo corregido."""
        imagen = self._exigir_imagen()
        if self.paneles:
            raise ValueError("Endereza la imagen antes de definir paneles (sus coordenadas cambiarían).")
        angulo = estimar_inclinacion(imagen)
        if abs(angulo) >= ANGULO_MINIMO:
            self.imagen = enderezar_imagen(imagen, angulo)
            self.angulo += angulo
        return angulo

    # --- paneles y calibración ----------------------------------------------------

    def agregar_panel(self, esquina1, esquina2) -> int:
        imagen = self._exigir_imagen()
        alto, ancho = imagen.shape[:2]
        (xa, ya), (xb, yb) = esquina1, esquina2
        x0, x1 = sorted((int(round(xa)), int(round(xb))))
        y0, y1 = sorted((int(round(ya)), int(round(yb))))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(ancho - 1, x1), min(alto - 1, y1)
        if x1 - x0 < 20 or y1 - y0 < 20:
            raise ValueError("El recuadro es demasiado pequeño: marca dos esquinas opuestas de la zona de trazado.")
        self.paneles.append(Panel(f"Panel {len(self.paneles) + 1}", (x0, y0, x1, y1)))
        return len(self.paneles) - 1

    def calibrar_eje(
        self, panel: int, nombre: str, unidad: str, punto1, valor1: float, punto2, valor2: float,
        escala: Escala = Escala.LINEAL,
    ) -> Eje:
        """Calibra un eje con dos clics (x, y) sobre marcas conocidas y sus valores."""
        if nombre != EJE_CAUDAL and nombre not in EJES_VERTICALES:
            raise ValueError(f"Eje desconocido: {nombre}.")
        if not unidad.strip():
            raise ValueError("Indica la unidad del eje tal como aparece en el gráfico.")
        horizontal = nombre == EJE_CAUDAL
        k = 0 if horizontal else 1
        eje = Eje(
            nombre, unidad.strip(), Orientacion.HORIZONTAL if horizontal else Orientacion.VERTICAL,
            p1=float(punto1[k]), v1=float(valor1), p2=float(punto2[k]), v2=float(valor2), escala=escala,
        )
        validar_eje(eje)
        self.paneles[panel].ejes[nombre] = eje
        return eje

    def fijar_umbral(self, panel: int, umbral: int) -> None:
        self.paneles[panel].umbral = int(umbral)

    def vista_previa(self, panel: int, umbral: int | None = None) -> np.ndarray:
        """Máscara aproximada del recuadro (bool) para el deslizante del umbral."""
        p = self.paneles[panel]
        mascara, _ = vista_previa_mascara(self._exigir_imagen(), p.recuadro, p.umbral if umbral is None else umbral)
        return mascara

    def mascara(self, panel: int) -> np.ndarray:
        """Máscara completa del panel a resolución real (se guarda mientras no cambie el umbral)."""
        p = self.paneles[panel]
        if p._cache is None or p._cache[0] != p.umbral:
            p._cache = (p.umbral, preprocesar(self._exigir_imagen(), p.recuadro, p.umbral))
        return p._cache[1]

    def _eje(self, panel: int, nombre: str) -> Eje:
        ejes = self.paneles[panel].ejes
        if nombre not in ejes:
            raise ValueError(f"Calibra primero el eje {nombre} de {self.paneles[panel].nombre}.")
        return ejes[nombre]

    # --- curvas ---------------------------------------------------------------------

    def digitalizar_curva(
        self, panel: int, semillas, magnitud: Magnitud, diametro: float | None = None,
        grado: int = GRADO_POR_DEFECTO, nivel: float | None = None, rama: Rama | None = None,
    ) -> CurvaRegistrada:
        """Sigue la curva entre las semillas, la ajusta y la añade a la bomba.

        Con `nivel` (η de una curva de igual rendimiento) la curva se describe como
        Q(H) sobre los ejes Q y H, con su rama izquierda/derecha.
        """
        eje_x = self._eje(panel, EJE_CAUDAL)
        iso = nivel is not None
        if iso and magnitud != Magnitud.EFICIENCIA:
            raise ValueError("Solo las curvas de eficiencia pueden ser de igual rendimiento.")
        eje_y = self._eje(panel, "H" if iso else EJE_DE_MAGNITUD[magnitud])
        funcion_de = "y" if iso else "x"
        curva, avisos = digitalizar(
            self.mascara(panel), semillas, eje_x, eje_y, magnitud, diametro,
            funcion_de=funcion_de, nivel=nivel, rama=rama,
        )
        ajustada = ajustar(curva, grado, eje_x.unidad, eje_y.unidad)
        trazado = _trazado(ajustada, eje_x, eje_y)
        registrada = CurvaRegistrada(panel, [tuple(map(float, s)) for s in semillas], curva, ajustada, avisos, trazado)
        self.curvas.append(registrada)
        self.actualizar_graficas()
        return registrada

    # --- corrección manual de puntos ---------------------------------------------------
    # Tras digitalizar, el usuario puede quitar los puntos de una zona (p. ej. un tramo
    # que se fue por otra curva) o añadir puntos con clics. Cada cambio vuelve a ajustar
    # el polinomio con el mismo grado; el rango válido pasa a ser el de los puntos que
    # quedan. Los cambios se pueden deshacer uno a uno.

    def _ejes_curva(self, c: CurvaRegistrada) -> tuple[Eje, Eje]:
        eje_y = "H" if c.ajustada.es_iso_eficiencia else EJE_DE_MAGNITUD[c.ajustada.magnitud]
        return self._eje(c.panel, EJE_CAUDAL), self._eje(c.panel, eje_y)

    def puntos_curva(self, indice: int) -> np.ndarray:
        """Puntos digitalizados de una curva, en píxeles de la imagen (N, 2)."""
        c = self.curvas[indice]
        eje_x, eje_y = self._ejes_curva(c)
        d = c.digitalizada
        return np.column_stack([pixel_desde_valor(eje_x, d.x), pixel_desde_valor(eje_y, d.y)])

    def _reajustar(self, indice: int, x: np.ndarray, y: np.ndarray) -> None:
        """Sustituye los puntos de la curva y la vuelve a ajustar (solo si el ajuste es posible)."""
        c = self.curvas[indice]
        eje_x, eje_y = self._ejes_curva(c)
        orden = np.argsort(x if c.digitalizada.funcion_de == "x" else y)
        digitalizada = replace(c.digitalizada, x=np.asarray(x)[orden], y=np.asarray(y)[orden])
        try:
            ajustada = ajustar(digitalizada, c.ajustada.grado, eje_x.unidad, eje_y.unidad)
        except ValueError as e:
            raise ValueError(f"No se puede ajustar la curva con los puntos que quedarían: {e}") from e
        c.historial.append((c.digitalizada, c.ajustada, c.avisos, c.trazado, c.editada))
        c.digitalizada, c.ajustada, c.trazado = digitalizada, ajustada, _trazado(ajustada, eje_x, eje_y)
        c.avisos, c.editada = [], True  # los avisos del seguimiento ya no describen estos puntos
        self.actualizar_graficas()

    def quitar_puntos_curva(self, indice: int, esquina1, esquina2) -> int:
        """Quita los puntos de la curva dentro del rectángulo de dos esquinas (píxeles). Devuelve cuántos."""
        (xa, ya), (xb, yb) = esquina1, esquina2
        px = self.puntos_curva(indice)
        dentro = (
            (px[:, 0] >= min(xa, xb)) & (px[:, 0] <= max(xa, xb))
            & (px[:, 1] >= min(ya, yb)) & (px[:, 1] <= max(ya, yb))
        )
        if not dentro.any():
            raise ValueError("No hay puntos de la curva dentro de esa zona.")
        d = self.curvas[indice].digitalizada
        self._reajustar(indice, d.x[~dentro], d.y[~dentro])
        return int(dentro.sum())

    def agregar_punto_curva(self, indice: int, punto) -> tuple[float, float]:
        """Añade a la curva el punto de un clic (píxeles). Devuelve sus valores (Q, y)."""
        c = self.curvas[indice]
        eje_x, eje_y = self._ejes_curva(c)
        q = float(valor_desde_pixel(eje_x, punto[0]))
        v = float(valor_desde_pixel(eje_y, punto[1]))
        d = c.digitalizada
        self._reajustar(indice, np.append(d.x, q), np.append(d.y, v))
        return q, v

    def deshacer_edicion(self, indice: int) -> None:
        c = self.curvas[indice]
        if not c.historial:
            raise ValueError("No hay cambios que deshacer en esta curva.")
        c.digitalizada, c.ajustada, c.avisos, c.trazado, c.editada = c.historial.pop()
        self.actualizar_graficas()

    def quitar_curva(self, indice: int) -> None:
        del self.curvas[indice]
        self.actualizar_graficas()

    def agregar_punto_eficiencia(self, panel: int, punto, eta: float, diametro: float | None = None) -> PuntoEficiencia:
        """Punto de máximo rendimiento a partir de un clic (x, y) y su η."""
        niveles = [c.ajustada.nivel for c in self.curvas if c.ajustada.es_iso_eficiencia]
        if not niveles:
            raise ValueError("Digitaliza primero las curvas de igual rendimiento.")
        if eta <= max(niveles):
            raise ValueError(f"El punto de máximo rendimiento debe superar la curva más interna ({max(niveles):g} %).")
        q = float(valor_desde_pixel(self._eje(panel, EJE_CAUDAL), punto[0]))
        h = float(valor_desde_pixel(self._eje(panel, "H"), punto[1]))
        p = PuntoEficiencia(q, h, float(eta), diametro)
        self.puntos_eficiencia.append(p)
        self.actualizar_graficas()
        return p

    def quitar_punto_eficiencia(self, indice: int) -> None:
        del self.puntos_eficiencia[indice]
        self.actualizar_graficas()

    @property
    def bomba(self) -> Bomba:
        return Bomba(self.nombre_archivo, [c.ajustada for c in self.curvas], list(self.puntos_eficiencia))

    def diametros(self) -> list[float]:
        return self.bomba.diametros()

    def actualizar_graficas(self) -> None:
        """Redibuja las curvas en las MISMAS figuras de la sesión (nunca crea otras)."""
        self.gestor.bomba = self.bomba
        self.gestor.dibujar_curvas()

    # --- calculadoras ---------------------------------------------------------------------

    def calcular(self, cuadro: int, fila: int, *, q=None, h=None, diametro=None):
        """Calcula una fila de un cuadro y la dibuja con el tono de esa fila. Devuelve el resultado."""
        bomba = self.bomba
        if cuadro == CUADRO_ALTURA:
            resultado = calcular_altura(bomba, q, diametro)
        elif cuadro == CUADRO_CAUDAL:
            resultado = calcular_caudal(bomba, h, diametro)
        elif cuadro == CUADRO_PUNTO:
            resultado = evaluar_punto(bomba, q, h, diametro)
        else:
            raise ValueError(f"Cuadro desconocido: {cuadro}.")
        self.gestor.dibujar_resultado(resultado, color_fila(cuadro, fila), _grupo(cuadro, fila))
        return resultado

    def quitar_fila(self, cuadro: int, fila: int) -> None:
        self.gestor.quitar_grupo(_grupo(cuadro, fila))
