"""
mundo.py - modelo del mundo: lo que el robot "sabe" en cada instante.

La percepcion dice que hay en ESTE cuadro; el rastreador (personas.py) le pone
ID a cada persona y filtra los eventos; el mundo junta todo lo que necesitan
los comportamientos:

    personas        personas confirmadas (con ID), se vean o no en este cuadro
    eventos         lo que paso en ESTE cuadro: [("SALUDO", persona), ...]
    objetivo        la persona a seguir
    hay_cara        alguna persona confirmada se ve en este cuadro
    aparecio        se confirmo una persona nueva en este cuadro
    tiempo_sin_rostro
"""

import logging

import config
from atencion import Atencion
from personas import Rastreador

log = logging.getLogger("robot")


class Mundo:
    def __init__(self):
        self.ahora = 0.0
        self.ancho = self.alto = 0
        self.rastreador = Rastreador()
        self.eventos = []
        self.hay_cara = False
        self.aparecio = False
        self.alguna_vez_hubo_persona = False
        self._inicio_sin_rostro = None
        self.atencion = Atencion()

    def actualizar(self, caras, ancho, alto, ahora, yaw_robot=config.YAW_HOME):
        self.ahora = ahora
        self.ancho, self.alto = ancho, alto
        self.eventos = self.rastreador.actualizar(caras, ancho, alto, ahora, yaw_robot)

        self.hay_cara = any(p.visible for p in self.personas)
        self.aparecio = self.hay_eventos("PERSONA")
        if self.hay_cara:
            self.alguna_vez_hubo_persona = True
            self._inicio_sin_rostro = None
        elif self._inicio_sin_rostro is None:
            self._inicio_sin_rostro = ahora
        self._elegir_objetivo()

    # ---------------------------------------------------------------- consultas
    @property
    def personas(self):
        return self.rastreador.confirmadas

    def hay_eventos(self, tipo):
        return any(t == tipo for t, _ in self.eventos)

    def eventos_de(self, tipo):
        """Personas que dispararon el evento 'tipo' en este cuadro."""
        return [p for t, p in self.eventos if t == tipo]

    @property
    def tiempo_sin_rostro(self):
        """Segundos seguidos sin ver a nadie (0 si ahora hay alguien)."""
        if self._inicio_sin_rostro is None:
            return 0.0
        return self.ahora - self._inicio_sin_rostro

    @property
    def objetivo(self):
        """Persona a seguir (puede no verse en este cuadro: perdida < 1 s)."""
        for p in self.personas:
            if p.id == self.atencion.id_objetivo:
                return p
        return None

    def _elegir_objetivo(self):
        """T4: lo decide atencion.py (quien me mira > la mas cercana > la mas centrada,
        con histeresis)."""
        self.atencion.elegir(self.personas, self.ancho, self.ahora)
