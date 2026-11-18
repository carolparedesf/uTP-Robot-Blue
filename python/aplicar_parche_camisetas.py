"""
aplicar_parche_camisetas.py - agrega el metodo YOLO de camisetas a tus archivos actuales.

Modifica config.py, percepcion.py, operador.py, main.py y monitor.py. Antes de tocar cada
uno guarda una copia con extension .bak. Es seguro correrlo dos veces (lo ya aplicado se salta).
camisetas.py NO lo toca: ese se reemplaza entero por el que se entrega aparte.

Uso (en la carpeta del robot):   python aplicar_parche_camisetas.py
O con otra carpeta:              python aplicar_parche_camisetas.py "C:\\ruta\\al\\proyecto"
"""

import re
import shutil
import sys
from pathlib import Path

# Cada parche: (marca, patron regex (re.M), reemplazo, obligatorio)
#   marca: si este texto ya esta en el archivo, el parche se considera aplicado
PARCHES = {
    "config.py": [
        ("CAMISETA_METODO",
         r"^# SALIENDO: la persona seguida",
         '# CAMISETA con modelo propio (YOLO entrenado en Colab). Se alterna con las reglas HSV\n'
         '# en ejecucion: tecla c en la ventana del video, o CAMISETAS [HSV|YOLO] en la terminal.\n'
         'CAMISETA_METODO = "YOLO"                 # metodo al arrancar: "HSV" o "YOLO"\n'
         'MODELO_CAMISETAS = os.path.join(CARPETA, "best.pt")   # pesos del Colab (junto a los .py)\n'
         'CONFIANZA_YOLO = 0.4\n'
         'IMGSZ_YOLO = 640                         # bajar a 416 si no se llega a 10 Hz\n'
         'MARGEN_ASIGNACION_YOLO = 0.5             # una camiseta se asigna a la persona si su centro cae\n'
         '                                         # dentro del torso agrandado en esta fraccion\n'
         '# Nombre de clase del modelo (minusculas; basta con que lo contenga) -> camiseta\n'
         'CLASES_YOLO = {"olimpia": "OLIMPIA", "cerro": "CERRO"}\n'
         '\n'
         '# SALIENDO: la persona seguida',
         True),
    ],
    "percepcion.py": [
        ("ClasificadorCamisetas",
         r"^from camisetas import clasificar$",
         "from camisetas import ClasificadorCamisetas",
         True),
        ("self.camisetas = ClasificadorCamisetas",
         r"\n\n    def caras\(self, frame\):",
         "\n        self.camisetas = ClasificadorCamisetas() if config.USAR_CAMISETAS else None"
         "\n\n    def caras(self, frame):",
         True),
        ("self.camisetas.clasificar_todas",
         r"if config\.USAR_CAMISETAS:\s+for cara in caras:\s+cara\.camiseta = clasificar\(frame, cara\)",
         "if self.camisetas is not None and caras:\n"
         "            self.camisetas.clasificar_todas(frame, caras)",
         True),
    ],
    "operador.py": [
        ("import config",
         r"^import threading$",
         "import threading\n\nimport config",
         True),
        ("METODOS_CAMISETA",
         r"^(MODOS = .*)$",
         r'\1\nMETODOS_CAMISETA = ("HSV", "YOLO")',
         True),
        ('ord("c"): "CAMISETAS"',
         r'ord\("s"\): "STOP", ord\("g"\): "GO",',
         'ord("s"): "STOP", ord("g"): "GO", ord("c"): "CAMISETAS",',
         True),
        ("self.metodo_camisetas = config",
         r"^( +)self\.confirmar = None[^\n]*$",
         r"\g<0>\n\1self.metodo_camisetas = config.CAMISETA_METODO   # HSV o YOLO",
         True),
        ('partes[0] in ("CAMISETAS", "CAMISETA")',
         r'^        elif partes\[0\] == "STOP":',
         '        elif partes[0] in ("CAMISETAS", "CAMISETA"):\n'
         '            if len(partes) == 1:\n'
         '                nuevo = "YOLO" if self.metodo_camisetas == "HSV" else "HSV"\n'
         '            elif len(partes) == 2 and partes[1] in METODOS_CAMISETA:\n'
         '                nuevo = partes[1]\n'
         '            else:\n'
         '                log.warning(f"OPERADOR | metodo de camisetas desconocido: {comando} "\n'
         '                            f"(validos: CAMISETAS, CAMISETAS {\' | \'.join(METODOS_CAMISETA)})")\n'
         '                return\n'
         '            if nuevo != self.metodo_camisetas:\n'
         '                log.info(f"OPERADOR | camisetas {self.metodo_camisetas} -> {nuevo}")\n'
         '                self.metodo_camisetas = nuevo\n'
         '        elif partes[0] == "STOP":',
         True),
    ],
    "main.py": [
        ("fijar_metodo",
         r"^            ahora = time\.monotonic\(\)$",
         "            if percepcion.camisetas is not None:                 # metodo de camisetas (HSV/YOLO)\n"
         "                percepcion.camisetas.fijar_metodo(operador.metodo_camisetas)\n"
         "            ahora = time.monotonic()",
         True),
        ('info["camisetas"]',
         r"^( +)info = armar_info\(.*\)$",
         r'\g<0>\n\1if percepcion.camisetas is not None:\n'
         r'\1    info["camisetas"] = percepcion.camisetas.metodo_efectivo',
         True),
        ("cambiar el metodo de camisetas",
         r"^    s = STOP +g = GO \(seguir\) +q = salir$",
         "    c = cambiar el metodo de camisetas (HSV <-> YOLO)\n"
         "    s = STOP    g = GO (seguir)    q = salir",
         False),
    ],
    "monitor.py": [
        ("resultado.descripcion()",
         r'(?s)_texto\(frame, f"B\{resultado\.blanco.*?escala=0\.38, x=x0\)',
         "_texto(frame, resultado.descripcion(),\n"
         "               min(frame.shape[0] - 120, y1 + 14), color_torso, escala=0.38, x=x0)",
         True),
        ("Camisetas: ",
         r'^        if info\.get\("detenido"\):',
         '        if "camisetas" in info:\n'
         '            _texto(frame, f"Camisetas: {info[\'camisetas\']}", 125, AMARILLO, escala=0.6)\n'
         '        if info.get("detenido"):',
         True),
    ],
}


def aplicar(carpeta):
    errores = []
    for nombre, parches in PARCHES.items():
        ruta = carpeta / nombre
        if not ruta.exists():
            errores.append(f"{nombre}: no se encuentra en {carpeta}")
            continue
        crudo = ruta.read_bytes().decode("utf-8")
        crlf = "\r\n" in crudo
        texto = crudo.replace("\r\n", "\n")

        cambios = 0
        for marca, patron, reemplazo, obligatorio in parches:
            if marca in texto:
                continue                      # ya aplicado
            nuevo, n = re.subn(patron, lambda m, r=reemplazo: m.expand(r), texto,
                               count=1, flags=re.M)
            if n == 0:
                if obligatorio:
                    errores.append(f"{nombre}: no se encontro el punto de insercion "
                                   f"para '{marca}' (patron: {patron[:50]}...)")
                else:
                    print(f"  (opcional, se omite) {nombre}: '{marca}'")
                continue
            texto = nuevo
            cambios += 1

        if cambios and not any(e.startswith(nombre) for e in errores):
            shutil.copy2(ruta, ruta.with_suffix(ruta.suffix + ".bak"))
            ruta.write_bytes((texto.replace("\n", "\r\n") if crlf else texto).encode("utf-8"))
            print(f"OK   {nombre}: {cambios} cambio(s)  (copia en {nombre}.bak)")
        elif not cambios and not any(e.startswith(nombre) for e in errores):
            print(f"--   {nombre}: ya estaba aplicado")
    return errores


def main():
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    errores = aplicar(carpeta)
    if errores:
        print("\nNo se pudo aplicar todo:")
        for e in errores:
            print("  -", e)
        print("Los archivos con error quedaron sin modificar.")
        sys.exit(1)
    print("\nListo. Falta copiar camisetas.py (el nuevo) y best.pt a la carpeta, y pip install ultralytics.")


if __name__ == "__main__":
    main()
