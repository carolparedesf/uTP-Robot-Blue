"""
arbitro.py - T6: quien usa cada recurso.

Recursos: CUELLO y BUZZER (los ojos acompanan al recurso: la cara va con el
sonido y la mirada de las pupilas con el cuello).

En cada vuelta del bucle:
  1) Cada comportamiento dice si QUIERE actuar (quiere()).
  2) Los que estan haciendo una accion protegida y siguen queriendo,
     conservan sus recursos, salvo que los pida alguien con prioridad
     <= interrumpible_por (por ejemplo, la polca solo la cortan 0 y 1).
  3) El resto se reparte por prioridad (numero mas bajo = mas importante).
     Todo o nada: si a un comportamiento le falta un recurso, no recibe ninguno.
  4) Se avisa a los que perdieron recursos (al_perder), a los que los
     ganaron (al_iniciar), y actuan los ganadores (ejecutar), en orden de prioridad.
     Quien pierde el buzzer con un sonido a medias lo corta (S 0) en al_perder.

Tabla de prioridades (T6-b):

  Prio  Comportamiento         Recursos          Lo interrumpe
  ----  ---------------------  ----------------  ------------------------
   0    Detenido (STOP)        cuello + buzzer   nadie (hasta GO)
   0    Confirmar modo         buzzer            nadie (0,1-0,3 s)
   1    Saludo (asentir+R2D2)  cuello + buzzer   solo el operador (1,2 s)
   2    Hincha Olimpia (polca) buzzer            solo prioridad 0 y 1
   2    Hincha Cerro (abucheo) buzzer            solo prioridad 0 y 1
   3    Bienvenida             buzzer            solo el operador (0,9 s)
   3    Desaprobacion          cuello + buzzer   cualquiera mas prioritario
   3    Timido                 cuello            cualquiera mas prioritario
   3    Atrevido               cuello            cualquiera mas prioritario
   3    Maleducado (piropo)    buzzer            cualquiera mas prioritario
   4    Seguimiento            cuello            cualquiera mas prioritario
   5    Observador             cuello            cualquiera mas prioritario
   5    Aburrimiento           buzzer            cualquiera mas prioritario

Con prioridades iguales, ninguno le saca el recurso al que ya lo tiene.
"""

import logging

log = logging.getLogger("robot")

CUELLO = "CUELLO"
BUZZER = "BUZZER"
RECURSOS = (CUELLO, BUZZER)


class Arbitro:
    def __init__(self, comportamientos):
        # Ordenados por prioridad: asi el reparto y la ejecucion respetan la tabla
        self.comportamientos = sorted(comportamientos, key=lambda c: c.prioridad)
        self.duenos = {r: None for r in RECURSOS}

    def _retiene(self, c, quiere):
        """True si c conserva sus recursos este cuadro sin competir."""
        if not quiere[c] or not all(self.duenos[r] is c for r in c.recursos):
            return False
        limite = c.interrumpible_por
        if limite is None:
            # Interrumpible normal: solo lo protege el empate de prioridad
            limite = c.prioridad - 1
        for d in self.comportamientos:
            if (d is not c and quiere[d] and d.prioridad <= limite
                    and set(d.recursos) & set(c.recursos)):
                return False
        return True

    def paso(self, mundo, ahora):
        """Reparte los recursos y hace actuar a los ganadores.
        Devuelve False si se corto la comunicacion con el ESP32."""
        quiere = {c: c.quiere(mundo, ahora) for c in self.comportamientos}
        nuevos = {r: None for r in RECURSOS}

        # 2) Los duenos actuales que nadie con derecho viene a desplazar, siguen
        for c in self.comportamientos:
            if self._retiene(c, quiere) and all(nuevos[r] is None for r in c.recursos):
                for r in c.recursos:
                    nuevos[r] = c

        # 3) Reparto por prioridad, todo o nada
        for c in self.comportamientos:
            ya_tiene = c in nuevos.values()
            if quiere[c] and not ya_tiene and all(nuevos[r] is None for r in c.recursos):
                for r in c.recursos:
                    nuevos[r] = c

        antes = {c for c in self.duenos.values() if c is not None}
        despues = {c for c in nuevos.values() if c is not None}

        # Registrar cada cambio de dueno (T7)
        for r in RECURSOS:
            if nuevos[r] is not self.duenos[r]:
                log.info(f"RECURSO | {r}: {_nombre(self.duenos[r])} -> {_nombre(nuevos[r])}")

        # 4) Avisar y actuar
        ok = True
        for c in self.comportamientos:
            if c in antes and c not in despues:
                ok = c.al_perder(mundo, ahora) and ok
        self.duenos = nuevos
        for c in self.comportamientos:
            if c in despues and c not in antes:
                ok = c.al_iniciar(mundo, ahora) and ok
        for c in self.comportamientos:
            if c in despues:
                ok = c.ejecutar(mundo, ahora) and ok
        return ok

    def resumen(self):
        """Quien controla cada recurso, para el overlay (T7)."""
        return {r: _nombre(c) for r, c in self.duenos.items()}


def _nombre(c):
    return c.nombre if c is not None else "libre"
