"""
V1: línea base secuencial con bucles puros de Python (Requisito 1 y Condiciones de la simulación).

No tiene cálculo propio: usa la función común `actualizar_filas` de core/difusion.py, la misma que
V2 (hilos) y V3 (procesos) llaman con su banda de filas. V1 la llama una sola vez por iteración con
TODAS las filas interiores (1..n-2), así que es exactamente la versión paralela con un solo trabajador
y sin sincronización: la referencia contra la que se mide el speedup y se valida el resultado.

Condiciones de la simulación:
  - Bordes fijos: la placa inicial (core/grid.py) trae el superior en 100 y los otros tres en 0, y
    actualizar_filas nunca escribe la fila 0, la fila n-1 ni las columnas 0 y n-1.
  - Doble búfer: la iteración k+1 se escribe en `siguiente` leyendo solo de `actual` (iteración k).
  - 200 iteraciones: las fija config.ITERACIONES; quien use el motor llama run(config.ITERACIONES).
"""

from core.difusion import actualizar_filas
from core.engine_base import Engine
from core.grid import copiar


class SequentialEngine(Engine):
    name = "v1"

    def __init__(self, initial_plate, workers=1):
        # workers no se usa: se recibe solo para cumplir el contrato común
        self.actual = copiar(initial_plate)       # iteración k (COPIA: no se toca la placa original)
        self.siguiente = copiar(initial_plate)    # iteración k+1; ya trae los bordes fijos, que nunca se escriben
        self.n = len(initial_plate)
        self._cerrado = False

    def run(self, iterations):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        for _ in range(iterations):
            actualizar_filas(self.actual, self.siguiente, 1, self.n - 1)    # todas las filas interiores
            # Swap de referencias: la iteración recién calculada pasa a ser la actual, sin copiar la placa
            self.actual, self.siguiente = self.siguiente, self.actual

    def step(self):
        self.run(1)

    def snapshot(self):
        return copiar(self.actual)

    def close(self):
        self._cerrado = True      # no hay hilos ni procesos que liberar
