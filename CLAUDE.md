# CLAUDE.md — Digitalizador de curvas de bombas centrífugas

Reglas permanentes del proyecto. Deben respetarse en TODO el desarrollo.

## Objetivo
- El usuario carga un PDF o una imagen con las curvas del fabricante de una bomba centrífuga industrial.
- La app digitaliza las curvas y deduce funciones matemáticas (polinomios cuadráticos, cúbicos, etc.) que las representan.
- Esas funciones se usan después en calculadoras de operación.

## Restricciones (obligatorias)
1. **Sin IA.** PROHIBIDO usar IA/ML/LLM/APIs de visión para digitalizar. Solo visión por computador clásica (OpenCV, scikit-image, numpy, scipy) y ajuste numérico (`numpy.polyfit` / `scipy.optimize`).
2. **Magnitudes y gráficas.** Cada bomba tiene 4 magnitudes: altura manométrica (H), eficiencia (η), NPSH y potencia. Se presentan en 3 gráficas digitalizadas:
   - (a) H + η — usar doble eje Y cuando η y H tengan escalas distintas.
   - (b) NPSH.
   - (c) Potencia.
3. **Diámetro del impulsor.** Si las curvas dependen del diámetro del impulsor, cada curva debe quedar etiquetada con su diámetro.
4. **Unidades originales.** Respetar SIEMPRE las unidades del gráfico original (m, ft, m³/h, L/s, GPM, kW, HP…). Guardar la unidad de cada eje y no convertir salvo que el usuario lo pida.
5. **Estilo.** Curvas digitalizadas y todos sus textos/ejes en color NEGRO.
6. **Gráfica única por tipo.** Debe existir una única gráfica de cada tipo durante toda la sesión. Las calculadoras dibujan sobre esas mismas gráficas; nunca crean copias.
7. **Colores de las calculadoras.**
   - Cuadro 1 (cálculo de altura): tonos de MORADO.
   - Cuadro 2 (cálculo de caudal): tonos de AZUL.
   - Cuadro 3 (puntos de operación): tonos de NARANJA.
8. **Marcadores.** Cada punto calculado se muestra con un marcador y líneas punteadas (una horizontal y una vertical) hasta los ejes.
9. **Agregar filas.** Cada cuadro/calculadora permite agregar más puntos (filas) con un botón "Agregar".

## Convenciones
- Código modular, con tests (pytest) para la lógica numérica.
- Documentar supuestos y límites del método (rangos válidos, extrapolación).
