"""
personas.py - T2: memoria entre cuadros. Personas con ID y eventos filtrados.

La percepcion dice "en este cuadro hay estas caras". Aca se decide:
  - cual cara es la misma persona que en el cuadro anterior (tracking por ID),
  - y si cada evento es real o un falso positivo de un cuadro (filtros).

Definiciones operativas (los numeros estan en config.py):

  PERSONA    Una cara se confirma como persona si se vio en N de los ultimos
             M cuadros (3 de 5). Mantiene su ID mientras siga apareciendo;
             se borra si pasa TIEMPO_OLVIDO (1 s) sin verla.
             Asociacion: la cara nueva se une con la persona cuyo recuadro
             mas se solapa (IoU >= 0,2); si ninguna se solapa, con la mas
             cercana a menos de 3/4 de su ancho (movimiento rapido).

  ME_MIRA    La cara apunta a la camara: angulo <= 15 grados, sostenido 0,5 s
             (un cuadro malo suelto no corta la cuenta) y en >= 80 % de los
             cuadros de esa ventana. Se apaga si baja de 50 % (histeresis: no
             parpadea cuando el angulo esta justo en el borde).

  SALUDO     Muñeca por encima del hombro en >= 60 % de los cuadros (contando
             desde que la mano subio, dentro de los ultimos 2 s), y oscilacion 
             lateral de la muñeca respecto del codo de al menos 2 ciclos completos 
             (5 vaivenes: el primero puede ser medio, porque arranca desde donde 
             estaba la mano), cada vaiven >= 0,15 anchos de
             hombro. Es un evento: dispara una vez y espera 3 s (refractario).

  SALIENDO   Persona visible cerca del borde (15 % del ancho) y moviendose
             hacia afuera (>= 0,15 anchos de imagen por segundo), o del lado
             al que el cuello ya no puede girar (yaw en su limite).
             Filtro 3 de 5 cuadros.

  CAMISETA_OLIMPIA / CAMISETA_CERRO
             Reglas de color y patron sobre el torso (ver camisetas.py).
             Se confirma con 6 cuadros SEGUIDOS con la camiseta y se olvida
             con 6 cuadros seguidos sin ella (T6-d).
"""

import logging
from collections import deque

import config

log = logging.getLogger("robot")


# ============================================================
# Filtros temporales
# ============================================================
class FiltroNdeM:
    """Activo si la condicion se cumplio en al menos N de los ultimos M cuadros."""

    def __init__(self, n, m):
        self.n = n
        self.historial = deque(maxlen=m)

    def agregar(self, valor):
        self.historial.append(bool(valor))
        return self.activo

    @property
    def activo(self):
        return sum(self.historial) >= self.n

    @property
    def cuenta(self):
        return sum(self.historial)


class FiltroSostenido:
    """Activo si la condicion se SOSTIENE 'duracion' segundos, con histeresis.

    - La racha empieza en el primer cuadro que cumple; cuadros malos sueltos
      (huecos de hasta 'tolerancia' s) no la cortan.
    - Se activa cuando la racha dura 'duracion' Y en la ultima ventana de
      'duracion' s se cumplio en al menos 'fraccion_on' de los cuadros.
    - Se apaga cuando en la ventana baja de 'fraccion_off'."""

    def __init__(self, duracion, fraccion_on, fraccion_off, tolerancia=0.2):
        self.duracion = duracion
        self.fraccion_on = fraccion_on
        self.fraccion_off = fraccion_off
        self.tolerancia = tolerancia
        self.muestras = deque()          # (tiempo, valor)
        self.inicio_racha = None
        self.ultimo_bueno = None
        self.activo = False

    def agregar(self, ahora, valor):
        self.muestras.append((ahora, bool(valor)))
        while self.muestras and ahora - self.muestras[0][0] > self.duracion:
            self.muestras.popleft()
        fraccion = sum(v for _, v in self.muestras) / len(self.muestras)

        if valor:
            if self.inicio_racha is None or ahora - self.ultimo_bueno > self.tolerancia:
                self.inicio_racha = ahora
            self.ultimo_bueno = ahora
        racha = ahora - self.inicio_racha if self.inicio_racha is not None else 0.0

        if not self.activo and racha >= self.duracion - 1e-6 and fraccion >= self.fraccion_on:
            self.activo = True
        elif self.activo and fraccion < self.fraccion_off:
            self.activo = False
        return self.activo


class FiltroConsecutivo:
    """Cambia de estado solo despues de 'on' cuadros SEGUIDOS con la condicion
    (para activarse) u 'off' cuadros seguidos sin ella (para apagarse)."""

    def __init__(self, on, off):
        self.on, self.off = on, off
        self.activo = False
        self.seguidos = 0              # cuadros seguidos que contradicen el estado actual

    def agregar(self, valor):
        valor = bool(valor)
        self.seguidos = self.seguidos + 1 if valor != self.activo else 0
        if self.seguidos >= (self.off if self.activo else self.on):
            self.activo, self.seguidos = valor, 0
        return self.activo


def contar_vaivenes(valores, amplitud):
    """Cuenta los tramos de ida o de vuelta de al menos 'amplitud'.

    Ejemplo con amplitud 1:  0, 1.2, 0.1, 1.3, 0  ->  4 vaivenes = 2 ciclos.
    Un temblor menor que la amplitud no cuenta."""
    if not valores:
        return 0
    vaivenes = 0
    direccion = 0                       # +1 subiendo, -1 bajando, 0 todavia no se sabe
    minimo = maximo = extremo = valores[0]
    for v in valores[1:]:
        if direccion == 0:
            minimo, maximo = min(minimo, v), max(maximo, v)
            if v - minimo >= amplitud:
                direccion, extremo, vaivenes = 1, v, 1
            elif maximo - v >= amplitud:
                direccion, extremo, vaivenes = -1, v, 1
        elif direccion > 0:
            if v > extremo:
                extremo = v
            elif extremo - v >= amplitud:
                direccion, extremo, vaivenes = -1, v, vaivenes + 1
        else:
            if v < extremo:
                extremo = v
            elif v - extremo >= amplitud:
                direccion, extremo, vaivenes = 1, v, vaivenes + 1
    return vaivenes


# ============================================================
# SALUDO
# ============================================================
class DetectorSaludo:
    def __init__(self):
        # por brazo: deque de (tiempo, mano_arriba, x relativa al codo en anchos de hombro)
        self.brazos = {"izq": deque(), "der": deque()}
        self.ultimo = float("-inf")

    def agregar(self, ahora, cuerpo, ancho_cara):
        hombro_i, hombro_d = cuerpo.punto("hombro_izq"), cuerpo.punto("hombro_der")
        if hombro_i and hombro_d:
            ancho_hombros = max(abs(hombro_i[0] - hombro_d[0]), 1.0)
        else:
            ancho_hombros = 2.0 * max(ancho_cara, 1)      # aproximacion si falta un hombro

        for lado, muestras in self.brazos.items():
            hombro = cuerpo.punto(f"hombro_{lado}")
            codo = cuerpo.punto(f"codo_{lado}")
            muneca = cuerpo.punto(f"muneca_{lado}")
            if hombro is None or muneca is None:
                muestras.append((ahora, False, None))
            else:
                arriba = muneca[1] < hombro[1]            # y crece hacia abajo en la imagen
                pivote = codo if codo is not None else hombro
                muestras.append((ahora, arriba, (muneca[0] - pivote[0]) / ancho_hombros))
            while muestras and ahora - muestras[0][0] > config.VENTANA_SALUDO:
                muestras.popleft()

    def evaluar(self, ahora):
        """True SOLO en el cuadro en que se detecta el saludo."""
        if ahora - self.ultimo < config.REFRACTARIO_SALUDO:
            return False
        for muestras in self.brazos.values():
            # Se mira desde que la mano subio por primera vez dentro de la ventana
            # (si no, los cuadros de antes del saludo, con la mano abajo, lo retrasan)
            desde = next((i for i, (_, arriba, _) in enumerate(muestras) if arriba), None)
            if desde is None:
                continue
            tramo = list(muestras)[desde:]
            if len(tramo) < 5:
                continue
            fraccion_arriba = sum(1 for _, arriba, _ in tramo if arriba) / len(tramo)
            xs = [x for _, arriba, x in tramo if arriba and x is not None]
            if (fraccion_arriba >= config.FRACCION_MANO_ARRIBA
                    and contar_vaivenes(xs, config.AMPLITUD_SALUDO) >= 2 * config.CICLOS_SALUDO + 1):
                self.ultimo = ahora
                for m in self.brazos.values():           # empezar de cero despues de disparar
                    m.clear()
                return True
        return False

    def olvidar(self):
        for m in self.brazos.values():
            m.clear()


# ============================================================
# Persona
# ============================================================
class Persona:
    def __init__(self, id_persona, cara, ahora):
        self.id = id_persona
        self.cara = cara
        self.creada = ahora
        self.visto = ahora              # ultima vez que se la vio
        self.visible = True             # se ve en ESTE cuadro
        self.confirmada = False
        self.vx = 0.0                   # velocidad horizontal (pixeles por segundo)
        self.presencia = FiltroNdeM(config.PERSONA_N, config.PERSONA_M)
        self.filtro_mira = FiltroSostenido(config.TIEMPO_MIRA,
                                           config.FRACCION_MIRA_ON, config.FRACCION_MIRA_OFF)
        self.me_mira = False
        self.saludo = DetectorSaludo()
        self.filtro_saliendo = FiltroNdeM(config.SALIENDO_N, config.SALIENDO_M)
        self.saliendo = False
        self.lado_salida = 0            # -1 izquierda, +1 derecha (en la imagen)
        self.filtros_camiseta = {
            clase: FiltroConsecutivo(config.CAMISETA_CUADROS_ON, config.CAMISETA_CUADROS_OFF)
            for clase in ("OLIMPIA", "CERRO")}
        self.camiseta = None            # "OLIMPIA", "CERRO" o None (ya filtrada)

    @property
    def cx(self):
        return self.cara.cx

    @property
    def cy(self):
        return self.cara.cy

    @property
    def area(self):
        return self.cara.ancho * self.cara.alto

    def __repr__(self):
        return f"P{self.id}"


def iou(a, b):
    """Interseccion sobre union de dos recuadros (0 = no se tocan, 1 = iguales)."""
    x0, y0 = max(a.x_min, b.x_min), max(a.y_min, b.y_min)
    x1 = min(a.x_min + a.ancho, b.x_min + b.ancho)
    y1 = min(a.y_min + a.alto, b.y_min + b.alto)
    interseccion = max(0, x1 - x0) * max(0, y1 - y0)
    union = a.ancho * a.alto + b.ancho * b.alto - interseccion
    return interseccion / union if union > 0 else 0.0


# ============================================================
# Rastreador: IDs + eventos
# ============================================================
class Rastreador:
    def __init__(self):
        self.personas = []
        self._siguiente_id = 1

    @property
    def confirmadas(self):
        return [p for p in self.personas if p.confirmada]

    def actualizar(self, caras, ancho, alto, ahora, yaw_robot=config.YAW_HOME):
        """Devuelve la lista de eventos de este cuadro: [(TIPO, persona), ...]"""
        eventos = []
        asignadas = self._asociar(caras)

        # 1) Actualizar las que se vieron y crear las nuevas
        for p in self.personas:
            p.visible = False
        for cara, p in asignadas:
            if p is None:
                p = Persona(self._siguiente_id, cara, ahora)
                self._siguiente_id += 1
                self.personas.append(p)
            else:
                dt = ahora - p.visto
                if dt > 0:
                    p.vx = 0.5 * p.vx + 0.5 * (cara.cx - p.cara.cx) / dt
                p.cara = cara
                p.visto = ahora
            p.visible = True

        # 2) PERSONA: confirmar (N de M) y olvidar
        quedan = []
        for p in self.personas:
            p.presencia.agregar(p.visible)
            if not p.confirmada and p.presencia.activo:
                p.confirmada = True
                eventos.append(("PERSONA", p))
            if p.confirmada and ahora - p.visto > config.TIEMPO_OLVIDO:
                eventos.append(("SE_FUE", p))
                continue
            if not p.confirmada and p.presencia.historial and not any(list(p.presencia.historial)[-2:]):
                continue                     # candidata que no se confirmo: era ruido
            quedan.append(p)
        self.personas = quedan

        # 3) Eventos de cada persona confirmada
        for p in self.confirmadas:
            # ME_MIRA
            # Histeresis de angulo: para empezar a mirar hace falta <= 15 grados;
            # una vez que mira, sigue contando hasta 20 grados
            limite = config.ANGULO_MIRA_SALIDA if p.me_mira else config.ANGULO_MIRA
            mira_ahora = (p.visible and p.cara.angulo_mirada is not None
                          and p.cara.angulo_mirada <= limite)
            antes = p.me_mira
            p.me_mira = p.filtro_mira.agregar(ahora, mira_ahora)
            if p.me_mira and not antes:
                eventos.append(("ME_MIRA", p))
            elif antes and not p.me_mira:
                eventos.append(("DEJA_DE_MIRAR", p))

            # SALUDO
            if p.visible and p.cara.cuerpo is not None:
                p.saludo.agregar(ahora, p.cara.cuerpo, p.cara.ancho)
                if p.saludo.evaluar(ahora):
                    eventos.append(("SALUDO", p))

            # SALIENDO
            lado = self._lado_salida(p, ancho, yaw_robot) if p.visible else 0
            antes = p.saliendo
            p.saliendo = p.filtro_saliendo.agregar(lado != 0)
            if lado != 0:
                p.lado_salida = lado
            if p.saliendo and not antes:
                eventos.append(("SALIENDO", p))

            # CAMISETA: solo se actualiza si se ve el torso en este cuadro
            resultado = getattr(p.cara, "camiseta", None) if p.visible else None
            if resultado is not None:
                for clase, filtro in p.filtros_camiseta.items():
                    filtro.agregar(resultado.clase == clase)
                antes = p.camiseta
                activas = [c for c, f in p.filtros_camiseta.items() if f.activo]
                p.camiseta = activas[0] if len(activas) == 1 else None
                if p.camiseta and p.camiseta != antes:
                    eventos.append((f"CAMISETA_{p.camiseta}", p))
                elif antes and not p.camiseta:
                    eventos.append(("SIN_CAMISETA", p))

        for tipo, p in eventos:
            extra = ""
            if tipo == "SALIENDO":
                extra = " hacia la " + ("derecha" if p.lado_salida > 0 else "izquierda")
            elif tipo == "ME_MIRA" and p.cara.angulo_mirada is not None:
                extra = f" ({p.cara.angulo_mirada:.0f} grados)"
            log.info(f"EVENTO | {tipo} {p}{extra}")
        return eventos

    # ---------------------------------------------------------------- detalles
    def _asociar(self, caras):
        """Empareja cada cara con una persona existente (o None = persona nueva)."""
        pares = sorted(((iou(c, p.cara), i, j) for i, c in enumerate(caras)
                        for j, p in enumerate(self.personas)), reverse=True)
        cara_de = {}
        persona_usada = set()
        for valor, i, j in pares:
            if valor < config.IOU_MINIMO:
                break
            if i not in cara_de and j not in persona_usada:
                cara_de[i] = self.personas[j]
                persona_usada.add(j)

        # Segunda pasada: por distancia (la cara se movio mucho entre cuadros)
        for i, c in enumerate(caras):
            if i in cara_de:
                continue
            mejor, mejor_d = None, None
            for j, p in enumerate(self.personas):
                if j in persona_usada:
                    continue
                d = ((c.cx - p.cx) ** 2 + (c.cy - p.cy) ** 2) ** 0.5
                if d < 0.75 * max(p.cara.ancho, 1) and (mejor_d is None or d < mejor_d):
                    mejor, mejor_d = j, d
            if mejor is not None:
                cara_de[i] = self.personas[mejor]
                persona_usada.add(mejor)
        return [(c, cara_de.get(i)) for i, c in enumerate(caras)]

    @staticmethod
    def _lado_salida(p, ancho, yaw_robot):
        """+1 / -1 si la persona se esta yendo por la derecha / izquierda; 0 si no."""
        margen = config.MARGEN_BORDE * ancho
        velocidad = config.VELOCIDAD_SALIDA * ancho
        if p.cx > ancho - margen and p.vx > velocidad:
            return 1
        if p.cx < margen and p.vx < -velocidad:
            return -1
        # Fuera del rango del cuello: esta a un costado y el yaw ya no puede girar hacia ese lado
        error = p.cx - ancho / 2
        if abs(error) > 0.25 * ancho / 2:
            lado = 1 if error > 0 else -1
            hacia = config.SIGNO_YAW * lado            # hacia donde tendria que ir el yaw
            if (hacia > 0 and yaw_robot >= config.YAW_MAX - 1.0) or \
               (hacia < 0 and yaw_robot <= config.YAW_MIN + 1.0):
                return lado
        return 0
