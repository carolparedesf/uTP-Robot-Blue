"""
config.py - todos los numeros ajustables del robot en un solo lugar.

Si algo se mueve muy lento, muy rapido o para el lado contrario, se cambia ACA
y no hace falta tocar el resto del codigo.
"""

import math
import os

CARPETA = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# ESP32
# ============================================================
PUERTO_ESP32 = "COM10"        # cambiar por el puerto real
BAUDIOS = 115200
MOSTRAR_ENVIOS = True        # imprimir cada comando enviado (util para probar)

# ============================================================
# MONITOREO (T7)
# ============================================================
CARPETA_LOGS = os.path.join(CARPETA, "logs")   # un archivo .log nuevo por cada ejecucion
LOG_COMANDOS = False         # True = guardar tambien cada comando enviado (el archivo crece mucho)

# Posiciones de reposo (iguales a las del firmware)
YAW_HOME = 90.0
PITCH_HOME = 90.0
ROLL_HOME = 80.0

# Limites del firmware
YAW_MIN, YAW_MAX = 20.0, 160.0
PITCH_MIN, PITCH_MAX = 60.0, 120.0

# ============================================================
# CAMARA
# ============================================================
INDICE_CAMARA = 1            # 0 = camara de la notebook; la Brio te dio 1
FALLOS_CAMARA_MAX = 60       # fotogramas fallidos seguidos (~3 s) antes de cerrar el programa
RESOLUCION = None            # None = la que de la camara. Recomendado: (1280, 720)
ROTAR_90 = True              # la camara esta montada de costado

# FOV aproximado de la camara ANTES de rotar la imagen
HFOV = math.radians(51.4)
VFOV = math.radians(30.0)

# ============================================================
# PERCEPCION (T2) - modelos de MediaPipe (van en la misma carpeta que los .py)
# ============================================================
MODELO_CARAS = os.path.join(CARPETA, "face_landmarker.task")        # caras + orientacion
MODELO_CUERPOS = os.path.join(CARPETA, "pose_landmarker_lite.task")  # hombros, codos, munecas
CONFIANZA_MINIMA = 0.5       # umbral de deteccion de caras y de cuerpos
MAX_PERSONAS = 3             # cuantas caras / cuerpos busca como maximo
USAR_CUERPOS = True          # False = sin SALUDO (mas rapido, por si la notebook no da)

# PERSONA: seguimiento por ID (tracking)
PERSONA_N, PERSONA_M = 3, 5      # confirmada si se vio en 3 de los ultimos 5 cuadros
IOU_MINIMO = 0.2                 # solapamiento minimo para decir "es la misma cara"
TIEMPO_OLVIDO = 1.0              # segundos sin verla para borrar su ID (T3-c: perdida < 1 s)

# ME_MIRA: la cara apunta a la camara
ANGULO_MIRA = 15.0               # grados entre "hacia donde apunta la cara" y "la camara"
ANGULO_MIRA_SALIDA = 20.0        # ya mirando, deja de contar recien por encima de esto (histeresis)
TIEMPO_MIRA = 0.5                # sostenido al menos este tiempo
FRACCION_MIRA_ON = 0.8           # en la ventana, este % de cuadros deben cumplir para activar
FRACCION_MIRA_OFF = 0.5          # ...y por debajo de este % se desactiva (histeresis)

# SALUDO: mano arriba del hombro + oscilacion lateral
VENTANA_SALUDO = 2.0             # segundos que mira hacia atras
FRACCION_MANO_ARRIBA = 0.6       # % de cuadros de la ventana con la muneca sobre el hombro
CICLOS_SALUDO = 2                # ciclos completos izquierda-derecha (1 ciclo = 2 vaivenes)
AMPLITUD_SALUDO = 0.15           # cada vaiven mide al menos esto (en anchos de hombro)
REFRACTARIO_SALUDO = 3.0         # segundos sin volver a disparar para la misma persona

# ============================================================
# ATENCION (T4): a quien mirar si hay varias personas (ver atencion.py)
# ============================================================
PESO_MIRA = 2.0              # quien me mira siempre gana (los otros dos suman como mucho 1,5)
PESO_CERCA = 1.0             # cara mas grande = mas cerca
PESO_CENTRO = 0.5            # mas centrada en la imagen
MARGEN_CAMBIO = 0.3          # el retador tiene que ser mejor por al menos esto...
TIEMPO_CAMBIO = 1.0          # ...durante este tiempo seguido (histeresis)

# CAMISETA (ver camisetas.py)
USAR_CAMISETAS = True
S_BLANCO_MAX, V_BLANCO_MIN = 50, 150    # blanco: poca saturacion, mucho brillo (HSV 0-255)
V_NEGRO_MAX = 60                         # negro: poco brillo
S_COLOR_MIN, V_COLOR_MIN = 90, 40        # rojo / azul: bien saturados
BLANCO_MIN_OLIMPIA = 0.30                # fraccion minima de blanco
FRANJA_MIN, FRANJA_MAX = 0.10, 0.50      # alto de la franja negra (fraccion del torso)
COLOR_MIN_CERRO = 0.15                   # fraccion minima de rojo Y de azul
CAMBIOS_MIN_CERRO = 2                    # cambios rojo<->azul por fila (rayas verticales)
CAMISETA_CUADROS_ON = 6                  # cuadros SEGUIDOS con camiseta para confirmarla (T6-d)
CAMISETA_CUADROS_OFF = 6                 # cuadros SEGUIDOS sin ella para olvidarla

# CAMISETA con modelo propio (YOLO entrenado en Colab). Se alterna con las reglas HSV
# en ejecucion: tecla c en la ventana del video, o CAMISETAS [HSV|YOLO] en la terminal.
CAMISETA_METODO = "YOLO"                 # metodo al arrancar: "HSV" o "YOLO"
MODELO_CAMISETAS = os.path.join(CARPETA, "best.pt")   # pesos del Colab (junto a los .py)
CONFIANZA_YOLO = 0.65
IMGSZ_YOLO = 416                         # a 416 se llega a 10 Hz - a 640 da 9 Hz aprox.
MARGEN_ASIGNACION_YOLO = 0.5             # una camiseta se asigna a la persona si su centro cae
                                         # dentro del torso agrandado en esta fraccion
# Nombre de clase del modelo (minusculas; basta con que lo contenga) -> camiseta
CLASES_YOLO = {"olimpia": "OLIMPIA", "cerro": "CERRO"}

# SALIENDO: la persona seguida se va del campo de vision
MARGEN_BORDE = 0.15              # "cerca del borde" = 15 % del ancho de la imagen
VELOCIDAD_SALIDA = 0.15          # anchos de imagen por segundo hacia el borde
SALIENDO_N, SALIENDO_M = 3, 5

# ============================================================
# SEGUIMIENTO (T3)
# ============================================================
INTERVALO_ENVIO = 0.12       # segundos entre comandos (revision: probar 0.08)
KP_SEGUIMIENTO = 0.15        # (revision: probar 0.3)
CORRECCION_MAXIMA = 1.0      # grados por comando (revision: probar 4.0)
ALPHA_SUAVIZADO = 0.3
ZONA_MUERTA = 4            # grados

# Si un eje se mueve en sentido contrario, cambiar su signo
SIGNO_YAW = -1.0
SIGNO_PITCH = -1.0

# ============================================================
# ESTADOS Y GESTOS
# ============================================================
TIEMPO_PERDIDA_OBJETIVO = 1.0    # segundos sin rostro para considerarlo perdido
DURACION_DESAPROBACION = 0.8     # segundos
AMPLITUD_DESAPROBACION = 9.0     # grados de roll

YAW_OBSERVADOR_MIN = 60.0
YAW_OBSERVADOR_MAX = 120.0
PASO_OBSERVADOR = 0.5            # grados por envio
DURACION_VUELTA_HOME_MS = 1500   # al terminar el barrido, tarda esto en volver a HOME

# ============================================================
# SONIDOS Y OJOS (firmware v3)
# ============================================================
# nombre: (id del sonido en el firmware, duracion en ms)
SONIDOS = {
    "SALUDO":      (3, 920),
    "POLCA":       (4, 14880),
    "REPROBACION": (5, 760),
    "S4":          (7, 440),
    "MODO":        (9, 1560),
    "BOSTEZO":     (14, 1770),
    "R2D2":        (8, 580),
    "PIROPO":      (6, 750),
    "MODO_NEUTRO":     (10, 80),
    "MODO_TIMIDO":     (11, 160),
    "MODO_ATREVIDO":   (12, 280),
    "MODO_MALEDUCADO": (13, 200),
}

COOLDOWN_SALUDO = 10.0       # segundos minimos entre dos bienvenidas

# Saludo con la mano -> asentir (Tabla 1)
CABECEOS_SALUDO = 3          # el enunciado pide 2-3
AMPLITUD_CABECEO = 10.0      # grados de pitch hacia abajo
DURACION_MEDIO_CABECEO_MS = 200   # bajar = 200 ms, subir = 200 ms
COOLDOWN_SALUDO_MANO = 8.0   # segundos antes de devolverle el saludo a la MISMA persona

SIGNO_OJOS = -1.0            # si las pupilas miran al lado contrario, cambiar a 1.0
ANGULO_OJOS_MAX = 25.0       # grados de error que corresponden a la pupila en el borde

# ============================================================
# FASE 6: CAMISETAS, MODOS DE PERSONALIDAD Y OPERADOR
# ============================================================
COOLDOWN_POLCA = 25.0        # la polca no se repite para la misma persona antes de esto (T6-c: 20-30 s)
COOLDOWN_ABUCHEO = 25.0      # idem para el abucheo a los de Cerro

# Timido: desvia la mirada, espera y vuelve a espiar de a poco
DESVIO_YAW_TIMIDO = 10.0     # grados hacia el costado (la persona sigue en la imagen)
DESVIO_PITCH_TIMIDO = 10.0   # grados hacia abajo
DURACION_DESVIO_MS = 400     # cuanto tarda en desviar
TIEMPO_DESVIADO = 2.0        # segundos con la mirada desviada
DURACION_ESPIAR = 2.0        # segundos para volver de a poco
COOLDOWN_TIMIDO = 6.0        # segundos antes de volver a ponerse timido

# Atrevido: sostiene la mirada y levanta el menton periodicamente
AMPLITUD_MENTON = 10.0        # grados de pitch hacia arriba
PERIODO_MENTON = 1.5         # segundos por cada levantada de menton
DURACION_ATREVIDO = 6.0      # segundos de desafio
COOLDOWN_ATREVIDO = 5.0

# Maleducado: piropo al que se va
COOLDOWN_PIROPO = 40.0       # no piropea a mas de una persona cada 40 s (T6-c)

