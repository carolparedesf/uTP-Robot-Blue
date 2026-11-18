# Blue: cabeza robótica social de 3 GDL

µTP Robótica Social, Robótica II, Ingeniería Mecatrónica, FIUNA (2026).

**Grupo Robot Blue:** Victoria Carolina Paredes Frutos, Lourdes Rosanna Lopez Franco, Francisco Ramón González Galeano y David Sopino.

Cabeza robótica con cuello de 3 grados de libertad (yaw, pitch y roll), cámara, buzzer y ojos animados en una pantalla OLED. Una PC con Python detecta personas, miradas, saludos y camisetas de Olimpia y Cerro, y decide qué hace el robot. Un ESP32 mueve los servos, toca los sonidos y dibuja los ojos.

## Estructura

```
firmware/              proyecto PlatformIO del ESP32
  src/main.cpp           pines, límites y reposo de cada eje
  lib/                   MotionAxis, Neck, ToneSequencer, HeadSounds, Eyes, HeadProtocol
python/                programa de la PC
  main.py                bucle principal
  config.py              todos los parámetros ajustables
  camara.py              cámara (rota la imagen 90°)
  percepcion.py          caras y cuerpos (MediaPipe)
  camisetas.py           camisetas Olimpia / Cerro (YOLO o reglas HSV)
  personas.py            IDs de personas y eventos filtrados
  mundo.py               estado del mundo
  atencion.py            a quién mirar si hay varias personas
  mirada.py              control de la mirada
  comportamientos.py     los 13 comportamientos
  arbitro.py             reparto del cuello y el buzzer por prioridad
  operador.py            teclas y comandos de terminal
  robot.py               protocolo serie con el ESP32
  monitor.py             overlay del video y log
  prueba_percepcion.py   prueba de la cámara y la IA sin el robot
  best.pt                modelo YOLO de camisetas
requirements.txt
```

## Hardware

| Componente | Pin del ESP32 |
|---|---|
| Servo yaw (MG996R) | GPIO 18 |
| Servo pitch (MG996R) | GPIO 19 |
| Servo roll (MG996R) | GPIO 26 |
| Buzzer (módulo MH-FMD) | GPIO 25 |
| OLED SSD1306 128×64 (I²C, 0x3C) | SDA GPIO 21, SCL GPIO 22 |

Los servos se alimentan con una fuente de 12 V y un convertidor reductor regulado a ~5,2 V, **con GND común con el ESP32**. Regular el convertidor antes de conectar los servos. La cámara (Logitech Brio 100) va por USB a la PC, montada de costado.

## Instalación

### 1. Firmware

1. Instalar VS Code con la extensión PlatformIO.
2. Abrir la carpeta `firmware` y conectar el ESP32 por USB.
3. Compilar y subir con el botón **Upload** (o `pio run -t upload`). Las librerías se descargan solas.
4. Probar desde el Serial Monitor (115200 baudios): `HOME`, `J 70 90 80`, `S 3`, `E FELIZ`. Cerrar el Serial Monitor antes de usar Python.

### 2. Programa de la PC

Python 3.10 o más nuevo (probado con 3.13).

```
pip install -r requirements.txt
```

Descargar los modelos de MediaPipe dentro de la carpeta `python` (en PowerShell):

```
Invoke-WebRequest "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" -OutFile "face_landmarker.task"
Invoke-WebRequest "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" -OutFile "pose_landmarker_lite.task"
```

Si falta `best.pt`, las camisetas se detectan con reglas de color HSV y el programa lo avisa en el log.

### 3. Configurar `python/config.py`

| Parámetro | Qué poner |
|---|---|
| `PUERTO_ESP32` | Puerto del ESP32 (Windows: Administrador de dispositivos → Puertos COM y LPT) |
| `INDICE_CAMARA` | Número de la cámara: 0 suele ser la de la notebook, la externa 1 o 2 |
| `SIGNO_YAW`, `SIGNO_PITCH`, `SIGNO_OJOS` | Cambiar el signo si un eje o las pupilas se mueven al revés |

## Ejecución

```
cd python
python prueba_percepcion.py     # solo cámara + IA, sin el robot
python main.py                  # sistema completo
```

| Tecla (ventana del video) | Acción |
|---|---|
| `n` / `t` / `a` / `m` | Modo neutro / tímido / atrevido / maleducado |
| `c` | Cambiar el método de camisetas (YOLO / HSV) |
| `s` / `g` | Detener / seguir |
| `q` | Salir (el robot vuelve a reposo) |

También se pueden escribir comandos en la terminal: `MODE TIMIDO`, `STOP`, `GO`, `CAMISETAS HSV`.

Cada ejecución guarda un log con fecha y hora en `python/logs/`.

## Créditos

MediaPipe (Google) para caras y cuerpos, Ultralytics YOLO para el modelo de camisetas entrenado por el grupo, OpenCV, pySerial y NumPy. La lógica de comportamientos, el árbitro, el control de la mirada y el firmware son desarrollo propio.
# uTP-Robot-Blue
