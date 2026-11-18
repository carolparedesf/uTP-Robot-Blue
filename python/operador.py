"""
operador.py - comandos del operador (prioridad 0 en el arbitro).

Dos formas de mandar comandos mientras el robot funciona:

  1) TECLAS en la ventana del video:
        n = modo NEUTRO      t = modo TIMIDO      a = modo ATREVIDO
        m = modo MALEDUCADO  s = STOP             g = GO (seguir)      q = salir
  2) ESCRIBIENDO en la terminal y Enter:
        MODE TIMIDO     MODE NEUTRO     STOP     GO

El operador solo guarda el estado (modo actual, detenido o no). Los que
actuan son los comportamientos Detenido y ConfirmarModo (comportamientos.py).
"""

import logging
import queue
import threading

import config

log = logging.getLogger("robot")

MODOS = ("NEUTRO", "TIMIDO", "ATREVIDO", "MALEDUCADO")
METODOS_CAMISETA = ("HSV", "YOLO")
TECLAS = {
    ord("n"): "MODE NEUTRO", ord("t"): "MODE TIMIDO",
    ord("a"): "MODE ATREVIDO", ord("m"): "MODE MALEDUCADO",
    ord("s"): "STOP", ord("g"): "GO", ord("c"): "CAMISETAS",
}


class Operador:
    def __init__(self, leer_consola=True):
        self.modo = "NEUTRO"
        self.detenido = False
        self.confirmar = None            # modo nuevo cuyo sonido falta tocar
        self.metodo_camisetas = config.CAMISETA_METODO   # HSV o YOLO
        self._cola = queue.Queue()
        if leer_consola:
            threading.Thread(target=self._leer_consola, daemon=True).start()

    def _leer_consola(self):
        """Hilo aparte: input() se queda esperando sin trabar el bucle principal."""
        while True:
            try:
                linea = input()
            except (EOFError, OSError):
                return
            self._cola.put(linea)

    def tecla(self, codigo):
        """Recibe la tecla apretada en la ventana del video (o -1 si ninguna)."""
        comando = TECLAS.get(codigo)
        if comando:
            self._cola.put(comando)

    def procesar(self):
        """Aplica los comandos pendientes. Se llama una vez por cuadro."""
        while not self._cola.empty():
            self._aplicar(self._cola.get().strip().upper())

    def _aplicar(self, comando):
        partes = comando.split()
        if not partes:
            return
        if partes[0] == "MODE" and len(partes) == 2:
            modo = partes[1].replace("Í", "I")
            if modo not in MODOS:
                log.warning(f"OPERADOR | modo desconocido: {partes[1]} (validos: {', '.join(MODOS)})")
            elif modo != self.modo:
                log.info(f"MODO | {self.modo} -> {modo}")
                self.modo = modo
                self.confirmar = modo
        elif partes[0] in ("CAMISETAS", "CAMISETA"):
            if len(partes) == 1:
                nuevo = "YOLO" if self.metodo_camisetas == "HSV" else "HSV"
            elif len(partes) == 2 and partes[1] in METODOS_CAMISETA:
                nuevo = partes[1]
            else:
                log.warning(f"OPERADOR | metodo de camisetas desconocido: {comando} "
                            f"(validos: CAMISETAS, CAMISETAS {' | '.join(METODOS_CAMISETA)})")
                return
            if nuevo != self.metodo_camisetas:
                log.info(f"OPERADOR | camisetas {self.metodo_camisetas} -> {nuevo}")
                self.metodo_camisetas = nuevo
        elif partes[0] == "STOP":
            if not self.detenido:
                log.info("OPERADOR | STOP")
            self.detenido = True
        elif partes[0] in ("GO", "SEGUIR"):
            if self.detenido:
                log.info("OPERADOR | GO (el robot vuelve a funcionar)")
            self.detenido = False
        else:
            log.warning(f"OPERADOR | comando desconocido: {comando} "
                        "(validos: MODE <modo>, STOP, GO)")
