#pragma once
/*
 * NeckParams - persistencia de los parámetros del cuello en la memoria no volátil (NVS) del ESP32.
 * Guarda por eje: vmax, amax, direct, step y home. Los límites articulares NO se guardan
 * (son seguridad mecánica: viven en el código).
 */
#include "Neck.h"

bool neckLoadParams(Neck& neck);          // true si había datos válidos. Llamar antes de neck.begin()
void neckSaveParams(const Neck& neck);
void neckClearParams();                   // borra lo guardado (valores de fábrica en el próximo arranque)
