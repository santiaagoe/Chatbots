"""
Descarga los relatos de Sherlock Holmes desde Project Gutenberg.

Los textos originales en inglés de Arthur Conan Doyle son de dominio público.
Se guardan en indice_mcp/textos/ sin la cabecera ni el pie de Gutenberg.

Uso:  python scripts/descargar_libros.py
"""

import time
import urllib.request
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "indice_mcp" / "textos"

# Número del libro en Project Gutenberg → nombre del archivo
LIBROS = {
    244: "a_study_in_scarlet",
    2097: "the_sign_of_the_four",
    1661: "the_adventures_of_sherlock_holmes",
    834: "the_memoirs_of_sherlock_holmes",
    2852: "the_hound_of_the_baskervilles",
    108: "the_return_of_sherlock_holmes",
    3289: "the_valley_of_fear",
    2350: "his_last_bow",
    69700: "the_case_book_of_sherlock_holmes",
}


def limpiar(texto: str) -> str:
    """Quita la cabecera y el pie de licencia de Project Gutenberg."""
    inicio = texto.find("*** START OF")
    fin = texto.find("*** END OF")
    if inicio != -1:
        texto = texto[texto.find("\n", inicio) + 1:]
    if fin != -1:
        texto = texto[: texto.rfind("\n", 0, texto.find("*** END OF"))]
    return texto.strip()


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for numero, nombre in LIBROS.items():
        archivo = DESTINO / f"{nombre}.txt"
        if archivo.exists():
            print(f"✓ {nombre} (ya estaba)")
            continue
        url = f"https://www.gutenberg.org/cache/epub/{numero}/pg{numero}.txt"
        try:
            with urllib.request.urlopen(url, timeout=60) as respuesta:
                texto = respuesta.read().decode("utf-8", errors="ignore")
        except Exception as error:  # noqa: BLE001
            print(f"✗ {nombre}: no se pudo descargar ({error})")
            continue
        primera_linea = next((l for l in texto.splitlines() if l.strip()), "")
        archivo.write_text(limpiar(texto), encoding="utf-8")
        print(f"✓ {nombre}  ←  {primera_linea[:70]}")
        time.sleep(1)  # cortesía con los servidores de Gutenberg
    print(f"\nTextos guardados en {DESTINO}")


if __name__ == "__main__":
    main()
