"""
El índice de Sherlock Holmes: un servidor MCP.

En los relatos, Holmes guarda un índice de recortes y fichas sobre casos y
criminales que consulta constantemente. Este servidor MCP es ese índice:
expone herramientas para buscar en los textos originales de Conan Doyle
(dominio público, Project Gutenberg).

Gemini decide por sí mismo cuándo consultarlo (por ejemplo, si el visitante
pregunta por un caso antiguo o Holmes quiere citarse a sí mismo).

Uso:
  - Desde la app: se conecta en memoria (ver juego/motor.py).
  - Como servidor independiente (stdio), útil para otros clientes MCP:
        python indice_mcp/servidor.py

Los textos se descargan con:  python scripts/descargar_libros.py
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from fastmcp import FastMCP

CARPETA_TEXTOS = Path(__file__).parent / "textos"
TAMANO_FRAGMENTO = 900  # caracteres aproximados por fragmento

# Palabras demasiado comunes en inglés que no ayudan a buscar
VACIAS = set("""
a an and are as at be but by for from had has have he her his i in is it its me my
not of on or she so that the their them then there they this to was we were which
who will with you your said upon one would been all very what into no could when
""".split())

mcp = FastMCP(
    name="Índice de Sherlock Holmes",
    instructions=(
        "Archivo personal de Sherlock Holmes con los textos originales (en inglés) "
        "de los relatos de Arthur Conan Doyle."
    ),
)


def _tokens(texto: str) -> list[str]:
    return [t for t in re.findall(r"[a-z']+", texto.lower()) if t not in VACIAS and len(t) > 2]


def _titulo(archivo: Path) -> str:
    return archivo.stem.replace("_", " ").title()


@lru_cache(maxsize=1)
def _indice(carpeta: str | None = None) -> dict:
    """Divide cada libro en fragmentos y precalcula frecuencias (búsqueda tipo BM25)."""
    carpeta = carpeta or str(CARPETA_TEXTOS)
    fragmentos: list[dict] = []
    for archivo in sorted(Path(carpeta).glob("*.txt")):
        texto = archivo.read_text(encoding="utf-8", errors="ignore")
        parrafos = [" ".join(p.split()) for p in re.split(r"\n\s*\n", texto) if p.strip()]
        actual = ""
        for parrafo in parrafos:
            if len(actual) + len(parrafo) > TAMANO_FRAGMENTO and actual:
                fragmentos.append({"relato": _titulo(archivo), "texto": actual})
                actual = ""
            actual = f"{actual}\n\n{parrafo}" if actual else parrafo
        if actual:
            fragmentos.append({"relato": _titulo(archivo), "texto": actual})

    documentos = Counter()
    for f in fragmentos:
        f["frecuencias"] = Counter(_tokens(f["texto"]))
        f["largo"] = sum(f["frecuencias"].values()) or 1
        documentos.update(f["frecuencias"].keys())

    promedio = sum(f["largo"] for f in fragmentos) / max(len(fragmentos), 1)
    return {"fragmentos": fragmentos, "documentos": documentos, "promedio": promedio}


def buscar(consulta: str, max_resultados: int = 3, carpeta: str | None = None) -> list[dict]:
    indice = _indice(carpeta)
    fragmentos, n = indice["fragmentos"], len(indice["fragmentos"])
    terminos = _tokens(consulta)
    if not fragmentos or not terminos:
        return []

    k1, b = 1.5, 0.75
    puntajes = []
    for f in fragmentos:
        puntaje = 0.0
        for t in terminos:
            tf = f["frecuencias"].get(t, 0)
            if tf:
                df = indice["documentos"][t]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                puntaje += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * f["largo"] / indice["promedio"]))
        if puntaje > 0:
            puntajes.append((puntaje, f))
    puntajes.sort(key=lambda x: x[0], reverse=True)
    return [{"relato": f["relato"], "texto": f["texto"]} for _, f in puntajes[:max_resultados]]


@mcp.tool
def buscar_en_mis_archivos(consulta: str, max_resultados: int = 3) -> str:
    """Busca fragmentos de los relatos originales de Sherlock Holmes.

    Úsala cuando el visitante pregunte por un caso antiguo, un personaje del
    canon (Moriarty, Irene Adler, Lestrade...) o cuando quieras citar con
    exactitud algo que ocurrió en tus aventuras.

    IMPORTANTE: los textos están en inglés, así que escribe la consulta en
    INGLÉS con palabras clave concretas (por ejemplo: "Irene Adler photograph
    king", "speckled band snake", "Moriarty Reichenbach falls").
    Traduce al español lo que cites en tu respuesta.
    """
    max_resultados = max(1, min(int(max_resultados), 5))
    resultados = buscar(consulta, max_resultados)
    if not _indice()["fragmentos"]:
        return ("El índice está vacío: los textos no han sido descargados. "
                "Responde con tu propia memoria.")
    if not resultados:
        return "No encontré nada en el índice con esas palabras. Prueba otras palabras clave en inglés."
    return "\n\n---\n\n".join(f"[{r['relato']}]\n{r['texto']}" for r in resultados)


@mcp.tool
def listar_relatos() -> str:
    """Lista los libros de relatos disponibles en el índice de Holmes."""
    libros = sorted({f["relato"] for f in _indice()["fragmentos"]})
    return "\n".join(libros) if libros else "El índice está vacío."


if __name__ == "__main__":
    mcp.run()
