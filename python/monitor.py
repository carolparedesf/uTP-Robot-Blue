"""
monitor.py - T7: monitoreo.

  - configurar_log(): crea logs/robot_AAAAMMDD_HHMMSS.log. Todo lo que se
    registra con logging.getLogger("robot") va al archivo (con fecha, hora y
    milisegundos) y tambien a la consola.
  - Monitor: dibuja sobre el video (overlay).
"""

import logging
import os
from datetime import datetime

import cv2

import config


def configurar_log(carpeta=config.CARPETA_LOGS):
    """Prepara el log de esta ejecucion y devuelve la ruta del archivo."""
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, datetime.now().strftime("robot_%Y%m%d_%H%M%S.log"))

    log = logging.getLogger("robot")
    log.setLevel(logging.INFO)
    log.handlers.clear()

    archivo = logging.FileHandler(ruta, encoding="utf-8")
    archivo.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(archivo)

    consola = logging.StreamHandler()
    consola.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(consola)
    return ruta

BLANCO = (255, 255, 255)
VERDE = (0, 255, 0)
AMARILLO = (0, 255, 255)
ROJO = (0, 0, 255)
AZUL = (255, 0, 0)
GRIS = (160, 160, 160)
NARANJA = (0, 140, 255)
FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def _texto(frame, texto, y, color, escala=0.55, x=10):
    cv2.putText(frame, texto, (x, y), FUENTE, escala, color, 2)


def _dibujar_persona(frame, p, es_objetivo, puntaje=None, cambio=None):
    """Recuadro con ID; verde = objetivo, gris = otra persona; punteado si no se ve."""
    c = p.cara
    color = VERDE if es_objetivo else GRIS
    grosor = 2 if p.visible else 1
    cv2.rectangle(frame, (c.x_min, c.y_min), (c.x_min + c.ancho, c.y_min + c.alto), color, grosor)

    etiqueta = f"P{p.id}"
    if puntaje is not None:
        etiqueta += f" {puntaje:.1f}"
    if p.me_mira:
        etiqueta += " ME MIRA"
    if p.saliendo:
        etiqueta += " SALIENDO " + ("->" if p.lado_salida > 0 else "<-")
    if p.camiseta:
        etiqueta += f" {p.camiseta}"

    # Torso analizado para la camiseta: blanco = Olimpia, rojo = Cerro, gris = ninguna
    resultado = c.camiseta if p.visible else None
    if resultado is not None:
        x0, y0, x1, y1 = resultado.region
        color_torso = {"OLIMPIA": BLANCO, "CERRO": ROJO}.get(resultado.clase, GRIS)
        cv2.rectangle(frame, (x0, y0), (x1, y1), color_torso, 1)
        _texto(frame, resultado.descripcion(),
               min(frame.shape[0] - 120, y1 + 14), color_torso, escala=0.38, x=x0)
    ancho_texto = cv2.getTextSize(etiqueta, FUENTE, 0.5, 2)[0][0]
    x = max(0, min(c.x_min, frame.shape[1] - ancho_texto - 5))     # que no se corte en el borde
    _texto(frame, etiqueta, max(15, c.y_min - 8), color, escala=0.5, x=x)
    # Barra de histeresis: cuanto le falta a este retador para quedarse con la mirada (T4)
    if cambio is not None:
        x0, y0 = c.x_min, c.y_min + c.alto + 24
        cv2.rectangle(frame, (x0, y0), (x0 + c.ancho, y0 + 8), AMARILLO, 1)
        cv2.rectangle(frame, (x0, y0), (x0 + int(c.ancho * cambio), y0 + 8), AMARILLO, -1)
    if c.angulo_mirada is not None and p.visible:
        _texto(frame, f"{c.angulo_mirada:.0f} gr", c.y_min + c.alto + 18, color, escala=0.45, x=c.x_min)

    # Hombros, codos y munecas (para ver por que se detecta, o no, un SALUDO)
    if p.visible and c.cuerpo is not None:
        for lado in ("izq", "der"):
            puntos = [c.cuerpo.punto(f"{n}_{lado}") for n in ("hombro", "codo", "muneca")]
            for a, b in zip(puntos, puntos[1:]):
                if a and b:
                    cv2.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), NARANJA, 2)
            if puntos[2]:
                cv2.circle(frame, (int(puntos[2][0]), int(puntos[2][1])), 6, NARANJA, -1)


class Monitor:
    def __init__(self, titulo="Seguimiento facial - ESP32"):
        self.titulo = titulo
        self.ultimos_eventos = []      # [(texto, hasta_cuando)] para que se lean 2 s
        self.ultima_tecla = -1         # la lee el operador (main.py)

    def mostrar(self, frame, info):
        """Dibuja y muestra. Devuelve False si se apreto q."""
        alto, ancho = frame.shape[:2]
        cx, cy = ancho // 2, alto // 2
        cv2.drawMarker(frame, (cx, cy), AZUL, cv2.MARKER_CROSS, 20, 2)

        objetivo = info.get("objetivo")
        puntajes = info.get("puntajes", {})
        retador, progreso = info.get("cambio") or (None, None)
        for p in info.get("personas", []):
            _dibujar_persona(frame, p, p is objetivo, puntajes.get(p.id),
                             progreso if p.id == retador else None)

        cara = info.get("cara")
        if cara is not None:
            cv2.circle(frame, (cara.cx, cara.cy), 5, VERDE, -1)
            cv2.line(frame, (cx, cy), (cara.cx, cara.cy), AMARILLO, 2)

            _texto(frame, f"Error: X={info['error_x']}px Y={info['error_y']}px", 25, BLANCO)
            _texto(frame, f"Angulo: X={info['angulo_x']:.1f} Y={info['angulo_y']:.1f}", 50, BLANCO)
            _texto(frame, f"Objetivo: P{objetivo.id}  Rostro: ({cara.cx},{cara.cy})", 75, VERDE)
        else:
            _texto(frame, "No se detecta un rostro", 70, ROJO, escala=0.7, x=20)

        # Eventos de los ultimos 2 s (T2)
        ahora = cv2.getTickCount() / cv2.getTickFrequency()
        for tipo, p in info.get("eventos", []):
            self.ultimos_eventos.append((f"{tipo} P{p.id}", ahora + 2.0))
        self.ultimos_eventos = [(t, h) for t, h in self.ultimos_eventos if h > ahora][-4:]
        for i, (texto, _) in enumerate(self.ultimos_eventos):
            _texto(frame, texto, alto - 95 - 22 * i, NARANJA, escala=0.6)

        # Modo actual y STOP (T7)
        if "modo" in info:
            _texto(frame, f"Modo: {info['modo']}", 100, AMARILLO, escala=0.6)
        if "camisetas" in info:
            _texto(frame, f"Camisetas: {info['camisetas']}", 125, AMARILLO, escala=0.6)
        if info.get("detenido"):
            _texto(frame, "STOP (g = seguir)", alto // 2, ROJO, escala=1.0, x=20)

        # Siempre visibles: angulos comandados y quien controla cada recurso (T7)
        _texto(frame, f"Comandado: yaw {info.get('yaw', 0):.1f}  pitch {info.get('pitch', 0):.1f}"
                      f"  roll {info.get('roll', 0):.1f}", alto - 65, AMARILLO)
        recursos = info.get("recursos", {})
        _texto(frame, f"Cuello: {recursos.get('CUELLO', '-')}", alto - 40, BLANCO)
        _texto(frame, f"Buzzer: {recursos.get('BUZZER', '-')}   Ojos: {info.get('cara_fija', '')}",
               alto - 15, BLANCO)

        cv2.imshow(self.titulo, frame)
        tecla = cv2.waitKey(1)
        self.ultima_tecla = tecla & 0xFF if tecla != -1 else -1
        return self.ultima_tecla != ord("q")

    def cerrar(self):
        cv2.destroyAllWindows()
