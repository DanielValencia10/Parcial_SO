"""
Validación (Requisito 3): demuestra que V2 (hilos), V3 (procesos) y V4 (NumPy) producen la misma matriz
final que la línea base secuencial V1.

Qué se comprueba
  1. La referencia V1 es correcta por sí misma:
       - los bordes no cambian (superior en 100, los otros tres en 0);
       - todas las temperaturas quedan entre 0 y 100 (un promedio nunca sale del rango de sus vecinas);
       - la placa es simétrica de izquierda a derecha, como lo son sus condiciones de frontera.
  2. Cada versión contra V1, con varios tamaños y números de hilos/procesos: diferencia máxima
     max |T_version[i][j] - T_V1[i][j]| sobre toda la placa después de 200 iteraciones.
  3. Avanzar por tramos da lo mismo que de una vez: run(73) + run(127) == run(200). Así se comprueba que
     el estado (doble búfer, filas frontera) se conserva bien entre llamadas, como lo usa la interfaz.

Casos incluidos a propósito
  - 100 filas con 4 u 8 trabajadores: las 98 filas interiores no se reparten exacto, hay bandas desiguales.
  - Placa 7x7 con 8 trabajadores: hay más trabajadores que filas interiores.

Tolerancia: 1e-10
  Todas las versiones usan la misma fórmula y suman en el mismo orden ((arriba + abajo) + izq) + der,
  y multiplicar por 0.25 es exacto en coma flotante; por eso se espera diferencia 0.0 exacta.
  La tolerancia solo cubre el caso de que una versión sumara en otro orden: cada suma de redondeo
  aporta como mucho ~1.1e-16 * 400 (épsilon de la máquina por la mayor temperatura), las 3 sumas por
  celda dan < 1e-13 por iteración, y como el promedio nunca amplifica un error (sus pesos suman 1),
  en 200 iteraciones el error acumulado queda por debajo de 200 * 1e-13 = 2e-11. 1e-10 deja margen
  sobre ese límite y aun así es miles de millones de veces más pequeño que las temperaturas (0..100):
  cualquier error real de sincronización o de filas frontera da diferencias del orden de 1 o más.

Uso (desde la carpeta del proyecto):
    python validacion.py              tamaños 7, 50, 100 y 500 (unos segundos a un par de minutos)
    python validacion.py --completo   además los tamaños de la medición (1000 y 2000; tarda bastante)
"""

import sys
import time

import config
from core.grid import nueva_placa
from core.registry import NOMBRES, EngineUnavailable, load_engine_class

TOLERANCIA = 1e-10
TAMANOS_RAPIDOS = [7, 50, 100, 500]
VERSIONES_A_VALIDAR = [2, 3, 4]


def correr(version, placa, trabajadores, tramos=(config.ITERACIONES,)):
    """Ejecuta una versión y devuelve su placa final. `tramos` reparte las iteraciones en varias llamadas a run."""
    clase = load_engine_class(version)
    with clase(placa, trabajadores) as motor:
        for iteraciones in tramos:
            motor.run(iteraciones)
        return motor.snapshot()


def diferencia_maxima(a, b):
    """max |a[i][j] - b[i][j]| sobre toda la placa."""
    return max(abs(x - y) for fila_a, fila_b in zip(a, b) for x, y in zip(fila_a, fila_b))


def revisar_referencia(ref, inicial):
    """Comprueba que la placa de V1 cumpla las propiedades físicas del problema. Devuelve lista de fallos."""
    n = len(ref)
    fallos = []
    bordes = [(i, j) for i in range(n) for j in range(n) if i in (0, n - 1) or j in (0, n - 1)]
    if any(ref[i][j] != inicial[i][j] for i, j in bordes):
        fallos.append("los bordes cambiaron")
    t_min = min(min(fila) for fila in ref)
    t_max = max(max(fila) for fila in ref)
    if t_min < config.T_BORDES_RESTO or t_max > config.T_BORDE_SUPERIOR:
        fallos.append(f"temperaturas fuera de rango [{t_min}, {t_max}]")
    asimetria = max(abs(ref[i][j] - ref[i][n - 1 - j]) for i in range(n) for j in range(n))
    if asimetria > TOLERANCIA:
        fallos.append(f"no es simétrica (asimetría {asimetria:.2e})")
    return fallos, asimetria


def validar(tamanos):
    ok = True
    print(f"Validación contra V1 · {config.ITERACIONES} iteraciones · tolerancia {TOLERANCIA:g}\n")
    print(f"{'Tamaño':>9}  {'Versión':<15} {'Trab.':>5}  {'Dif. máxima':>12}  {'Por tramos':>12}  Resultado")
    print("-" * 74)

    for n in tamanos:
        inicial = nueva_placa(n)
        t0 = time.perf_counter()
        ref = correr(1, inicial, 1)
        t_ref = time.perf_counter() - t0

        fallos, asimetria = revisar_referencia(ref, inicial)
        estado = "OK" if not fallos else "FALLA: " + "; ".join(fallos)
        ok &= not fallos
        print(f"{n:>4}x{n:<4}  {'V1 referencia':<15} {1:>5}  {'—':>12}  {'—':>12}  {estado}"
              f"  (asimetría {asimetria:.1e}, {t_ref:.2f} s)")

        for version in VERSIONES_A_VALIDAR:
            # V4 corre en un solo hilo: probarla con varios trabajadores no aporta nada
            trabajadores = config.TRABAJADORES if version in (2, 3) else [1]
            for p in trabajadores:
                nombre = f"V{version} {NOMBRES[version]}"
                try:
                    dif = diferencia_maxima(correr(version, inicial, p), ref)
                    dif_tramos = diferencia_maxima(correr(version, inicial, p, tramos=(73, 127)), ref)
                except EngineUnavailable as exc:
                    print(f"{n:>4}x{n:<4}  {nombre:<15} {p:>5}  {'—':>12}  {'—':>12}  NO DISPONIBLE ({exc})")
                    ok = False
                    continue
                pasa = dif <= TOLERANCIA and dif_tramos <= TOLERANCIA
                ok &= pasa
                print(f"{n:>4}x{n:<4}  {nombre:<15} {p:>5}  {dif:>12.3e}  {dif_tramos:>12.3e}  "
                      f"{'OK' if pasa else 'FALLA'}")
        print()

    print("RESULTADO:", "todas las versiones coinciden con V1" if ok
          else "algo falló o faltan versiones, revisar las filas marcadas arriba")
    return ok


if __name__ == "__main__":      # obligatorio en Windows: V3 crea procesos que vuelven a importar este archivo
    tamanos = TAMANOS_RAPIDOS + [n for n in config.TAMANOS if n > max(TAMANOS_RAPIDOS)] \
        if "--completo" in sys.argv else TAMANOS_RAPIDOS
    sys.exit(0 if validar(tamanos) else 1)
