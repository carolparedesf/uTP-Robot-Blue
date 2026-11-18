#pragma once
/*
 * Eyes - ojos animados en una pantalla OLED SSD1306 de 128x64 por I2C.
 * Dibujo de los ojos: trabajo de la compañera (caras, pupila, parpadeo); acá se ordenó como
 * librería y se cambió CUÁNDO se dibuja.
 *
 * Por qué importa cuándo se dibuja: mandar la imagen entera por I2C a 400 kHz tarda ~23 ms
 * (1024 bytes x 9 bits / 400 000 bit/s) y durante ese tiempo el loop() no atiende servos ni
 * comandos. Por eso update() redibuja SOLO cuando cambia algo visible (cara, pupila o parpadeo)
 * y como máximo una vez cada MIN_FRAME_MS.
 *
 * Si la pantalla no responde, begin() devuelve false y todo lo demás sigue funcionando sin ojos.
 */
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

enum Face : uint8_t { FACE_NORMAL = 0, FACE_FELIZ, FACE_ENOJADA, FACE_DORMIDA, NUM_FACES };

class Eyes {
public:
  enum : unsigned long {
    MIN_FRAME_MS  = 50,     // como máximo 20 dibujos por segundo
    BLINK_MS      = 120,    // duración de un parpadeo
    BLINK_MIN_MS  = 2400,   // tiempo al azar entre parpadeos
    BLINK_MAX_MS  = 4800
  };

  Eyes(TwoWire& wire, uint8_t address = 0x3C);

  bool begin();                                    // false si no hay pantalla (el robot sigue)
  bool ok() const { return ok_; }
  void update(unsigned long now);                  // llamar en cada loop()

  void setFace(Face f, unsigned long ms = 0);      // ms > 0: cara temporal, después vuelve sola
  void setGaze(float x);                           // -1 izquierda .. 0 centro .. +1 derecha
  void reset();                                    // NORMAL, mirada al centro, sin cara temporal

  Face visibleFace(unsigned long now) const;
  float gaze() const { return gaze_; }

  static bool        parseFace(const char* name, Face& out);   // "NORMAL", "FELIZ", ...
  static const char* faceName(Face f);

private:
  void draw(Face f, int pupilPx, bool blink);
  void drawEye(int cx, Face f, int pupilPx, bool blink, bool left);

  Adafruit_SSD1306 oled_;
  uint8_t          address_;
  bool             ok_;

  Face          base_, temp_;
  unsigned long tempStart_, tempDur_;
  float         gaze_;

  bool          blinking_;
  unsigned long nextBlink_, blinkStart_;

  bool          drawnOnce_;
  Face          drawnFace_;
  int           drawnPupil_;
  bool          drawnBlink_;
  unsigned long lastDraw_;
};
