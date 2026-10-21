# Simulación Paralela de Difusión de Calor

Parcial I (segunda oportunidad) — Infraestructuras Paralelas y Distribuidas (750023C), Universidad del Valle.

Una placa cuadrada de N × N celdas: cada iteración, cada celda interior pasa a ser el promedio de sus cuatro
vecinas de la iteración anterior (doble búfer). Los bordes son fijos (superior en 100, los otros tres en 0, interior
inicial en 0) y todas las ejecuciones hacen 200 iteraciones.

## Estructura

```
config.py               constantes: iteraciones, bordes, tamaños, trabajadores, opciones de la GUI
core/
  engine_base.py        contrato común: Engine(placa, workers), run, step, snapshot, close
  registry.py           lista de versiones V1..V4 y carga bajo demanda
  grid.py               la placa: lista de filas array('d'); crear y copiar
  difusion.py           la única función de cálculo: actualiza un rango de filas (la usan V1, V2 y V3)
  particion.py          reparto de las filas interiores en bandas, una por hilo o proceso
  v1_sequential.py      V1 secuencial, bucles puros de Python (línea base)
  v2_threads.py         V2 hilos con una barrera por iteración
  v3_processes.py       V3 procesos: bandas de filas y filas frontera
  v4_numpy.py           V4 variante adicional con NumPy (SIMD), comparada aparte
gui/
  app.py                ventana, bucle principal y dibujo de la placa
  controls.py           botones, teclado y panel lateral
  renderer.py           mapa de calor: escala de colores y leyenda
```

Las versiones V1 a V4 se usan todas igual (contrato de `core/engine_base.py`), así que la interfaz y la medición
funcionan con cualquiera de ellas. La medición nunca incluye la interfaz gráfica ni la escritura a disco.

## Cómo ejecutarlo

Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Interfaz gráfica:

```powershell
python -m gui.app
```

Controles: **Espacio** inicia o pausa · **N** avanza una iteración · **R** reinicia · **1-4** elige la versión ·
**↑ ↓** hilos o procesos · **[ ]** tamaño de la placa · **← →** velocidad · **B** muestra las bandas de filas de cada
hilo o proceso · **Esc** sale. Al pasar el ratón sobre la placa se ve la temperatura de la celda.

El tiempo que muestra la interfaz es solo de cómputo y sirve como referencia visual; los tiempos del informe salen
del programa de medición.

## Equipo y mediciones

El análisis de rendimiento (tamaños 100, 500, 1000 y 2000; 1, 2, 4 y 8 hilos o procesos; mínimo 3 ejecuciones
por configuración) y sus gráficas se ejecutan con el programa de medición. Sus instrucciones y las características
del equipo (procesador y número de núcleos) las completa quien lo implementó.
