#pragma once
/*
 * Neck - cuello de 3 servos (yaw, pitch, roll).
 * Une tres MotionAxis con tres objetos Servo, y corre el reloj de 20 ms (= período del PWM de
 * servo, una actualización por trama). No sabe qué pines hay: los recibe de quien lo arma (main).
 */
#include <Arduino.h>
#include <ESP32Servo.h>
#include <MotionAxis.h>

enum AxisId : uint8_t { YAW = 0, PITCH = 1, ROLL = 2, NUM_AXES = 3 };

struct NeckHw {
  int pin[NUM_AXES];  // pin de señal de cada servo
  int minUs;          // pulso a 0°
  int maxUs;          // pulso a 180°
};

class Neck {
public:
  enum : unsigned long {
    TICK_MS      = 20,      // período de actualización
    MIN_TIMED_MS = 40,      // duración mínima de un movimiento con duración
    MAX_TIMED_MS = 10000
  };

  Neck(const NeckHw& hw, const MotionConfig (&defaults)[NUM_AXES]);

  // Adjunta los servos en HOME, escalonados (evita el pico de corriente de arrancar los 3 juntos).
  // Si hay parámetros guardados (neckLoadParams), cargarlos ANTES de llamar a begin().
  void begin(unsigned long staggerMs = 250);
  void update(unsigned long now);              // llamar en cada loop()

  void setTarget(AxisId id, float deg);        // perfil vmax/amax
  void moveTimed(float yaw, float pitch, float roll, unsigned long ms);  // los 3 llegan juntos
  void goHome(unsigned long ms = 0);           // ms = 0 -> perfil vmax/amax
  void stop();                                 // frena con rampa donde esté
  bool moving() const;

  MotionAxis&       axis(int i)       { return axes_[i]; }
  const MotionAxis& axis(int i) const { return axes_[i]; }
  static const char* axisName(int i);

private:
  void writeAxis(int i);

  NeckHw        hw_;
  MotionAxis    axes_[NUM_AXES];
  Servo         servos_[NUM_AXES];
  int           lastUs_[NUM_AXES];
  unsigned long lastTick_;
};
