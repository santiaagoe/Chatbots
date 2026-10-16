"""
Cifrados del juego.

Toda la criptografía la hace este módulo, no la IA: así cada mensaje
cifrado es siempre correcto y descifrable. Gemini solo pone la narración.

Se usa el alfabeto español de 27 letras (con Ñ). Antes de cifrar, el texto
se normaliza: mayúsculas, sin tildes y solo letras y espacios.
"""

from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass, field, asdict

ALFABETO = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"  # 27 letras


# ---------------------------------------------------------------------------
# Normalización y comparación
# ---------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Mayúsculas, sin tildes (conservando la Ñ), solo letras y espacios."""
    texto = texto.upper().replace("Ñ", "\0")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.replace("\0", "Ñ")
    limpio = "".join(c if c in ALFABETO else " " for c in texto)
    return " ".join(limpio.split())


def solo_letras(texto: str) -> str:
    return normalizar(texto).replace(" ", "")


def respuestas_coinciden(propuesta: str, correcta: str) -> bool:
    """Ignora mayúsculas, tildes, puntuación y espacios."""
    return bool(solo_letras(propuesta)) and solo_letras(propuesta) == solo_letras(correcta)


# ---------------------------------------------------------------------------
# Estructura de un mensaje cifrado
# ---------------------------------------------------------------------------

@dataclass
class MensajeCifrado:
    tipo: str                  # identificador, p. ej. "morse"
    mensaje: str               # texto original normalizado (la solución)
    cifrado: str               # versión cifrada en texto
    svg: str | None = None     # solo para los bailarines
    clave: dict = field(default_factory=dict)
    pistas: list[str] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        return CIFRADOS[self.tipo]["nombre"]

    def a_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Morse
# ---------------------------------------------------------------------------

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "Ñ": "--.--", "O": "---", "P": ".--.", "Q": "--.-",
    "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--",
    "X": "-..-", "Y": "-.--", "Z": "--..",
}
MORSE_INV = {v: k for k, v in MORSE.items()}


def morse_cifrar(texto: str) -> str:
    return " / ".join(" ".join(MORSE[c] for c in palabra) for palabra in normalizar(texto).split())


def morse_descifrar(codigo: str) -> str:
    return " ".join(
        "".join(MORSE_INV[s] for s in palabra.split())
        for palabra in codigo.split("/")
    )


# ---------------------------------------------------------------------------
# Espejo
# ---------------------------------------------------------------------------

def espejo_cifrar(texto: str) -> str:
    return normalizar(texto)[::-1]


def espejo_descifrar(codigo: str) -> str:
    return codigo[::-1]


# ---------------------------------------------------------------------------
# Sustituciones: Atbash, César, Vigenère
# ---------------------------------------------------------------------------

def _desplazar(letra: str, n: int) -> str:
    return ALFABETO[(ALFABETO.index(letra) + n) % len(ALFABETO)]


def atbash(texto: str) -> str:
    """Atbash es su propio inverso: A↔Z, B↔Y…"""
    inverso = ALFABETO[::-1]
    return "".join(inverso[ALFABETO.index(c)] if c in ALFABETO else c for c in normalizar(texto))


def cesar_cifrar(texto: str, n: int) -> str:
    return "".join(_desplazar(c, n) if c in ALFABETO else c for c in normalizar(texto))


def cesar_descifrar(codigo: str, n: int) -> str:
    return cesar_cifrar(codigo, -n)


def vigenere_cifrar(texto: str, clave: str, signo: int = 1) -> str:
    clave = solo_letras(clave)
    resultado, i = [], 0
    for c in normalizar(texto):
        if c in ALFABETO:
            resultado.append(_desplazar(c, signo * ALFABETO.index(clave[i % len(clave)])))
            i += 1
        else:
            resultado.append(c)
    return "".join(resultado)


def vigenere_descifrar(codigo: str, clave: str) -> str:
    return vigenere_cifrar(codigo, clave, signo=-1)


# ---------------------------------------------------------------------------
# Bacon (cada letra = 5 símbolos A/B)
# ---------------------------------------------------------------------------

def _bacon_letra(c: str) -> str:
    return format(ALFABETO.index(c), "05b").replace("0", "A").replace("1", "B")


def bacon_cifrar(texto: str) -> str:
    return " / ".join(" ".join(_bacon_letra(c) for c in palabra) for palabra in normalizar(texto).split())


def bacon_descifrar(codigo: str) -> str:
    return " ".join(
        "".join(ALFABETO[int(g.replace("A", "0").replace("B", "1"), 2)] for g in palabra.split())
        for palabra in codigo.split("/")
    )


# ---------------------------------------------------------------------------
# Polibio (rejilla de 6 filas × 5 columnas para las 27 letras)
# ---------------------------------------------------------------------------

def polibio_cifrar(texto: str) -> str:
    def par(c: str) -> str:
        i = ALFABETO.index(c)
        return f"{i // 5 + 1}{i % 5 + 1}"
    return " / ".join(" ".join(par(c) for c in palabra) for palabra in normalizar(texto).split())


def polibio_descifrar(codigo: str) -> str:
    return " ".join(
        "".join(ALFABETO[(int(p[0]) - 1) * 5 + int(p[1]) - 1] for p in palabra.split())
        for palabra in codigo.split("/")
    )


def polibio_filas() -> str:
    """La rejilla en una línea de texto (se lee bien en cualquier nota, sin alinear columnas)."""
    return "; ".join(f"fila {f + 1}: {' '.join(ALFABETO[f * 5:(f + 1) * 5])}" for f in range(6))


def polibio_tabla() -> str:
    filas = ["    1 2 3 4 5"]
    for f in range(6):
        letras = ALFABETO[f * 5:(f + 1) * 5]
        filas.append(f"{f + 1}   " + " ".join(letras))
    return "\n".join(filas)


# ---------------------------------------------------------------------------
# Cerca (rail fence) de 3 rieles
# ---------------------------------------------------------------------------

def _patron_cerca(largo: int, rieles: int) -> list[int]:
    patron, riel, paso = [], 0, 1
    for _ in range(largo):
        patron.append(riel)
        if riel == 0:
            paso = 1
        elif riel == rieles - 1:
            paso = -1
        riel += paso
    return patron


def cerca_cifrar(texto: str, rieles: int = 3) -> str:
    letras = solo_letras(texto)
    patron = _patron_cerca(len(letras), rieles)
    cifrado = "".join(letras[i] for r in range(rieles) for i in range(len(letras)) if patron[i] == r)
    return " ".join(cifrado[i:i + 5] for i in range(0, len(cifrado), 5))


def cerca_descifrar(codigo: str, rieles: int = 3) -> str:
    letras = codigo.replace(" ", "")
    patron = _patron_cerca(len(letras), rieles)
    orden = sorted(range(len(letras)), key=lambda i: (patron[i], i))
    resultado = [""] * len(letras)
    for letra, posicion in zip(letras, orden):
        resultado[posicion] = letra
    return "".join(resultado)


# ---------------------------------------------------------------------------
# Cada tercera palabra (como en "El Gloria Scott")
# ---------------------------------------------------------------------------

RELLENO = [
    "querido", "señor", "mañana", "llegó", "carta", "tiempo", "siempre", "pronto",
    "hermana", "lluvia", "noche", "visita", "jardín", "estimado", "caballo", "salud",
    "viaje", "tren", "buen", "favor", "campo", "madre", "tío", "cena", "hoy",
    "invierno", "noticias", "abrazo", "recuerdos", "también",
]


def tercera_cifrar(texto: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    palabras = []
    for oculta in normalizar(texto).lower().split():
        palabras += rng.sample(RELLENO, 2) + [oculta]
    palabras += rng.sample(RELLENO, 2)
    frase = " ".join(palabras)
    return frase[0].upper() + frase[1:] + "."


def tercera_descifrar(codigo: str) -> str:
    palabras = codigo.rstrip(".").split()
    return " ".join(palabras[2::3]).upper()


# ---------------------------------------------------------------------------
# Los bailarines (figuras propias, 3 × 3 × 3 = 27 posiciones)
# ---------------------------------------------------------------------------

_BRAZO_IZQ = [(6, 8), (3, 20), (7, 32)]    # arriba, horizontal, abajo
_BRAZO_DER = [(30, 8), (33, 20), (29, 32)]
_PIERNAS = [((8, 52), (28, 52)), ((14, 54), (22, 54)), ((5, 42), (24, 54))]
_TINTA = "#2b1d0e"


def _figura(indice: int, x: int, y: int, fin_palabra: bool) -> str:
    a, b, c = indice // 9, (indice // 3) % 3, indice % 3
    (bix, biy), (bdx, bdy) = _BRAZO_IZQ[a], _BRAZO_DER[b]
    (p1x, p1y), (p2x, p2y) = _PIERNAS[c]
    partes = [
        f'<circle cx="{x+18}" cy="{y+9}" r="5" fill="{_TINTA}"/>',
        f'<line x1="{x+18}" y1="{y+14}" x2="{x+18}" y2="{y+34}"/>',
        f'<line x1="{x+18}" y1="{y+20}" x2="{x+bix}" y2="{y+biy}"/>',
        f'<line x1="{x+18}" y1="{y+20}" x2="{x+bdx}" y2="{y+bdy}"/>',
        f'<line x1="{x+18}" y1="{y+34}" x2="{x+p1x}" y2="{y+p1y}"/>',
        f'<line x1="{x+18}" y1="{y+34}" x2="{x+p2x}" y2="{y+p2y}"/>',
    ]
    if fin_palabra:  # bandera en la mano derecha
        partes.append(
            f'<polygon points="{x+bdx},{y+bdy-12} {x+bdx+9},{y+bdy-8} {x+bdx},{y+bdy-4}" fill="{_TINTA}"/>'
            f'<line x1="{x+bdx}" y1="{y+bdy}" x2="{x+bdx}" y2="{y+bdy-12}"/>'
        )
    return "".join(partes)


def _svg(contenido: str, ancho: int, alto: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
        f'width="{ancho}" height="{alto}" style="max-width:100%;height:auto">'
        f'<g stroke="{_TINTA}" stroke-width="2.5" stroke-linecap="round" fill="none">'
        f"{contenido}</g></svg>"
    )


def bailarines_indices(texto: str) -> list[tuple[int, bool]]:
    """Lista de (índice de letra, ¿termina palabra?)."""
    resultado = []
    for palabra in normalizar(texto).split():
        for j, c in enumerate(palabra):
            resultado.append((ALFABETO.index(c), j == len(palabra) - 1))
    return resultado


def bailarines_svg(texto: str, por_fila: int = 12) -> str:
    figuras = bailarines_indices(texto)
    filas = (len(figuras) + por_fila - 1) // por_fila
    contenido = "".join(
        _figura(idx, (i % por_fila) * 42 + 4, (i // por_fila) * 66 + 6, fin)
        for i, (idx, fin) in enumerate(figuras)
    )
    return _svg(contenido, min(len(figuras), por_fila) * 42 + 8, filas * 66 + 6)


def bailarines_leyenda() -> str:
    """Tabla con todas las figuras y su letra (se entrega como última pista)."""
    contenido = []
    for i, letra in enumerate(ALFABETO):
        x, y = (i % 9) * 46 + 6, (i // 9) * 84 + 4
        contenido.append(_figura(i, x, y, False))
        contenido.append(
            f'<text x="{x+18}" y="{y+74}" text-anchor="middle" font-family="Georgia, serif" '
            f'font-size="15" fill="{_TINTA}" stroke="none">{letra}</text>'
        )
    return _svg("".join(contenido), 9 * 46 + 8, 3 * 84 + 6)


def bailarines_descifrar(indices: list[tuple[int, bool]]) -> str:
    texto = ""
    for idx, fin in indices:
        texto += ALFABETO[idx] + (" " if fin else "")
    return texto.strip()


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

CLAVES_VIGENERE = ["BAKER", "WATSON", "LONDRES", "HUDSON", "ADLER", "VIOLIN"]

CIFRADOS: dict[str, dict] = {
    "morse": {"nombre": "Código Morse", "dificultad": "fácil"},
    "espejo": {"nombre": "Escritura en espejo", "dificultad": "fácil"},
    "atbash": {"nombre": "Atbash", "dificultad": "fácil"},
    "cesar": {"nombre": "Cifrado César", "dificultad": "medio"},
    "bacon": {"nombre": "Cifrado de Bacon", "dificultad": "medio"},
    "polibio": {"nombre": "Cuadrado de Polibio", "dificultad": "medio"},
    "cerca": {"nombre": "Cifrado de la cerca (rail fence)", "dificultad": "medio"},
    "vigenere": {"nombre": "Cifrado de Vigenère", "dificultad": "difícil"},
    "tercera": {"nombre": "Mensaje oculto cada tercera palabra", "dificultad": "difícil"},
    "bailarines": {"nombre": "Los bailarines", "dificultad": "difícil"},
}

DIFICULTADES = ["fácil", "medio", "difícil"]


def nombres_para_elegir() -> list[str]:
    return [datos["nombre"] for datos in CIFRADOS.values()]


def tipo_por_nombre(nombre: str) -> str | None:
    for tipo, datos in CIFRADOS.items():
        if datos["nombre"] == nombre:
            return tipo
    return None


def cifrar(mensaje: str, tipo: str, rng: random.Random | None = None) -> MensajeCifrado:
    """Cifra un mensaje con el tipo indicado y prepara sus tres pistas."""
    rng = rng or random.Random()
    m = normalizar(mensaje)
    if not m:
        raise ValueError("El mensaje no tiene letras para cifrar.")

    if tipo == "morse":
        return MensajeCifrado(tipo, m, morse_cifrar(m), pistas=[
            "Observe que solo hay dos signos distintos, uno breve y uno largo. Un telegrafista no dudaría.",
            "Es el alfabeto de los telegrafistas: la E es un solo punto y la T una sola raya.",
            "Es código Morse; las barras separan palabras. Por ejemplo, la A es «.-» y la S es «...».",
        ])
    if tipo == "espejo":
        return MensajeCifrado(tipo, m, espejo_cifrar(m), pistas=[
            "Las letras son las de siempre; lo extraño es el orden. ¿Ha probado a mirarlo desde el otro extremo?",
            "Nada se ha sustituido: el mensaje está entero, solo que dado vuelta.",
            "Léalo de derecha a izquierda, como si lo viera reflejado en un espejo.",
        ])
    if tipo == "atbash":
        return MensajeCifrado(tipo, m, atbash(m), pistas=[
            "Cada letra ha sido reemplazada por otra, siempre la misma. Un método antiquísimo, anterior a Cristo.",
            "El alfabeto se ha doblado sobre sí mismo: el principio se encuentra con el final.",
            "La A vale Z, la B vale Y, la C vale X… (alfabeto de 27 letras, con Ñ).",
        ])
    if tipo == "cesar":
        n = rng.randint(3, 9)
        return MensajeCifrado(tipo, m, cesar_cifrar(m, n), clave={"desplazamiento": n}, pistas=[
            "Cada letra ocupa el lugar de otra, pero el orden del alfabeto se ha conservado.",
            "Un general romano usaba este truco: desplazar todas las letras el mismo número de posiciones.",
            f"Retroceda cada letra {n} posiciones en el alfabeto (de 27 letras, con Ñ).",
        ])
    if tipo == "bacon":
        return MensajeCifrado(tipo, m, bacon_cifrar(m), pistas=[
            "Solo dos letras y siempre en grupos de cinco. Cada grupo es una letra del mensaje.",
            "Lo ideó un filósofo inglés del siglo XVII. Piense en A como 0 y en B como 1.",
            "Cada grupo es un número en binario (A=0, B=1) que indica la posición de la letra: AAAAA=A, AAAAB=B, AAABA=C… (alfabeto con Ñ).",
        ])
    if tipo == "polibio":
        return MensajeCifrado(tipo, m, polibio_cifrar(m), clave={"tabla": polibio_tabla()}, pistas=[
            "Cada letra se ha convertido en un par de cifras; ninguna cifra pasa de 6.",
            "Imagine una rejilla: la primera cifra indica la fila y la segunda, la columna.",
            "Rejilla de 6 filas y 5 columnas con el alfabeto en orden; la primera cifra es la fila y la "
            "segunda, la columna (A=11, E=15, F=21). " + polibio_filas() + ".",
        ])
    if tipo == "cerca":
        return MensajeCifrado(tipo, m, cerca_cifrar(m), clave={"rieles": 3}, pistas=[
            "Están todas las letras del mensaje, ninguna cambiada. Solo se ha alterado su orden.",
            "Imagine el mensaje escrito en zigzag sobre varias líneas, como los listones de una cerca.",
            "Tres rieles: escriba el mensaje en zigzag bajando y subiendo por tres filas; el texto cifrado es la fila 1, luego la 2, luego la 3. Los espacios no cuentan.",
        ])
    if tipo == "vigenere":
        clave = rng.choice(CLAVES_VIGENERE)
        return MensajeCifrado(tipo, m, vigenere_cifrar(m, clave), clave={"palabra": clave}, pistas=[
            "Es una sustitución, pero la misma letra no siempre se transforma igual. Un cifrado que muchos llaman indescifrable.",
            "Es como un César con varios desplazamientos que se repiten, dictados por una palabra clave.",
            f"Es Vigenère y la palabra clave es «{clave}». Reste a cada letra la posición de la letra de la clave (A=0, B=1…).",
        ])
    if tipo == "tercera":
        return MensajeCifrado(tipo, m, tercera_cifrar(m, rng), pistas=[
            "Una carta absurda. Nadie escribe así… salvo que quiera ocultar algo entre palabras inocentes.",
            "No lea todas las palabras: el mensaje verdadero sigue un ritmo regular.",
            "Lea solo una de cada tres palabras, empezando por la tercera.",
        ])
    if tipo == "bailarines":
        indices = bailarines_indices(m)
        return MensajeCifrado(
            tipo, m, "[figuras danzantes]", svg=bailarines_svg(m),
            clave={"indices": indices}, pistas=[
                "Cada figurita es una letra. Las que sostienen una bandera señalan el final de una palabra.",
                "Fíjese en las tres partes de cada figura: brazo izquierdo, brazo derecho y piernas. Cada una tiene tres posiciones.",
                "Le entrego mi tabla completa de figuras. Compare una por una.",
            ])
    raise ValueError(f"Tipo de cifrado desconocido: {tipo}")


def cifrar_al_azar(mensaje: str, dificultad: str, evitar: list[str] | None = None,
                   rng: random.Random | None = None) -> MensajeCifrado:
    """Elige un cifrado de la dificultad dada, sin repetir los recién usados."""
    rng = rng or random.Random()
    candidatos = [t for t, d in CIFRADOS.items() if d["dificultad"] == dificultad]
    frescos = [t for t in candidatos if t not in (evitar or [])]
    return cifrar(mensaje, rng.choice(frescos or candidatos), rng)
