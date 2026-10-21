"""
Programa de medicion: corre cada version con cada tamano y numero de hilos/procesos, varias veces,
y guarda los tiempos en resultados/mediciones.csv y los datos del equipo en resultados/equipo.json.

Solo se cronometra engine.run(200). Crear el motor (arrancar hilos o procesos) se anota aparte y el
CSV se escribe entre ejecuciones, nunca dentro del tiempo medido. Aqui no hay interfaz grafica.

Uso:  python medicion.py
      python medicion.py --tamanos 100,500 --trabajadores 1,2,4 --repeticiones 3 --versiones 2,3
      python medicion.py --continuar      (sigue donde quedo, sin repetir lo que ya esta en el CSV)
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time

import config
from core import grid
from core.registry import NOMBRES, EngineUnavailable, load_engine_class

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
COLUMNAS = ["version", "nombre", "tamano", "trabajadores", "ejecucion", "iteraciones", "segundos", "arranque_s"]


# --- datos del equipo
def _nombre_procesador():
    try:
        if sys.platform == "win32":
            import winreg
            clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(clave, "ProcessorNameString")[0].strip()
        if sys.platform == "darwin":
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("model name"):
                    return linea.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "desconocido"


def _nucleos_fisicos():
    try:
        if sys.platform == "win32":
            salida = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"],
                text=True, timeout=30)
            return int(salida.strip())
        if sys.platform == "darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.physicalcpu"], text=True))
        nucleos = set()
        fisico = None
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for linea in f:
                if linea.startswith("physical id"):
                    fisico = linea.split(":")[1].strip()
                elif linea.startswith("core id"):
                    nucleos.add((fisico, linea.split(":")[1].strip()))
        return len(nucleos) or None
    except Exception:
        return None


def datos_equipo():
    gil = getattr(sys, "_is_gil_enabled", None)
    return {
        "procesador": _nombre_procesador(),
        "nucleos_fisicos": _nucleos_fisicos(),
        "nucleos_logicos": os.cpu_count(),
        "sistema": f"{platform.system()} {platform.release()} ({platform.version()})",
        "python": platform.python_version(),
        "gil_activo": gil() if gil else True,      # Python sin free-threading siempre tiene GIL
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }


# --- medir
def medir_una(clase, n, p, iteraciones):
    """Una ejecucion completa. Devuelve (segundos de run, segundos de arranque)."""
    placa = grid.nueva_placa(n)                  # placa nueva en cada ejecucion
    t0 = time.perf_counter()
    motor = clase(placa, p)
    arranque = time.perf_counter() - t0
    try:
        t0 = time.perf_counter()
        motor.run(iteraciones)                   # lo unico que se cronometra
        segundos = time.perf_counter() - t0
    finally:
        motor.close()
    return segundos, arranque


def leer_csv(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    def lista(s):
        return [int(x) for x in s.split(",") if x.strip()]

    ap = argparse.ArgumentParser(description="Mide el tiempo de cada version de la difusion de calor")
    ap.add_argument("--tamanos", type=lista, default=config.TAMANOS)
    ap.add_argument("--trabajadores", type=lista, default=config.TRABAJADORES)
    ap.add_argument("--repeticiones", type=int, default=config.REPETICIONES)
    ap.add_argument("--versiones", type=lista, default=config.GUI_VERSIONES)
    ap.add_argument("--iteraciones", type=int, default=config.ITERACIONES)
    ap.add_argument("--salida", default=CARPETA, help="carpeta de resultados")
    ap.add_argument("--continuar", action="store_true", help="no repetir lo que ya esta en el CSV")
    a = ap.parse_args()

    os.makedirs(a.salida, exist_ok=True)
    ruta_csv = os.path.join(a.salida, "mediciones.csv")

    equipo = datos_equipo()
    with open(os.path.join(a.salida, "equipo.json"), "w", encoding="utf-8") as f:
        json.dump(equipo, f, indent=2, ensure_ascii=False)
    print("Equipo:")
    for k, v in equipo.items():
        print(f"  {k}: {v}")

    # versiones que se pueden cargar (si alguna no existe todavia se salta)
    clases = {}
    for v in a.versiones:
        try:
            clases[v] = load_engine_class(v)
        except EngineUnavailable as exc:
            print(f"AVISO: se salta V{v}: {exc}")

    filas = leer_csv(ruta_csv) if a.continuar else []
    hechas = {(int(f["version"]), int(f["tamano"]), int(f["trabajadores"]), int(f["ejecucion"]))
              for f in filas if int(f["iteraciones"]) == a.iteraciones}

    # V1 y V4 corren en un solo hilo; V2 y V3 con cada numero de trabajadores
    plan = [(n, v, p, rep)
            for n in a.tamanos
            for v in clases
            for p in (a.trabajadores if v in (2, 3) else [1])
            for rep in range(1, a.repeticiones + 1)
            if (v, n, p, rep) not in hechas]
    print(f"\n{len(plan)} ejecuciones de {a.iteraciones} iteraciones. Resultados en {ruta_csv}\n")

    t_total = time.perf_counter()
    for i, (n, v, p, rep) in enumerate(plan, 1):
        print(f"[{i}/{len(plan)}] V{v} {NOMBRES[v]:<12} {n}x{n}  p={p}  ejecucion {rep} ...", end=" ", flush=True)
        segundos, arranque = medir_una(clases[v], n, p, a.iteraciones)
        print(f"{segundos:.3f} s  (arranque {arranque:.2f} s)")
        filas.append({"version": v, "nombre": NOMBRES[v], "tamano": n, "trabajadores": p, "ejecucion": rep,
                      "iteraciones": a.iteraciones, "segundos": f"{segundos:.6f}", "arranque_s": f"{arranque:.4f}"})
        # se guarda despues de cada ejecucion por si se interrumpe (fuera del tiempo medido)
        with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNAS)
            w.writeheader()
            w.writerows(filas)

    print(f"\nListo en {(time.perf_counter() - t_total) / 60:.1f} min. Para las graficas: python graficas.py")


if __name__ == "__main__":
    main()
