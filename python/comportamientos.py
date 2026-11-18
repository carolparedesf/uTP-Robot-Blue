"""
comportamientos.py - T5: que quiere hacer el robot.

Cada comportamiento es una clase con:
    nombre, prioridad, recursos, interrumpible_por   (ver tabla en arbitro.py)
    quiere(mundo, ahora)      -> True si quiere actuar en este cuadro
    al_iniciar(mundo, ahora)  -> el arbitro le acaba de dar sus recursos
    ejecutar(mundo, ahora)    -> actua (solo si tiene sus recursos)
    al_perder(mundo, ahora)   -> el arbitro le saco los recursos

Ningun comportamiento decide si PUEDE actuar: solo dice si QUIERE.
El arbitro es el que decide (T6).

Las funciones devuelven False solo si se corto la comunicacion con el ESP32.
"""

import logging
import math

import config
from arbitro import BUZZER, CUELLO
from mirada import limitar

log = logging.getLogger("robot")


def expresar(robot, sonido, cara):
    """Sonido y cara JUNTOS; la cara dura lo mismo que el sonido.
    Devuelve (ok, duracion en segundos)."""
    id_sonido, duracion_ms = config.SONIDOS[sonido]
    ok = robot.sonido(id_sonido) and robot.cara(cara, duracion_ms)
    if ok:
        log.info(f"EXPRESION | {sonido} + {cara}")
    return ok, duracion_ms / 1000.0


class Comportamiento:
    nombre = "?"
    prioridad = 9
    recursos = ()
    # None = lo interrumpe cualquiera mas prioritario; un numero = solo lo
    # interrumpen los de prioridad <= ese numero (-1 = nadie)
    interrumpible_por = None

    def __init__(self, robot):
        self.robot = robot

    def quiere(self, mundo, ahora):
        return False

    def al_iniciar(self, mundo, ahora):
        return True

    def ejecutar(self, mundo, ahora):
        return True

    def al_perder(self, mundo, ahora):
        return True


# ============================================================
# Prioridad 1: SALUDO (cuello + buzzer) - alguien saluda con la mano: asiente + R2D2
# ============================================================
class Saludo(Comportamiento):
    nombre = "SALUDO"
    prioridad = 1
    recursos = (CUELLO, BUZZER)
    interrumpible_por = 0          # gesto corto (1,2 s): solo lo corta el operador

    def __init__(self, robot):
        super().__init__(robot)
        self.ultimo_por_persona = {}   # id -> ultima vez que se le devolvio el saludo
        self.pendiente = None          # (persona, cuando se vio el saludo)
        self.pasos = []                # [(t, pitch, ms), ...] cabeceos que faltan mandar
        self.inicio = None

    def quiere(self, mundo, ahora):
        if self.inicio is not None:
            return True
        for p in mundo.eventos_de("SALUDO"):
            if ahora - self.ultimo_por_persona.get(p.id, float("-inf")) >= config.COOLDOWN_SALUDO_MANO:
                self.pendiente = (p, ahora)
                break
        # Si los recursos estan ocupados (p. ej. una bienvenida), espera hasta 2 s
        if self.pendiente is not None and ahora - self.pendiente[1] > 2.0:
            self.pendiente = None
        return self.pendiente is not None

    def al_iniciar(self, mundo, ahora):
        persona, _ = self.pendiente
        self.pendiente = None
        self.ultimo_por_persona[persona.id] = ahora
        self.inicio = ahora

        # Cabeceos: abajo y arriba, CABECEOS_SALUDO veces, desde el pitch actual
        r = self.robot
        medio = config.DURACION_MEDIO_CABECEO_MS
        abajo = limitar(r.pitch + config.SIGNO_PITCH * config.AMPLITUD_CABECEO,
                        config.PITCH_MIN, config.PITCH_MAX)
        self.base = (r.yaw, r.pitch, config.ROLL_HOME)
        self.pasos = []
        for k in range(config.CABECEOS_SALUDO):
            self.pasos.append((2 * k * medio / 1000.0, abajo, medio))
            self.pasos.append(((2 * k + 1) * medio / 1000.0, r.pitch, medio))
        duracion_ms = 2 * config.CABECEOS_SALUDO * medio

        log.info(f"GESTO | saludo a {persona}: asiente {config.CABECEOS_SALUDO} veces")
        id_sonido, _ = config.SONIDOS["R2D2"]
        ok = r.sonido(id_sonido) and r.cara("FELIZ", duracion_ms)
        if ok:
            log.info("EXPRESION | R2D2 + FELIZ")
        return ok

    def ejecutar(self, mundo, ahora):
        t = ahora - self.inicio
        yaw, _, roll = self.base
        while self.pasos and t >= self.pasos[0][0]:
            _, pitch, ms = self.pasos.pop(0)
            if not self.robot.mover(yaw, pitch, roll, ms):
                return False
        fin = 2 * config.CABECEOS_SALUDO * config.DURACION_MEDIO_CABECEO_MS / 1000.0
        if not self.pasos and t >= fin:
            self.inicio = None         # termino: el proximo cuadro suelta los recursos
            log.info("GESTO | saludo finalizado")
        return True

    def al_perder(self, mundo, ahora):
        # Si termino solo, no hay nada que cortar. Si lo corto el operador
        # (STOP o cambio de modo) a mitad del gesto, corta tambien el sonido
        interrumpido = self.inicio is not None
        self.inicio = None
        self.pasos = []
        return self.robot.silencio() if interrumpido else True


# ============================================================
# Prioridad 3: BIENVENIDA (buzzer) - aparece alguien: saludo sonoro + ojos felices
# ============================================================
class Bienvenida(Comportamiento):
    nombre = "BIENVENIDA"
    prioridad = 3
    recursos = (BUZZER,)
    interrumpible_por = 0          # accion corta (0,9 s): solo la corta el operador

    def __init__(self, robot):
        super().__init__(robot)
        self.ultimo = -config.COOLDOWN_SALUDO
        self.pendiente = False
        self.hasta = None              # mientras suena, conserva el buzzer

    def quiere(self, mundo, ahora):
        if self.hasta is not None:
            if ahora < self.hasta:
                return True
            self.hasta = None
        # Cooldown (T6-c): no saluda de nuevo antes de COOLDOWN_SALUDO segundos
        if mundo.aparecio and ahora - self.ultimo >= config.COOLDOWN_SALUDO:
            self.ultimo = ahora
            self.pendiente = True
        return self.pendiente

    def ejecutar(self, mundo, ahora):
        if not self.pendiente:
            return True
        self.pendiente = False
        ok, duracion = expresar(self.robot, "SALUDO", "FELIZ")
        self.hasta = ahora + duracion
        return ok

    def al_perder(self, mundo, ahora):
        # Solo la corta el operador: si el sonido seguia, se corta (si no, el
        # firmware responderia BUSY al sonido del operador)
        sonando = self.hasta is not None and ahora < self.hasta
        self.hasta = None
        return self.robot.silencio() if sonando else True


# ============================================================
# Prioridad 3: DESAPROBACION (cuello + buzzer) - se fue la persona
# ============================================================
def roll_desaprobacion(t):
    """Roll del gesto de desaprobacion en el instante t (segundos desde el inicio)."""
    if t < 0.2:
        return config.ROLL_HOME
    elif t < 0.4:
        return config.ROLL_HOME + config.AMPLITUD_DESAPROBACION
    elif t < 0.6:
        return config.ROLL_HOME - config.AMPLITUD_DESAPROBACION
    return config.ROLL_HOME


class Desaprobacion(Comportamiento):
    nombre = "DESAPROBACION"
    prioridad = 3
    recursos = (CUELLO, BUZZER)

    def __init__(self, robot):
        super().__init__(robot)
        self.hecha = False             # una sola vez por cada perdida
        self.inicio = None             # gesto en curso
        self.fin_sonido = 0.0

    def quiere(self, mundo, ahora):
        if mundo.hay_cara:             # volvio alguien: se cancela y se rearma
            self.hecha = False
            self.inicio = None
            return False
        if self.inicio is not None:
            return True
        return (mundo.alguna_vez_hubo_persona and not self.hecha
                and mundo.tiempo_sin_rostro >= config.TIEMPO_PERDIDA_OBJETIVO)

    def al_iniciar(self, mundo, ahora):
        self.hecha = True
        self.inicio = ahora
        log.info("GESTO | desaprobacion: mas de 1 s sin rostro")
        ok, duracion = expresar(self.robot, "REPROBACION", "ENOJADA")
        self.fin_sonido = ahora + duracion
        return ok

    def ejecutar(self, mundo, ahora):
        t = ahora - self.inicio
        r = self.robot
        if t < config.DURACION_DESAPROBACION:
            if r.listo_para_mover():
                return r.mover(r.yaw, r.pitch, roll_desaprobacion(t))
            return True
        # Fin del gesto: roll a reposo y suelta los recursos
        self.inicio = None
        log.info("GESTO | desaprobacion finalizada")
        return r.mover(r.yaw, r.pitch, config.ROLL_HOME)

    def al_perder(self, mundo, ahora):
        self.inicio = None
        if ahora < self.fin_sonido:    # la interrumpieron: el buzzer queda libre YA
            return self.robot.silencio()
        return True


# ============================================================
# Prioridad 4: SEGUIMIENTO (cuello) - eye contact con la persona objetivo
#   Si la persona no se ve por un momento (< 1 s), mantiene la mirada (T3-c)
# ============================================================
class Seguimiento(Comportamiento):
    nombre = "SEGUIMIENTO"
    prioridad = 4
    recursos = (CUELLO,)

    def __init__(self, robot, mirada):
        super().__init__(robot)
        self.mirada = mirada
        self.id_seguido = None

    def quiere(self, mundo, ahora):
        return mundo.objetivo is not None

    def al_iniciar(self, mundo, ahora):
        self.mirada.reset()            # filtros desde cero al recuperar el rostro
        self.id_seguido = mundo.objetivo.id
        if self.robot.cara_fija == "DORMIDA":
            # Despertar. Se manda en al_iniciar para que llegue ANTES de la cara
            # feliz de la bienvenida (una cara fija cancela la temporal)
            return self.robot.cara("NORMAL")
        return True

    def ejecutar(self, mundo, ahora):
        if mundo.objetivo.id != self.id_seguido:
            # Cambio de objetivo (T4): los filtros traian el error de la persona anterior
            self.id_seguido = mundo.objetivo.id
            self.mirada.reset()
        if not mundo.objetivo.visible:
            return True                # perdida corta (< 1 s, T3-c): mantiene la mirada
        _, _, angulo_x, angulo_y = self.mirada.medir(mundo.objetivo, mundo.ancho, mundo.alto)
        self.mirada.actualizar(angulo_x, angulo_y)

        r = self.robot
        if not r.listo_para_mover():
            return True
        correccion_yaw, correccion_pitch = self.mirada.correcciones()
        yaw = limitar(r.yaw + config.SIGNO_YAW * correccion_yaw, config.YAW_MIN, config.YAW_MAX)
        pitch = limitar(r.pitch + config.SIGNO_PITCH * correccion_pitch,
                        config.PITCH_MIN, config.PITCH_MAX)

        # Pupilas hacia la persona (se adelantan al cuello)
        ojos = limitar(config.SIGNO_OJOS * angulo_x / config.ANGULO_OJOS_MAX, -1.0, 1.0)
        if not r.mirada(ojos):
            return False
        return r.mover(yaw, pitch, config.ROLL_HOME)

    def al_perder(self, mundo, ahora):
        self.mirada.reset()
        return self.robot.mirada(0)    # pupilas al centro; el cuello queda donde estaba


# ============================================================
# Prioridad 5: OBSERVADOR (cuello) - nadie a la vista: un barrido y a HOME
# ============================================================
class Observador(Comportamiento):
    nombre = "OBSERVADOR"
    prioridad = 5
    recursos = (CUELLO,)

    def __init__(self, robot):
        super().__init__(robot)
        self.direccion = 1
        self.toco_min = self.toco_max = False
        self.en_reposo = False         # termino el barrido (lo lee Aburrimiento)

    def quiere(self, mundo, ahora):
        return (not mundo.hay_cara
                and mundo.tiempo_sin_rostro >= config.TIEMPO_PERDIDA_OBJETIVO)

    def al_iniciar(self, mundo, ahora):
        self.toco_min = self.toco_max = False
        self.en_reposo = False
        log.info("OBSERVADOR | empieza el barrido")
        return True

    def ejecutar(self, mundo, ahora):
        r = self.robot
        if self.en_reposo or not r.listo_para_mover():
            return True

        if r.yaw >= config.YAW_OBSERVADOR_MAX:
            self.direccion = -1
            self.toco_max = True
        elif r.yaw <= config.YAW_OBSERVADOR_MIN:
            self.direccion = 1
            self.toco_min = True

        if self.toco_min and self.toco_max:
            # Ya miro a los dos lados: vuelve a HOME despacio y se queda quieto
            self.en_reposo = True
            log.info("OBSERVADOR | barrido terminado: HOME y reposo")
            return r.home(config.DURACION_VUELTA_HOME_MS)

        # Limites del firmware (no los del barrido): si el yaw venia de fuera
        # de 60..120, camina de a poco en vez de saltar
        yaw = limitar(r.yaw + self.direccion * config.PASO_OBSERVADOR,
                      config.YAW_MIN, config.YAW_MAX)

        # Pitch al centro de a poco
        diferencia = config.PITCH_HOME - r.pitch
        if abs(diferencia) > config.PASO_OBSERVADOR:
            pitch = r.pitch + (config.PASO_OBSERVADOR if diferencia > 0 else -config.PASO_OBSERVADOR)
        else:
            pitch = config.PITCH_HOME
        return r.mover(yaw, pitch, config.ROLL_HOME)

    def al_perder(self, mundo, ahora):
        self.en_reposo = False
        return True


# ============================================================
# Prioridad 5: ABURRIMIENTO (buzzer) - despues del barrido: bostezo y se duerme
# ============================================================
class Aburrimiento(Comportamiento):
    nombre = "ABURRIMIENTO"
    prioridad = 5
    recursos = (BUZZER,)

    def __init__(self, robot, observador):
        super().__init__(robot)
        self.observador = observador
        self.hecho = False
        self.hasta = None

    def quiere(self, mundo, ahora):
        if not self.observador.en_reposo:
            self.hecho = False
            self.hasta = None
            return False
        if self.hasta is not None and ahora >= self.hasta:
            self.hasta = None          # termino el bostezo: suelta el buzzer
        return self.hasta is not None or not self.hecho

    def ejecutar(self, mundo, ahora):
        if self.hecho:
            return True
        self.hecho = True
        id_sonido, duracion_ms = config.SONIDOS["BOSTEZO"]
        self.hasta = ahora + duracion_ms / 1000.0
        log.info("EXPRESION | BOSTEZO + DORMIDA")
        return self.robot.sonido(id_sonido) and self.robot.cara("DORMIDA")   # sin ms: queda fija

    def al_perder(self, mundo, ahora):
        sonando = self.hasta is not None and ahora < self.hasta
        self.hasta = None
        return self.robot.silencio() if sonando else True


# ============================================================
# Prioridad 0: OPERADOR - STOP y confirmacion de cambio de modo
# ============================================================
class Detenido(Comportamiento):
    nombre = "STOP (operador)"
    prioridad = 0
    recursos = (CUELLO, BUZZER)
    interrumpible_por = -1         # nadie: solo termina con GO

    def __init__(self, robot, operador):
        super().__init__(robot)
        self.operador = operador

    def quiere(self, mundo, ahora):
        return self.operador.detenido

    def al_iniciar(self, mundo, ahora):
        return self.robot.stop()       # el firmware frena el cuello, corta el sonido y resetea los ojos

    def al_perder(self, mundo, ahora):
        log.info("OPERADOR | el robot retoma lo que corresponda")
        return True


class ConfirmarModo(Comportamiento):
    nombre = "CONFIRMAR MODO"
    prioridad = 0
    recursos = (BUZZER,)
    interrumpible_por = -1         # sonido de 0,1-0,3 s

    def __init__(self, robot, operador):
        super().__init__(robot)
        self.operador = operador
        self.hasta = None

    def quiere(self, mundo, ahora):
        if self.hasta is not None:
            if ahora < self.hasta:
                return True
            self.hasta = None
        return self.operador.confirmar is not None

    def ejecutar(self, mundo, ahora):
        modo = self.operador.confirmar
        if modo is None:
            return True
        self.operador.confirmar = None
        id_sonido, duracion_ms = config.SONIDOS[f"MODO_{modo}"]
        self.hasta = ahora + duracion_ms / 1000.0
        log.info(f"EXPRESION | sonido de confirmacion del modo {modo}")
        return self.robot.sonido(id_sonido)


# ============================================================
# Prioridad 2: HINCHAS (buzzer) - camiseta del objetivo: polca o abucheo
#   Solo los interrumpen el operador (0) y el saludo (1).
#   Coexisten con el seguimiento: la polca usa el buzzer, el seguimiento el cuello.
# ============================================================
class Hincha(Comportamiento):
    prioridad = 2
    recursos = (BUZZER,)
    interrumpible_por = 1
    camiseta = sonido = cara = None
    cooldown = 0.0

    def __init__(self, robot):
        super().__init__(robot)
        self.ultimo_por_persona = {}   # id -> ultima vez (cooldown por persona, T6-c)
        self.para = None               # persona a la que le esta sonando
        self.pendiente = None
        self.hasta = None

    def quiere(self, mundo, ahora):
        p = mundo.objetivo
        if self.hasta is not None:
            # Sigue sonando mientras siga mirando a esa persona
            if ahora < self.hasta and p is self.para:
                return True
            self.hasta = None
        self.pendiente = None
        if (p is not None and p.visible and p.camiseta == self.camiseta
                and ahora - self.ultimo_por_persona.get(p.id, float("-inf")) >= self.cooldown):
            self.pendiente = p
        return self.pendiente is not None

    def ejecutar(self, mundo, ahora):
        if self.hasta is not None or self.pendiente is None:
            return True
        p, self.pendiente = self.pendiente, None
        self.ultimo_por_persona[p.id] = ahora
        self.para = p
        log.info(f"HINCHA | {p} tiene la camiseta de {self.camiseta}")
        ok, duracion = expresar(self.robot, self.sonido, self.cara)
        self.hasta = ahora + duracion
        return ok

    def al_perder(self, mundo, ahora):
        sonando = self.hasta is not None and ahora < self.hasta
        self.hasta = None
        return self.robot.silencio() if sonando else True


class HinchaOlimpia(Hincha):
    nombre = "HINCHA OLIMPIA"
    camiseta, sonido, cara = "OLIMPIA", "POLCA", "FELIZ"
    cooldown = config.COOLDOWN_POLCA


class HinchaCerro(Hincha):
    nombre = "HINCHA CERRO"
    camiseta, sonido, cara = "CERRO", "REPROBACION", "ENOJADA"
    cooldown = config.COOLDOWN_ABUCHEO


# ============================================================
# Prioridad 3: MODOS DE PERSONALIDAD
# ============================================================
class Timido(Comportamiento):
    """Si la persona lo mira: desvia la mirada (costado y abajo), la mantiene
    desviada unos segundos y vuelve a espiar de a poco."""
    nombre = "TIMIDO"
    prioridad = 3
    recursos = (CUELLO,)

    def __init__(self, robot, operador):
        super().__init__(robot)
        self.operador = operador
        self.inicio = None             # gesto en curso
        self.proximo = 0.0             # cooldown

    def _cancelar(self, ahora):
        self.inicio = None
        self.proximo = ahora + config.COOLDOWN_TIMIDO

    def quiere(self, mundo, ahora):
        p = mundo.objetivo
        if self.inicio is not None:
            if self.operador.modo != "TIMIDO" or p is None:
                self._cancelar(ahora)
                return False
            return True
        return (self.operador.modo == "TIMIDO" and p is not None and p.visible
                and p.me_mira and ahora >= self.proximo)

    def al_iniciar(self, mundo, ahora):
        r, p = self.robot, mundo.objetivo
        self.inicio = ahora
        self.origen = (r.yaw, r.pitch)
        # Hacia el lado contrario a donde esta la persona en la imagen, y hacia abajo
        hacia_persona = config.SIGNO_YAW * (1 if p.cx >= mundo.ancho / 2 else -1)
        yaw = limitar(r.yaw - hacia_persona * config.DESVIO_YAW_TIMIDO, config.YAW_MIN, config.YAW_MAX)
        pitch = limitar(r.pitch + config.SIGNO_PITCH * config.DESVIO_PITCH_TIMIDO,
                        config.PITCH_MIN, config.PITCH_MAX)
        self.desvio = (yaw, pitch)
        log.info(f"GESTO | timido: {p} lo mira, desvia la mirada")
        return r.mirada(0) and r.mover(yaw, pitch, config.ROLL_HOME, config.DURACION_DESVIO_MS)

    def ejecutar(self, mundo, ahora):
        r = self.robot
        t = ahora - self.inicio - (config.DURACION_DESVIO_MS / 1000.0 + config.TIEMPO_DESVIADO)
        if t < 0 or not r.listo_para_mover():
            return True                # desviando o manteniendo la mirada desviada
        # Vuelve a espiar de a poco (curva suave: arranca y termina despacio)
        f = min(1.0, t / config.DURACION_ESPIAR)
        f = f * f * (3 - 2 * f)
        yaw = self.desvio[0] + (self.origen[0] - self.desvio[0]) * f
        pitch = self.desvio[1] + (self.origen[1] - self.desvio[1]) * f
        if f >= 1.0:
            log.info("GESTO | timido: termino de espiar")
            self._cancelar(ahora)
        return r.mover(yaw, pitch, config.ROLL_HOME)

    def al_perder(self, mundo, ahora):
        if self.inicio is not None:
            self._cancelar(ahora)
        return True


class Atrevido(Comportamiento):
    """Si la persona lo mira: sostiene la mirada (sigue en yaw) y levanta el
    menton periodicamente (oscilacion de pitch hacia arriba)."""
    nombre = "ATREVIDO"
    prioridad = 3
    recursos = (CUELLO,)

    def __init__(self, robot, mirada, operador):
        super().__init__(robot)
        self.mirada = mirada
        self.operador = operador
        self.inicio = None
        self.proximo = 0.0

    def quiere(self, mundo, ahora):
        p = mundo.objetivo
        if self.inicio is not None:
            if (self.operador.modo != "ATREVIDO" or p is None or not p.me_mira
                    or ahora - self.inicio >= config.DURACION_ATREVIDO):
                self.inicio = None
                self.proximo = ahora + config.COOLDOWN_ATREVIDO
                return False
            return True
        return (self.operador.modo == "ATREVIDO" and p is not None and p.visible
                and p.me_mira and ahora >= self.proximo)

    def al_iniciar(self, mundo, ahora):
        self.inicio = ahora
        self.base_yaw, self.base_pitch = self.robot.yaw, self.robot.pitch
        self.mirada.reset()
        log.info(f"GESTO | atrevido: sostiene la mirada de {mundo.objetivo} y levanta el menton")
        return True

    def ejecutar(self, mundo, ahora):
        p, r = mundo.objetivo, self.robot
        ojos = 0.0
        if p.visible:
            _, _, angulo_x, angulo_y = self.mirada.medir(p, mundo.ancho, mundo.alto)
            self.mirada.actualizar(angulo_x, angulo_y)
            ojos = limitar(config.SIGNO_OJOS * angulo_x / config.ANGULO_OJOS_MAX, -1.0, 1.0)
        if not r.listo_para_mover():
            return True
        # Yaw: sigue a la persona. Pitch: queda fijo (la camara sube con el menton
        # y el seguimiento en pitch pelearia contra el gesto)
        if p.visible:
            correccion_yaw, _ = self.mirada.correcciones()
            self.base_yaw = limitar(self.base_yaw + config.SIGNO_YAW * correccion_yaw,
                                    config.YAW_MIN, config.YAW_MAX)
        t = ahora - self.inicio
        menton = config.AMPLITUD_MENTON * 0.5 * (1 - math.cos(2 * math.pi * t / config.PERIODO_MENTON))
        pitch = limitar(self.base_pitch - config.SIGNO_PITCH * menton,     # hacia ARRIBA
                        config.PITCH_MIN, config.PITCH_MAX)
        return r.mirada(ojos) and r.mover(self.base_yaw, pitch, config.ROLL_HOME)

    def al_perder(self, mundo, ahora):
        if self.inicio is not None:
            self.inicio = None
            self.proximo = ahora + config.COOLDOWN_ATREVIDO
        log.info("GESTO | atrevido finalizado")
        # Menton a su lugar (el proximo dueno del cuello sigue desde ahi)
        return self.robot.mover(self.base_yaw, self.base_pitch, config.ROLL_HOME)


class Maleducado(Comportamiento):
    """Cuando la persona seguida se va (SALIENDO): piropo, una vez por salida y
    como mucho uno cada 40 s."""
    nombre = "MALEDUCADO"
    prioridad = 3
    recursos = (BUZZER,)

    def __init__(self, robot, operador):
        super().__init__(robot)
        self.operador = operador
        self.ultimo = float("-inf")
        self.pendiente = None          # (persona, cuando salio)
        self.hasta = None

    def quiere(self, mundo, ahora):
        if self.hasta is not None:
            if ahora < self.hasta:
                return True
            self.hasta = None
        if self.operador.modo == "MALEDUCADO" and ahora - self.ultimo >= config.COOLDOWN_PIROPO:
            for p in mundo.eventos_de("SALIENDO"):
                if p is mundo.objetivo:
                    self.pendiente = (p, ahora)
        # Si el buzzer esta ocupado, espera como mucho 1 s (despues ya no tiene sentido)
        if self.pendiente is not None and ahora - self.pendiente[1] > 1.0:
            self.pendiente = None
        return self.pendiente is not None

    def ejecutar(self, mundo, ahora):
        if self.pendiente is None:
            return True
        p, _ = self.pendiente
        self.pendiente = None
        self.ultimo = ahora
        log.info(f"GESTO | maleducado: piropo a {p}, que se va")
        ok, duracion = expresar(self.robot, "PIROPO", "FELIZ")
        self.hasta = ahora + duracion
        return ok

    def al_perder(self, mundo, ahora):
        sonando = self.hasta is not None and ahora < self.hasta
        self.hasta = None
        return self.robot.silencio() if sonando else True


def crear_comportamientos(robot, mirada, operador):
    observador = Observador(robot)
    return [
        Detenido(robot, operador),
        ConfirmarModo(robot, operador),
        Saludo(robot),
        HinchaOlimpia(robot),
        HinchaCerro(robot),
        Bienvenida(robot),
        Desaprobacion(robot),
        Timido(robot, operador),
        Atrevido(robot, mirada, operador),
        Maleducado(robot, operador),
        Seguimiento(robot, mirada),
        observador,
        Aburrimiento(robot, observador),
    ]
