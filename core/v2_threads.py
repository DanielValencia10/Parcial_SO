"""
V2: version con hilos. Cada hilo calcula su banda de filas y al final de cada iteracion
todos esperan en una barrera; cuando llegan todos se intercambian las placas.

Ojo: por el GIL de Python los hilos no corren el calculo al mismo tiempo, asi que esta
version no deberia ser mas rapida que la secuencial.
"""

import threading

from core import grid, particion
from core.difusion import actualizar_filas
from core.engine_base import Engine

TIMEOUT_BARRERA = 120   # para que no se quede colgado si un hilo falla


class ThreadedEngine(Engine):
    name = "v2"

    def __init__(self, initial_plate, workers=1):
        n = len(initial_plate)
        self.rangos = particion.rangos_de_filas(n, workers)
        self.p = len(self.rangos)

        # doble bufer: las dos placas empiezan iguales para que ambas tengan los bordes
        self.actual = grid.copiar(initial_plate)
        self.siguiente = grid.copiar(initial_plate)

        self._n = 0
        self._cerrado = False
        self._error = None

        # inicio y fin: los p hilos + el hilo principal que llama a run()
        self._inicio = threading.Barrier(self.p + 1)
        self._fin = threading.Barrier(self.p + 1)
        # barrera de cada iteracion, cuando llegan todos se hace el intercambio
        self._iter = threading.Barrier(self.p, action=self._intercambiar, timeout=TIMEOUT_BARRERA)

        # los hilos se crean una sola vez y se reutilizan
        self._hilos = [threading.Thread(target=self._trabajar, args=(i,), daemon=True)
                       for i in range(self.p)]
        for hilo in self._hilos:
            hilo.start()

    def _intercambiar(self):
        # esto lo hace un solo hilo mientras los otros esperan en la barrera
        self.actual, self.siguiente = self.siguiente, self.actual

    def _trabajar(self, i):
        fila_ini, fila_fin = self.rangos[i]
        while True:
            self._inicio.wait()
            if self._cerrado:
                return
            try:
                for _ in range(self._n):
                    # cada hilo escribe solo sus filas, asi no se pisan entre ellos
                    actualizar_filas(self.actual, self.siguiente, fila_ini, fila_fin)
                    self._iter.wait()
            except threading.BrokenBarrierError:
                pass
            except Exception as exc:
                if self._error is None:
                    self._error = exc
                self._iter.abort()        # rompe la barrera para que los demas no se queden esperando
            self._fin.wait()

    def run(self, iterations):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        if iterations <= 0:
            return
        self._n = iterations
        self._inicio.wait()      # arrancan los hilos
        self._fin.wait()         # espera a que terminen
        if self._error is not None:
            raise RuntimeError(f"Un hilo fallo: {self._error!r}") from self._error

    def step(self):
        self.run(1)

    def snapshot(self):
        return grid.copiar(self.actual)

    def close(self):
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self._inicio.wait(timeout=5)      # los despierta para que salgan del while
        except threading.BrokenBarrierError:
            pass
        for hilo in self._hilos:
            hilo.join(timeout=5)
