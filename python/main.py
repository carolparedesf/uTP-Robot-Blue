"""
main.py - cabeza robotica social (uTP Robotica Social, Robotica II).

Solo coordina las partes. Cada parte vive en su archivo:

    camara.py          imagen
    percepcion.py      T2  que ve en este cuadro (caras, orientacion, cuerpos)
    personas.py        T2  personas con ID y eventos filtrados (ME_MIRA, SALUDO, SALIENDO)
    mundo.py               que sabe (personas, eventos, objetivo, tiempo sin nadie)
    atencion.py        T4  a quien mirar si hay varias personas (con histeresis)
    comportamientos.py T5  que quiere hacer cada comportamiento
    arbitro.py         T6  quien usa el cuello y el buzzer
    mirada.py          T3  de la cara a los grados
    robot.py           T1  comandos al ESP32
    camisetas.py       T2  Olimpia / Cerro por color y patron
    operador.py            comandos del operador: MODE, STOP, GO (teclado o terminal)
    monitor.py         T7  dibujo en pantalla y log con hora (carpeta logs/)

Uso:   python main.py

Teclas en la ventana del video:
    n / t / a / m = modo NEUTRO / TIMIDO / ATREVIDO / MALEDUCADO
    c = cambiar el metodo de camisetas (HSV <-> YOLO)
    s = STOP    g = GO (seguir)    q = salir
O escribir en la terminal: MODE TIMIDO, STOP, GO ...
"""

import logging
import time

import config
from arbitro import Arbitro
from camara import Camara
from comportamientos import crear_comportamientos
from mirada import ControlMirada
from monitor import Monitor, configurar_log
from mundo import Mundo
from operador import Operador
from percepcion import Percepcion
from robot import Robot

log = logging.getLogger("robot")


def armar_info(mundo, arbitro, robot, mirada, operador):
    """Datos para el overlay (T7)."""
    info = {
        "personas": mundo.personas,
        "objetivo": mundo.objetivo,
        "eventos": mundo.eventos,
        "puntajes": mundo.atencion.puntajes,
        "cambio": mundo.atencion.progreso_cambio(mundo.ahora),
        "recursos": arbitro.resumen(),
        "yaw": robot.yaw, "pitch": robot.pitch, "roll": robot.roll,
        "cara_fija": robot.cara_fija,
        "modo": operador.modo,
        "detenido": operador.detenido,
    }
    objetivo = mundo.objetivo
    if objetivo is not None and objetivo.visible:
        error_x, error_y, angulo_x, angulo_y = mirada.medir(objetivo, mundo.ancho, mundo.alto)
        info.update(cara=objetivo.cara, error_x=error_x, error_y=error_y,
                    angulo_x=angulo_x, angulo_y=angulo_y)
    return info


def main():
    ruta_log = configurar_log()
    log.info(f"SISTEMA | inicio. Log en {ruta_log}")
    robot = Robot()
    percepcion = camara = monitor = None
    try:
        percepcion = Percepcion()
        camara = Camara()
        log.info("SISTEMA | camara conectada")

        mirada = ControlMirada()
        mundo = Mundo()
        operador = Operador()
        arbitro = Arbitro(crear_comportamientos(robot, mirada, operador))
        monitor = Monitor()

        fallos = 0                # fotogramas fallidos seguidos
        while True:
            frame = camara.leer()
            if frame is None:
                fallos += 1
                if fallos == 1:
                    log.warning("SISTEMA | la camara no entrego un fotograma, reintentando...")
                if fallos >= config.FALLOS_CAMARA_MAX:
                    log.error("SISTEMA | la camara dejo de responder")
                    break
                time.sleep(0.05)
                continue
            if fallos:
                log.info(f"SISTEMA | camara recuperada despues de {fallos} fallos")
                fallos = 0

            operador.procesar()                              # comandos del operador
            if percepcion.camisetas is not None:                 # metodo de camisetas (HSV/YOLO)
                percepcion.camisetas.fijar_metodo(operador.metodo_camisetas)
            ahora = time.monotonic()
            alto, ancho = frame.shape[:2]

            caras = percepcion.caras(frame)                  # que ve
            mundo.actualizar(caras, ancho, alto, ahora, robot.yaw)   # que sabe
            ok = arbitro.paso(mundo, ahora)                  # quien actua y que hace
            robot.leer_respuestas()                          # que respondio el ESP32
            if not ok:
                break

            info = armar_info(mundo, arbitro, robot, mirada, operador)
            if percepcion.camisetas is not None:
                info["camisetas"] = percepcion.camisetas.metodo_efectivo
            if not monitor.mostrar(frame, info):             # q = salir
                break
            operador.tecla(monitor.ultima_tecla)
    finally:
        robot.cerrar()            # vuelve a HOME
        if camara:
            camara.cerrar()
        if percepcion:
            percepcion.cerrar()
        if monitor:
            monitor.cerrar()
        log.info("SISTEMA | programa finalizado")


if __name__ == "__main__":
    main()
