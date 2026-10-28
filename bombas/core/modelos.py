"""Estructuras de datos del proyecto.

Todas las magnitudes se guardan en las unidades ORIGINALES del gráfico
(regla 4 de CLAUDE.md): cada eje lleva su unidad y nunca se convierte aquí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class Magnitud(str, Enum):
    ALTURA = "H"
    EFICIENCIA = "η"
    NPSH = "NPSH"
    POTENCIA = "P"


class Escala(str, Enum):
    LINEAL = "lineal"
    LOG = "log"


class Orientacion(str, Enum):
    HORIZONTAL = "x"  # se calibra con la coordenada x del píxel
    VERTICAL = "y"  # se calibra con la coordenada y del píxel


@dataclass
class Eje:
    """Eje calibrado con dos marcas conocidas: píxel p1 ↔ valor v1, píxel p2 ↔ valor v2.

    `p1`/`p2` son la coordenada del píxel en la dirección del eje
    (x para ejes horizontales, y para verticales), ya corregida la inclinación.
    """

    nombre: str
    unidad: str
    orientacion: Orientacion
    p1: float
    v1: float
    p2: float
    v2: float
    escala: Escala = Escala.LINEAL


@dataclass
class Calibracion:
    """Calibración de un panel: recuadro de trazado, inclinación y ejes."""

    recuadro: tuple[int, int, int, int]  # x0, y0, x1, y1 en píxeles
    ejes: dict[str, Eje] = field(default_factory=dict)
    angulo_grados: float = 0.0  # inclinación corregida antes de calibrar


@dataclass
class CurvaDigitalizada:
    """Puntos extraídos de una curva, en unidades originales."""

    magnitud: Magnitud
    eje_x: str
    eje_y: str
    x: np.ndarray
    y: np.ndarray
    diametro: float | None = None  # diámetro del impulsor, si la curva depende de él
    unidad_diametro: str = "mm"


@dataclass
class CurvaAjustada:
    """Polinomio y(x) ajustado a una curva digitalizada.

    `coeficientes` va de mayor a menor grado (convención de numpy.polyval).
    Solo es válido en [x_min, x_max]; fuera de ese rango es extrapolación.
    """

    magnitud: Magnitud
    coeficientes: np.ndarray
    x_min: float
    x_max: float
    unidad_x: str
    unidad_y: str
    r2: float
    rmse: float
    diametro: float | None = None
    unidad_diametro: str = "mm"

    @property
    def grado(self) -> int:
        return len(self.coeficientes) - 1

    @property
    def etiqueta(self) -> str:
        if self.diametro is None:
            return self.magnitud.value
        return f"{self.magnitud.value} – {self.diametro:g} {self.unidad_diametro}"

    def evaluar(self, x):
        return np.polyval(self.coeficientes, x)

    def en_rango(self, x) -> bool:
        x = np.asarray(x, dtype=float)
        return bool(np.all((x >= self.x_min) & (x <= self.x_max)))


@dataclass
class Bomba:
    """Conjunto de curvas ajustadas de una bomba."""

    nombre: str = ""
    curvas: list[CurvaAjustada] = field(default_factory=list)

    def curva(self, magnitud: Magnitud, diametro: float | None = None) -> CurvaAjustada | None:
        """Curva de esa magnitud para ese diámetro.

        Si no hay curva para el diámetro pedido pero existe una única curva
        de la magnitud sin diámetro (p. ej. η común a todos), se devuelve esa.
        """
        candidatas = [c for c in self.curvas if c.magnitud == magnitud]
        for c in candidatas:
            if c.diametro == diametro:
                return c
        sin_diametro = [c for c in candidatas if c.diametro is None]
        return sin_diametro[0] if len(sin_diametro) == 1 else None

    def diametros(self) -> list[float]:
        return sorted({c.diametro for c in self.curvas if c.diametro is not None})
