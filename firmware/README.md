# Cabeza social 3 GDL - firmware ESP32 (µTP Robótica Social)

## Estructura

```
src/main.cpp            pines, valores de fábrica y conexión de las piezas (único lugar con hardware)
lib/MotionAxis/         un eje: perfil vmax/amax, minimum-jerk, cuantización al paso   (C++ puro)
lib/Neck/               3 MotionAxis + 3 Servo + reloj de 20 ms   |  NeckParams: guardado en NVS
lib/ToneSequencer/      motor no bloqueante de notas para el buzzer
lib/HeadSounds/         catálogo: id de sonido -> melodía
lib/Eyes/               ojos en OLED SSD1306: caras, mirada, parpadeo; redibuja solo si algo cambia
lib/HeadProtocol/       protocolo de texto (J, HOME, STOP, S, E, EYE, Q, PROF, STEP...) sobre cualquier Stream
tools/host_test/        prueba de MotionAxis en la PC (CSV de trayectorias)
```

Dependencias (la flecha significa "usa a"); nada apunta hacia arriba:

```
main.cpp -> HeadProtocol -> Neck -> MotionAxis
                         -> HeadSounds -> ToneSequencer
                         -> Eyes -> Adafruit SSD1306
```

Reglas del diseño: las librerías no conocen pines (los recibe `main`); `MotionAxis` no incluye
Arduino; el protocolo recibe un `Stream&` (hoy `Serial`, mañana WiFi o BLE sin tocar nada más).

## Pines

| Componente | Pin |
|---|---|
| Servo yaw (MG996R) | GPIO 18 |
| Servo pitch (MG996R) | GPIO 19 |
| Servo roll (MG90S) | GPIO 26 |
| Buzzer (módulo MH-FMD, activo en bajo, VCC a 3V3) | GPIO 25 |
| OLED SSD1306 SDA / SCL (dirección 0x3C) | GPIO 21 / 22 |

## Notas de hardware

- El buzzer usa su **propio canal de PWM (LEDC 6, temporizador 3)** y no `tone()`. En el núcleo 2.x,
  `tone()` usa el canal 0, que comparte temporizador con los servos: cada sonido les cambiaba la
  frecuencia de 50 Hz y quedaban descontrolados. `main()` reserva el temporizador 0 para los servos
  con `ESP32PWM::allocateTimer(0)`.
- El módulo MH-FMD suena con el pin en BAJO: en silencio el pin queda en ALTO (sin corriente).
- Si la pantalla no responde, el robot arranca igual (sin ojos) y lo avisa por el puerto serie.
- La pantalla se redibuja solo cuando cambia algo visible: cada dibujo tarda ~23 ms.

## Comandos nuevos (ojos)

| Comando | Qué hace |
|---|---|
| `E NORMAL\|FELIZ\|ENOJADA\|DORMIDA [ms]` | Cara. Con `ms`, temporal: después vuelve sola a la anterior |
| `EYE x` | Mirada de las pupilas: -1 izquierda, 0 centro, +1 derecha (acepta decimales) |
| `STOP` | Además de frenar y callar, deja los ojos en NORMAL y al centro |
| `Q` | Devuelve `ST yaw pitch roll sonando moviendo CARA` |

## Sonidos (`S id`)

| id | Sonido | id | Sonido |
|---|---|---|---|
| 1 | beep agudo | 8 | R2D2 corto |
| 2 | beep grave | 9 | confirmación de modo |
| 3 | saludo | 10 | modo neutro |
| 4 | polca Olimpia | 11 | modo tímido |
| 5 | reprobación (Cerro) | 12 | modo atrevido |
| 6 | piropo | 13 | modo maleducado |
| 7 | sonido S4 de la compañera (uso a definir) | 0 | silencio |

## Compilar

- PlatformIO: abrir esta carpeta y `pio run -t upload`. Las carpetas de `lib/` se detectan solas;
  `ESP32Servo` se descarga por `lib_deps`.
- Arduino IDE: copiar cada carpeta de `lib/` a `Documents/Arduino/libraries/`, instalar `ESP32Servo`
  y usar `src/main.cpp` como sketch (renombrarlo a `.ino`).

## Dónde cayó cada cosa del código anterior

| Antes (un solo archivo)                    | Ahora                                        |
|--------------------------------------------|----------------------------------------------|
| `struct Axis` (estado + config)            | `MotionConfig` + `MotionAxis`                |
| `stepAxis`, perfil, timed, cuantización    | `MotionAxis::update/profileStep/timedStep/quantize` |
| `setTarget`, `startTimed`, `stopMotion`    | `MotionAxis` (por eje) y `Neck` (los 3)      |
| `writeAxis`, `motionTick`, `goHome`        | `Neck`                                       |
| `saveParams`, `loadParams`                 | `NeckParams`                                 |
| `Note`, `soundPlay`, `soundTick`           | `ToneSequencer`                              |
| arreglos de notas y tabla `SOUNDS`         | `HeadSounds`                                 |
| `handleLine`, `serialTick`                 | `HeadProtocol`                               |
| pines, `axes[]` de fábrica, `setup/loop`   | `src/main.cpp`                               |

## Cómo se agrega...

- Un sonido: arreglo de notas + una línea en la tabla de `HeadSounds.cpp`.
- Un comando: una rama más en `HeadProtocol::handleLine`.
- Una cara: un valor más en `Face` y su dibujo en `Eyes::drawEye`.
- Un parámetro guardable: una clave más en `NeckParams.cpp` (y subir `VERSION`).
- Probar la trayectoria sin hardware: ver el encabezado de `tools/host_test/motion_axis_demo.cpp`.
