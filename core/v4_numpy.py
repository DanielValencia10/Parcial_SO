"""
V4: variante adicional con NumPy (SIMD, Taller 4). Se compara aparte y NO sustituye la línea base.

Un solo hilo: cada iteración calcula TODO el interior de la placa con operaciones vectorizadas
(cuatro vistas desplazadas sumadas), leyendo de un búfer y escribiendo en el otro (doble búfer).
Las sumas siguen el mismo orden que la fórmula del enunciado, ((arriba + abajo) + izquierda) + derecha,
y multiplicar por 0.25 es exacto en coma flotante; por eso el resultado coincide bit a bit con la
línea base si esta también suma en ese orden.
"""

from array import array

import numpy as np

from core.engine_base import Engine


class NumpyEngine(Engine):
    name = "v4"

    def __init__(self, initial_plate, workers=1):
        # workers no se usa: la variante SIMD corre en un solo hilo
        self.actual = np.array([np.frombuffer(fila, dtype=np.float64) for fila in initial_plate])  # COPIA
        # El segundo búfer parte de la misma placa: los bordes quedan fijos en los dos y nunca se escriben
        self.siguiente = self.actual.copy()
        self._cerrado = False

    def run(self, iterations):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        a, b = self.actual, self.siguiente
        for _ in range(iterations):
            dentro = b[1:-1, 1:-1]
            np.add(a[:-2, 1:-1], a[2:, 1:-1], out=dentro)    # arriba + abajo
            dentro += a[1:-1, :-2]                            # + izquierda
            dentro += a[1:-1, 2:]                             # + derecha
            dentro *= 0.25
            a, b = b, a                                       # swap de referencias: la iteración k+1 sale de la k
        self.actual, self.siguiente = a, b

    def step(self):
        self.run(1)

    def snapshot(self):
        return [array("d", fila.tobytes()) for fila in self.actual]

    def close(self):
        self._cerrado = True      # no hay hilos ni procesos que liberar
