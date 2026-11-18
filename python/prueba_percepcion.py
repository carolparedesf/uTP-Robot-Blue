"""
prueba_percepcion.py - prueba la fase 4 SIN el ESP32 (solo camara + IA).

Muestra cada persona con su ID, ME_MIRA, SALIENDO, el angulo de la cara y
los brazos; los eventos aparecen abajo a la izquierda y en el log.
Sirve para ajustar los umbrales de config.py antes de conectar el robot.

Uso:   python prueba_percepcion.py        (tecla q = salir)
"""

import logging
import time

from camara import Camara
from monitor import Monitor, configurar_log
from mundo import Mundo
from percepcion import Percepcion

log = logging.getLogger("robot")


def main():
    configurar_log()
    percepcion, camara, monitor = Percepcion(), Camara(), Monitor("Prueba de percepcion")
    mundo = Mundo()
    anterior = time.monotonic()
    fps = 0.0
    try:
        while True:
            frame = camara.leer()
            if frame is None:
                break
            ahora = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(ahora - anterior, 1e-3)
            anterior = ahora

            alto, ancho = frame.shape[:2]
            mundo.actualizar(percepcion.caras(frame), ancho, alto, ahora)
            info = {"personas": mundo.personas, "objetivo": mundo.objetivo,
                    "eventos": mundo.eventos,
                    "puntajes": mundo.atencion.puntajes,
                    "cambio": mundo.atencion.progreso_cambio(ahora),
                    "recursos": {"CUELLO": f"(sin robot)  {fps:.0f} fps"}}
            if not monitor.mostrar(frame, info):
                break
    finally:
        camara.cerrar()
        percepcion.cerrar()
        monitor.cerrar()


if __name__ == "__main__":
    main()
