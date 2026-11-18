#pragma once
/*
 * MotionAxis - lógica de movimiento de UN eje. C++ puro: no incluye Arduino ni toca hardware,
 * así que se puede probar en la PC (ver tools/host_test).
 *
 * Tres piezas, en este orden dentro de update(dt):
 *   1) Generación de trayectoria:
 *        - perfil vmax/amax con frenado anticipado   (seguimiento: el objetivo cambia seguido)
 *        - minimum-jerk con duración fija            (gestos: llegar en 'ms' milisegundos)
 *        - salto directo                             (cuando el perfil no ayuda, p. ej. MG90S)
 *   2) Cuantización al paso mínimo del servo (zona muerta + juego mecánico):
 *        la posición que sale (out) avanza en múltiplos de 'step', así el servo recibe
 *        saltos limpios en vez de incrementos que ignora y ejecuta de golpe.
 *   3) Al llegar al reposo, out se ajusta al valor exacto.
 */

struct MotionConfig {
  float minDeg;   // límites articulares por software
  float maxDeg;
  float homeDeg;  // reposo
  float vmax;     // °/s   (perfil de seguimiento)
  float amax;     // °/s²
  bool  direct;   // true: salta directo al objetivo, sin perfil
  float step;     // paso mínimo en grados; 0 = salida continua (sin cuantizar)
};

class MotionAxis {
public:
  explicit MotionAxis(const MotionConfig& cfg);

  // --- configuración (ajustable en caliente) ---
  const MotionConfig& config() const { return cfg_; }
  void setProfile(float vmax, float amax, bool direct);
  void setStep(float step);
  void setHome(float deg);                    // se recorta a los límites

  // --- órdenes ---
  void reset(float deg);                      // pos = target = out = deg, sin movimiento
  void setTarget(float deg);                  // perfil vmax/amax (cancela un movimiento con duración)
  void startTimed(float deg, unsigned long ms);  // minimum-jerk desde la posición actual
  void stop();                                // frena con rampa donde esté
  void update(float dt);                      // avanza dt segundos

  // --- estado ---
  float pos() const    { return pos_; }       // posición ideal del perfil
  float out() const    { return out_; }       // posición que se manda al servo (cuantizada)
  float vel() const    { return vel_; }
  float target() const { return target_; }
  bool  timed() const  { return timed_; }
  bool  moving() const;

private:
  void profileStep(float dt);
  void timedStep(float dt);
  void quantize();

  MotionConfig cfg_;
  float pos_, vel_, target_, out_;
  bool  timed_;
  float p0_, tElapsed_, tDur_;                // movimiento con duración: inicio, transcurrido, total (s)
};
