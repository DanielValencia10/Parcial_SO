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
  race.py               la carrera: V1..V4 a la vez, cada una en su propio proceso
  renderer.py           mapa de calor: escala de colores y leyenda
medicion.py             programa de medición: tiempos de cada versión y datos del equipo
graficas.py             gráficas de tiempo, speedup y eficiencia, y tabla resumen
resultados/             salida de medicion.py y graficas.py
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
hilo o proceso **L** cambia la escala de colores (logarítmica o lineal) · **M** activa la carrera · **Esc** sale. Al pasar el ratón sobre la placa se ve la temperatura de la celda.

**Carrera (M):** las cuatro versiones corren a la vez las mismas 200 iteraciones, cada una en su propio proceso,
con la misma placa inicial y el mismo número de hilos o procesos. Todas arrancan juntas con una señal de salida
(crear hilos o procesos no cuenta) y el tiempo de cada una es solo el de `run()`. Las cuatro placas se ven a la vez
en una cuadrícula de 2 × 2 (vista reducida a unas 100 × 100 celdas, solo para dibujar) con su progreso, tiempo y
puesto; al terminar se ve quién ganó, el speedup contra V1 y la diferencia máxima entre las matrices finales.
Como corren al mismo tiempo, compiten por los núcleos: sirve para verlas competir, no reemplaza la medición.

El tiempo que muestra la interfaz es solo de cómputo y sirve como referencia visual; los tiempos del informe salen
del programa de medición.

## Equipo y mediciones

Equipo donde se midió:

- Procesador: AMD Ryzen 7 8845HS (8 núcleos físicos, 16 lógicos)
- Windows 11, Python 3.14.5 (con GIL)

Los datos exactos de cada medición quedan en `resultados/equipo.json`.

Medición (tamaños 100, 500, 1000 y 2000; 1, 2, 4 y 8 hilos o procesos; 3 ejecuciones de 200 iteraciones por
configuración). Tarda alrededor de una hora y cuarto, porque V1 y V2 en bucles puros de Python tardan unos
2-3 minutos por ejecución con 2000×2000:

```powershell
python medicion.py
```

Solo se cronometra `run(200)`: crear la placa y arrancar los hilos o procesos se anota aparte (`arranque_s`) y el
CSV se escribe entre ejecuciones. Se guarda después de cada ejecución; si se interrumpe, `python medicion.py
--continuar` sigue donde quedó. También se pueden elegir partes, por ejemplo
`python medicion.py --tamanos 100,500 --versiones 2,3`.

Gráficas y tabla resumen (promedio, speedup = T(V1) / T(versión) y eficiencia = speedup / p):

```powershell
python graficas.py
```

Salidas en `resultados/`: `mediciones.csv` (cada ejecución), `resumen.csv` (promedios), `rendimiento_vs_trabajadores.png`,
`rendimiento_vs_tamano.png` y `comparacion_versiones.png`.
