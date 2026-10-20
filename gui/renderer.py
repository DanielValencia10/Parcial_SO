"""
PROVISIONAL. El mapa de calor (escala de colores y leyenda) es de Martín según el reparto.
Este archivo existe para que la interfaz corra hoy; Martín lo reemplaza conservando estas dos funciones:

    placa_a_rgb(arr)                  ndarray float (n, n)  ->  ndarray uint8 (n, n, 3)
    dibujar_leyenda(screen, rect, font)   barra de colores con su escala, dentro de `rect`

app.py no usa nada más de este módulo.
"""

import numpy as np
import pygame

import config

T_MIN = config.T_BORDES_RESTO
T_MAX = config.T_BORDE_SUPERIOR

# Escala azul oscuro -> violeta -> naranja -> amarillo (posición 0..1, color RGB)
_PARADAS = [(0.00, (12, 16, 56)), (0.25, (58, 32, 138)), (0.50, (178, 52, 110)),
            (0.75, (250, 140, 40)), (1.00, (255, 238, 150))]
_POS = np.array([p for p, _ in _PARADAS])
_RGB = np.array([c for _, c in _PARADAS], dtype=np.float64)


def _escala(valores):
    """Valores en [0, 1] -> colores RGB (uint8), con interpolación lineal entre las paradas."""
    v = np.clip(valores, 0.0, 1.0)
    canales = [np.interp(v, _POS, _RGB[:, k]) for k in range(3)]
    return np.stack(canales, axis=-1).astype(np.uint8)


def placa_a_rgb(arr):
    """Convierte las temperaturas (T_MIN..T_MAX) en una imagen RGB."""
    return _escala((arr - T_MIN) / (T_MAX - T_MIN))


def dibujar_leyenda(screen, rect, font):
    """Barra vertical de colores con T_MAX arriba y T_MIN abajo."""
    barra = pygame.Rect(rect.x, rect.y + 16, 16, rect.h - 32)
    grad = _escala(np.linspace(1.0, 0.0, barra.h))[:, None, :].repeat(barra.w, axis=1)
    screen.blit(pygame.surfarray.make_surface(grad.swapaxes(0, 1)), barra.topleft)
    pygame.draw.rect(screen, (46, 53, 70), barra.inflate(2, 2), 1)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = barra.bottom - round(frac * barra.h)
        txt = font.render(f"{T_MIN + frac * (T_MAX - T_MIN):.0f}", True, (196, 203, 218))
        screen.blit(txt, (barra.right + 6, y - txt.get_height() // 2))
