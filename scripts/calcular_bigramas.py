"""
Calcula juego/bigramas.py: qué tan probable es que una letra siga a otra en español.

Usa solo textos en español escritos para este proyecto (el prompt de Holmes, los casos
escritos a mano y el README), así la tabla no depende de ningún corpus externo.

    python scripts/calcular_bigramas.py
"""

from __future__ import annotations

import ast
import math
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from juego.cifrados import ALFABETO, normalizar  # noqa: E402


def textos_del_proyecto() -> str:
    prompt = (RAIZ / "personaje" / "prompt_sistema.md").read_text(encoding="utf-8")
    readme = re.sub(r"```.*?```", " ", (RAIZ / "README.md").read_text(encoding="utf-8"), flags=re.DOTALL)
    arbol = ast.parse((RAIZ / "juego" / "caso_muestra.py").read_text(encoding="utf-8"))
    casos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.keyword) and nodo.arg != "escena_visual":  # escena_visual está en inglés
            casos += [n.value for n in ast.walk(nodo.value) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return "\n".join([prompt, readme, *casos])


def calcular() -> tuple[dict[str, float], int]:
    palabras = normalizar(textos_del_proyecto()).split()
    pares: Counter = Counter()
    desde: Counter = Counter()
    for palabra in palabras:
        marcada = f"^{palabra}$"
        for a, b in zip(marcada, marcada[1:]):
            pares[a + b] += 1
            desde[a] += 1
    tabla = {}
    for a in "^" + ALFABETO:
        total = desde[a] + 0.5 * (len(ALFABETO) + 1)
        for b in ALFABETO + "$":
            tabla[a + b] = round(math.log((pares[a + b] + 0.5) / total), 2)
    return tabla, len(palabras)


def main() -> None:
    tabla, palabras = calcular()
    lineas = ['"""Probabilidad (logaritmo) de que una letra siga a otra en español.', "",
              "Calculada con los textos en español de este mismo proyecto (el prompt de Holmes, los casos",
              "y el README) por scripts/calcular_bigramas.py. ^ marca el inicio de palabra y $ el final.",
              '"""', "", f"# {palabras} palabras de muestra", "BIGRAMAS = {"]
    items = sorted(tabla.items())
    for i in range(0, len(items), 8):
        lineas.append("    " + " ".join(f'"{k}": {v},' for k, v in items[i:i + 8]))
    lineas.append("}")
    destino = RAIZ / "juego" / "bigramas.py"
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {len(tabla)} pares, {palabras} palabras de muestra")


if __name__ == "__main__":
    main()
