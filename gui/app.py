"""
Interfaz gráfica de la difusión de calor con pygame. Ejecutar: python -m gui.app

Muestra la placa como mapa de calor y su evolución durante las 200 iteraciones del enunciado.
Funciona con cualquier versión (V1 secuencial, V2 hilos, V3 procesos, V4 NumPy) porque solo usa el
contrato de core/engine_base.py: crear con la placa y los trabajadores, run/step, snapshot y close.
El tiempo que muestra es SOLO el de cómputo (engine.run); dibujar nunca entra en esa cuenta.
"""

import os
import time
import traceback

import numpy as np
import pygame

import config
from core import grid as grid_mod
from core.registry import EngineUnavailable, load_engine_class
from gui import controls, renderer

WINDOW_SIZE = (1280, 800)
LEGEND_W = 70
COLOR_BAND_LINE = (240, 244, 250)


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Difusión de calor — secuencial vs. paralelo")
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.fonts = controls.make_fonts()
        self.clock = pygame.time.Clock()

        sizes = config.GUI_TAMANOS
        self.ui = controls.UIState(
            version=config.GUI_VERSIONES[0],
            size_idx=sizes.index(config.GUI_TAMANO) if config.GUI_TAMANO in sizes else 0,
            workers_idx=config.TRABAJADORES.index(config.GUI_TRABAJADORES),
            speed_idx=config.GUI_VELOCIDADES.index(config.GUI_VELOCIDAD))

        self.origin = None          # placa en la iteración 0: de aquí parte cada corrida
        self.engine = None          # motor de la versión activa (se crea al primer avance)
        self.arr = None             # placa actual como ndarray, para dibujar
        self.rangos = None          # bandas (fila_inicio, fila_fin) por hilo/proceso, si el motor las expone
        self.rev = 0                # sube cada vez que cambia la placa (invalida la caché del dibujo)
        self.board_rect = pygame.Rect(0, 0, 1, 1)
        self._cache_key = None
        self._cache_surf = None
        self._cache_rect = None
        self.running_app = True

        self._safe(self._reset)

    # --- utilidades
    def _safe(self, fn, *args, **kwargs):
        """Ejecuta fn; si algo falla, pausa y lo muestra en pantalla en vez de caerse."""
        try:
            return fn(*args, **kwargs)
        except NotImplementedError as exc:
            origin = traceback.extract_tb(exc.__traceback__)[-1]
            self._fail(f"Pendiente de implementar: {origin.name}() en {os.path.basename(origin.filename)}")
        except EngineUnavailable as exc:
            self._fail(str(exc))
        except Exception as exc:                      # noqa: BLE001 - la GUI no debe caerse
            self._fail(f"Error: {type(exc).__name__}: {exc}")
            self._close_engine()
        return None

    def _fail(self, message):
        self.ui.running = False
        self.ui.status = message

    def _close_engine(self):
        if self.engine is not None:
            self.engine.close()
            self.engine = None
        self.rangos = None

    def _show(self, placa):
        """Muestra `placa` (lista de array('d')) y actualiza las métricas de temperatura del interior."""
        self.arr = np.array([np.frombuffer(fila, dtype=np.float64) for fila in placa])
        interior = self.arr[1:-1, 1:-1]
        self.ui.t_max = float(interior.max()) if interior.size else 0.0
        self.ui.t_mean = float(interior.mean()) if interior.size else 0.0
        self.rev += 1

    # --- acciones
    def _reset(self):
        """Placa inicial nueva (con el tamaño elegido) y corrida en cero."""
        ui = self.ui
        self._close_engine()
        self.origin = grid_mod.nueva_placa(ui.size)
        self._show(self.origin)
        ui.running = False
        ui.iteration = 0
        ui.compute_s = 0.0
        ui.status = ""

    def _ensure_engine(self):
        """Crea el motor de la versión activa a partir de la placa inicial (si todavía no existe)."""
        if self.engine is not None:
            return
        ui = self.ui
        clase = load_engine_class(ui.version)
        self.engine = clase(grid_mod.copiar(self.origin), ui.workers if ui.parallel else 1)
        self.rangos = getattr(self.engine, "rangos", None)

    def _advance(self, n):
        """Avanza n iteraciones y mide SOLO el cómputo; el dibujo se hace después, fuera del cronómetro."""
        ui = self.ui
        n = min(n, ui.total - ui.iteration)
        if n <= 0:
            return
        self._ensure_engine()
        t0 = time.perf_counter()
        self.engine.run(n)
        ui.compute_s += time.perf_counter() - t0
        ui.iteration += n
        self._show(self.engine.snapshot())
        if ui.finished:
            ui.running = False
            ui.tiempos[ui.clave(ui.version)] = ui.compute_s
            ui.status = f"Corrida completa: {ui.total} iteraciones en {ui.compute_s:.2f} s de cómputo"

    def _change(self, **cambios):
        """Cambia versión, tamaño o trabajadores: la corrida vuelve a empezar desde la placa inicial."""
        for k, v in cambios.items():
            setattr(self.ui, k, v)
        self._reset()

    def _apply(self, action):
        name, data = action
        ui = self.ui
        if name == "quit":
            self.running_app = False
        elif name == "toggle_run":
            if ui.finished:                           # "Repetir": nueva corrida desde la placa inicial
                self._safe(self._reset)
            ui.running = not ui.running
            ui.status = "" if ui.running else ui.status
        elif name == "step":
            ui.running = False
            self._safe(self._advance, 1)
        elif name == "reset":
            self._safe(self._reset)
        elif name == "version":
            if data != ui.version:
                self._safe(self._change, version=data)
        elif name == "workers":
            idx = max(0, min(len(config.TRABAJADORES) - 1, ui.workers_idx + data))
            if idx != ui.workers_idx and ui.parallel:
                self._safe(self._change, workers_idx=idx)
        elif name == "size":
            idx = max(0, min(len(config.GUI_TAMANOS) - 1, ui.size_idx + data))
            if idx != ui.size_idx:
                self._safe(self._change, size_idx=idx)

    # --- dibujo
    def _draw_board(self, area):
        """Dibuja la placa escalada y centrada en `area`. Solo se redibuja si algo cambió."""
        ui = self.ui
        n = self.arr.shape[0]
        cell = min(area.w, area.h) / n
        side = max(1, int(n * cell))
        rect = pygame.Rect(0, 0, side, side)
        rect.center = area.center
        key = (self.rev, ui.show_bands, side, ui.version, ui.workers)
        if key != self._cache_key:
            rgb = renderer.placa_a_rgb(self.arr)
            surf = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
            surf = pygame.transform.scale(surf, (side, side))
            if ui.show_bands and ui.parallel and self.rangos:
                self._draw_bands(surf, n)
            self._cache_surf, self._cache_key = surf, key
        self.screen.blit(self._cache_surf, rect.topleft)
        pygame.draw.rect(self.screen, controls.COLOR_EDGE, rect.inflate(2, 2), 1)
        self.board_rect = rect

    def _draw_bands(self, surf, n):
        """Separadores y etiqueta por banda: muestra qué filas calcula cada hilo/proceso."""
        px = surf.get_height() / n
        word = "Proceso" if self.ui.version == 3 else "Hilo"
        for i, (s, e) in enumerate(self.rangos):
            y0 = round(s * px)
            if i > 0:
                pygame.draw.line(surf, COLOR_BAND_LINE, (0, y0), (surf.get_width() - 1, y0), 2)
            if (e - s) * px >= 22:
                txt = self.fonts.small.render(f"{word} {i} · filas {s}-{e - 1}", True, (255, 255, 255))
                chip = pygame.Surface((txt.get_width() + 12, txt.get_height() + 4), pygame.SRCALPHA)
                chip.fill((10, 12, 18, 190))
                surf.blit(chip, (6, y0 + 4))
                surf.blit(txt, (12, y0 + 6))

    def _hover_text(self):
        """Temperatura de la celda bajo el ratón (vacío si el ratón está fuera de la placa)."""
        pos = pygame.mouse.get_pos()
        r = self.board_rect
        if self.arr is None or not r.collidepoint(pos):
            return ""
        n = self.arr.shape[0]
        c = min(n - 1, int((pos[0] - r.x) * n / r.w))
        f = min(n - 1, int((pos[1] - r.y) * n / r.h))
        return f"celda ({f}, {c})  ·  {self.arr[f, c]:.3f}"

    def _draw(self):
        self.screen.fill(controls.COLOR_BG)
        self.ui.buttons = []                          # cada cuadro registra sus botones desde cero
        w, h = self.screen.get_size()
        left_w = w - controls.SIDEBAR_W
        status = pygame.Rect(16, h - controls.STATUS_H - 10, left_w - 32, controls.STATUS_H)
        area = pygame.Rect(16, 12, left_w - 32 - LEGEND_W, status.y - 12 - 8)

        if self.arr is not None:
            self._draw_board(area)
            renderer.dibujar_leyenda(
                self.screen, pygame.Rect(area.right + 14, area.y, LEGEND_W - 14, area.h), self.fonts.small)
            self.ui.hover = self._hover_text()
        else:
            msg = self.fonts.body.render("Placa no disponible: revisar core/grid.py", True, controls.COLOR_WARN)
            self.screen.blit(msg, msg.get_rect(center=area.center))

        controls.draw_status(self.screen, status, self.ui, self.fonts)
        controls.draw_sidebar(self.screen, self.ui, self.fonts)
        pygame.display.flip()

    # --- bucle
    def run(self):
        ultimo = time.perf_counter()
        try:
            while self.running_app:
                for event in pygame.event.get():
                    action = controls.handle_event(event, self.ui)
                    if action:
                        self._apply(action)
                if self.ui.running:
                    ahora = time.perf_counter()
                    debidas = int((ahora - ultimo) * self.ui.speed)     # iteraciones que tocan a esta velocidad
                    if debidas >= 1:
                        self._safe(self._advance, debidas)
                        ultimo = ahora
                else:
                    ultimo = time.perf_counter()
                self._draw()
                self.clock.tick(60)
        finally:
            self._close_engine()
            pygame.quit()


def main():
    """Inicializa pygame y ejecuta el bucle principal."""
    App().run()


if __name__ == "__main__":
    main()
