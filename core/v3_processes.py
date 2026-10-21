"""
V3: version con procesos. Cada proceso se queda con su banda de filas (mas una fila extra arriba y otra
abajo, las filas frontera) y en cada iteracion solo le manda a sus vecinos las filas del borde de su banda.

Los procesos no comparten memoria, por eso las filas frontera se mandan por tuberias (Pipe).
Como cada proceso tiene su propio GIL, aqui si se calcula en paralelo.
"""

import multiprocessing as mp
from array import array

from core import grid, particion
from core.difusion import actualizar_filas
from core.engine_base import Engine


def _intercambiar_fronteras(i, placa, m, arriba, abajo):
    """Manda mi primera fila al de arriba y mi ultima al de abajo, y recibo las de ellos.
    placa[0] y placa[m+1] son las filas frontera; mis filas son de la 1 a la m."""

    def con_arriba():
        if arriba is not None:
            arriba.recv_bytes_into(placa[0])
            arriba.send_bytes(placa[1])

    def con_abajo():
        if abajo is not None:
            abajo.send_bytes(placa[m])
            abajo.recv_bytes_into(placa[m + 1])

    # Si dos vecinos se mandan al mismo tiempo y la tuberia se llena, los dos se quedan esperando
    # (interbloqueo). Para evitarlo, en cada par el de arriba manda primero y el de abajo recibe primero.
    # Ademas los procesos pares primero hablan con el de abajo y los impares con el de arriba,
    # asi todos los pares se comunican al mismo tiempo y no uno detras de otro.
    if i % 2 == 0:
        con_abajo()
        con_arriba()
    else:
        con_arriba()
        con_abajo()


def _trabajador(i, ctrl, arriba, abajo):
    """Lo que corre cada proceso. Recibe ordenes del proceso principal por `ctrl`."""
    banda = ctrl.recv()                 # lo primero que llega es su banda
    m = len(banda) - 2
    actual = banda
    siguiente = grid.copiar(banda)      # doble bufer dentro del proceso
    ctrl.send(("listo", None))
    while True:
        orden, dato = ctrl.recv()
        if orden == "run":
            try:
                for _ in range(dato):
                    actualizar_filas(actual, siguiente, 1, m + 1)
                    actual, siguiente = siguiente, actual
                    # nadie puede seguir sin las filas nuevas de sus vecinos: esto sincroniza
                    _intercambiar_fronteras(i, actual, m, arriba, abajo)
            except Exception as exc:
                ctrl.send(("error", f"proceso {i}: {exc!r}"))
                return
            ctrl.send(("ok", None))
        elif orden == "snapshot":
            ctrl.send(("ok", actual[1:m + 1]))
        else:   # "salir"
            return


class ProcessEngine(Engine):
    name = "v3"

    def __init__(self, initial_plate, workers=1):
        n = len(initial_plate)
        self.rangos = particion.rangos_de_filas(n, workers)
        self.p = len(self.rangos)
        self._cerrado = False
        # los bordes de arriba y abajo no cambian, los guarda el principal para armar el snapshot
        self._borde_sup = array("d", initial_plate[0])
        self._borde_inf = array("d", initial_plate[n - 1])

        ctx = mp.get_context("spawn")     # igual en Windows y Linux
        # una tuberia entre cada par de bandas vecinas: tubos[i] une la banda i con la i+1
        tubos = [ctx.Pipe() for _ in range(self.p - 1)]
        self._ctrl = []
        self._procs = []
        for i in range(self.p):
            arriba = tubos[i - 1][1] if i > 0 else None
            abajo = tubos[i][0] if i < self.p - 1 else None
            mio, suyo = ctx.Pipe()
            proc = ctx.Process(target=_trabajador, args=(i, suyo, arriba, abajo), daemon=True)
            proc.start()
            suyo.close()
            self._ctrl.append(mio)
            self._procs.append(proc)
        # las bandas se mandan despues de arrancar todos, asi los procesos arrancan a la vez
        # y no uno por uno esperando a que el anterior reciba su banda
        for c, (ini, fin) in zip(self._ctrl, self.rangos):
            c.send([initial_plate[f] for f in range(ini - 1, fin + 1)])   # banda con filas frontera
        # el principal no usa las tuberias entre vecinos; se cierran para que si un proceso muere
        # su vecino reciba un error en vez de quedarse esperando
        for a, b in tubos:
            a.close()
            b.close()
        # espera a que todos los procesos esten listos (asi el arranque no cuenta en las mediciones)
        self._recibir_todos()

    def _recibir_todos(self):
        respuestas = []
        errores = []
        for i, c in enumerate(self._ctrl):
            try:
                estado, dato = c.recv()
            except (EOFError, OSError):
                estado, dato = "error", f"proceso {i} termino inesperadamente"
            if estado == "error":
                errores.append(dato)
            respuestas.append(dato)
        if errores:
            self.close()
            raise RuntimeError("; ".join(errores))
        return respuestas

    def _mandar_a_todos(self, orden, dato=None):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        for i, c in enumerate(self._ctrl):
            try:
                c.send((orden, dato))
            except OSError:
                self.close()
                raise RuntimeError(f"proceso {i} termino inesperadamente") from None

    def run(self, iterations):
        if iterations <= 0:
            return
        self._mandar_a_todos("run", iterations)
        self._recibir_todos()     # espera a que todos terminen

    def step(self):
        self.run(1)

    def snapshot(self):
        self._mandar_a_todos("snapshot")
        placa = [array("d", self._borde_sup)]
        for filas in self._recibir_todos():
            placa.extend(filas)
        placa.append(array("d", self._borde_inf))
        return placa

    def close(self):
        if self._cerrado:
            return
        self._cerrado = True
        for c in self._ctrl:
            try:
                c.send(("salir", None))
            except (BrokenPipeError, OSError):
                pass
        for proc in self._procs:
            proc.join(timeout=5)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
        for c in self._ctrl:
            c.close()
