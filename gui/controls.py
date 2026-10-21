"""
Estado de la interfaz, botones, teclado y panel lateral. Traduce eventos en acciones para app.py.
Los colores del mapa de calor NO están aquí: son de gui/renderer.py.
"""

from collections import namedtuple
from dataclasses import dataclass, field

import pygame

import config
from core.registry import NOMBRES
from gui import renderer

SIDEBAR_W = 380
STATUS_H = 24

# --- Paleta de la interfaz
COLOR_BG = (14, 17, 24)
COLOR_PANEL = (22, 26, 36)
COLOR_CARD = (30, 35, 48)
COLOR_EDGE = (46, 53, 70)
COLOR_TEXT = (228, 232, 240)
COLOR_BODY = (196, 203, 218)
COLOR_DIM = (136, 146, 166)
COLOR_ACCENT = (255, 184, 76)
COLOR_ON_BG = (34, 56, 92)
COLOR_ON_EDGE = (86, 148, 255)
COLOR_BTN = (40, 46, 62)
COLOR_BTN_HI = (54, 62, 84)
COLOR_BTN_OFF = (28, 32, 43)
COLOR_OK = (110, 220, 140)
COLOR_WARN = (255, 184, 76)
COLOR_BAD = (240, 100, 100)

VERSION_LABEL = {v: f"V{v} {NOMBRES[v]}" for v in NOMBRES}

Fonts = namedtuple("Fonts", "title head body small big")


def make_fonts():
    names = "segoeui,helveticaneue,dejavusans,arial"
    f = pygame.font.SysFont
    return Fonts(f(names, 22, bold=True), f(names, 17, bold=True), f(names, 15),
                 f(names, 13), f(names, 26, bold=True))


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: tuple
    kind: str = "normal"      # "primary" | "normal"
    active: bool = False
    enabled: bool = True


@dataclass
class UIState:
    """Estado mutable de la interfaz."""
    running: bool = False
    version: int = 1
    size_idx: int = 0
    workers_idx: int = 0
    speed_idx: int = 0
    show_bands: bool = True
    escala: str = renderer.ESCALA_INICIAL   # escala de colores del mapa de calor: "log" o "lineal"
    iteration: int = 0                 # iteraciones hechas en la corrida actual
    total: int = config.ITERACIONES    # iteraciones fijas del enunciado
    compute_s: float = 0.0             # tiempo de CÓMPUTO acumulado de la corrida (sin dibujo)
    t_max: float = 0.0                 # temperatura máxima del interior
    t_mean: float = 0.0                # temperatura media del interior
    status: str = ""
    hover: str = ""                    # temperatura de la celda bajo el ratón
    buttons: list = field(default_factory=list)
    tiempos: dict = field(default_factory=dict)   # (versión, tamaño, trabajadores) -> segundos de una corrida completa

    @property
    def workers(self):
        return config.TRABAJADORES[self.workers_idx]

    @property
    def size(self):
        return config.GUI_TAMANOS[self.size_idx]

    @property
    def speed(self):
        return config.GUI_VELOCIDADES[self.speed_idx]

    @property
    def parallel(self):
        """V2 (hilos) y V3 (procesos) usan trabajadores; V1 y V4 corren en un solo hilo."""
        return self.version in (2, 3)

    @property
    def worker_word(self):
        return "proceso" if self.version == 3 else "hilo"

    @property
    def finished(self):
        return self.iteration >= self.total

    @property
    def ms_iter(self):
        """Promedio de ms por iteración en la corrida actual."""
        return 1000 * self.compute_s / self.iteration if self.iteration else 0.0

    def clave(self, version):
        """Llave de `tiempos`: los trabajadores solo cuentan en V2 y V3."""
        return (version, self.size, self.workers if version in (2, 3) else 1)


# --- eventos
def _do(state, name, data):
    """Aplica una acción de la UI. Devuelve una acción para app.py o None si ya se resolvió."""
    if name == "speed":
        state.speed_idx = max(0, min(len(config.GUI_VELOCIDADES) - 1, state.speed_idx + data))
        return None
    if name == "toggle_bands":
        state.show_bands = not state.show_bands
        return None
    if name == "toggle_scale":
        otras = renderer.ESCALAS
        state.escala = otras[(otras.index(state.escala) + 1) % len(otras)]
        return None
    return (name, data)     # el resto lo ejecuta app.py


def handle_event(event, state):
    """Procesa un evento de pygame y devuelve una acción (nombre, datos) o None."""
    if event.type == pygame.QUIT:
        return ("quit", None)

    if event.type == pygame.KEYDOWN:
        k = event.key
        if k in (pygame.K_ESCAPE, pygame.K_q):
            return ("quit", None)
        simples = {
            pygame.K_SPACE: ("toggle_run", None), pygame.K_n: ("step", None),
            pygame.K_r: ("reset", None), pygame.K_b: ("toggle_bands", None),
            pygame.K_l: ("toggle_scale", None),
            pygame.K_UP: ("workers", +1), pygame.K_DOWN: ("workers", -1),
            pygame.K_RIGHT: ("speed", +1), pygame.K_LEFT: ("speed", -1),
            pygame.K_RIGHTBRACKET: ("size", +1), pygame.K_LEFTBRACKET: ("size", -1),
        }
        if k in simples:
            return _do(state, *simples[k])
        if pygame.K_1 <= k <= pygame.K_9 and (k - pygame.K_0) in config.GUI_VERSIONES:
            return ("version", k - pygame.K_0)

    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for b in state.buttons:
            if b.enabled and b.rect.collidepoint(event.pos):
                return _do(state, *b.action)

    return None


# --- dibujo básico
def _text(screen, font, text, x, y, color, right=False):
    surf = font.render(text, True, color)
    screen.blit(surf, (x - surf.get_width() if right else x, y))
    return surf.get_width()


def _draw_button(screen, font, b):
    hover = b.enabled and b.rect.collidepoint(pygame.mouse.get_pos())
    if not b.enabled:
        bg, fg, edge = COLOR_BTN_OFF, (88, 96, 114), None
    elif b.kind == "primary":
        bg = (255, 205, 120) if hover else COLOR_ACCENT
        fg, edge = (30, 22, 8), None
    elif b.active:
        bg, fg, edge = COLOR_ON_BG, COLOR_TEXT, COLOR_ON_EDGE
    else:
        bg = COLOR_BTN_HI if hover else COLOR_BTN
        fg, edge = COLOR_TEXT, None
    pygame.draw.rect(screen, bg, b.rect, border_radius=7)
    if edge:
        pygame.draw.rect(screen, edge, b.rect, 1, border_radius=7)
    surf = font.render(b.label, True, fg)
    screen.blit(surf, surf.get_rect(center=b.rect.center))


def _row(screen, state, font, x, y, width, height, specs, gap=8):
    """Fila de botones. specs: (etiqueta, acción, kind, active, enabled, peso)."""
    total = sum(s[5] for s in specs)
    avail = width - gap * (len(specs) - 1)
    cx = x
    for i, (label, action, kind, active, enabled, weight) in enumerate(specs):
        w = round(avail * weight / total) if i < len(specs) - 1 else x + width - cx
        b = Button(pygame.Rect(cx, y, w, height), label, action, kind, active, enabled)
        state.buttons.append(b)
        _draw_button(screen, font, b)
        cx += w + gap


def _spec(label, action, kind="normal", active=False, enabled=True, weight=1):
    return (label, action, kind, active, enabled, weight)


def _stepper(screen, state, fonts, x, y, width, label, value, minus, plus, enabled=True):
    """Fila 'etiqueta  [-]  valor  [+]'."""
    _text(screen, fonts.body, label, x, y + 4, COLOR_BODY if enabled else COLOR_DIM)
    bm = Button(pygame.Rect(x + 110, y, 32, 28), "-", minus, enabled=enabled)
    bp = Button(pygame.Rect(x + width - 32, y, 32, 28), "+", plus, enabled=enabled)
    for b in (bm, bp):
        state.buttons.append(b)
        _draw_button(screen, fonts.head, b)
    surf = fonts.body.render(value, True, COLOR_TEXT if enabled else COLOR_DIM)
    mid = (bm.rect.right + bp.rect.left) // 2
    screen.blit(surf, surf.get_rect(center=(mid, y + 14)))


# --- paneles
def draw_status(screen, rect, state, fonts):
    """Una línea bajo la placa: avisos a la izquierda y la temperatura de la celda bajo el ratón a la derecha."""
    if state.status:
        _text(screen, fonts.body, state.status, rect.x, rect.y + 2, COLOR_WARN)
    else:
        _text(screen, fonts.small, "Pasa el ratón sobre la placa para ver la temperatura de cada celda",
              rect.x, rect.y + 5, COLOR_DIM)
    if state.hover:
        _text(screen, fonts.body, state.hover, rect.right, rect.y + 2, COLOR_TEXT, right=True)


def _tarjeta_metricas(screen, state, fonts, card):
    cx, cy = card.x + 12, card.y + 10
    _text(screen, fonts.body, f"Iteración {state.iteration} / {state.total}", cx, cy, COLOR_TEXT)
    _text(screen, fonts.body, f"Cómputo {state.compute_s:.3f} s", card.right - 12, cy, COLOR_BODY, right=True)
    cy += 26
    track = pygame.Rect(cx, cy, card.w - 24, 8)
    pygame.draw.rect(screen, COLOR_EDGE, track, border_radius=4)
    done = pygame.Rect(track.x, track.y, round(track.w * min(1.0, state.iteration / state.total)), track.h)
    if done.w:
        pygame.draw.rect(screen, COLOR_ACCENT, done, border_radius=4)
    cy += 16
    _text(screen, fonts.small, "Tiempo por iteración", cx, cy, COLOR_DIM)
    ms = f"{state.ms_iter:.2f} ms" if state.iteration else "—"
    _text(screen, fonts.big, ms, cx, cy + 14, COLOR_TEXT)
    _text(screen, fonts.small, f"T máx. interior  {state.t_max:.2f}", card.right - 12, cy + 4, COLOR_BODY, right=True)
    _text(screen, fonts.small, f"T media interior  {state.t_mean:.3f}", card.right - 12, cy + 24, COLOR_BODY, right=True)


def _tarjeta_tiempos(screen, state, fonts, card):
    """Tiempo de la última corrida COMPLETA de cada versión con el tamaño y los trabajadores actuales."""
    cx, cy = card.x + 12, card.y + 10
    _text(screen, fonts.body, f"Última corrida completa · {state.size}×{state.size}", cx, cy, COLOR_TEXT)
    cy += 26
    base = state.tiempos.get(state.clave(1))
    for v in config.GUI_VERSIONES:
        t = state.tiempos.get(state.clave(v))
        actual = v == state.version
        _text(screen, fonts.small, VERSION_LABEL[v], cx, cy, COLOR_TEXT if actual else COLOR_BODY)
        if t is None:
            _text(screen, fonts.small, "—", card.right - 12, cy, COLOR_DIM, right=True)
        else:
            _text(screen, fonts.small, f"{t:.3f} s", card.right - 70, cy, COLOR_TEXT, right=True)
            if base and v != 1:
                s = base / t
                color = COLOR_OK if s > 1.05 else (COLOR_WARN if s >= 0.95 else COLOR_BAD)
                _text(screen, fonts.small, f"{s:.2f}×", card.right - 12, cy, color, right=True)
            elif v == 1:
                _text(screen, fonts.small, "base", card.right - 12, cy, COLOR_DIM, right=True)
        cy += 20
    _text(screen, fonts.small, "Solo cómputo, sin dibujar (los oficiales: medición)", cx, cy + 2, COLOR_DIM)


def draw_sidebar(screen, state, fonts):
    """Panel derecho: botones y métricas."""
    w, h = screen.get_size()
    x0 = w - SIDEBAR_W
    pygame.draw.rect(screen, COLOR_PANEL, (x0, 0, SIDEBAR_W, h))
    pygame.draw.line(screen, COLOR_EDGE, (x0, 0), (x0, h))
    pad = 18
    x, inner = x0 + pad, SIDEBAR_W - 2 * pad
    y = 14

    _text(screen, fonts.title, "Difusión de calor", x, y, COLOR_TEXT)
    _text(screen, fonts.small, "Parcial I · 750023C", x + inner, y + 8, COLOR_DIM, right=True)
    y += 34

    if state.running:
        inicio = "Pausar"
    else:
        inicio = "Repetir" if state.finished else "Iniciar"
    _row(screen, state, fonts.body, x, y, inner, 38, [
        _spec(inicio, ("toggle_run", None), "primary", weight=2),
        _spec("Paso", ("step", None), enabled=not state.finished),
        _spec("Reiniciar", ("reset", None))])
    y += 48

    _text(screen, fonts.small, "Versión", x, y, COLOR_DIM)
    y += 18
    versions = list(config.GUI_VERSIONES)
    for i in range(0, len(versions), 2):
        _row(screen, state, fonts.small, x, y, inner, 32, [
            _spec(VERSION_LABEL[v], ("version", v), active=(state.version == v))
            for v in versions[i:i + 2]], gap=6)
        y += 38
    _text(screen, fonts.small, "V4 es una variante adicional: no sustituye la línea base (V1).",
          x, y - 2, COLOR_DIM)
    y += 22

    par = state.parallel
    workers_label = "Procesos" if state.version == 3 else "Hilos"
    _stepper(screen, state, fonts, x, y, inner, workers_label, str(state.workers) if par else "—",
             ("workers", -1), ("workers", +1), enabled=par)
    y += 34
    _stepper(screen, state, fonts, x, y, inner, "Matriz", f"{state.size} × {state.size}",
             ("size", -1), ("size", +1))
    y += 34
    _stepper(screen, state, fonts, x, y, inner, "Velocidad", f"{state.speed} iter/s",
             ("speed", -1), ("speed", +1))
    y += 40

    _row(screen, state, fonts.small, x, y, inner, 30, [
        _spec("Bandas (reparto de filas)", ("toggle_bands", None),
              active=state.show_bands and par, enabled=par, weight=3),
        _spec(f"Escala: {state.escala}", ("toggle_scale", None), weight=2)])
    y += 40

    card = pygame.Rect(x, y, inner, 118)
    pygame.draw.rect(screen, COLOR_CARD, card, border_radius=8)
    _tarjeta_metricas(screen, state, fonts, card)
    y = card.bottom + 10

    card = pygame.Rect(x, y, inner, 26 + 20 * len(versions) + 36)
    pygame.draw.rect(screen, COLOR_CARD, card, border_radius=8)
    _tarjeta_tiempos(screen, state, fonts, card)

    _text(screen, fonts.small, "Espacio inicia · N paso · R reinicia · 1-4 versión", x, h - 42, COLOR_DIM)
    _text(screen, fonts.small, "B bandas · L escala de colores", x, h - 24, COLOR_DIM)
