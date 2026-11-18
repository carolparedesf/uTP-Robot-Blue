#include "MotionAxis.h"
#include <math.h>

static float clampf(float v, float lo, float hi) {
  return v < lo ? lo : (v > hi ? hi : v);
}

MotionAxis::MotionAxis(const MotionConfig& cfg)
  : cfg_(cfg), pos_(cfg.homeDeg), vel_(0), target_(cfg.homeDeg), out_(cfg.homeDeg),
    timed_(false), p0_(0), tElapsed_(0), tDur_(0) {}

// ---------------------------------------------------------------- configuración
void MotionAxis::setProfile(float vmax, float amax, bool direct) {
  cfg_.vmax = vmax;
  cfg_.amax = amax;
  cfg_.direct = direct;
}

void MotionAxis::setStep(float step) { cfg_.step = step; }

void MotionAxis::setHome(float deg) { cfg_.homeDeg = clampf(deg, cfg_.minDeg, cfg_.maxDeg); }

// ---------------------------------------------------------------- órdenes
void MotionAxis::reset(float deg) {
  pos_ = target_ = out_ = deg;
  vel_ = 0;
  timed_ = false;
}

// Objetivo con perfil vmax/amax. Cancela un movimiento con duración en curso y conserva
// la velocidad que llevaba, así no hay saltos de velocidad.
void MotionAxis::setTarget(float deg) {
  target_ = clampf(deg, cfg_.minDeg, cfg_.maxDeg);
  timed_ = false;
}

void MotionAxis::startTimed(float deg, unsigned long ms) {
  target_   = clampf(deg, cfg_.minDeg, cfg_.maxDeg);
  p0_       = pos_;
  tElapsed_ = 0;
  tDur_     = ms / 1000.0f;
  timed_    = true;
  vel_      = 0;
}

// Nuevo objetivo = punto donde se detendría frenando con amax
void MotionAxis::stop() {
  float dist = cfg_.direct ? 0.0f : (vel_ * fabsf(vel_)) / (2.0f * cfg_.amax);
  setTarget(pos_ + dist);
}

void MotionAxis::update(float dt) {
  if (timed_)            timedStep(dt);
  else if (cfg_.direct)  { pos_ = target_; vel_ = 0; }
  else                   profileStep(dt);
  quantize();
}

bool MotionAxis::moving() const {
  return timed_ || vel_ != 0 || pos_ != target_ || out_ != pos_;
}

// ---------------------------------------------------------------- trayectorias
// Perfil con límite de aceleración y frenado anticipado:
// vdes = min(vmax, sqrt(2*amax*distancia)); la velocidad real se acerca a vdes como máximo amax*dt.
void MotionAxis::profileStep(float dt) {
  float err  = target_ - pos_;
  float dist = fabsf(err);
  float vdes = sqrtf(2.0f * cfg_.amax * dist);
  if (vdes > cfg_.vmax) vdes = cfg_.vmax;
  if (err < 0) vdes = -vdes;

  float dv = cfg_.amax * dt;
  if      (vdes > vel_ + dv) vel_ += dv;
  else if (vdes < vel_ - dv) vel_ -= dv;
  else                       vel_ = vdes;

  pos_ += vel_ * dt;

  bool cruzo = (err > 0 && pos_ > target_) || (err < 0 && pos_ < target_);
  if (cruzo || (dist < 0.05f && fabsf(vel_) < 1.0f)) {
    pos_ = target_;
    vel_ = 0;
  }
}

// Minimum-jerk: s(τ) = 10τ³ - 15τ⁴ + 6τ⁵, τ = t/T. Velocidad y aceleración nulas en los extremos.
void MotionAxis::timedStep(float dt) {
  tElapsed_ += dt;
  float tau = tElapsed_ / tDur_;
  if (tau >= 1.0f) {
    pos_ = target_;
    vel_ = 0;
    timed_ = false;
    return;
  }
  float t2 = tau * tau, t3 = t2 * tau;
  float D = target_ - p0_;
  pos_ = p0_ + D * (10.0f * t3 - 15.0f * t3 * tau + 6.0f * t3 * t2);
  vel_ = D / tDur_ * (30.0f * t2 - 60.0f * t3 + 30.0f * t3 * tau);
}

// ---------------------------------------------------------------- cuantización
// out solo se mueve en múltiplos de 'step' cuando el perfil se aleja lo suficiente; tras cada
// salto queda pegado al perfil, así que no hay vaivén en el umbral. En reposo se ajusta exacto.
void MotionAxis::quantize() {
  bool salto  = cfg_.direct && !timed_;                    // un salto directo no se cuantiza
  bool reposo = !timed_ && vel_ == 0.0f && pos_ == target_;
  if (salto || reposo || cfg_.step <= 0.0f) {
    out_ = pos_;
    return;
  }
  float d  = pos_ - out_;
  float ad = fabsf(d);
  if (ad >= cfg_.step) {
    int n = (int)(ad / cfg_.step);
    out_ += copysignf(n * cfg_.step, d);
  }
}
