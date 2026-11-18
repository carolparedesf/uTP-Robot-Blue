"""
camara.py - abrir la camara y entregar cada imagen ya derecha.
"""

import cv2

import config


class Camara:
    def __init__(self, indice=config.INDICE_CAMARA):
        self.cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError("No se pudo abrir la webcam. Verifica el indice de la camara.")

        if config.RESOLUCION:
            ancho, alto = config.RESOLUCION
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)

    def leer(self):
        """Devuelve la imagen (rotada si hace falta) o None si fallo la camara."""
        ok, frame = self.cap.read()
        if not ok:
            return None
        if config.ROTAR_90:
            # Rotar la imagen para que el rostro quede derecho
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        return frame

    def cerrar(self):
        self.cap.release()
