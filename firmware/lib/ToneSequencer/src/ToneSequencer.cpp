#include "ToneSequencer.h"

static const uint8_t RESOLUCION_BITS = 10;

ToneSequencer::ToneSequencer(int pin, bool activoEnBajo, uint8_t ledcChannel)
  : pin_(pin), activoEnBajo_(activoEnBajo), channel_(ledcChannel), attached_(false),
    notes_(nullptr), len_(0), idx_(0), playing_(false), noteStart_(0), lastFreqUpdate_(0) {}

// ---------------------------------------------------------------- hardware (canal LEDC propio)
void ToneSequencer::sonar(uint32_t hz) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  if (!attached_) {
    ledcAttachChannel(pin_, hz, RESOLUCION_BITS, channel_);
    attached_ = true;
  }
  ledcWriteTone(pin_, hz);
#else
  if (!attached_) {
    ledcAttachPin(pin_, channel_);
    attached_ = true;
  }
  ledcWriteTone(channel_, hz);       // reconfigura SOLO el temporizador de este canal
#endif
}

// Silencio = PWM desconectado y pin fijo en el nivel de reposo (sin corriente por el buzzer)
void ToneSequencer::silencio() {
  if (attached_) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcDetach(pin_);
#else
    ledcWrite(channel_, 0);
    ledcDetachPin(pin_);
#endif
    attached_ = false;
  }
  pinMode(pin_, OUTPUT);
  digitalWrite(pin_, activoEnBajo_ ? HIGH : LOW);
}

// ---------------------------------------------------------------- reproductor
void ToneSequencer::begin() { silencio(); }

void ToneSequencer::stop() {
  silencio();
  playing_ = false;
}

void ToneSequencer::startNote() {
  const Note& n = notes_[idx_];
  if (n.f0 == 0) silencio();
  else           sonar(n.f0);
  lastFreqUpdate_ = millis();
}

bool ToneSequencer::play(const Melody& m) {
  if (playing_ || m.len == 0) return false;
  notes_ = m.notes;
  len_ = m.len;
  idx_ = 0;
  playing_ = true;
  noteStart_ = millis();
  startNote();
  return true;
}

void ToneSequencer::update(unsigned long now) {
  if (!playing_) return;
  const Note& n = notes_[idx_];
  unsigned long el = now - noteStart_;
  if (el >= n.ms) {
    noteStart_ += n.ms;                // acumula para no derivar
    if (++idx_ >= len_) { stop(); return; }
    startNote();
    return;
  }
  // Glissando: actualiza la frecuencia cada ~10 ms
  if (n.f0 != 0 && n.f1 != n.f0 && now - lastFreqUpdate_ >= 10) {
    int32_t f = (int32_t)n.f0 + ((int32_t)n.f1 - (int32_t)n.f0) * (int32_t)el / (int32_t)n.ms;
    sonar((uint32_t)f);
    lastFreqUpdate_ = now;
  }
}
