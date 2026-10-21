"""
Mapa de calor: convierte cada temperatura en un color y dibuja la leyenda (Entrega: la placa como mapa de calor).

Paleta: "inferno" (la de matplotlib), muestreada en 9 colores e interpolada.
  - Va de negro (frío) a amarillo claro (caliente) y su brillo SUBE siempre: más claro = más caliente,
    también en escala de grises o para personas con daltonismo. Una paleta arcoíris no cumple eso.
  - Está diseñada para que pasos iguales de valor se vean como pasos iguales de color.

Dos escalas (tecla L o botón del panel):
  - "log" (la de arranque): el color sigue log10(T) entre 0.01 y 100; todo lo que esté por debajo de
    0.01 queda negro. Con 200 iteraciones el calor solo baja unas decenas de filas desde el borde
    superior y casi toda la placa está por debajo de 1; en escala lineal eso se ve todo negro. La
    logarítmica da un color distinto a cada orden de magnitud (100, 10, 1, 0.1, 0.01) y deja ver hasta
    dónde llegó el frente de calor, incluso en 2000x2000.
  - "lineal": el color es proporcional a T entre 0 y 100. Es la lectura literal de la temperatura.

La conversión usa una tabla de 1024 colores precalculada (LUT): cada celda solo busca su color por
índice, sin interpolar en cada cuadro, así que alcanza para 2000x2000 = 4 millones de celdas.

app.py usa solo estas dos funciones:
    placa_a_rgb(arr, escala)                    ndarray float (n, n)  ->  ndarray uint8 (n, n, 3)
    dibujar_leyenda(screen, rect, font, escala) barra de colores con su escala, dentro de `rect`
"""

import math

import numpy as np
import pygame

import config

ESCALAS = ("log", "lineal")
ESCALA_INICIAL = "log"

T_MIN = config.T_BORDES_RESTO        # 0
T_MAX = config.T_BORDE_SUPERIOR      # 100
T_LOG_MIN = 0.01                     # piso de la escala logarítmica: 4 órdenes de magnitud por debajo de T_MAX

# Paleta inferno (posición 0..1, color RGB), muestreada de matplotlib
_PARADAS = [(0.000, (0, 0, 4)), (0.125, (33, 12, 74)), (0.250, (87, 16, 110)),
            (0.375, (138, 34, 106)), (0.500, (188, 55, 84)), (0.625, (228, 90, 49)),
            (0.750, (249, 142, 9)), (0.875, (249, 203, 53)), (1.000, (252, 255, 164))]

_N_LUT = 1024
_x = np.linspace(0.0, 1.0, _N_LUT)
_pos = np.array([p for p, _ in _PARADAS])
_rgb = np.array([c for _, c in _PARADAS], dtype=np.float64)
_LUT = np.stack([np.interp(_x, _pos, _rgb[:, k]) for k in range(3)], axis=-1).round().astype(np.uint8)

_LOG_LO = math.log10(T_LOG_MIN)      # -2
_LOG_HI = math.log10(T_MAX)          #  2

COLOR_TEXTO = (196, 203, 218)
COLOR_TENUE = (136, 146, 166)
COLOR_BORDE = (46, 53, 70)


def normalizar(t, escala=ESCALA_INICIAL):
    """Temperatura(s) -> posición en la paleta, entre 0 y 1."""
    t = np.asarray(t, dtype=np.float64)
    if escala == "log":
        return (np.log10(np.clip(t, T_LOG_MIN, T_MAX)) - _LOG_LO) / (_LOG_HI - _LOG_LO)
    return np.clip((t - T_MIN) / (T_MAX - T_MIN), 0.0, 1.0)


def _colores(v):
    """Posiciones 0..1 -> colores RGB uint8, buscando en la tabla."""
    return _LUT[(v * (_N_LUT - 1)).round().astype(np.intp)]


def placa_a_rgb(arr, escala=ESCALA_INICIAL):
    """Convierte la placa de temperaturas en una imagen RGB (n, n, 3)."""
    return _colores(normalizar(arr, escala))


def _marcas(escala):
    """Temperaturas que se rotulan en la leyenda."""
    if escala == "log":
        return [100, 10, 1, 0.1, 0.01]
    return [100, 75, 50, 25, 0]


def _rotulo(t):
    return f"{t:g}"         # 100, 10, 1, 0.1, 0.01 / 75, 50, 25, 0


def dibujar_leyenda(screen, rect, font, escala=ESCALA_INICIAL):
    """Barra vertical de colores (caliente arriba, frío abajo) con sus temperaturas y el nombre de la escala."""
    titulo = font.render("T", True, COLOR_TEXTO)
    screen.blit(titulo, (rect.x + 8 - titulo.get_width() // 2, rect.y))

    barra = pygame.Rect(rect.x, rect.y + titulo.get_height() + 6, 16, rect.h - 2 * titulo.get_height() - 18)
    # El color de cada fila de píxeles sale de la misma tabla que la placa: la leyenda nunca miente
    grad = _colores(np.linspace(1.0, 0.0, barra.h))[:, None, :].repeat(barra.w, axis=1)
    screen.blit(pygame.surfarray.make_surface(grad.swapaxes(0, 1)), barra.topleft)
    pygame.draw.rect(screen, COLOR_BORDE, barra.inflate(2, 2), 1)

    for t in _marcas(escala):
        y = barra.bottom - 1 - round(float(normalizar(t, escala)) * (barra.h - 1))
        pygame.draw.line(screen, COLOR_TEXTO, (barra.right, y), (barra.right + 3, y))
        txt = font.render(_rotulo(t), True, COLOR_TEXTO)
        screen.blit(txt, (barra.right + 6, y - txt.get_height() // 2))

    nombre = font.render(escala, True, COLOR_TENUE)
    screen.blit(nombre, (rect.x, barra.bottom + 6))
