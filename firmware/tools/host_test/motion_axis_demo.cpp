// Prueba en la PC (sin ESP32) de MotionAxis: imprime la trayectoria como CSV para graficar o
// pegar en el informe.
//
// Compilar y correr (desde la raíz del proyecto):
//   g++ -std=c++11 -Ilib/MotionAxis/src tools/host_test/motion_axis_demo.cpp lib/MotionAxis/src/MotionAxis.cpp -o demo
//   ./demo > trayectoria.csv
//
// Columnas: t_ms, escenario, pos (perfil ideal), out (lo que recibe el servo), vel
#include <cstdio>
#include "MotionAxis.h"

static void correr(const char* nombre, MotionAxis& ax, float tiempo_s) {
  const float dt = 0.02f;                      // 20 ms, igual que el firmware
  for (int i = 0; i <= (int)(tiempo_s / dt); i++) {
    printf("%d,%s,%.2f,%.2f,%.1f\n", i * 20, nombre, ax.pos(), ax.out(), ax.vel());
    ax.update(dt);
  }
}

int main() {
  printf("t_ms,escenario,pos,out,vel\n");

  MotionConfig yaw = {20, 160, 90, 90, 300, false, 4.0f};       // como el yaw real
  MotionAxis a(yaw);
  a.setTarget(130);
  correr("perfil_step5", a, 1.0f);

  MotionAxis b(yaw);
  b.setStep(0);                                                    // mismo movimiento, sin cuantizar
  b.setTarget(130);
  correr("perfil_continuo", b, 1.0f);

  MotionAxis c(yaw);
  c.startTimed(130, 600);                                          // gesto: llega en 600 ms
  correr("timed_600ms", c, 0.8f);
  return 0;
}
