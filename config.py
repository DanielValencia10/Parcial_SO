"""
Constantes compartidas por las versiones, la GUI y las mediciones.
Parcial I (segunda oportunidad): simulación paralela de difusión de calor.
"""

# --- Simulación (enunciado)
ITERACIONES = 200            # iteraciones fijas en todas las ejecuciones, para que los tiempos sean comparables
T_BORDE_SUPERIOR = 100.0     # borde superior fijo
T_BORDES_RESTO = 0.0         # los otros tres bordes, fijos
T_INTERIOR = 0.0             # temperatura inicial del interior

# --- Medición y gráficas (enunciado: tamaños y trabajadores de ejemplo, mínimo 3 ejecuciones)
TAMANOS = [100, 500, 1000, 2000]
TRABAJADORES = [1, 2, 4, 8]      # hilos (V2) o procesos (V3)
REPETICIONES = 3

# --- GUI
GUI_VERSIONES = [1, 2, 3, 4]                 # 1 = secuencial, 2 = hilos, 3 = procesos, 4 = NumPy (SIMD)
GUI_TAMANOS = [50, 100, 500, 1000, 2000]     # tamaños que ofrece la interfaz
GUI_TAMANO = 100                             # con el que arranca (debe estar en GUI_TAMANOS)
GUI_TRABAJADORES = 4                         # con los que arranca (debe estar en TRABAJADORES)
GUI_VELOCIDADES = [1, 5, 15, 30, 60]         # iteraciones por segundo que se intentan mostrar
GUI_VELOCIDAD = 30                           # con la que arranca (debe estar en GUI_VELOCIDADES)
