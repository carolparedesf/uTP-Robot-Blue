#include "NeckParams.h"
#include <Preferences.h>

static const char* NS = "cabeza";
static const uint8_t VERSION = 2;   // subir si cambia el formato guardado

static void key(char* k, size_t n, char tag, int i) { snprintf(k, n, "%c%d", tag, i); }

void neckSaveParams(const Neck& neck) {
  Preferences prefs;
  prefs.begin(NS, false);
  prefs.putUChar("ver", VERSION);
  for (int i = 0; i < NUM_AXES; i++) {
    const MotionConfig& c = neck.axis(i).config();
    char k[8];
    key(k, sizeof k, 'v', i); prefs.putFloat(k, c.vmax);
    key(k, sizeof k, 'a', i); prefs.putFloat(k, c.amax);
    key(k, sizeof k, 's', i); prefs.putFloat(k, c.step);
    key(k, sizeof k, 'h', i); prefs.putFloat(k, c.homeDeg);
    key(k, sizeof k, 'd', i); prefs.putBool(k, c.direct);
  }
  prefs.end();
}

bool neckLoadParams(Neck& neck) {
  Preferences prefs;
  prefs.begin(NS, false);
  bool ok = (prefs.getUChar("ver", 0) == VERSION);
  if (ok) {
    for (int i = 0; i < NUM_AXES; i++) {
      MotionAxis& ax = neck.axis(i);
      const MotionConfig c = ax.config();   // copia: valores por defecto si falta una clave
      char k[8];
      key(k, sizeof k, 'v', i); float v  = prefs.getFloat(k, c.vmax);
      key(k, sizeof k, 'a', i); float am = prefs.getFloat(k, c.amax);
      key(k, sizeof k, 's', i); float s  = prefs.getFloat(k, c.step);
      key(k, sizeof k, 'h', i); float h  = prefs.getFloat(k, c.homeDeg);
      key(k, sizeof k, 'd', i); bool  d  = prefs.getBool(k, c.direct);
      if (v > 0 && am > 0 && s >= 0 && h >= c.minDeg && h <= c.maxDeg) {   // descarta valores corruptos
        ax.setProfile(v, am, d);
        ax.setStep(s);
        ax.setHome(h);
      }
    }
  }
  prefs.end();
  return ok;
}

void neckClearParams() {
  Preferences prefs;
  prefs.begin(NS, false);
  prefs.clear();
  prefs.end();
}
