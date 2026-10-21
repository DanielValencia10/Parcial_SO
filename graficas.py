"""
Graficas de rendimiento a partir de resultados/mediciones.csv (lo genera medicion.py).
Saca el promedio de cada configuracion, el speedup y la eficiencia, y guarda en resultados/:
  - resumen.csv                      tabla con promedios, speedup y eficiencia
  - rendimiento_vs_trabajadores.png  tiempo, speedup y eficiencia contra el numero de hilos/procesos
  - rendimiento_vs_tamano.png        lo mismo contra el tamano de la matriz
  - comparacion_versiones.png        las cuatro versiones juntas (V4 se compara aparte)

speedup = tiempo de V1 / tiempo de la version     eficiencia = speedup / numero de hilos o procesos
Uso: python graficas.py
"""

import argparse
import csv
import json
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")       # sin ventana, solo guarda los archivos
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter, NullLocator, ScalarFormatter

from core.registry import NOMBRES

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")

# Colores. Para tamanos o numero de trabajadores (que tienen orden) se usa un solo tono de azul,
# de claro (el menor) a oscuro (el mayor). Para las versiones un color distinto cada una.
AZULES = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
          "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
COLOR_VERSION = {1: "#52514e", 2: "#2a78d6", 3: "#eb6834", 4: "#1baf7a"}
MARCADOR = {1: "s", 2: "o", 3: "^", 4: "D"}
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRIS = "#898781"
REJILLA = "#e1e0d9"
EJE = "#c3c2b7"


def azules(k):
    """k tonos de azul repartidos de claro a oscuro."""
    if k == 1:
        return [AZULES[4]]
    return [AZULES[round(i * (len(AZULES) - 1) / (k - 1))] for i in range(k)]


# --- datos
def resumir(ruta_csv):
    """Agrupa las ejecuciones por (version, tamano, trabajadores) y saca promedio, desviacion, etc."""
    grupos = defaultdict(list)
    arranques = defaultdict(list)
    with open(ruta_csv, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            k = (int(fila["version"]), int(fila["tamano"]), int(fila["trabajadores"]))
            grupos[k].append(float(fila["segundos"]))
            arranques[k].append(float(fila["arranque_s"]))
            iteraciones = int(fila["iteraciones"])
    res = {}
    for k, ts in grupos.items():
        res[k] = {"prom": statistics.mean(ts), "desv": statistics.stdev(ts) if len(ts) > 1 else 0.0,
                  "min": min(ts), "reps": len(ts), "arranque": statistics.mean(arranques[k])}
    # speedup contra V1 del mismo tamano (si V1 no esta, contra la misma version con 1 trabajador)
    for (v, n, p), r in res.items():
        base = res.get((1, n, 1)) or res.get((v, n, 1))
        r["speedup"] = base["prom"] / r["prom"] if base else None
        r["eficiencia"] = r["speedup"] / p if r["speedup"] else None
    return res, iteraciones


def guardar_resumen(res, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["version", "nombre", "tamano", "trabajadores", "ejecuciones", "promedio_s", "desviacion_s",
                    "minimo_s", "speedup", "eficiencia", "arranque_s"])
        for (v, n, p), r in sorted(res.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])):
            w.writerow([v, NOMBRES[v], n, p, r["reps"], f"{r['prom']:.4f}", f"{r['desv']:.4f}", f"{r['min']:.4f}",
                        f"{r['speedup']:.3f}" if r["speedup"] else "", f"{r['eficiencia']:.3f}" if r["eficiencia"] else "",
                        f"{r['arranque']:.3f}"])


# --- estilo
def estilo():
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "font.size": 9.5,
        "axes.edgecolor": EJE,
        "axes.labelcolor": TINTA_2,
        "axes.titlesize": 11,
        "axes.titlecolor": TINTA,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": REJILLA,
        "grid.linewidth": 0.7,
        "xtick.color": GRIS,
        "ytick.color": GRIS,
        "xtick.labelcolor": TINTA_2,
        "ytick.labelcolor": TINTA_2,
        "legend.frameon": False,
        "lines.linewidth": 1.6,
        "lines.markersize": 6,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def eje_x(ax, valores, base, titulo):
    ax.set_xscale("log", base=base)
    ax.set_xticks(valores)
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlim(valores[0] / 1.15, valores[-1] * 1.3)    # espacio a la derecha para las etiquetas
    ax.set_xlabel(titulo)


def eje_log_y(ax):
    """Escala log en Y con marcas solo en 1, 2 y 5 (si no, se llena de numeros)."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())


def eje_tiempo(ax):
    eje_log_y(ax)
    ax.set_ylabel("Tiempo promedio (s)")


_pendientes = []    # etiquetas al final de cada linea, se ponen al final para que no se encimen


def etiqueta_final(ax, x, y, texto):
    _pendientes.append((ax, x, y, texto))


def _posiciones(grupo, sep):
    centro = sum(grupo) / len(grupo)
    return [centro + (i - (len(grupo) - 1) / 2) * sep for i in range(len(grupo))]


def _abajo(grupo, sep):
    return _posiciones(grupo, sep)[0]


def _arriba(grupo, sep):
    return _posiciones(grupo, sep)[-1]


def poner_etiquetas(fig, separacion_pt=10):
    """Pone el nombre al final de cada linea, en gris. Si dos quedan muy cerca las separa."""
    por_eje = {}
    for ax, x, y, texto in _pendientes:
        por_eje.setdefault(ax, []).append((x, y, texto))
    _pendientes.clear()
    for ax, items in por_eje.items():
        ax.get_xlim(), ax.get_ylim()                        # que matplotlib fije los limites antes
        pix = [(ax.transData.transform((x, y))[1], x, y, t) for x, y, t in items]
        pix.sort()
        separacion = separacion_pt * fig.dpi / 72              # de puntos a pixeles
        # grupos de etiquetas que se encimarian; cada grupo se reparte centrado en su posicion real
        grupos = []
        for yp, *_ in pix:
            grupos.append([yp])
            while len(grupos) > 1 and _abajo(grupos[-1], separacion) < _arriba(grupos[-2], separacion) + separacion:
                ultimo = grupos.pop()
                grupos[-1].extend(ultimo)
        destino = [y for g in grupos for y in _posiciones(g, separacion)]
        for (yp, x, y, t), yd in zip(pix, destino):
            ax.annotate(t, (x, y), xytext=(6, (yd - yp) * 72 / fig.dpi), textcoords="offset points",
                        va="center", fontsize=8, color=TINTA_2, annotation_clip=False)


def pie_de_pagina(fig, equipo, iteraciones, reps, hay_v1):
    base = "V1 (secuencial)" if hay_v1 else "la misma versión con 1 trabajador (falta V1)"
    texto = (f"Promedio de {reps} ejecuciones de {iteraciones} iteraciones. Speedup = tiempo de {base} / tiempo de "
             f"la versión; eficiencia = speedup / p. No se cuenta el arranque de hilos/procesos.")
    if equipo:
        texto += (f"\nEquipo: {equipo['procesador']} · {equipo['nucleos_fisicos']} núcleos físicos, "
                  f"{equipo['nucleos_logicos']} lógicos · Python {equipo['python']} (GIL "
                  f"{'activo' if equipo['gil_activo'] else 'desactivado'}) · {equipo['sistema']}")
    fig.text(0.5, 0.01, texto, ha="center", va="bottom", fontsize=8, color=TINTA_2)


# --- graficas
def contra_trabajadores(res, versiones, tamanos, trabajadores, iteraciones, reps, equipo, hay_v1, ruta):
    """Filas: V2 y V3. Columnas: tiempo, speedup y eficiencia. Una linea por tamano."""
    fig, ejes = plt.subplots(len(versiones), 3, figsize=(15, 4.3 * len(versiones) + 0.9), squeeze=False, dpi=140)
    colores = dict(zip(tamanos, azules(len(tamanos))))
    for fila, v in zip(ejes, versiones):
        a_t, a_s, a_e = fila
        palabra = "procesos" if v == 3 else "hilos"
        a_s.plot(trabajadores, trabajadores, ":", color=GRIS, linewidth=1.2, label="ideal (speedup = p)")
        a_e.axhline(1.0, linestyle=":", color=GRIS, linewidth=1.2, label="ideal (eficiencia = 1)")
        for n in tamanos:
            ps = [p for p in trabajadores if (v, n, p) in res]
            if not ps:
                continue
            datos = [res[(v, n, p)] for p in ps]
            estilo_linea = dict(color=colores[n], marker=MARCADOR[v], label=f"{n}×{n}")
            a_t.plot(ps, [d["prom"] for d in datos], **estilo_linea)
            a_s.plot(ps, [d["speedup"] for d in datos], **estilo_linea)
            a_e.plot(ps, [d["eficiencia"] for d in datos], **estilo_linea)
            etiqueta_final(a_s, ps[-1], datos[-1]["speedup"], f"{n}×{n}")
        for ax in fila:
            eje_x(ax, trabajadores, 2, f"Número de {palabra}")
        eje_tiempo(a_t)
        a_s.set_ylabel("Speedup")
        a_s.set_ylim(bottom=0)
        a_e.set_ylabel("Eficiencia")
        a_e.set_ylim(0, max(1.15, max((r["eficiencia"] or 0) for k, r in res.items() if k[0] == v) * 1.1))
        a_t.set_title(f"V{v} {NOMBRES[v]}: tiempo")
        a_s.set_title(f"V{v} {NOMBRES[v]}: speedup")
        a_e.set_title(f"V{v} {NOMBRES[v]}: eficiencia")
        a_t.legend(title="Matriz", fontsize=8, title_fontsize=8, loc="best")
        a_s.legend(handles=a_s.get_lines()[:1], fontsize=8, loc="upper left")
    fig.suptitle("Rendimiento contra el número de hilos o procesos", fontsize=13, color=TINTA)
    pie_de_pagina(fig, equipo, iteraciones, reps, hay_v1)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    poner_etiquetas(fig)
    fig.savefig(ruta, dpi=fig.dpi)
    plt.close(fig)


def contra_tamano(res, versiones, tamanos, trabajadores, iteraciones, reps, equipo, hay_v1, ruta):
    """Filas: V2 y V3. Columnas: tiempo, speedup y eficiencia. Una linea por numero de trabajadores."""
    fig, ejes = plt.subplots(len(versiones), 3, figsize=(15, 4.3 * len(versiones) + 0.9), squeeze=False, dpi=140)
    colores = dict(zip(trabajadores, azules(len(trabajadores))))
    for fila, v in zip(ejes, versiones):
        a_t, a_s, a_e = fila
        palabra = "procesos" if v == 3 else "hilos"
        if hay_v1:
            ns = [n for n in tamanos if (1, n, 1) in res]
            a_t.plot(ns, [res[(1, n, 1)]["prom"] for n in ns], color=COLOR_VERSION[1], marker=MARCADOR[1],
                     linestyle="--", label="V1 Secuencial")
        a_s.axhline(1.0, linestyle=":", color=GRIS, linewidth=1.2, label="igual que V1")
        a_e.axhline(1.0, linestyle=":", color=GRIS, linewidth=1.2, label="ideal")
        for p in trabajadores:
            ns = [n for n in tamanos if (v, n, p) in res]
            if not ns:
                continue
            datos = [res[(v, n, p)] for n in ns]
            estilo_linea = dict(color=colores[p], marker=MARCADOR[v], label=f"{p} {palabra if p > 1 else palabra[:-1]}")
            a_t.plot(ns, [d["prom"] for d in datos], **estilo_linea)
            a_s.plot(ns, [d["speedup"] for d in datos], **estilo_linea)
            a_e.plot(ns, [d["eficiencia"] for d in datos], **estilo_linea)
            etiqueta_final(a_s, ns[-1], datos[-1]["speedup"], f"p={p}")
        for ax in fila:
            eje_x(ax, tamanos, 10, "Tamaño de la matriz (n de n×n)")
        eje_tiempo(a_t)
        a_s.set_ylabel("Speedup")
        a_s.set_ylim(bottom=0)
        a_e.set_ylabel("Eficiencia")
        a_e.set_ylim(0, max(1.15, max((r["eficiencia"] or 0) for k, r in res.items() if k[0] == v) * 1.1))
        a_t.set_title(f"V{v} {NOMBRES[v]}: tiempo")
        a_s.set_title(f"V{v} {NOMBRES[v]}: speedup")
        a_e.set_title(f"V{v} {NOMBRES[v]}: eficiencia")
        a_t.legend(fontsize=8, loc="best")
    fig.suptitle("Rendimiento contra el tamaño de la matriz", fontsize=13, color=TINTA)
    pie_de_pagina(fig, equipo, iteraciones, reps, hay_v1)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    poner_etiquetas(fig)
    fig.savefig(ruta, dpi=fig.dpi)
    plt.close(fig)


def comparacion(res, tamanos, trabajadores, iteraciones, reps, equipo, hay_v1, ruta):
    """Las cuatro versiones juntas: V2 y V3 con el maximo de trabajadores, V1 y V4 con uno."""
    p_max = max(trabajadores)
    series = [(1, 1), (2, p_max), (3, p_max), (4, 1)]
    paneles = 2 if hay_v1 else 1
    fig, ejes = plt.subplots(1, paneles, figsize=(7.2 * paneles, 5.8), squeeze=False, dpi=140)
    a_t = ejes[0][0]
    for v, p in series:
        ns = [n for n in tamanos if (v, n, p) in res]
        if not ns:
            continue
        nombre = f"V{v} {NOMBRES[v]}" + (f" ({p})" if v in (2, 3) else "")
        a_t.plot(ns, [res[(v, n, p)]["prom"] for n in ns], color=COLOR_VERSION[v], marker=MARCADOR[v],
                 linestyle="--" if v == 1 else "-", label=nombre)
        etiqueta_final(a_t, ns[-1], res[(v, ns[-1], p)]["prom"], f"V{v}")
    eje_x(a_t, tamanos, 10, "Tamaño de la matriz (n de n×n)")
    eje_tiempo(a_t)
    a_t.set_title("Tiempo de cada versión")
    a_t.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=4)
    if hay_v1:
        a_s = ejes[0][1]
        a_s.axhline(1.0, linestyle=":", color=GRIS, linewidth=1.2)
        for v, p in series[1:]:
            ns = [n for n in tamanos if (v, n, p) in res and (1, n, 1) in res]
            if not ns:
                continue
            nombre = f"V{v} {NOMBRES[v]}" + (f" ({p})" if v in (2, 3) else "")
            a_s.plot(ns, [res[(v, n, p)]["speedup"] for n in ns], color=COLOR_VERSION[v], marker=MARCADOR[v],
                     label=nombre)
            etiqueta_final(a_s, ns[-1], res[(v, ns[-1], p)]["speedup"], f"V{v} {res[(v, ns[-1], p)]['speedup']:.1f}×")
        eje_x(a_s, tamanos, 10, "Tamaño de la matriz (n de n×n)")
        eje_log_y(a_s)
        a_s.set_ylabel("Speedup contra V1 (escala log)")
        a_s.set_title("Speedup contra V1")
        a_s.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    fig.suptitle(f"Comparación de versiones (V2 y V3 con {p_max} hilos/procesos; V4 es la variante con NumPy)",
                 fontsize=12, color=TINTA)
    pie_de_pagina(fig, equipo, iteraciones, reps, hay_v1)
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    poner_etiquetas(fig)
    fig.savefig(ruta, dpi=fig.dpi)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Graficas de rendimiento a partir de mediciones.csv")
    ap.add_argument("--carpeta", default=CARPETA, help="carpeta con mediciones.csv (ahi se guardan las graficas)")
    a = ap.parse_args()

    ruta_csv = os.path.join(a.carpeta, "mediciones.csv")
    if not os.path.exists(ruta_csv):
        raise SystemExit(f"No existe {ruta_csv}. Primero corre: python medicion.py")
    res, iteraciones = resumir(ruta_csv)
    equipo = None
    if os.path.exists(os.path.join(a.carpeta, "equipo.json")):
        with open(os.path.join(a.carpeta, "equipo.json"), encoding="utf-8") as f:
            equipo = json.load(f)

    tamanos = sorted({n for _, n, _ in res})
    trabajadores = sorted({p for v, _, p in res if v in (2, 3)})
    versiones = [v for v in (2, 3) if any(k[0] == v for k in res)]
    reps = min(r["reps"] for r in res.values())
    hay_v1 = any(k[0] == 1 for k in res)
    if not hay_v1:
        print("AVISO: no hay mediciones de V1; el speedup se calcula contra cada version con 1 trabajador")

    guardar_resumen(res, os.path.join(a.carpeta, "resumen.csv"))
    estilo()
    if versiones:
        contra_trabajadores(res, versiones, tamanos, trabajadores, iteraciones, reps, equipo, hay_v1,
                            os.path.join(a.carpeta, "rendimiento_vs_trabajadores.png"))
        contra_tamano(res, versiones, tamanos, trabajadores, iteraciones, reps, equipo, hay_v1,
                      os.path.join(a.carpeta, "rendimiento_vs_tamano.png"))
    comparacion(res, tamanos, trabajadores or [1], iteraciones, reps, equipo, hay_v1,
                os.path.join(a.carpeta, "comparacion_versiones.png"))

    # tabla en la terminal
    print(f"\n{'version':<16}{'matriz':>10}{'p':>4}{'promedio (s)':>14}{'speedup':>10}{'eficiencia':>12}")
    for (v, n, p), r in sorted(res.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])):
        s = f"{r['speedup']:.2f}" if r["speedup"] else "-"
        e = f"{r['eficiencia']:.2f}" if r["eficiencia"] else "-"
        print(f"{'V' + str(v) + ' ' + NOMBRES[v]:<16}{f'{n}x{n}':>10}{p:>4}{r['prom']:>14.4f}{s:>10}{e:>12}")
    print(f"\nGraficas y resumen.csv guardados en {a.carpeta}")


if __name__ == "__main__":
    main()
