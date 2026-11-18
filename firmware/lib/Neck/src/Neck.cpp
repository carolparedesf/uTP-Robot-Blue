#include "Neck.h"

Neck::Neck(const NeckHw& hw, const MotionConfig (&d)[NUM_AXES])
  : hw_(hw), axes_{MotionAxis(d[0]), MotionAxis(d[1]), MotionAxis(d[2])}, lastTick_(0) {
  for (int i = 0; i < NUM_AXES; i++) lastUs_[i] = -1;
}

const char* Neck::axisName(int i) {
  static const char* const names[NUM_AXES] = {"YAW", "PITCH", "ROLL"};
  return (i >= 0 && i < NUM_AXES) ? names[i] : "?";
}

void Neck::begin(unsigned long staggerMs) {
  for (int i = 0; i < NUM_AXES; i++) {
    axes_[i].reset(axes_[i].config().homeDeg);
    servos_[i].attach(hw_.pin[i], hw_.minUs, hw_.maxUs);
    writeAxis(i);
    delay(staggerMs);
  }
  lastTick_ = millis();
}

void Neck::writeAxis(int i) {
  int us = hw_.minUs + (int)lroundf(axes_[i].out() * (hw_.maxUs - hw_.minUs) / 180.0f);
  if (us != lastUs_[i]) {          // resolución de 1 us (~0.09°)
    servos_[i].writeMicroseconds(us);
    lastUs_[i] = us;
  }
}

void Neck::update(unsigned long now) {
  if (now - lastTick_ < TICK_MS) return;
  lastTick_ += TICK_MS;
  if (now - lastTick_ > 10 * TICK_MS) lastTick_ = now;  // si nos atrasamos mucho, resincronizar
  const float dt = TICK_MS / 1000.0f;
  for (int i = 0; i < NUM_AXES; i++) {
    axes_[i].update(dt);
    writeAxis(i);
  }
}

void Neck::setTarget(AxisId id, float deg) { axes_[id].setTarget(deg); }

void Neck::moveTimed(float yaw, float pitch, float roll, unsigned long ms) {
  axes_[YAW].startTimed(yaw, ms);
  axes_[PITCH].startTimed(pitch, ms);
  axes_[ROLL].startTimed(roll, ms);
}

void Neck::goHome(unsigned long ms) {
  for (int i = 0; i < NUM_AXES; i++) {
    float home = axes_[i].config().homeDeg;
    if (ms >= MIN_TIMED_MS) axes_[i].startTimed(home, ms);
    else                    axes_[i].setTarget(home);
  }
}

void Neck::stop() {
  for (int i = 0; i < NUM_AXES; i++) axes_[i].stop();
}

bool Neck::moving() const {
  for (int i = 0; i < NUM_AXES; i++)
    if (axes_[i].moving()) return true;
  return false;
}
