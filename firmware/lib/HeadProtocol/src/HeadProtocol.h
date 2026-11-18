#pragma once
/*
 * HeadProtocol - protocolo de texto PC <-> MCU. Lee líneas de un Stream (Serial, y mañana WiFi o
 * BLE sin tocar nada más) sin bloquear, y las traduce a llamadas sobre Neck y ToneSequencer.
 *
 * Una línea por comando, terminada en \n; no distingue mayúsculas:
 *   J yaw pitch [roll [ms]]   objetivo en grados. Con ms (>= 40): llega en ese tiempo (gestos).
 *   HOME [ms]                 reposo
 *   STOP                      frena con rampa, silencia el buzzer y pone los ojos en NORMAL
 *   S id                      sonido (S 0 = silencio). Si ya suena otro -> ERR: BUSY
 *   E cara [ms]               ojos: NORMAL | FELIZ | ENOJADA | DORMIDA. Con ms: temporal
 *   EYE x                     hacia dónde miran las pupilas: -1 izquierda .. 0 centro .. +1 derecha
 *   Q                         estado: "ST yaw pitch roll snd moving cara"
 *   PROF eje vmax amax direct | STEP eje grados | SETHOME y p r | DUMP | SAVE | FACTORY   (ajuste)
 */
#include <Arduino.h>
#include <Neck.h>
#include <ToneSequencer.h>
#include <Eyes.h>

class HeadProtocol {
public:
  HeadProtocol(Stream& port, Neck& neck, ToneSequencer& buzzer, Eyes& eyes);
  void update();                  // llamar en cada loop(): lee bytes y ejecuta líneas completas
  void handleLine(char* line);    // público para poder probarlo sin puerto

private:
  void printConfig();

  Stream&        port_;
  Neck&          neck_;
  ToneSequencer& buzzer_;
  Eyes&          eyes_;
  char           buf_[64];
  uint8_t        len_;
};
