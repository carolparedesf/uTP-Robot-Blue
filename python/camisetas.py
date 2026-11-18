"""
camisetas.py - T2: CAMISETA_OLIMPIA / CAMISETA_CERRO. Dos metodos que se alternan en ejecucion:

  HSV   reglas de color y patron sobre el torso (la version original, sin modelo).
  YOLO  modelo propio entrenado en Colab (best.pt, ver config.MODELO_CAMISETAS).

Los dos entregan lo mismo (ResultadoCamiseta por cara), asi que personas.py, el filtro de
6 cuadros (T6-d) y los comportamientos no saben cual se esta usando. El metodo se cambia con la
tecla 'c' en la ventana del video o escribiendo CAMISETAS [HSV|YOLO] en la terminal (operador.py).

--------------------------------------------------------------------------- METODO HSV
1) REGION DEL TORSO: entre los hombros (achicada 15 % de cada lado para no
   agarrar brazos ni fondo), desde un poco debajo de los hombros hasta las
   caderas (o 1,1 anchos de hombro si no se ven). Sin cuerpo: debajo de la cara.
   El recorte se achica a 48 x 48 pixeles: es rapido y suaviza arrugas.

2) CADA PIXEL se clasifica en HSV (H de 0 a 180 en OpenCV):
      blanco: poca saturacion y mucho brillo
      negro:  poco brillo
      rojo:   H <= 10 o H >= 165, saturado          azul: 100 <= H <= 130, saturado

3) REGLAS (pensadas para NO confundir remeras lisas, T2):
   OLIMPIA = remera blanca CON una franja negra horizontal en el pecho:
      - al menos 30 % de blanco, y
      - una franja de filas en las que >= 50 % de la fila es negra, de alto
        entre 10 % y 50 % del torso, con blanco arriba Y abajo de la franja.
      Una remera blanca lisa no tiene franja -> no es Olimpia.
      Una remera negra lisa no tiene blanco  -> no es Olimpia.
   CERRO = rayas VERTICALES rojas y azules:
      - al menos 15 % de rojo y 15 % de azul, y
      - recorriendo cada fila de izquierda a derecha, el color cambia
        rojo <-> azul al menos 3 veces (mediana de las filas = 4 rayas o mas).
      Remera roja o azul lisa: le falta un color -> no es Cerro.
      Remera roja con campera azul abierta: azul|rojo|azul = 2 cambios -> no es Cerro.
      Rayas horizontales: en cada fila hay un solo color -> no es Cerro.

--------------------------------------------------------------------------- METODO YOLO
  Se corre el modelo UNA vez por cuadro sobre la imagen completa (no una vez por persona).
  Cada camiseta detectada se asigna a la persona cuyo torso (la misma region del metodo HSV)
  contiene su centro, con un margen (config.MARGEN_ASIGNACION_YOLO). Cada deteccion se asigna
  a una sola persona (la mas cercana). El nombre de clase del modelo se traduce con
  config.CLASES_YOLO (por ejemplo, una clase "Olimpia" -> OLIMPIA). Una clase que no este en la
  tabla cuenta como "otra camiseta": no activa ninguna reaccion.
  Si no se puede cargar el modelo (falta ultralytics o best.pt) se usa HSV y se avisa en el log.

FILTRO (T6-d): la camiseta se confirma con 6 cuadros SEGUIDOS con la misma clase y se olvida
con 6 cuadros seguidos sin ella (personas.py). Vale para los dos metodos.
"""

import logging
import math
from dataclasses import dataclass

import cv2
import numpy as np

import config

log = logging.getLogger("robot")

LADO = 48     # el torso se analiza a 48 x 48 pixeles
METODOS = ("HSV", "YOLO")


@dataclass
class ResultadoCamiseta:
    clase: str              # "OLIMPIA", "CERRO" o None
    blanco: float           # fracciones de pixeles (para ajustar umbrales en pantalla)
    negro: float
    rojo: float
    azul: float
    franja: float           # alto de la franja negra (fraccion del torso), 0 si no hay
    cambios: float          # cambios rojo<->azul por fila (mediana)
    region: tuple           # (x0, y0, x1, y1) en la imagen
    metodo: str = "HSV"     # quien lo calculo: "HSV" o "YOLO"
    confianza: float = None  # solo YOLO: confianza de la deteccion (None si no hubo)

    def descripcion(self):
        """Texto corto para el overlay (monitor.py)."""
        if self.metodo == "YOLO":
            if self.confianza is None:
                return "YOLO: sin camiseta"
            return f"YOLO: {self.clase or 'otra'} {self.confianza:.2f}"
        return (f"B{self.blanco:.2f} N{self.negro:.2f} R{self.rojo:.2f} "
                f"A{self.azul:.2f} f{self.franja:.2f} c{self.cambios:.0f}")


# ============================================================
# Region del torso (comun a los dos metodos)
# ============================================================
def region_torso(cara, ancho_img, alto_img):
    """(x0, y0, x1, y1) del torso, o None si es muy chico o queda fuera de la imagen."""
    cuerpo = cara.cuerpo
    hi = cuerpo.punto("hombro_izq") if cuerpo else None
    hd = cuerpo.punto("hombro_der") if cuerpo else None
    if hi and hd:
        x0, x1 = min(hi[0], hd[0]), max(hi[0], hd[0])
        ancho_hombros = x1 - x0
        x0, x1 = x0 + 0.15 * ancho_hombros, x1 - 0.15 * ancho_hombros
        y0 = (hi[1] + hd[1]) / 2 + 0.10 * ancho_hombros
        ci, cd = cuerpo.punto("cadera_izq"), cuerpo.punto("cadera_der")
        if ci and cd:
            y1 = (ci[1] + cd[1]) / 2 - 0.10 * ancho_hombros
        else:
            y1 = y0 + 1.1 * ancho_hombros
    else:
        x0, x1 = cara.cx - 0.9 * cara.ancho, cara.cx + 0.9 * cara.ancho
        y0 = cara.y_min + 1.4 * cara.alto
        y1 = y0 + 1.8 * cara.alto

    x0, y0 = int(max(0, x0)), int(max(0, y0))
    x1, y1 = int(min(ancho_img, x1)), int(min(alto_img, y1))
    if x1 - x0 < 20 or y1 - y0 < 20:
        return None
    return x0, y0, x1, y1


# ============================================================
# Metodo HSV
# ============================================================
def _mascaras(recorte_bgr):
    hsv = cv2.cvtColor(recorte_bgr, cv2.COLOR_BGR2HSV)
    h = hsv[:, :, 0].astype(int)
    s = hsv[:, :, 1].astype(int)
    v = hsv[:, :, 2].astype(int)
    blanco = (s <= config.S_BLANCO_MAX) & (v >= config.V_BLANCO_MIN)
    negro = v <= config.V_NEGRO_MAX
    color = (s >= config.S_COLOR_MIN) & (v >= config.V_COLOR_MIN)
    rojo = color & ((h <= 10) | (h >= 165))
    azul = color & (h >= 100) & (h <= 130)
    return blanco, negro, rojo, azul


def _franja_negra(blanco, negro):
    """Alto (fraccion) de la franja negra horizontal mas larga con blanco arriba y abajo."""
    filas_negras = negro.mean(axis=1) >= 0.5
    blanco_fila = blanco.mean(axis=1)
    mejor = 0
    i = 0
    while i < LADO:
        if not filas_negras[i]:
            i += 1
            continue
        j = i
        while j < LADO and filas_negras[j]:
            j += 1
        alto = (j - i) / LADO
        arriba = blanco_fila[:i].mean() if i >= 3 else 0.0
        abajo = blanco_fila[j:].mean() if LADO - j >= 3 else 0.0
        if (config.FRANJA_MIN <= alto <= config.FRANJA_MAX
                and arriba >= 0.4 and abajo >= 0.4):
            mejor = max(mejor, alto)
        i = j
    return mejor


def _cambios_rojo_azul(rojo, azul):
    """Mediana, sobre las filas, de cuantas veces el color pasa de rojo a azul o al reves."""
    cambios = []
    for fila in range(LADO):
        etiquetas = np.where(rojo[fila], 1, np.where(azul[fila], 2, 0))
        # tramos de al menos 2 pixeles del mismo color (ignora pixeles sueltos)
        tramos = []
        actual, largo = 0, 0
        for e in etiquetas:
            if e == actual:
                largo += 1
            else:
                if actual and largo >= 2:
                    tramos.append(actual)
                actual, largo = e, 1
        if actual and largo >= 2:
            tramos.append(actual)
        n = sum(1 for a, b in zip(tramos, tramos[1:]) if a != b)
        cambios.append(n)
    return float(np.median(cambios))


def clasificar(frame, cara):
    """Metodo HSV: ResultadoCamiseta del torso de esa cara, o None si no hay torso visible."""
    alto_img, ancho_img = frame.shape[:2]
    region = region_torso(cara, ancho_img, alto_img)
    if region is None:
        return None
    x0, y0, x1, y1 = region
    recorte = cv2.resize(frame[y0:y1, x0:x1], (LADO, LADO), interpolation=cv2.INTER_AREA)
    blanco, negro, rojo, azul = _mascaras(recorte)

    fb, fn, fr, fa = blanco.mean(), negro.mean(), rojo.mean(), azul.mean()
    franja = _franja_negra(blanco, negro) if fb >= config.BLANCO_MIN_OLIMPIA else 0.0
    cambios = (_cambios_rojo_azul(rojo, azul)
               if fr >= config.COLOR_MIN_CERRO and fa >= config.COLOR_MIN_CERRO else 0.0)

    clase = None
    if franja > 0:
        clase = "OLIMPIA"
    elif cambios >= config.CAMBIOS_MIN_CERRO:
        clase = "CERRO"
    return ResultadoCamiseta(clase, float(fb), float(fn), float(fr), float(fa),
                             float(franja), cambios, region)


# ============================================================
# Metodo YOLO
# ============================================================
def traducir_clase(nombre):
    """Nombre de clase del modelo -> "OLIMPIA" / "CERRO" / None (segun config.CLASES_YOLO)."""
    nombre = str(nombre).lower()
    for clave, clase in config.CLASES_YOLO.items():
        if clave in nombre:
            return clase
    return None


def asignar_detecciones(regiones, detecciones, margen=None):
    """Asigna cada deteccion a la persona cuyo torso la contiene (como mucho una persona por
    deteccion y una deteccion por persona).

    regiones:    una por persona, (x0, y0, x1, y1) del torso o None si no se ve
    detecciones: [(x0, y0, x1, y1, clase, confianza), ...]
    Devuelve una lista paralela a 'regiones' con la deteccion elegida o None."""
    margen = config.MARGEN_ASIGNACION_YOLO if margen is None else margen
    pares = []
    for i, region in enumerate(regiones):
        if region is None:
            continue
        x0, y0, x1, y1 = region
        w, h = x1 - x0, y1 - y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for j, (a0, b0, a1, b1, _, conf) in enumerate(detecciones):
            dx, dy = (a0 + a1) / 2, (b0 + b1) / 2
            if (x0 - margen * w <= dx <= x1 + margen * w
                    and y0 - margen * h <= dy <= y1 + margen * h):
                distancia = math.hypot((dx - cx) / w, (dy - cy) / h)
                pares.append((distancia, -conf, i, j))
    pares.sort()

    elegidas = [None] * len(regiones)
    usadas = set()
    for _, _, i, j in pares:
        if elegidas[i] is None and j not in usadas:
            elegidas[i] = detecciones[j]
            usadas.add(j)
    return elegidas


class DetectorYolo:
    """Carga best.pt y detecta camisetas en el cuadro completo."""

    def __init__(self, pesos=None):
        from ultralytics import YOLO        # import aqui: sin ultralytics, el metodo HSV sigue andando
        self.modelo = YOLO(pesos or config.MODELO_CAMISETAS)
        self.clases = {int(i): traducir_clase(n) for i, n in self.modelo.names.items()}
        log.info("CAMISETAS | modelo YOLO cargado. Clases: "
                 + ", ".join(f"{n}->{self.clases[int(i)] or 'otra'}"
                             for i, n in self.modelo.names.items()))
        if not any(self.clases.values()):
            log.warning("CAMISETAS | ninguna clase del modelo coincide con config.CLASES_YOLO: "
                        "ajustar los nombres")

    def detectar(self, frame):
        r = self.modelo.predict(frame, conf=config.CONFIANZA_YOLO,
                                imgsz=config.IMGSZ_YOLO, verbose=False)[0]
        salida = []
        for caja in r.boxes:
            x0, y0, x1, y1 = caja.xyxy[0].tolist()
            salida.append((x0, y0, x1, y1, self.clases.get(int(caja.cls)), float(caja.conf)))
        return salida


# ============================================================
# Clasificador: elige el metodo en cada cuadro
# ============================================================
class ClasificadorCamisetas:
    def __init__(self, metodo=None):
        self.metodo = (metodo or config.CAMISETA_METODO).upper()
        if self.metodo not in METODOS:
            self.metodo = "HSV"
        self._yolo = None
        self._yolo_fallo = False
        self._cargar_yolo()                 # se carga ya, para que alternar despues no trabe el video

    def _cargar_yolo(self):
        if self._yolo is None and not self._yolo_fallo:
            try:
                self._yolo = DetectorYolo()
            except Exception as e:
                self._yolo_fallo = True
                log.warning(f"CAMISETAS | no se pudo cargar el modelo YOLO ({e}). Se usa HSV")
        return self._yolo

    @property
    def metodo_efectivo(self):
        """El metodo que realmente se esta usando (YOLO cae a HSV si no se pudo cargar)."""
        return "YOLO" if self.metodo == "YOLO" and self._yolo is not None else "HSV"

    def fijar_metodo(self, metodo):
        metodo = metodo.upper()
        if metodo in METODOS and metodo != self.metodo:
            log.info(f"CAMISETAS | metodo {self.metodo} -> {metodo}")
            self.metodo = metodo

    def clasificar_todas(self, frame, caras):
        """Pone cara.camiseta (ResultadoCamiseta o None) en cada cara del cuadro."""
        if self.metodo_efectivo == "YOLO":
            try:
                self._con_yolo(frame, caras)
                return
            except Exception as e:          # un fallo del modelo no debe frenar el robot
                log.error(f"CAMISETAS | fallo YOLO ({e}). Se usa HSV")
                self._yolo, self._yolo_fallo = None, True
        for cara in caras:
            cara.camiseta = clasificar(frame, cara)

    def _con_yolo(self, frame, caras):
        alto_img, ancho_img = frame.shape[:2]
        regiones = [region_torso(c, ancho_img, alto_img) for c in caras]
        detecciones = self._yolo.detectar(frame) if any(r is not None for r in regiones) else []
        elegidas = asignar_detecciones(regiones, detecciones)

        for cara, region, det in zip(caras, regiones, elegidas):
            if region is None:              # sin torso visible: no se actualiza el filtro
                cara.camiseta = None
            elif det is None:               # torso visible pero sin camiseta detectada
                cara.camiseta = ResultadoCamiseta(None, 0, 0, 0, 0, 0, 0, region, "YOLO", None)
            else:
                x0, y0, x1, y1, clase, conf = det
                caja = (int(max(0, x0)), int(max(0, y0)),
                        int(min(ancho_img, x1)), int(min(alto_img, y1)))
                cara.camiseta = ResultadoCamiseta(clase, 0, 0, 0, 0, 0, 0, caja, "YOLO", conf)
