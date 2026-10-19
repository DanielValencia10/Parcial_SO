"""
Contrato común de todas las versiones (secuencial, hilos, procesos, NumPy):
Engine(placa, workers), run(n), step(), snapshot() y close().

La placa es una lista de filas y cada fila es un array('d') de temperaturas.
La GUI, la validación y la medición usan cualquier versión SOLO a través de estos métodos.

Opcional: si el motor tiene un atributo `rangos` (lista de tuplas (fila_inicio, fila_fin),
una por hilo o proceso), la GUI dibuja esas bandas sobre la placa.
"""


class Engine:
    """Interfaz base. Cada versión hereda y rellena los métodos."""

    name = "base"   # Etiqueta para el CSV y las gráficas: "v1", "v2", "v3", "v4"

    def __init__(self, initial_plate, workers=1):
        """Prepara el motor a partir de una COPIA de initial_plate (no modifica el original)."""
        raise NotImplementedError

    def run(self, iterations):
        """Avanza `iterations` iteraciones."""
        raise NotImplementedError

    def step(self):
        """Avanza una iteración (equivale a run(1))."""
        raise NotImplementedError

    def snapshot(self):
        """Devuelve (una copia de) la placa actual: lista de filas array('d')."""
        raise NotImplementedError

    def close(self):
        """Libera hilos/procesos. Debe poder llamarse más de una vez sin error."""
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()          # se llama siempre, incluso si hubo una excepción
        return False          # no se traga la excepción
