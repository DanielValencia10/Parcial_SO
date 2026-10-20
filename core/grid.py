"""
La placa: lista de filas, cada fila un array('d') de temperaturas (formato acordado por el grupo).
Aquí solo se crea y se copia; el cálculo vive en las versiones.
"""

from array import array

import config


def nueva_placa(n):
    """Placa n x n con bordes fijos: el superior en T_BORDE_SUPERIOR, los otros tres en T_BORDES_RESTO,
    y el interior en T_INTERIOR."""
    placa = [array("d", [config.T_INTERIOR]) * n for _ in range(n)]
    for fila in placa:
        fila[0] = config.T_BORDES_RESTO          # borde izquierdo
        fila[n - 1] = config.T_BORDES_RESTO      # borde derecho
    placa[n - 1] = array("d", [config.T_BORDES_RESTO]) * n    # borde inferior
    placa[0] = array("d", [config.T_BORDE_SUPERIOR]) * n      # borde superior
    return placa


def copiar(placa):
    """Copia profunda de la placa (cada versión parte de su propia copia)."""
    return [array("d", fila) for fila in placa]
