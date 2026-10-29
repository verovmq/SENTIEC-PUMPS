"""Lógica de las tres calculadoras (sin UI).

- Cuadro 1, cálculo de altura: Q y diámetro → H, η, NPSH, P.
- Cuadro 2, cálculo de caudal: H y diámetro → Q. Si hay dos caudales válidos
  (curva con joroba cerca del cierre), se devuelven LOS DOS como opciones; no
  se elige uno por defecto.
- Cuadro 3, punto de operación: el usuario da un punto conocido (Q, H); se
  indica si queda por encima o por debajo de la curva de la bomba y η, NPSH, P.

Todos los valores van en las unidades originales del gráfico (sin convertir).

Supuestos y límites:
- Fuera del rango digitalizado de una curva el polinomio se evalúa igual, pero
  el resultado lleva un aviso de extrapolación: no es un dato fiable.
- La inversión H→Q solo busca caudales dentro del rango digitalizado.
- η sale de la curva η(Q) (gráfico tipo A) o, si la bomba tiene curvas de igual
  rendimiento (tipo B), de `iso_eficiencia` en el punto (Q, H). En el Cuadro 3
  de tipo B se usa el punto dado por el usuario, que es donde opera la bomba.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bombas.core.ajuste import invertir
from bombas.core.iso_eficiencia import eficiencia_en
from bombas.core.modelos import Bomba, CurvaAjustada, Magnitud

GRAFICA_ALTURA = "altura"  # (a) H + η
GRAFICA_NPSH = "npsh"  # (b)
GRAFICA_POTENCIA = "potencia"  # (c)
TOLERANCIA_SOBRE_CURVA = 0.005  # fracción de H: dentro de ±0,5 % se considera "sobre la curva"


@dataclass
class Valor:
    """Un resultado numérico con su unidad y sus avisos."""

    valor: float | None
    unidad: str = ""
    cota_minima: bool = False  # η ≥ valor (dentro del lazo más interno de igual rendimiento)
    avisos: list[str] = field(default_factory=list)


@dataclass
class PuntoGrafico:
    """Punto a dibujar con marcador y líneas punteadas hasta los ejes."""

    grafica: str  # GRAFICA_ALTURA, GRAFICA_NPSH o GRAFICA_POTENCIA
    x: float
    y: float
    eje_y: str = "y"  # "y2" para η en el eje secundario de la gráfica (a)
    etiqueta: str = ""


@dataclass
class Estado:
    """Valores de la bomba en un caudal: H, η, NPSH y P."""

    q: float
    h: Valor
    eta: Valor
    npsh: Valor
    potencia: Valor
    eta_de_mapa: bool = False  # η sale de curvas de igual rendimiento (sin eje propio)

    @property
    def avisos(self) -> list[str]:
        return self.h.avisos + self.eta.avisos + self.npsh.avisos + self.potencia.avisos


@dataclass
class ResultadoAltura:
    estado: Estado

    def puntos(self) -> list[PuntoGrafico]:
        return _puntos_estado(self.estado, "Q→H")


@dataclass
class ResultadoCaudal:
    h: float
    opciones: list[Estado]  # 0, 1 o 2 caudales; con 2, la UI muestra ambas opciones
    avisos: list[str] = field(default_factory=list)

    def puntos(self) -> list[PuntoGrafico]:
        puntos = []
        for i, estado in enumerate(self.opciones, start=1):
            sufijo = f" (opción {i})" if len(self.opciones) > 1 else ""
            puntos += _puntos_estado(estado, f"H→Q{sufijo}")
        return puntos


@dataclass
class ResultadoPunto:
    q: float
    h: float
    h_bomba: Valor  # H de la curva de la bomba en ese Q
    diferencia: float | None  # h − h_bomba
    posicion: str | None  # "por encima", "por debajo" o "sobre la curva"
    eta: Valor
    npsh: Valor
    potencia: Valor

    @property
    def avisos(self) -> list[str]:
        return self.h_bomba.avisos + self.eta.avisos + self.npsh.avisos + self.potencia.avisos

    def puntos(self) -> list[PuntoGrafico]:
        puntos = [PuntoGrafico(GRAFICA_ALTURA, self.q, self.h, etiqueta="Punto de operación")]
        if self.npsh.valor is not None:
            puntos.append(PuntoGrafico(GRAFICA_NPSH, self.q, self.npsh.valor, etiqueta="Punto de operación"))
        if self.potencia.valor is not None:
            puntos.append(PuntoGrafico(GRAFICA_POTENCIA, self.q, self.potencia.valor, etiqueta="Punto de operación"))
        return puntos


def _nombre(magnitud: Magnitud) -> str:
    return {Magnitud.ALTURA: "H", Magnitud.EFICIENCIA: "η", Magnitud.NPSH: "NPSH", Magnitud.POTENCIA: "P"}[magnitud]


def _evaluar(curva: CurvaAjustada | None, x: float, magnitud: Magnitud, diametro) -> Valor:
    if curva is None:
        d = f" para el diámetro {diametro:g}" if diametro is not None else ""
        return Valor(None, avisos=[f"No hay curva de {_nombre(magnitud)}{d}."])
    avisos = []
    if not curva.en_rango(x):
        avisos.append(
            f"{_nombre(magnitud)}: Q={x:g} está fuera del rango digitalizado "
            f"[{curva.x_min:g}, {curva.x_max:g}] {curva.unidad_x}; valor extrapolado, no fiable."
        )
    return Valor(float(curva.evaluar(x)), curva.unidad_y, avisos=avisos)


def _validar_diametro(bomba: Bomba, diametro: float | None) -> None:
    diametros = bomba.diametros()
    if diametros and diametro not in diametros:
        raise ValueError(f"Elige un diámetro digitalizado: {', '.join(f'{d:g}' for d in diametros)}.")


def _eficiencia(bomba: Bomba, q: float, h: float | None, diametro) -> Valor:
    iso = bomba.iso_eficiencia()
    if iso:
        if h is None:
            return Valor(None, "%", avisos=["η: no se puede calcular sin H."])
        r = eficiencia_en(iso, q, h, bomba.puntos_eficiencia)
        return Valor(r.valor, "%", r.cota_minima, [r.aviso] if r.aviso else [])
    return _evaluar(bomba.curva(Magnitud.EFICIENCIA, diametro), q, Magnitud.EFICIENCIA, diametro)


def _estado(bomba: Bomba, q: float, diametro, h: Valor | None = None) -> Estado:
    if h is None:
        h = _evaluar(bomba.curva(Magnitud.ALTURA, diametro), q, Magnitud.ALTURA, diametro)
    return Estado(
        q=q,
        h=h,
        eta=_eficiencia(bomba, q, h.valor, diametro),
        npsh=_evaluar(bomba.curva(Magnitud.NPSH, diametro), q, Magnitud.NPSH, diametro),
        potencia=_evaluar(bomba.curva(Magnitud.POTENCIA, diametro), q, Magnitud.POTENCIA, diametro),
        eta_de_mapa=bool(bomba.iso_eficiencia()),
    )


def _puntos_estado(e: Estado, etiqueta: str) -> list[PuntoGrafico]:
    puntos = []
    if e.h.valor is not None:
        puntos.append(PuntoGrafico(GRAFICA_ALTURA, e.q, e.h.valor, etiqueta=etiqueta))
    # Con curvas de igual rendimiento η no tiene eje propio: el punto H ya lo sitúa en el mapa.
    if e.eta.valor is not None and not e.eta_de_mapa:
        puntos.append(PuntoGrafico(GRAFICA_ALTURA, e.q, e.eta.valor, eje_y="y2", etiqueta=etiqueta))
    if e.npsh.valor is not None:
        puntos.append(PuntoGrafico(GRAFICA_NPSH, e.q, e.npsh.valor, etiqueta=etiqueta))
    if e.potencia.valor is not None:
        puntos.append(PuntoGrafico(GRAFICA_POTENCIA, e.q, e.potencia.valor, etiqueta=etiqueta))
    return puntos


def calcular_altura(bomba: Bomba, q: float, diametro: float | None = None) -> ResultadoAltura:
    """Cuadro 1: H, η, NPSH y P para un caudal."""
    _validar_diametro(bomba, diametro)
    return ResultadoAltura(_estado(bomba, q, diametro))


def calcular_caudal(bomba: Bomba, h: float, diametro: float | None = None) -> ResultadoCaudal:
    """Cuadro 2: caudal(es) para una altura. Devuelve todas las soluciones válidas."""
    _validar_diametro(bomba, diametro)
    curva_h = bomba.curva(Magnitud.ALTURA, diametro)
    if curva_h is None:
        return ResultadoCaudal(h, [], [f"No hay curva de H para el diámetro {diametro}."])
    caudales = invertir(curva_h, h)
    if not caudales:
        return ResultadoCaudal(
            h, [], [f"H={h:g} {curva_h.unidad_y} no se alcanza dentro del rango digitalizado de la curva."]
        )
    opciones = [_estado(bomba, q, diametro, Valor(h, curva_h.unidad_y)) for q in caudales]
    avisos = []
    if len(opciones) > 1:
        avisos.append(
            f"Hay {len(opciones)} caudales con H={h:g} {curva_h.unidad_y}: "
            + ", ".join(f"Q={e.q:.4g}" for e in opciones)
            + ". Elige el que corresponda a tu instalación."
        )
    return ResultadoCaudal(h, opciones, avisos)


def evaluar_punto(bomba: Bomba, q: float, h: float, diametro: float | None = None) -> ResultadoPunto:
    """Cuadro 3: sitúa un punto conocido (Q, H) respecto a la curva de la bomba."""
    _validar_diametro(bomba, diametro)
    h_bomba = _evaluar(bomba.curva(Magnitud.ALTURA, diametro), q, Magnitud.ALTURA, diametro)
    diferencia = posicion = None
    if h_bomba.valor is not None:
        diferencia = h - h_bomba.valor
        if abs(diferencia) <= TOLERANCIA_SOBRE_CURVA * abs(h_bomba.valor):
            posicion = "sobre la curva"
        else:
            posicion = "por encima" if diferencia > 0 else "por debajo"
    return ResultadoPunto(
        q=q,
        h=h,
        h_bomba=h_bomba,
        diferencia=diferencia,
        posicion=posicion,
        eta=_eficiencia(bomba, q, h, diametro),
        npsh=_evaluar(bomba.curva(Magnitud.NPSH, diametro), q, Magnitud.NPSH, diametro),
        potencia=_evaluar(bomba.curva(Magnitud.POTENCIA, diametro), q, Magnitud.POTENCIA, diametro),
    )
