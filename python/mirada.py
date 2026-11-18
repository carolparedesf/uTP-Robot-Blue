"""
mirada.py - T3: de "donde esta la cara en la imagen" a "cuanto girar el cuello".

Pasos para cada cuadro:
  1) error en pixeles respecto al centro de la imagen
  2) pixeles -> grados (con el campo de vision de la camara)
  3) suavizado exponencial (evita temblores)
  4) zona muerta (si el error es chico, no se mueve)
  5) segundo suavizado
  6) control proporcional con saturacion (cuanto corregir en este envio)
"""

import math

import config


def limitar(valor, minimo, maximo):
    return max(minimo, min(valor, maximo))


def aplicar_zona_muerta(error, umbral=config.ZONA_MUERTA):
    if abs(error) < umbral:
        return 0.0
    return error


def suavizar(actual, anterior, alpha=config.ALPHA_SUAVIZADO):
    if anterior is None:
        return actual
    return alpha * actual + (1.0 - alpha) * anterior


def control_proporcional(error, kp=config.KP_SEGUIMIENTO,
                         correccion_maxima=config.CORRECCION_MAXIMA):
    return limitar(kp * error, -correccion_maxima, correccion_maxima)


class ControlMirada:
    def __init__(self):
        self.reset()

    def reset(self):
        """Olvida lo anterior (al perder o recuperar el rostro)."""
        self.angulo_x_anterior = 0.0
        self.angulo_y_anterior = 0.0
        self.error_yaw_suave = 0.0
        self.error_pitch_suave = 0.0

    def medir(self, cara, ancho, alto):
        """Pasos 1 y 2: error en pixeles y en grados. No cambia el estado."""
        cx, cy = ancho // 2, alto // 2

        # Al rotar 90 grados, los campos de vision se intercambian
        if config.ROTAR_90:
            fx = (ancho / 2) / math.tan(config.VFOV / 2)
            fy = (alto / 2) / math.tan(config.HFOV / 2)
        else:
            fx = (ancho / 2) / math.tan(config.HFOV / 2)
            fy = (alto / 2) / math.tan(config.VFOV / 2)

        error_x = cara.cx - cx
        error_y = cara.cy - cy
        angulo_x = math.degrees(math.atan(error_x / fx))
        angulo_y = math.degrees(math.atan(error_y / fy))
        return error_x, error_y, angulo_x, angulo_y

    def actualizar(self, angulo_x, angulo_y):
        """Pasos 3 a 5: suavizado, zona muerta y segundo suavizado."""
        ax = suavizar(angulo_x, self.angulo_x_anterior)
        ay = suavizar(angulo_y, self.angulo_y_anterior)
        self.angulo_x_anterior = ax
        self.angulo_y_anterior = ay

        error_yaw = aplicar_zona_muerta(ax)
        error_pitch = aplicar_zona_muerta(ay)

        self.error_yaw_suave = suavizar(error_yaw, self.error_yaw_suave)
        self.error_pitch_suave = suavizar(error_pitch, self.error_pitch_suave)

    def correcciones(self):
        """Paso 6: cuantos grados mover yaw y pitch en este envio."""
        return (control_proporcional(self.error_yaw_suave),
                control_proporcional(self.error_pitch_suave))
