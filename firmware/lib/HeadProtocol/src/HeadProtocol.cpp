#include "HeadProtocol.h"
#include <HeadSounds.h>
#include <NeckParams.h>

HeadProtocol::HeadProtocol(Stream& port, Neck& neck, ToneSequencer& buzzer, Eyes& eyes)
  : port_(port), neck_(neck), buzzer_(buzzer), eyes_(eyes), len_(0) {}

// Lectura de línea NO bloqueante (readStringUntil espera hasta 1 s si falta el '\n')
void HeadProtocol::update() {
  while (port_.available() > 0) {
    char c = port_.read();
    if (c == '\n') {
      buf_[len_] = 0;
      handleLine(buf_);
      len_ = 0;
    } else if (len_ < sizeof(buf_) - 1) {
      buf_[len_++] = c;
    } else {
      len_ = 0;                     // línea demasiado larga: descartar
      port_.println("ERR: linea demasiado larga");
    }
  }
}

void HeadProtocol::printConfig() {
  for (int i = 0; i < NUM_AXES; i++) {
    const MotionConfig& c = neck_.axis(i).config();
    port_.printf("CFG %s vmax=%.0f amax=%.0f direct=%d step=%.1f home=%.1f lim=%.0f..%.0f\n",
                 Neck::axisName(i), c.vmax, c.amax, c.direct ? 1 : 0, c.step, c.homeDeg,
                 c.minDeg, c.maxDeg);
  }
}

void HeadProtocol::handleLine(char* line) {
  // limpiar espacios y pasar a mayúsculas
  while (*line == ' ') line++;
  for (char* p = line; *p; p++) *p = toupper((unsigned char)*p);
  int n = strlen(line);
  while (n > 0 && (line[n - 1] == ' ' || line[n - 1] == '\r')) line[--n] = 0;
  if (n == 0) return;

  if (strcmp(line, "STOP") == 0) {
    neck_.stop();
    buzzer_.stop();
    eyes_.reset();
    port_.println("ACK: STOP");
  }
  else if (strcmp(line, "HOME") == 0 || strncmp(line, "HOME ", 5) == 0) {
    float ms = 0;
    if (line[4] == ' ') sscanf(line + 5, "%f", &ms);
    if (ms > Neck::MAX_TIMED_MS) ms = Neck::MAX_TIMED_MS;
    neck_.goHome((unsigned long)(ms > 0 ? ms : 0));
    port_.println("ACK: HOME");
  }
  else if (strcmp(line, "Q") == 0) {
    port_.printf("ST %.1f %.1f %.1f %d %d %s\n",
                 neck_.axis(YAW).out(), neck_.axis(PITCH).out(), neck_.axis(ROLL).out(),
                 buzzer_.playing() ? 1 : 0, neck_.moving() ? 1 : 0,
                 Eyes::faceName(eyes_.visibleFace(millis())));
  }
  else if (strncmp(line, "J ", 2) == 0) {
    float y, p, r, ms;
    int k = sscanf(line + 2, "%f %f %f %f", &y, &p, &r, &ms);
    if (k >= 2) {
      bool timed = (k == 4 && ms >= Neck::MIN_TIMED_MS);
      if (timed && ms > Neck::MAX_TIMED_MS) ms = Neck::MAX_TIMED_MS;
      if (timed) {
        neck_.moveTimed(y, p, r, (unsigned long)ms);
      } else {
        neck_.setTarget(YAW, y);
        neck_.setTarget(PITCH, p);
        if (k >= 3) neck_.setTarget(ROLL, r);   // si no viene roll, se mantiene el objetivo actual
      }
      port_.printf("ACK: J -> Yaw:%.1f Pitch:%.1f Roll:%.1f%s\n",
                   neck_.axis(YAW).target(), neck_.axis(PITCH).target(), neck_.axis(ROLL).target(),
                   timed ? " (timed)" : "");
    } else {
      port_.println("ERR: formato J invalido (J yaw pitch [roll [ms]])");
    }
  }
  else if (strncmp(line, "S ", 2) == 0) {
    int id;
    if (sscanf(line + 2, "%d", &id) != 1) {
      port_.println("ERR: formato S invalido");
    } else if (id == 0) {
      buzzer_.stop();
      port_.println("ACK: S 0");
    } else if (buzzer_.playing()) {
      port_.println("ERR: BUSY");            // nunca se superponen sonidos
    } else {
      const Melody* m = findMelody(id);
      if (m && buzzer_.play(*m)) port_.printf("ACK: S %d\n", id);
      else                       port_.println("ERR: sonido desconocido");
    }
  }
  else if (strncmp(line, "EYE ", 4) == 0) {
    float x;
    if (sscanf(line + 4, "%f", &x) == 1) {
      eyes_.setGaze(x);
      port_.printf("ACK: EYE %.2f\n", eyes_.gaze());
    } else {
      port_.println("ERR: EYE x (-1 a 1)");
    }
  }
  else if (strncmp(line, "E ", 2) == 0) {
    char name[16];
    float ms = 0;
    Face f;
    int k = sscanf(line + 2, "%15s %f", name, &ms);
    if (k >= 1 && Eyes::parseFace(name, f)) {
      if (ms < 0) ms = 0;
      if (ms > 60000) ms = 60000;
      eyes_.setFace(f, (unsigned long)ms);
      if (ms > 0) port_.printf("ACK: E %s %.0f\n", Eyes::faceName(f), ms);
      else        port_.printf("ACK: E %s\n", Eyes::faceName(f));
    } else {
      port_.println("ERR: E NORMAL|FELIZ|ENOJADA|DORMIDA [ms]");
    }
  }
  else if (strncmp(line, "PROF ", 5) == 0) {
    int e, d;
    float vm, am;
    if (sscanf(line + 5, "%d %f %f %d", &e, &vm, &am, &d) == 4 &&
        e >= 0 && e < NUM_AXES && vm > 0 && am > 0) {
      neck_.axis(e).setProfile(vm, am, d != 0);
      port_.printf("ACK: PROF %s vmax=%.0f amax=%.0f direct=%d\n", Neck::axisName(e), vm, am, d);
    } else {
      port_.println("ERR: PROF eje(0-2) vmax amax direct(0/1)");
    }
  }
  else if (strncmp(line, "STEP ", 5) == 0) {
    int e;
    float st;
    if (sscanf(line + 5, "%d %f", &e, &st) == 2 && e >= 0 && e < NUM_AXES && st >= 0 && st <= 20) {
      neck_.axis(e).setStep(st);
      port_.printf("ACK: STEP %s %.1f\n", Neck::axisName(e), st);
    } else {
      port_.println("ERR: STEP eje(0-2) grados(0-20)");
    }
  }
  else if (strncmp(line, "SETHOME ", 8) == 0) {
    float h[NUM_AXES];
    if (sscanf(line + 8, "%f %f %f", &h[0], &h[1], &h[2]) == 3) {
      for (int i = 0; i < NUM_AXES; i++) neck_.axis(i).setHome(h[i]);
      port_.printf("ACK: SETHOME %.1f %.1f %.1f\n", neck_.axis(YAW).config().homeDeg,
                   neck_.axis(PITCH).config().homeDeg, neck_.axis(ROLL).config().homeDeg);
    } else {
      port_.println("ERR: SETHOME yaw pitch roll");
    }
  }
  else if (strcmp(line, "DUMP") == 0) {
    printConfig();
  }
  else if (strcmp(line, "SAVE") == 0) {
    neckSaveParams(neck_);
    port_.println("ACK: SAVE");
  }
  else if (strcmp(line, "FACTORY") == 0) {
    neckClearParams();
    port_.println("ACK: FACTORY (reiniciando)");
    delay(100);
    ESP.restart();
  }
  else {
    port_.println("ERR: comando desconocido");
  }
}
