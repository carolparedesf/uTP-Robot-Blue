#pragma once
/*
 * HeadSounds - catálogo de sonidos de la cabeza: id -> melodía.
 * Para agregar un sonido: definir su arreglo de notas en HeadSounds.cpp y agregarlo a la tabla.
 *
 *   1 beep agudo | 2 beep grave | 3 saludo | 4 polca Olimpia | 5 reprobación (Cerro)
 *   6 piropo | 7 sonido S4 de la compañera | 8 R2D2 corto | 9 confirmación de modo
 *   10 neutro | 11 tímido | 12 atrevido | 13 maleducado   (10..13: confirmación de cada modo)
 */
#include <ToneSequencer.h>

const Melody* findMelody(int id);   // nullptr si el id no existe
