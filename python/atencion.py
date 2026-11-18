"""
atencion.py - T4: a quien mira el robot cuando hay varias personas.

Criterio (documentado para el informe):

  1) Cada persona visible recibe un PUNTAJE:

        puntaje = 2,0 x (me mira: 1 o 0)
                + 1,0 x (tamano de su cara / la cara mas grande)   -> la mas cercana
                + 0,5 x (1 - distancia al centro / medio ancho)    -> la mas centrada

     Como "me mira" vale 2 y lo demas suma como mucho 1,5, quien mira al robot
     SIEMPRE le gana a quien no lo mira (T4: "elegir a la que esta mirando").
     Si nadie mira (o miran todos), gana la mas cercana y, a igualdad, la mas centrada.

  2) HISTERESIS: el objetivo actual NO cambia porque otro sea apenas mejor.
     Un retador tiene que superar al actual por al menos MARGEN_CAMBIO
     durante TIEMPO_CAMBIO segundos seguidos. Si deja de ser mejor un
     instante, la cuenta vuelve a cero.

  3) Si el objetivo se va (se borra su ID tras 1 s sin verlo), se elige al
     mejor de inmediato. Si solo no se ve por un momento, se lo espera.
"""

import logging

import config

log = logging.getLogger("robot")


def puntaje(p, personas_visibles, ancho):
    area_max = max(q.area for q in personas_visibles) or 1
    cerca = p.area / area_max
    centro = 1.0 - min(1.0, abs(p.cx - ancho / 2) / (ancho / 2))
    return (config.PESO_MIRA * (1.0 if p.me_mira else 0.0)
            + config.PESO_CERCA * cerca
            + config.PESO_CENTRO * centro)


def motivo(p):
    return "me mira" if p.me_mira else "la mas cercana/centrada"


class Atencion:
    def __init__(self):
        self.id_objetivo = None
        self.retador = None            # id de quien quiere quitarle el lugar
        self.retador_desde = None
        self.puntajes = {}             # id -> puntaje (para el overlay)

    def progreso_cambio(self, ahora):
        """(id del retador, fraccion 0..1 del tiempo de histeresis) o None."""
        if self.retador is None:
            return None
        return self.retador, min(1.0, (ahora - self.retador_desde) / config.TIEMPO_CAMBIO)

    def elegir(self, personas, ancho, ahora):
        """Devuelve el id del objetivo (o None)."""
        visibles = [p for p in personas if p.visible]
        self.puntajes = {p.id: puntaje(p, visibles, ancho) for p in visibles}
        actual = next((p for p in personas if p.id == self.id_objetivo), None)

        # 3) No hay objetivo (o se fue): el mejor, ya
        if actual is None:
            self._sin_retador()
            mejor = max(visibles, key=lambda p: self.puntajes[p.id], default=None)
            self._cambiar(mejor, f"{motivo(mejor)}" if mejor else "")
            return self.id_objetivo

        # El objetivo no se ve un momento: se lo espera (T3-c)
        if not actual.visible:
            self._sin_retador()
            return self.id_objetivo

        # 2) Histeresis
        otros = [p for p in visibles if p is not actual]
        mejor = max(otros, key=lambda p: self.puntajes[p.id], default=None)
        if mejor is None or self.puntajes[mejor.id] < self.puntajes[actual.id] + config.MARGEN_CAMBIO:
            self._sin_retador()
            return self.id_objetivo

        if self.retador != mejor.id:
            self.retador, self.retador_desde = mejor.id, ahora     # empieza la cuenta
        elif ahora - self.retador_desde >= config.TIEMPO_CAMBIO:
            self._sin_retador()
            self._cambiar(mejor, f"{motivo(mejor)}, mejor que {actual} durante "
                                 f"{config.TIEMPO_CAMBIO:.1f} s")
        return self.id_objetivo

    def _sin_retador(self):
        self.retador = self.retador_desde = None

    def _cambiar(self, persona, razon):
        nuevo = persona.id if persona is not None else None
        if nuevo == self.id_objetivo:
            return
        antes = f"P{self.id_objetivo}" if self.id_objetivo is not None else "ninguno"
        despues = f"P{nuevo}" if nuevo is not None else "ninguno"
        log.info(f"OBJETIVO | {antes} -> {despues}" + (f" ({razon})" if razon else ""))
        self.id_objetivo = nuevo
