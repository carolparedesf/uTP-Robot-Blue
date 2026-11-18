#include "Eyes.h"

static const int W = 128, H = 64;
static const int EYE_L_X = 34, EYE_R_X = 94, EYE_Y = 32;   // centros de los ojos
static const int PUPIL_RANGE = 9;                          // desplazamiento máximo de la pupila (px)

Eyes::Eyes(TwoWire& wire, uint8_t address)
  // reloj I2C a 400 kHz durante y después de cada dibujo
  : oled_(W, H, &wire, -1, 400000UL, 400000UL), address_(address), ok_(false),
    base_(FACE_NORMAL), temp_(FACE_NORMAL), tempStart_(0), tempDur_(0), gaze_(0),
    blinking_(false), nextBlink_(0), blinkStart_(0),
    drawnOnce_(false), drawnFace_(FACE_NORMAL), drawnPupil_(0), drawnBlink_(false), lastDraw_(0) {}

bool Eyes::begin() {
  // periphBegin = false: Wire ya lo inició main() con los pines correctos
  ok_ = oled_.begin(SSD1306_SWITCHCAPVCC, address_, true, false);
  if (ok_) {
    oled_.clearDisplay();
    oled_.display();
    nextBlink_ = millis() + 2500;
  }
  return ok_;
}

// ---------------------------------------------------------------- órdenes
void Eyes::setFace(Face f, unsigned long ms) {
  if (f >= NUM_FACES) return;
  if (ms > 0) {
    temp_ = f;
    tempStart_ = millis();
    tempDur_ = ms;
  } else {
    base_ = f;
    tempDur_ = 0;          // una cara fija cancela la temporal
  }
}

void Eyes::setGaze(float x) {
  if (x < -1.0f) x = -1.0f;
  if (x >  1.0f) x =  1.0f;
  gaze_ = x;
}

void Eyes::reset() {
  base_ = FACE_NORMAL;
  tempDur_ = 0;
  gaze_ = 0;
}

Face Eyes::visibleFace(unsigned long now) const {
  if (tempDur_ > 0 && now - tempStart_ < tempDur_) return temp_;
  return base_;
}

// ---------------------------------------------------------------- reloj
void Eyes::update(unsigned long now) {
  if (!ok_) return;

  // Parpadeo con tiempos al azar
  if (!blinking_ && (long)(now - nextBlink_) >= 0) {
    blinking_ = true;
    blinkStart_ = now;
  }
  if (blinking_ && now - blinkStart_ >= BLINK_MS) {
    blinking_ = false;
    nextBlink_ = now + random(BLINK_MIN_MS, BLINK_MAX_MS);
  }

  // Redibujar solo si cambió algo visible, y no más seguido que MIN_FRAME_MS
  Face f   = visibleFace(now);
  int pupil = (int)lroundf(gaze_ * PUPIL_RANGE);
  bool changed = !drawnOnce_ || f != drawnFace_ || pupil != drawnPupil_ || blinking_ != drawnBlink_;
  if (!changed || now - lastDraw_ < MIN_FRAME_MS) return;

  draw(f, pupil, blinking_);
  drawnOnce_  = true;
  drawnFace_  = f;
  drawnPupil_ = pupil;
  drawnBlink_ = blinking_;
  lastDraw_   = now;
}

// ---------------------------------------------------------------- dibujo (diseño de la compañera)
void Eyes::draw(Face f, int pupilPx, bool blink) {
  oled_.clearDisplay();
  drawEye(EYE_L_X, f, pupilPx, blink, true);
  drawEye(EYE_R_X, f, pupilPx, blink, false);
  oled_.display();                     // ~23 ms: por eso se llama solo cuando hace falta
}

// Ojos redondos de 44 px de diámetro
void Eyes::drawEye(int cx, Face f, int pupilPx, bool blink, bool left) {
  const int cy = EYE_Y;

  if (f == FACE_DORMIDA || blink) {    // ojo cerrado: una línea gruesa
    oled_.drawLine(cx - 17, cy,     cx + 17, cy,     SSD1306_WHITE);
    oled_.drawLine(cx - 17, cy + 1, cx + 17, cy + 1, SSD1306_WHITE);
    return;
  }

  if (f == FACE_FELIZ) {               // arco de alegría
    for (int x = -18; x <= 18; x++) {
      int y = 15 - (x * x) / 25;
      oled_.drawPixel(cx + x, cy - y,     SSD1306_WHITE);
      oled_.drawPixel(cx + x, cy - y + 1, SSD1306_WHITE);
    }
    return;
  }

  oled_.fillCircle(cx, cy, 22, SSD1306_WHITE);           // globo
  int px = cx + pupilPx;
  oled_.fillCircle(px, cy + 2, 10, SSD1306_BLACK);       // pupila
  oled_.fillCircle(px - 3, cy - 2, 3, SSD1306_WHITE);    // brillo

  if (f == FACE_ENOJADA) {             // ceja interior inclinada
    if (left) {
      oled_.drawLine(cx - 19, cy - 17, cx + 18, cy - 6, SSD1306_BLACK);
      oled_.drawLine(cx - 19, cy - 16, cx + 18, cy - 5, SSD1306_BLACK);
    } else {
      oled_.drawLine(cx - 18, cy - 6, cx + 19, cy - 17, SSD1306_BLACK);
      oled_.drawLine(cx - 18, cy - 5, cx + 19, cy - 16, SSD1306_BLACK);
    }
  }
}

// ---------------------------------------------------------------- nombres
static const char* const FACE_NAMES[NUM_FACES] = {"NORMAL", "FELIZ", "ENOJADA", "DORMIDA"};

const char* Eyes::faceName(Face f) { return (f < NUM_FACES) ? FACE_NAMES[f] : "?"; }

bool Eyes::parseFace(const char* name, Face& out) {
  for (uint8_t i = 0; i < NUM_FACES; i++) {
    if (strcmp(name, FACE_NAMES[i]) == 0) { out = (Face)i; return true; }
  }
  return false;
}
