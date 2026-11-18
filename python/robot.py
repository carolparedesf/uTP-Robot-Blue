"""
robot.py - T1: comunicacion con el ESP32 por el puerto serie.

Es el UNICO archivo que sabe como se escriben los comandos del firmware.
El resto del programa dice "mover", "sonido", "cara"... y esta clase los
traduce al protocolo:

    J yaw pitch [roll [ms]]   HOME [ms]   STOP   S id   S 0   E cara [ms]   EYE x   Q
"""

import logging
import time

import serial

import config

log = logging.getLogger("robot")


class Robot:
    def __init__(self, puerto=config.PUERTO_ESP32, baudios=config.BAUDIOS):
        log.info(f"SISTEMA | conectando con el ESP32 en {puerto}")
        # serial_for_url acepta "COM3" y tambien "loop://" (sirve para probar sin placa)
        self.puerto = serial.serial_for_url(puerto, baudrate=baudios, timeout=0, write_timeout=1)

        # La placa puede reiniciarse al abrir el puerto
        time.sleep(2)
        self.puerto.reset_input_buffer()
        self._pendiente = b""

        # Lo ultimo que se le mando al robot. Lo comparten todos los comportamientos:
        # asi cada uno arranca desde donde quedo el anterior (recuperacion suave, T6-f)
        self.yaw = config.YAW_HOME
        self.pitch = config.PITCH_HOME
        self.roll = config.ROLL_HOME
        self.cara_fija = "NORMAL"           # ultima cara fija (sin duracion)
        self._ultimo_mover = float("-inf")
        log.info("SISTEMA | ESP32 conectado")

    # ------------------------------------------------------------ envio
    def enviar(self, linea):
        """Envia una linea. Devuelve False si se corto la comunicacion."""
        try:
            self.puerto.write((linea + "\n").encode("ascii"))
        except (serial.SerialException, OSError) as e:
            log.error(f"ESP32 | error de comunicacion: {e}")
            return False
        if config.MOSTRAR_ENVIOS:
            print(f"Enviado al ESP32: {linea}")
        if config.LOG_COMANDOS:
            log.info(f"CMD | {linea}")
        return True

    def listo_para_mover(self):
        """True si ya paso INTERVALO_ENVIO desde el ultimo comando de cuello."""
        return time.monotonic() - self._ultimo_mover >= config.INTERVALO_ENVIO

    def mover(self, yaw, pitch, roll=config.ROLL_HOME, ms=None):
        if ms:
            ok = self.enviar(f"J {yaw:.1f} {pitch:.1f} {roll:.1f} {int(ms)}")
        else:
            ok = self.enviar(f"J {yaw:.1f} {pitch:.1f} {roll:.1f}")
        if ok:
            self.yaw, self.pitch, self.roll = yaw, pitch, roll
            self._ultimo_mover = time.monotonic()
        return ok

    def home(self, ms=None):
        ok = self.enviar(f"HOME {int(ms)}" if ms else "HOME")
        if ok:
            self.yaw, self.pitch, self.roll = config.YAW_HOME, config.PITCH_HOME, config.ROLL_HOME
            self._ultimo_mover = time.monotonic()
        return ok

    def stop(self):
        ok = self.enviar("STOP")
        if ok:
            self.cara_fija = "NORMAL"        # el firmware pone los ojos en NORMAL
        return ok

    def sonido(self, id_sonido):
        return self.enviar(f"S {id_sonido}")

    def silencio(self):
        """Corta el sonido que este sonando (S 0). Lo usa quien pierde el buzzer."""
        return self.enviar("S 0")

    def cara(self, nombre, ms=0):
        """Con ms: cara temporal (despues vuelve sola a la fija). Sin ms: cara fija."""
        ok = self.enviar(f"E {nombre} {int(ms)}" if ms else f"E {nombre}")
        if ok and not ms:
            self.cara_fija = nombre
        return ok

    def mirada(self, x):
        """Pupilas: -1 izquierda .. 0 centro .. +1 derecha."""
        return self.enviar(f"EYE {x:.2f}")

    # ------------------------------------------------------------ respuestas
    def leer_respuestas(self):
        """Lee lo que respondio el ESP32 SIN esperar. Devuelve las lineas completas.
        Hay que llamarla seguido: si nadie lee, las respuestas se acumulan."""
        try:
            datos = self.puerto.read(self.puerto.in_waiting or 0)
        except (serial.SerialException, OSError):
            return []
        if not datos:
            return []
        self._pendiente += datos
        *lineas, self._pendiente = self._pendiente.split(b"\n")
        respuestas = [l.decode("ascii", errors="replace").strip() for l in lineas]
        respuestas = [r for r in respuestas if r]
        for r in respuestas:
            if r.startswith("ERR"):
                log.warning(f"ESP32 | {r}")
        return respuestas

    # ------------------------------------------------------------ cierre
    def cerrar(self):
        """Intenta volver a HOME y cierra el puerto."""
        try:
            self.puerto.write(b"HOME\n")
            self.puerto.flush()
            time.sleep(0.2)
        except (serial.SerialException, OSError):
            pass
        self.puerto.close()
