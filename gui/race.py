"""
Carrera: las versiones corren a la vez las mismas ITERACIONES, cada una en su propio proceso.
Todas parten de la misma placa, con las mismas reglas y el mismo número de hilos o procesos, y arrancan
juntas con una señal de salida. Gana la que termina primero.

Reglas de la carrera (iguales para todas):
- La salida se da cuando TODAS ya crearon su motor: crear hilos o procesos no cuenta.
- El tiempo de cada una es solo el de engine.run(): ni copiar la placa para la vista en vivo ni copiar la
  placa final cuentan.
- Cada una avanza en tandas de ITERACIONES // TANDAS iteraciones; al terminar cada tanda informa su progreso
  y manda una vista reducida de su placa para dibujarla en vivo.

Como corren todas al mismo tiempo, compiten por los núcleos: estos tiempos sirven para ver la carrera, no
reemplazan los de medicion.py, donde cada configuración corre sola.
"""

import multiprocessing as mp
import time
from array import array

import numpy as np

TANDAS = 20         # veces que cada participante informa su progreso y manda su vista
VISTA_LADO = 100    # la vista en vivo se reduce a unas 100 x 100 celdas (solo para dibujar)

# estado de cada participante (valor en un entero compartido)
PREPARANDO, LISTO, CORRIENDO, TERMINO, CANCELADO, FALLO = range(6)


def paso_de_vista(n):
    """Cada cuántas filas y columnas se toma una celda para la vista reducida de una placa n x n."""
    return max(1, -(-n // VISTA_LADO))      # división hacia arriba


def reducir(placa):
    """Vista reducida de una placa (lista de array('d')): una celda de cada k filas y columnas."""
    k = paso_de_vista(len(placa))
    filas = [array("d", fila[::k]) for fila in placa[::k]]
    return b"".join(f.tobytes() for f in filas), len(filas[0])


def _participante(version, placa, workers, iteraciones, estado, progreso, salida, cancelar, cola):
    """Lo que ejecuta CADA proceso de la carrera (a nivel de módulo: debe poder serializarse)."""
    motor = None
    try:
        from core.registry import load_engine_class
        motor = load_engine_class(version)(placa, workers if version in (2, 3) else 1)
        estado.value = LISTO
        salida.wait()                                    # todos esperan la salida juntos
        paso = max(1, iteraciones // TANDAS)
        hechas = 0
        elapsed = 0.0
        estado.value = CORRIENDO
        while hechas < iteraciones:
            if cancelar.is_set():
                estado.value = CANCELADO
                return
            n = min(paso, iteraciones - hechas)
            t0 = time.perf_counter()
            motor.run(n)
            elapsed += time.perf_counter() - t0          # solo cuenta run()
            hechas += n
            progreso.value = hechas
            if hechas < iteraciones:                     # vista en vivo (la final se manda abajo)
                datos, ancho = reducir(motor.snapshot())
                cola.put(("vista", version, datos, ancho, hechas))
        final = motor.snapshot()                         # el reloj ya se detuvo
        datos, ancho = reducir(final)
        cola.put(("vista", version, datos, ancho, iteraciones))
        estado.value = TERMINO
        cola.put(("final", version, elapsed, b"".join(fila.tobytes() for fila in final), len(final[0])))
    except Exception as exc:                             # noqa: BLE001 - se informa a la GUI
        estado.value = FALLO
        cola.put(("error", version, f"{type(exc).__name__}: {exc}", None, 0))
    finally:
        if motor is not None:
            motor.close()


class Race:
    """Una carrera en marcha. La GUI la crea, llama a poll() en cada cuadro y lee su estado."""

    def __init__(self, versiones, placa, workers, iteraciones):
        ctx = mp.get_context("spawn")
        self.versiones = list(versiones)
        self.iteraciones = iteraciones
        self._salida = ctx.Event()
        self._cancelar = ctx.Event()
        self._cola = ctx.Queue()
        self._estado = {v: ctx.Value("i", PREPARANDO) for v in self.versiones}
        self._progreso = {v: ctx.Value("i", 0) for v in self.versiones}
        self.resultados = {}        # versión -> (segundos, placa final)
        self.errores = {}           # versión -> mensaje
        self.vistas = {}            # versión -> ndarray reducido de su placa más reciente (para dibujar)
        self.t_inicio = None        # reloj del padre en la salida (solo para el cronómetro en vivo)
        self.cancelada = False
        # no son daemon: V3 crea sus propios procesos y un daemon no puede tener hijos
        self._procs = {
            v: ctx.Process(target=_participante,
                           args=(v, placa, workers, iteraciones, self._estado[v], self._progreso[v],
                                 self._salida, self._cancelar, self._cola))
            for v in self.versiones}
        for p in self._procs.values():
            p.start()

    # --- en cada cuadro
    def poll(self):
        """Recoge mensajes, da la salida cuando todos están listos y detecta procesos caídos."""
        while not self._cola.empty():
            tipo, version, a, b, c = self._cola.get()
            if tipo == "vista":                          # a = bytes, b = ancho
                self.vistas[version] = np.frombuffer(a, dtype=np.float64).reshape(-1, b)
            elif tipo == "error":                        # a = mensaje
                self.errores[version] = a
            else:                                        # "final": a = segundos, b = bytes, c = ancho
                valores = array("d")
                valores.frombytes(b)
                self.resultados[version] = (
                    a, [valores[i:i + c] for i in range(0, len(valores), c)])
        if self.t_inicio is None and not self.cancelada:
            estados = [self._estado[v].value for v in self.versiones]
            if all(e in (LISTO, FALLO) for e in estados) and LISTO in estados:
                self.t_inicio = time.perf_counter()
                self._salida.set()                       # ¡salida!
        for v, p in self._procs.items():                 # un proceso que muere sin avisar no cuelga la GUI
            if not p.is_alive() and self._estado[v].value in (PREPARANDO, LISTO, CORRIENDO):
                self._estado[v].value = FALLO
                self.errores.setdefault(v, "el proceso terminó inesperadamente")

    # --- estado para dibujar
    @property
    def terminada(self):
        """Todos llegaron a la meta (o fallaron). Una carrera cancelada no cuenta como terminada."""
        return all(v in self.resultados or v in self.errores for v in self.versiones)

    @property
    def fase(self):
        if self.cancelada:
            return "cancelada"
        if self.terminada:
            return "terminada"
        return "preparando" if self.t_inicio is None else "corriendo"

    @property
    def ranking(self):
        """Versiones que llegaron, de la más rápida a la más lenta (por su tiempo, no por el orden de la cola)."""
        return sorted(self.resultados, key=lambda v: self.resultados[v][0])

    def hechas(self, version):
        """Iteraciones completadas por `version` (0..iteraciones)."""
        return self.iteraciones if version in self.resultados else self._progreso[version].value

    def segundos(self, version):
        """Segundos de `version`: su tiempo final si ya llegó; si no, el cronómetro en vivo."""
        if version in self.resultados:
            return self.resultados[version][0]
        if self.t_inicio is None or version in self.errores:
            return 0.0
        return time.perf_counter() - self.t_inicio

    # --- cierre
    def cancel(self):
        """Detiene la carrera y limpia los procesos (se puede llamar varias veces)."""
        self.cancelada = self.cancelada or not self.terminada
        self._cancelar.set()
        self._salida.set()                               # por si alguno seguía esperando la salida
        for p in self._procs.values():
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
