#pragma once
/*
 * ToneSequencer - reproduce secuencias de notas en un buzzer pasivo SIN bloquear el loop().
 * Solo sabe de notas y tiempos; no sabe qué sonido es cuál (eso está en HeadSounds).
 *
 * activoEnBajo = true para el módulo MH-FMD (suena con el pin en BAJO): en silencio el pin queda
 * en ALTO, así no circula corriente por el buzzer. false = buzzer suelto o con transistor NPN.
 *
 * Canal LEDC propio: NO usa tone() del núcleo. En el núcleo 2.x, tone() usa siempre el canal 0,
 * que comparte temporizador con los primeros servos de ESP32Servo: cada sonido les cambiaba la
 * frecuencia (de 50 Hz a la de la nota) y los servos quedaban descontrolados. Por defecto se usa
 * el canal 6 (temporizador 3), y main() reserva el temporizador 0 para los servos.
 */
#include <Arduino.h>

// Una nota: frecuencia inicial y final (glissando si difieren) y duración. f0 = 0 -> silencio.
struct Note {
  uint16_t f0;
  uint16_t f1;
  uint16_t ms;
};

struct Melody {
  const Note* notes;
  uint8_t     len;
};

class ToneSequencer {
public:
  explicit ToneSequencer(int pin, bool activoEnBajo = true, uint8_t ledcChannel = 6);
  void begin();
  bool play(const Melody& m);          // false si ya hay una sonando
  void stop();
  bool playing() const { return playing_; }
  void update(unsigned long now);      // llamar en cada loop()

private:
  void startNote();
  void sonar(uint32_t hz);             // conecta el PWM al pin y fija la frecuencia
  void silencio();                     // desconecta el PWM y deja el pin en reposo

  int           pin_;
  bool          activoEnBajo_;
  uint8_t       channel_;
  bool          attached_;
  const Note*   notes_;
  uint8_t       len_, idx_;
  bool          playing_;
  unsigned long noteStart_, lastFreqUpdate_;
};
