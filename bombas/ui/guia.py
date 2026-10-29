"""Guía paso a paso de cada pestaña, con imágenes de ejemplo.

Los textos nombran los botones y campos tal como aparecen en la interfaz
(«Nuevo panel», «Guardar eje», «Digitalizar curva»…). Si se cambia el texto de
un botón hay que cambiarlo también aquí; tests/test_guia.py lo comprueba.

Las imágenes (imagenes_guia/) se generan con herramientas/generar_imagenes_guia.py
a partir de los gráficos de prueba de tests/datos.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nicegui import app, ui

from bombas.ui.lienzo import AYUDA

IMAGENES = Path(__file__).parent / "imagenes_guia"
URL_IMAGENES = "/guia"
# Ruta fija para toda la aplicación: con ui.image(Path) NiceGUI crea rutas ligadas a
# cada cliente y, al cerrarse o recargarse una pestaña, las imágenes dejan de cargar.
app.add_static_files(URL_IMAGENES, IMAGENES)


@dataclass(frozen=True)
class Paso:
    titulo: str
    texto: str  # Markdown
    imagen: str | None = None
    pie: str = ""


CARGAR = [
    Paso(
        "Elige el archivo",
        "Haz clic en el recuadro **«PDF o imagen»** (o en su botón **+**) y elige el archivo; también "
        "puedes arrastrarlo encima. Admite PDF, PNG, JPG, BMP y TIF.\n\n"
        "Se carga solo: no hay que pulsar nada más. Debajo aparecen el nombre, el tamaño en píxeles "
        "y la imagen.",
    ),
    Paso(
        "Solo para PDF: página y resolución",
        "- Si el PDF tiene varias páginas, escribe el número en **«Página (PDF)»**.\n"
        "- En **«Resolución PDF (DPI)»** deja **300**. Si las curvas se ven borrosas o muy finas, "
        "elige **400**.\n\n"
        "Después de cambiar cualquiera de los dos, pulsa **«Volver a cargar con esta página/DPI»**.",
    ),
    Paso(
        "Sigue en «2. Calibrar»",
        "Si la imagen se ve bien, pasa a la pestaña **«2. Calibrar»**.\n\n"
        "⚠ Cargar otro archivo (o volver a cargar) **empieza de cero**: se borran los paneles, "
        "las calibraciones y las curvas digitalizadas.",
    ),
]

CALIBRAR = [
    Paso(
        "Solo si el escaneo está torcido: «Enderezar imagen»",
        "Si el gráfico está inclinado (típico de un escaneo), pulsa **«Enderezar imagen»** "
        "**antes** de crear paneles. Si la imagen ya está recta, no cambia nada.\n\n"
        "En imágenes grandes puede tardar **hasta un minuto**: verás el aviso «Enderezando la imagen…». "
        "Espera a que desaparezca y **no recargues la página**.",
    ),
    Paso(
        "Crea un panel por cada gráfico: «Nuevo panel»",
        "Un **panel** es la zona de trazado de un gráfico (el rectángulo dentro de sus ejes).\n\n"
        "1. Pulsa **«Nuevo panel»**.\n"
        "2. **Clic 1**: en la esquina superior izquierda de la zona de trazado.\n"
        "3. **Clic 2**: en la esquina inferior derecha.\n\n"
        "Aparece un recuadro verde con su nombre («Panel 1») y queda elegido en **«Panel activo»**.\n\n"
        "- Si el documento tiene **varios gráficos** separados (por ejemplo, potencia arriba y "
        "altura abajo), crea **un panel para cada uno**.\n"
        "- Si un mismo gráfico tiene **varios ejes verticales** (H a la izquierda, η y NPSH a la "
        "derecha), es **un solo panel**: luego calibras todos sus ejes.\n"
        "- Si un mismo gráfico tiene **varias curvas de altura** (una por diámetro de impulsor), "
        "también es **un solo panel**: no crees un panel por diámetro.\n\n"
        "**Para rehacer un panel**: elígelo en **«Panel activo»**, pulsa **«Borrar panel»** y confirma "
        "con **«Borrar»**. Se borran su recuadro, su calibración y las curvas digitalizadas en él; los "
        "demás paneles no cambian. Después crea otro con **«Nuevo panel»**.\n\n"
        "Si solo quieres **corregir un eje**, no hace falta borrar el panel: vuelve a marcar ese eje y "
        "pulsa **«Guardar eje»** (se sobrescribe).",
        "calibrar_panel.png",
        "Panel 1 (H, η y NPSH) con sus dos clics. La potencia, en otro gráfico, es el Panel 2.",
    ),
    Paso(
        "Ajusta el «Umbral de oscuridad»",
        "La imagen de la **derecha** es la máscara: lo que el programa reconoce como trazo de curva. "
        "Mueve el deslizante:\n\n"
        "- **Hacia la izquierda** (más bajo): solo entra lo muy negro. Si faltan tramos de curva, súbelo.\n"
        "- **Hacia la derecha** (más alto): entran trazos más claros. Si aparecen la cuadrícula o "
        "rayas sueltas, bájalo.\n\n"
        "Busca el punto en que **las curvas se vean completas** con la menor cantidad de cuadrícula y "
        "texto. Algún corte corto (donde se cruzan dos curvas o pasa una etiqueta) no importa. "
        "En gráficos limpios suele valer entre **100 y 150**; en escaneos, algo más alto.\n\n"
        "El umbral es de cada panel: si cambias de **«Panel activo»**, ajusta también el del otro.",
        "calibrar_umbral.png",
        "Máscara del Panel 1 con tres umbrales distintos.",
    ),
    Paso(
        "Calibra el eje horizontal (Q)",
        "En **«Ejes de Panel 1»** abre **«Q — Caudal (eje horizontal)»**:\n\n"
        "1. En **«Unidad»** elige la del gráfico (m³/h, L/s, GPM…). Si no está, escríbela y pulsa Intro. "
        "**No conviertas unidades**: pon la que aparece en el gráfico.\n"
        "2. **«Escala»**: **lineal** casi siempre. Elige *logarítmica* solo si las rayas del eje se "
        "juntan cada vez más (1, 10, 100…).\n"
        "3. Pulsa **«Marca 1»** y haz clic en la imagen sobre una raya del eje que tenga número "
        "(por ejemplo el **0**). Escribe ese número en **«Valor 1»**.\n"
        "4. Pulsa **«Marca 2»**, haz clic en otra raya con número **lo más lejos posible** de la primera "
        "(por ejemplo el **3500**) y escribe ese número en **«Valor 2»**.\n"
        "5. Pulsa **«Guardar eje»**. El título del eje muestra **✔** y la unidad.\n\n"
        "En el eje horizontal solo cuenta la **posición horizontal** del clic: puedes hacerlo sobre el "
        "número o sobre la línea vertical de la cuadrícula que sale de él.",
        "calibrar_eje_q.png",
        "Eje Q: Marca 1 en el 0 y Marca 2 en el 3500, unidad m³/h.",
    ),
    Paso(
        "Calibra la altura (H) y los demás ejes verticales",
        "Abre **«H — Altura manométrica»** y repite lo mismo: **«Unidad»**, **«Marca 1»** + "
        "**«Valor 1»**, **«Marca 2»** + **«Valor 2»** y **«Guardar eje»**.\n\n"
        "En los ejes verticales solo cuenta la **altura** del clic: haz clic a la altura de la raya, "
        "sobre el eje o sobre la línea horizontal de la cuadrícula que sale de ella.",
        "calibrar_eje_h.png",
        "Eje H: Marca 1 en el 0 y Marca 2 en el 250, unidad m.",
    ),
    Paso(
        "η, NPSH y P: cada eje con SUS números",
        "Calibra igual **«η — Eficiencia (solo si tiene eje propio)»**, **«NPSH — NPSH»** y "
        "**«P — Potencia»**, pero usando los "
        "números de **su propia escala**: en el NPSH, el 5 y el 10 del eje de NPSH, no los de H.\n\n"
        "- Calibra **solo los ejes que tenga ese panel**. La potencia suele estar en otro panel: elígelo "
        "en **«Panel activo»** y calibra allí su Q y su P.\n"
        "- **η solo si tiene eje propio** (en %). Si la eficiencia viene como curvas de igual "
        "rendimiento dibujadas sobre H–Q (con valores 60, 65, 70… sobre las curvas), no tiene eje: "
        "no la calibres.\n"
        "- Si te equivocas, vuelve a marcar y pulsa **«Guardar eje»**: se sobrescribe.",
        "calibrar_eje_npsh.png",
        "Eje NPSH: Marca 1 en su 5 y Marca 2 en su 10.",
    ),
    Paso(
        "Sigue en «3. Digitalizar»",
        "Cuando todos los ejes que necesitas muestren **✔**, pasa a la pestaña **«3. Digitalizar»**.",
    ),
]

DIGITALIZAR = [
    Paso(
        "Elige el panel",
        "En **«Panel activo»** elige el panel donde está la curva. La imagen se ve atenuada (más clara) "
        "para que destaquen tus clics y las curvas ya digitalizadas, que se dibujan en negro.",
    ),
    Paso(
        "Rellena «Nueva curva»",
        "- **«Magnitud»**: qué es la curva (H, η, NPSH o P).\n"
        "- **«Diámetro impulsor (mm)»**: escribe el diámetro si la curva es de un impulsor concreto "
        "(por ejemplo **738**). Déjalo **vacío** si la curva vale para todos (por ejemplo, una única "
        "curva de NPSH o de eficiencia). Ver el paso 3 si el gráfico tiene varios diámetros.\n"
        "- **«Grado»**: grado del polinomio. Deja **3**. Usa **4** si la curva tiene un máximo marcado "
        "(la eficiencia) o forma de S, y **2** si es casi recta.\n"
        "- Si la magnitud es **η**, elige **«η(Q) con su propio eje»** para una curva de eficiencia "
        "normal (con su eje en %). La otra opción es para las curvas de igual rendimiento (paso 9).",
    ),
    Paso(
        "Si el gráfico tiene varios diámetros de impulsor",
        "Muchos fabricantes dibujan en la **misma gráfica** una curva de H **por cada diámetro** del "
        "impulsor (por ejemplo 768, 738 y 608 mm, con el diámetro escrito junto a la curva). Todas "
        "están en el **mismo panel**; cada una se digitaliza **por separado** con **su diámetro**:\n\n"
        "1. **«Magnitud»** = H, **«Diámetro impulsor (mm)»** = **768**, clic 1 y clic 2 sobre la curva "
        "de 768 y **«Digitalizar curva»**.\n"
        "2. Cambia **«Diámetro impulsor (mm)»** a **738**, clics sobre la curva de 738 y "
        "**«Digitalizar curva»**.\n"
        "3. Lo mismo con **608**.\n\n"
        "No hay límite: digitaliza tantas curvas como diámetros tenga el gráfico. Antes de cada "
        "**«Digitalizar curva»** comprueba que el diámetro escrito es el de la curva que marcaste: "
        "el campo **no se vacía solo** entre una curva y otra.\n\n"
        "Para las demás magnitudes (η, NPSH, P), mira el gráfico:\n\n"
        "- Si hay **una curva por diámetro** (por ejemplo, una potencia para 635 mm y otra para "
        "508 mm), digitaliza cada una con **su diámetro**.\n"
        "- Si hay **una sola curva** que vale para todos (lo habitual en el NPSH), digitalízala con el "
        "diámetro **vacío**: las calculadoras la usarán para cualquier diámetro.\n\n"
        "Escribe **exactamente el mismo número** en todas las curvas del mismo impulsor: 738 y 740 "
        "serían dos diámetros distintos. En la lista **«Curvas "
        "digitalizadas»** cada curva aparece con su diámetro («H – 738 mm») para que lo compruebes.",
        "digitalizar_diametros.png",
        "Tres curvas de altura en la misma gráfica: cada una con sus dos clics y su diámetro.",
    ),
    Paso(
        "Haz clic sobre la curva: principio y final",
        "Haz clic **sobre el trazo**, en orden:\n\n"
        "1. **Clic 1** al **principio** de la curva (su extremo izquierdo).\n"
        "2. **Clic 2** al **final** (su extremo derecho).\n\n"
        "Cada clic aparece numerado en verde y el contador muestra «2 clic(s) sobre la curva». Con "
        "dos clics suele bastar.\n\n"
        "Pon el primero y el último en los **extremos reales** de la curva: el polinomio solo es "
        "válido entre ellos. Si un clic te sale mal, pulsa **«Borrar clics»** y empieza de nuevo.",
        "digitalizar_clics.png",
        "Curva de 738 mm: un clic al principio y otro al final.",
    ),
    Paso(
        "Si la curva se cruza con otra: un clic extra",
        "El programa sigue **una sola línea** desde tu primer clic. En un cruce normal (en ángulo) "
        "continúa por la curva correcta, pero si tu curva va **casi paralela o encima de otra** en un "
        "tramo, o la corta una etiqueta, puede desviarse.\n\n"
        "Para evitarlo, haz un **clic extra justo después** de esa zona, sobre tu curva (y otro justo "
        "antes si el tramo es largo). Los clics deben seguir en orden de izquierda a derecha.",
        "digitalizar_cruce.png",
        "El clic 2 obliga a seguir la curva de 738 mm tras cruzar la MCSF y la de eficiencia.",
    ),
    Paso(
        "Pulsa «Digitalizar curva» y revisa el resultado",
        "Pulsa **«Digitalizar curva»**. La curva calculada se dibuja **en negro** sobre la imagen y "
        "aparece en la lista **«Curvas digitalizadas»** con:\n\n"
        "- **R²**: lo bien que el polinomio sigue los puntos. Lo normal es **0,99 o más**.\n"
        "- El **rango válido** (de qué Q a qué Q).\n"
        "- Avisos **⚠** si algo fue raro (un salto, un tramo no encontrado).\n\n"
        "Comprueba que la línea negra va **justo encima** del trazo original. Si en algún tramo se "
        "separa o se va por otra curva, tienes dos opciones:\n\n"
        "- **Corregir solo ese tramo** con el lápiz ✏ de la curva (paso siguiente).\n"
        "- Borrarla con la **papelera** 🗑 y repetirla con más clics donde se desvió.",
        "digitalizar_resultado.png",
        "Las tres curvas de altura ya digitalizadas, en negro sobre el original.",
    ),
    Paso(
        "Corregir puntos a mano (lápiz ✏)",
        "Sirve para arreglar un tramo sin repetir toda la curva, por ejemplo donde el programa se fue "
        "por otra curva que se cruza.\n\n"
        "1. En **«Curvas digitalizadas»** pulsa el **lápiz ✏** de la curva. Sus puntos aparecen en "
        "**verde** sobre la imagen y la tarjeta «Nueva curva» se cambia por la de corrección.\n"
        "2. Para **quitar** puntos, deja elegido **«Borrar puntos (zona)»**: haz **clic en una esquina** "
        "de la zona con los puntos malos y **clic en la esquina opuesta**. Se borran los puntos que "
        "queden dentro del rectángulo.\n"
        "3. Para **añadir** puntos (por ejemplo, para rellenar el hueco), elige **«Añadir punto»** y haz "
        "clic **sobre el trazo correcto**, un clic por punto.\n"
        "4. Después de cada cambio la curva se **vuelve a ajustar** y verás el nuevo **R²**. Si te "
        "equivocas, pulsa **«Deshacer»** (deshace los cambios uno a uno).\n"
        "5. Pulsa **«Terminar corrección»**. En la lista, la curva queda marcada como «corregida a mano».\n\n"
        "Si borras puntos de un **extremo**, el rango válido de la curva se acorta hasta los puntos que quedan.",
        "digitalizar_correccion.png",
        "Ejemplo: cuatro puntos que se fueron por encima del trazo, encerrados con dos clics para borrarlos.",
    ),
    Paso(
        "Repite con cada curva",
        "Haz lo mismo con cada curva: una por **diámetro** para H, y las de η, NPSH y P. Para la "
        "potencia, cambia **«Panel activo»** al panel donde esté.",
    ),
    Paso(
        "Solo si la eficiencia son curvas de igual rendimiento",
        "En algunos gráficos la eficiencia son curvas con un valor (60, 65, 70… %) dibujadas sobre "
        "el gráfico H–Q. Cada una tiene forma de U, con una **rama izquierda** y una **rama derecha** "
        "que se digitalizan **por separado**:\n\n"
        "1. **«Magnitud»**: η — eficiencia, y elige **«Curva de igual rendimiento (sobre H–Q)»**.\n"
        "2. **«η de la curva (%)»**: el número escrito en la curva (por ejemplo **75**).\n"
        "3. **«Rama»**: rama izquierda o rama derecha.\n"
        "4. Deja **«Diámetro impulsor (mm)»** vacío y **«Grado»** en 2 o 3.\n"
        "5. Clics **de abajo arriba**: clic 1 en el extremo **inferior** de la rama y clic 2 en el "
        "**superior**. Pulsa **«Digitalizar curva»**.\n\n"
        "Repite con la otra rama y con cada valor de η. Si un valor solo aparece a un lado, "
        "digitaliza solo esa rama.",
        "digitalizar_iso.png",
        "Curva de 75 %: rama izquierda y rama derecha, cada una con sus dos clics de abajo arriba.",
    ),
    Paso(
        "Punto de máximo rendimiento (si el gráfico lo marca)",
        "Cuando hay curvas de igual rendimiento aparece la tarjeta **«Punto de máximo rendimiento»**. "
        "Si el gráfico marca el máximo como un punto con su valor (por ejemplo **81**):\n\n"
        "1. Escribe el valor en **«η del punto (%)»**.\n"
        "2. Pulsa **«Marcar en la imagen»**.\n"
        "3. Haz clic **justo en el punto**.\n\n"
        "Sin este punto, dentro de la curva más interna el programa solo puede decir «η ≥ 80 %».",
        "digitalizar_maximo.png",
        "El punto de 81 % del gráfico ER-3407.",
    ),
    Paso(
        "Sigue en «4. Gráficas y calculadoras»",
        "Cuando tengas todas las curvas, pasa a la pestaña **«4. Gráficas y calculadoras»**.",
    ),
]

CALCULADORAS = [
    Paso(
        "Las tres gráficas",
        "A la izquierda están las tres gráficas de la sesión: **altura y eficiencia**, **NPSH** y "
        "**potencia**, con las curvas digitalizadas en negro. Si digitalizaste varios diámetros, todas "
        "sus curvas salen **juntas en la misma gráfica**, cada una **rotulada con su diámetro** "
        "(«H – 768 mm», «H – 738 mm»…). Se actualizan solas cuando digitalizas o borras curvas.\n\n"
        "Para ampliar, arrastra con el ratón sobre una zona; con **doble clic** vuelve a la vista completa.",
        "calculadoras_grafica.png",
        "Un punto de cada cuadro: morado (Cuadro 1), azul (Cuadro 2) y naranja (Cuadro 3).",
    ),
    Paso(
        "El campo «Diámetro» de cada fila",
        "Cada fila de los tres cuadros tiene un desplegable **«Diámetro»** con los diámetros que "
        "digitalizaste (por ejemplo 608, 738 y 768 mm). Elige el **diámetro del impulsor de tu bomba**: "
        "el cálculo usa la curva de H de ese diámetro.\n\n"
        "- Para η, NPSH y P usa la curva de **ese mismo diámetro**; si no la hay, la curva única "
        "digitalizada **sin diámetro**. Si tampoco existe, aparece el aviso «No hay curva de … para el "
        "diámetro …» y ese valor sale como «—».\n"
        "- El desplegable **empieza vacío**: hasta que elijas el diámetro, la fila muestra «Elige el "
        "«Diámetro» de esta fila.» y no calcula nada. Así nunca se calcula con un impulsor que no es "
        "el tuyo.\n"
        "- Cada fila tiene su propio diámetro: para **comparar diámetros**, pulsa **«Agregar»** y pon "
        "el mismo caudal en varias filas con distinto diámetro (por ejemplo Q = 2000 con 768 y con "
        "608). Cada punto se dibuja sobre la curva de su diámetro.\n"
        "- Si ninguna curva tiene diámetro, el desplegable no aparece.",
    ),
    Paso(
        "Cuadro 1 (morado): conozco el caudal",
        "Escribe el caudal en **«Q»** y elige el **«Diámetro»**. Al momento aparecen **H, η, NPSH y P** "
        "para ese caudal, y el punto se dibuja en morado con líneas punteadas hasta los ejes.",
    ),
    Paso(
        "Cuadro 2 (azul): conozco la altura",
        "Escribe la altura en **«H»** y elige el **«Diámetro»**. Aparece el **caudal Q** que da esa "
        "altura y sus η, NPSH y P.\n\n"
        "Si la curva tiene una joroba, una misma altura puede darse con **dos caudales**: se muestran "
        "los dos como **«Opción 1»** y **«Opción 2»** y se dibujan ambos. Elige el que corresponda a "
        "tu instalación.",
    ),
    Paso(
        "Cuadro 3 (naranja): tengo un punto de operación",
        "Escribe **«Q»** y **«H»** de un punto conocido y elige el **«Diámetro»**. El punto se dibuja en "
        "naranja y se indica si queda **por encima o por debajo** de la curva de la bomba (y cuánto), "
        "junto con η, NPSH y P en ese caudal.",
    ),
    Paso(
        "Más filas: «Agregar»",
        "Cada cuadro tiene un botón **«Agregar»** que añade otra fila, con otro tono del mismo color. "
        "La **×** de una fila la borra junto con su punto.\n\n"
        "Los avisos **⚠** indican, por ejemplo, que el valor está **fuera del rango digitalizado** "
        "(extrapolación: el resultado es menos fiable) o que falta alguna curva.",
    ),
]


def mostrar(pasos: list[Paso], titulo: str = "Guía paso a paso", marca: str = "guia") -> None:
    """Guía abierta al empezar, con un paso por fila y su imagen a la derecha.

    El botón «Cerrar guía» la oculta y deja en su lugar «Abrir guía» para volver a verla.
    """
    abrir = ui.button("Abrir guía", icon="menu_book", on_click=lambda: ver(True)).props("outline").classes(
        "mb-2"
    ).mark(f"abrir-{marca}")
    with ui.card().classes("w-full mb-2").mark(marca) as tarjeta:
        with ui.row().classes("w-full items-center no-wrap"):
            ui.icon("menu_book", size="sm")
            ui.label(titulo).classes("text-base font-medium flex-grow")
            ui.button("Cerrar guía", icon="close", on_click=lambda: ver(False)).props("flat").mark(f"cerrar-{marca}")
        for n, paso in enumerate(pasos, start=1):
            with ui.row().classes("w-full no-wrap items-start gap-4 py-3 border-t"):
                ui.label(str(n)).classes(
                    "w-7 h-7 shrink-0 rounded-full text-white text-center font-medium leading-7"
                ).style(f"background:{AYUDA}")
                with ui.column().classes("flex-grow gap-1"):
                    ui.label(paso.titulo).classes("font-medium")
                    ui.markdown(paso.texto).classes("text-sm")
                if paso.imagen:
                    _imagen(paso)
        with ui.row().classes("w-full justify-end"):
            ui.button("Cerrar guía", icon="close", on_click=lambda: ver(False)).props("flat")

    def ver(abierta: bool) -> None:
        tarjeta.set_visibility(abierta)
        abrir.set_visibility(not abierta)

    ver(True)


def _imagen(paso: Paso) -> None:
    """Miniatura que se amplía al hacer clic."""
    ruta = f"{URL_IMAGENES}/{paso.imagen}"
    with ui.dialog() as ampliada, ui.card().classes("max-w-none"):
        ui.image(ruta).style("width: min(90vw, 1000px)")
        ui.label(paso.pie).classes("text-sm text-gray-700")
    with ui.column().classes("w-2/5 max-w-md shrink-0 gap-1"):
        ui.image(ruta).classes("w-full border rounded cursor-zoom-in").on("click", ampliada.open)
        ui.label(f"{paso.pie} (clic para ampliar)" if paso.pie else "Clic para ampliar").classes(
            "text-xs text-gray-600"
        )
