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
from gui.race import Race, paso_de_vista

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
        self.race = None            # Race en marcha (None si no hay carrera corriendo)
        self.finales = {}           # versión -> placa final de la última carrera
        self.vistas = {}            # versión -> vista reducida de su placa en la carrera (ndarray)
        self.rev = 0              # sube cada vez que cambia la placa (invalida la caché del dibujo)
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
        self._cancel_race()
        self._close_engine()
        self.origin = grid_mod.nueva_placa(ui.size)
        self._show(self.origin)
        ui.running = False
        ui.iteration = 0
        ui.compute_s = 0.0
        ui.status = ""
        self.finales = {}
        self.vistas = {}
        ui.carrera_view = None
        ui.diff = {}

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

    # --- carrera
    def _race_view(self, race):
        """Resumen de la carrera para dibujar (datos simples: controls.py no conoce a Race)."""
        ranking = race.ranking
        return {"fase": race.fase,
                "segundos": {v: r[0] for v, r in race.resultados.items()},
                "carriles": [{"v": v, "hechas": race.hechas(v), "segundos": race.segundos(v),
                              "puesto": ranking.index(v) + 1 if v in ranking else 0,
                              "error": race.errores.get(v)} for v in race.versiones]}

    def _race_tick(self):
        """Un cuadro de la carrera: la crea si no existe, la sigue y la cierra cuando todos llegan."""
        ui = self.ui
        if self.race is None:
            self._close_engine()
            self.finales = {}
            ui.diff = {}
            self._show(self.origin)                   # SIEMPRE desde la iteración 0 y la misma placa
            k = paso_de_vista(len(self.origin))       # las cuatro vistas arrancan con la placa inicial
            self.vistas = {v: self.arr[::k, ::k] for v in config.GUI_VERSIONES}
            self.race = Race(config.GUI_VERSIONES, grid_mod.copiar(self.origin), ui.workers, ui.total)
        race = self.race
        race.poll()
        self.vistas.update(race.vistas)
        ui.carrera_view = self._race_view(race)
        ui.status = ("Preparando la carrera… (V3 crea sus procesos antes de la salida)"
                     if race.fase == "preparando" else "")
        if race.terminada:
            self._finish_race()

    def _finish_race(self):
        """Todos llegaron: se muestra la placa del ganador, se compara con la base y se anota el resultado."""
        ui, race = self.ui, self.race
        ui.carrera_view = self._race_view(race)
        self.vistas.update(race.vistas)
        self.race = None
        race.cancel()                                 # los procesos ya terminaron: solo los recoge
        ui.running = False
        self.finales = {v: placa for v, (_, placa) in race.resultados.items()}
        ranking = race.ranking
        if not ranking:
            ui.status = "Ninguna versión terminó la carrera: " + "; ".join(
                f"V{v}: {m}" for v, m in sorted(race.errores.items()))
            return
        # exactitud: diferencia máxima de cada versión contra V1 (o la más rápida si V1 no corrió)
        base = 1 if 1 in self.finales else ranking[0]
        ref = np.array([np.frombuffer(f, dtype=np.float64) for f in self.finales[base]])
        ui.diff_base = base
        ui.diff = {v: float(np.abs(ref - np.array([np.frombuffer(f, dtype=np.float64) for f in p])).max())
                   for v, p in self.finales.items() if v != base}
        ganador = ranking[0]
        ui.status = f"Ganó V{ganador}: {ui.total} iteraciones en {race.resultados[ganador][0]:.2f} s"
        if race.errores:
            ui.status += " · no corrieron: " + ", ".join(f"V{v}" for v in sorted(race.errores))

    def _cancel_race(self, message=""):
        """Detiene la carrera en marcha (si la hay) y limpia sus procesos."""
        if self.race is not None:
            self.race.cancel()
            self.race = None
            self.ui.carrera_view = None
            self.ui.status = message

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
            if ui.carrera:                            # la carrera arranca o se cancela; no se pausa
                if ui.running:
                    ui.running = False
                    self._cancel_race("Carrera cancelada")
                else:
                    ui.running = True
                    ui.status = ""
                return
            if ui.finished:                           # "Repetir": nueva corrida desde la placa inicial
                self._safe(self._reset)
            ui.running = not ui.running
            ui.status = "" if ui.running else ui.status
        elif name == "step":
            if not ui.carrera:
                ui.running = False
                self._safe(self._advance, 1)
        elif name == "reset":
            self._safe(self._reset)
        elif name == "compare":
            self._safe(self._reset)                   # cancela lo que haya y vuelve a la placa inicial
            ui.carrera = not ui.carrera
            ui.status = ("Carrera: pulsa «¡Iniciar carrera!». Todas parten de la misma placa."
                         if ui.carrera else "")
        elif name == "version":
            if ui.carrera:                            # en la carrera se ven las cuatro a la vez
                pass
            elif data != ui.version:
                self._safe(self._change, version=data)
        elif name == "workers":
            idx = max(0, min(len(config.TRABAJADORES) - 1, ui.workers_idx + data))
            if idx != ui.workers_idx and (ui.parallel or ui.carrera):
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
        key = (self.rev, ui.show_bands, side, ui.version, ui.workers, ui.escala)
        if key != self._cache_key:
            rgb = renderer.placa_a_rgb(self.arr, ui.escala)
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

    def _draw_cuatro(self, area):
        """La carrera: las cuatro placas a la vez en una cuadrícula de 2 x 2, cada una con su progreso."""
        gap = 10
        w, h = (area.w - gap) // 2, (area.h - gap) // 2
        view = self.ui.carrera_view
        carriles = {c["v"]: c for c in view["carriles"]} if view else {}
        for i, v in enumerate(config.GUI_VERSIONES):
            cell = pygame.Rect(area.x + (i % 2) * (w + gap), area.y + (i // 2) * (h + gap), w, h)
            c = carriles.get(v)
            color = controls.VERSION_COLORS[v]
            ganadora = bool(c and c["puesto"] == 1 and view["fase"] == "terminada")
            # cabecera: nombre a la izquierda; progreso, tiempo y puesto a la derecha
            nombre = self.fonts.body.render(controls.VERSION_LABEL[v], True, color)
            self.screen.blit(nombre, (cell.x + 2, cell.y + 1))
            if c and not c["error"]:
                partes = [f"{100 * c['hechas'] // self.ui.total}%"]
                if c["segundos"]:
                    partes.append(f"{c['segundos']:.2f} s")
                if c["puesto"]:
                    partes.append(f"{c['puesto']}º")
                info = self.fonts.body.render("  ·  ".join(partes), True,
                                              controls.COLOR_ACCENT if ganadora else controls.COLOR_BODY)
                self.screen.blit(info, (cell.right - info.get_width() - 2, cell.y + 1))
            # la placa, cuadrada y centrada bajo la cabecera
            zona = pygame.Rect(cell.x, cell.y + 26, w, h - 26)
            lado = max(1, min(zona.w, zona.h))
            rect = pygame.Rect(0, 0, lado, lado)
            rect.center = zona.center
            vista = self.vistas.get(v)
            if c and c["error"]:
                pygame.draw.rect(self.screen, controls.COLOR_CARD, rect)
                msg = self.fonts.body.render(f"V{v} no disponible", True, controls.COLOR_BAD)
                self.screen.blit(msg, msg.get_rect(center=rect.center))
            elif vista is not None:
                surf = pygame.surfarray.make_surface(renderer.placa_a_rgb(vista, self.ui.escala).swapaxes(0, 1))
                self.screen.blit(pygame.transform.scale(surf, (lado, lado)), rect.topleft)
            pygame.draw.rect(self.screen, controls.COLOR_ACCENT if ganadora else color,
                             rect.inflate(2, 2), 3 if ganadora else 1)

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
            if self.ui.carrera and self.vistas:
                self._draw_cuatro(area)
                self.ui.hover = ""
            else:
                self._draw_board(area)
                self.ui.hover = self._hover_text()
            renderer.dibujar_leyenda(
                self.screen, pygame.Rect(area.right + 14, area.y, LEGEND_W - 14, area.h), self.fonts.small,
                self.ui.escala)
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
                if self.ui.running and self.ui.carrera:
                    self._safe(self._race_tick)           # la carrera avanza sola, en sus propios procesos
                elif self.ui.running:
                    ahora = time.perf_counter()
                    debidas = int((ahora - ultimo) * self.ui.speed)     # iteraciones que tocan a esta velocidad
                    if debidas >= 1:
                        self._safe(self._advance, debidas)
                        ultimo = ahora
                else:
                    ultimo = time.perf_counter()
                    if self.race is not None:             # se pausó o se cambió algo durante la carrera
                        self._cancel_race("Carrera cancelada")
                self._draw()
                self.clock.tick(60)
        finally:
            self._cancel_race()
            self._close_engine()
            pygame.quit()


def main():
    """Inicializa pygame y ejecuta el bucle principal."""
    App().run()


if __name__ == "__main__":
    main()
