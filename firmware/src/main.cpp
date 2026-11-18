/*
 * Cabeza social 3 GDL - firmware del ESP32  (µTP Robótica Social - Robótica II)
 *
 * Este archivo solo ARMA el sistema: dice qué pines hay, qué valores de fábrica tiene cada eje y
 * conecta las piezas. La lógica vive en lib/ (ver README.md).
 */
#include <Arduino.h>
#include <Wire.h>
#include <ESP32Servo.h>
#include <Neck.h>
#include <NeckParams.h>
#include <ToneSequencer.h>
#include <Eyes.h>
#include <HeadProtocol.h>

// ---------------------------------------------------------------- hardware
constexpr int PIN_YAW    = 18;  // MG996R
constexpr int PIN_PITCH  = 19;  // MG996R
constexpr int PIN_ROLL   = 26;  // MG996R   (antes MG90S)
constexpr int PIN_BUZZER = 25;  // módulo buzzer pasivo MH-FMD, suena con el pin en BAJO

constexpr int     OLED_SDA  = 21;    // pines I2C normales del ESP32
constexpr int     OLED_SCL  = 22;
constexpr uint8_t OLED_ADDR = 0x3C;  // 0x3D dirección alternativa (ver pantalla y jumper)

const NeckHw HW = { {PIN_YAW, PIN_PITCH, PIN_ROLL}, 500, 2500 };   // pulso 500..2500 us = 0..180°

// ---------------------------------------------------------------- valores de fábrica por eje
// 'step' = zona muerta medida del conjunto servo + estructura inicialmente de (yaw 5°, pitch 4°, roll 2°), 
// al modificar los servos utilizados (los 3 mg996r) se utiliza 4° para todos (yaw= pitch= roll= 4°).
// vmax conviene mantenerlo por debajo de la velocidad del servo (MG996R ~350-430 °/s sin carga,
// MG90S ~600-750 °/s) para que cada salto de 'step' termine antes del siguiente.
// El roll (MG90S) arranca en modo directo, que fue lo que mejor funcionó. Luego se modifico por un MG996R en modo indirecto
const MotionConfig DEFAULTS[NUM_AXES] = {
  //          min  max  home  vmax  amax direct step
  /* YAW   */ { 20, 160,  90,   100,  200, false, 0.0f },
  /* PITCH */ { 60, 120,  90,   100,  200, false, 0.0f },
  /* ROLL  */ { 50, 110,  80,   100,  200, false, 0.0f },
};

// ---------------------------------------------------------------- objetos
Neck           neck(HW, DEFAULTS);
ToneSequencer  buzzer(PIN_BUZZER, true, 6);   // activo en bajo (MH-FMD), canal LEDC 6 (temporizador 3)
Eyes           eyes(Wire, OLED_ADDR);
HeadProtocol   protocol(Serial, neck, buzzer, eyes);

void setup() {
  Serial.begin(115200);
  buzzer.begin();                          // primero: deja el buzzer en reposo (sin corriente)
  randomSeed(esp_random());                // parpadeos al azar

  Wire.begin(OLED_SDA, OLED_SCL);
  Wire.setClock(400000);
  if (!eyes.begin()) {
    Serial.println("AVISO: no se encontro la pantalla OLED. El robot sigue funcionando sin ojos.");
  }

  // Los servos solo pueden usar el temporizador 0 del PWM (canales 0, 1, 8 y 9). Así el buzzer,
  // en el canal 6 (temporizador 3), nunca les cambia la frecuencia de 50 Hz.
  ESP32PWM::allocateTimer(0);

  neckLoadParams(neck);   // si hay parámetros guardados, pisan los de fábrica (antes de begin)
  neck.begin();
  Serial.println("MCU listo (v3: cuello + sonidos + ojos). Esperando comandos...");
}

void loop() {
  unsigned long now = millis();
  protocol.update();
  neck.update(now);
  buzzer.update(now);
  eyes.update(now);
}
