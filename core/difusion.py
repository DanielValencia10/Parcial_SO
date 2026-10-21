"""
Funcion de calculo que usan todas las versiones (V1, V2 y V3), para que todas hagan exactamente lo mismo.
Cada celda interior queda como el promedio de sus 4 vecinas de la iteracion anterior.
"""

from array import array


def actualizar_filas(actual, siguiente, fila_ini, fila_fin):
    """Calcula las filas fila_ini..fila_fin-1 de `siguiente` leyendo solo de `actual`.
    No toca la primera ni la ultima columna (bordes fijos)."""
    for f in range(fila_ini, fila_fin):
        arriba = actual[f - 1]
        centro = actual[f]
        abajo = actual[f + 1]
        # se suma en el mismo orden que V4 (arriba + abajo + izq + der) para que den igual
        siguiente[f][1:-1] = array("d", [
            (a + b + iz + de) * 0.25
            for a, b, iz, de in zip(arriba[1:-1], abajo[1:-1], centro[:-2], centro[2:])
        ])
