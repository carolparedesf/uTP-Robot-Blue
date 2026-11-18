"""
percepcion.py - T2: que ve el robot EN ESTE CUADRO (sin memoria).

Dos modelos de MediaPipe (Tasks API):
  - FaceLandmarker: 478 puntos de cada cara + la matriz de orientacion de la
    cabeza. De ahi salen el recuadro de la cara y "hacia donde apunta".
  - PoseLandmarker (lite): 33 puntos del cuerpo. Usamos nariz, hombros,
    codos, munecas y caderas (SALUDO, y el torso para CAMISETA).
  - camisetas.py: Olimpia / Cerro por color y patron en el torso.

A cada cara se le pega el cuerpo cuya nariz cae dentro de su recuadro.
La memoria entre cuadros (IDs, filtros N de M, eventos) esta en personas.py.
"""

import math
from dataclasses import dataclass, field

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import config
from camisetas import ClasificadorCamisetas

# Puntos del cuerpo que usamos (numeracion de MediaPipe Pose)
PUNTOS_CUERPO = {
    "nariz": 0,
    "hombro_izq": 11, "hombro_der": 12,
    "codo_izq": 13, "codo_der": 14,
    "muneca_izq": 15, "muneca_der": 16,
    "cadera_izq": 23, "cadera_der": 24,
}


@dataclass
class Cuerpo:
    # nombre -> (x, y, visibilidad) en pixeles; visibilidad de 0 a 1
    puntos: dict = field(default_factory=dict)

    def punto(self, nombre, visibilidad_minima=0.5):
        """(x, y) si el punto se ve bien, si no None."""
        p = self.puntos.get(nombre)
        if p is None or p[2] < visibilidad_minima:
            return None
        return p[0], p[1]


@dataclass
class Cara:
    x_min: int
    y_min: int
    ancho: int
    alto: int
    confianza: float = None          # el FaceLandmarker no da puntaje: filtra con CONFIANZA_MINIMA
    angulo_mirada: float = None      # grados entre "hacia donde apunta la cara" y la camara
    cuerpo: Cuerpo = None            # el cuerpo de esta persona (si se encontro)
    camiseta: object = None          # ResultadoCamiseta de este cuadro (camisetas.py) o None

    @property
    def cx(self):          # centro en x (pixeles)
        return self.x_min + self.ancho // 2

    @property
    def cy(self):          # centro en y (pixeles)
        return self.y_min + self.alto // 2


def angulo_hacia_camara(matriz):
    """Angulo (grados) entre la direccion en que apunta la cara y la linea cara->camara.

    La matriz 4x4 de MediaPipe lleva la cara del modelo canonico al espacio de
    la camara: la columna 3 de la rotacion es "hacia donde apunta la nariz" y la
    traslacion t es donde esta la cara. La camara esta en el origen, asi que la
    direccion cara->camara es -t. Si la persona mira a la camara, ambos vectores
    son paralelos y el angulo es 0. Se usa el valor absoluto del coseno para no
    depender del signo del eje z de la convencion."""
    m = np.asarray(matriz, dtype=float).reshape(4, 4)
    adelante = m[:3, 2]
    hacia_camara = -m[:3, 3]
    n1, n2 = np.linalg.norm(adelante), np.linalg.norm(hacia_camara)
    if n1 < 1e-9 or n2 < 1e-9:
        return None
    coseno = abs(float(np.dot(adelante, hacia_camara)) / (n1 * n2))
    return math.degrees(math.acos(min(1.0, coseno)))


def asignar_cuerpos(caras, cuerpos):
    """A cada cara le pega el cuerpo cuya nariz cae dentro de su recuadro (agrandado 30 %)."""
    libres = list(cuerpos)
    for cara in caras:
        mejor, mejor_distancia = None, None
        margen_x, margen_y = 0.3 * cara.ancho, 0.3 * cara.alto
        for cuerpo in libres:
            nariz = cuerpo.punto("nariz", 0.3)
            if nariz is None:
                continue
            x, y = nariz
            if (cara.x_min - margen_x <= x <= cara.x_min + cara.ancho + margen_x
                    and cara.y_min - margen_y <= y <= cara.y_min + cara.alto + margen_y):
                distancia = math.hypot(x - cara.cx, y - cara.cy)
                if mejor is None or distancia < mejor_distancia:
                    mejor, mejor_distancia = cuerpo, distancia
        if mejor is not None:
            cara.cuerpo = mejor
            libres.remove(mejor)
    return caras


class Percepcion:
    def __init__(self):
        opciones_caras = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=config.MODELO_CARAS),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=config.MAX_PERSONAS,
            min_face_detection_confidence=config.CONFIANZA_MINIMA,
            min_face_presence_confidence=config.CONFIANZA_MINIMA,
            output_facial_transformation_matrixes=True,
        )
        self.detector_caras = vision.FaceLandmarker.create_from_options(opciones_caras)

        self.detector_cuerpos = None
        if config.USAR_CUERPOS:
            opciones_cuerpos = vision.PoseLandmarkerOptions(
                base_options=python.BaseOptions(model_asset_path=config.MODELO_CUERPOS),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=config.MAX_PERSONAS,
                min_pose_detection_confidence=config.CONFIANZA_MINIMA,
                min_pose_presence_confidence=config.CONFIANZA_MINIMA,
            )
            self.detector_cuerpos = vision.PoseLandmarker.create_from_options(opciones_cuerpos)
        self.camisetas = ClasificadorCamisetas() if config.USAR_CAMISETAS else None

    def caras(self, frame):
        """Lista de caras del cuadro (cada una con su orientacion y su cuerpo, si hay)."""
        alto, ancho = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        imagen = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        resultado = self.detector_caras.detect(imagen)
        matrices = resultado.facial_transformation_matrixes or []
        caras = []
        for i, puntos in enumerate(resultado.face_landmarks):
            xs = [p.x * ancho for p in puntos]
            ys = [p.y * alto for p in puntos]
            x0, y0 = int(max(0, min(xs))), int(max(0, min(ys)))
            x1, y1 = int(min(ancho - 1, max(xs))), int(min(alto - 1, max(ys)))
            angulo = angulo_hacia_camara(matrices[i]) if i < len(matrices) else None
            caras.append(Cara(x0, y0, x1 - x0, y1 - y0, angulo_mirada=angulo))

        if self.detector_cuerpos is not None and caras:
            cuerpos = []
            for puntos in self.detector_cuerpos.detect(imagen).pose_landmarks:
                cuerpos.append(Cuerpo({
                    nombre: (puntos[i].x * ancho, puntos[i].y * alto, puntos[i].visibility or 0.0)
                    for nombre, i in PUNTOS_CUERPO.items()
                }))
            asignar_cuerpos(caras, cuerpos)
        if self.camisetas is not None and caras:
            self.camisetas.clasificar_todas(frame, caras)
        return caras

    def cerrar(self):
        self.detector_caras.close()
        if self.detector_cuerpos is not None:
            self.detector_cuerpos.close()
