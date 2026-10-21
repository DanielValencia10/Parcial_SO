"""
Reparte las filas de la placa en bandas, una por hilo o proceso.
Solo se reparten las filas interiores porque la fila 0 y la n-1 son bordes fijos.
"""


def rangos_de_filas(n, p):
    """Devuelve una lista de (fila_inicio, fila_fin) para cada trabajador (fila_fin no se incluye)."""
    interiores = n - 2
    p = max(1, min(p, interiores))      # no puede haber mas bandas que filas
    base = interiores // p
    extra = interiores % p              # las primeras bandas llevan una fila de mas si no da exacto
    rangos = []
    inicio = 1
    for i in range(p):
        fin = inicio + base + (1 if i < extra else 0)
        rangos.append((inicio, fin))
        inicio = fin
    return rangos
