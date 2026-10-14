"""
«El relato de Watson»: al terminar, Watson escribe lo ocurrido como un cuento de la Strand Magazine.

Una sola consulta a Gemini (salida JSON). Para que no invente, recibe la solución del caso
y lo que de verdad pasó en la conversación: qué preguntó el visitante, qué descifró y a quién acusó.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from juego.caso import Caso

MAX_MENSAJES = 40          # últimos mensajes visibles que se le cuentan a Watson
MAX_CARACTERES_MENSAJE = 500
MAX_CARACTERES_TOTAL = 12000


class RelatoWatson(BaseModel):
    titulo: str = Field(description="Título al estilo de Conan Doyle, p. ej. «La aventura de…»")
    parrafos: list[str] = Field(description="Entre 4 y 6 párrafos del relato, sin Markdown")


INSTRUCCION = """Eres el Dr. John H. Watson, amigo y cronista de Sherlock Holmes. Escribe en español un relato
breve (entre 350 y 450 palabras, de 4 a 6 párrafos) al estilo de los que publicas en la Strand Magazine,
sobre lo que ocurrió hoy en Baker Street.

Reglas:
- Esa noche tú no estabas en Baker Street: escribes a partir de lo que Holmes te contó. Puedes decirlo.
- Cuenta SOLO lo que pasó en la conversación de abajo. No inventes preguntas, hallazgos ni aciertos del
  visitante, ni cosas que Holmes no dijo. Puedes añadir ambientación (la niebla, la chimenea, el violín).
- El visitante es el protagonista junto a Holmes. Llámalo «nuestro visitante» o «el visitante de aquella
  noche». No le inventes nombre, aspecto ni oficio; si en la conversación dijo su nombre, puedes usarlo.
- Sé honesto con el resultado: si el visitante se equivocó o se rindió, cuéntalo con amabilidad y algo de humor.
- Tono cálido, admirativo con Holmes y con la ironía suave de tus relatos. Sin violencia gráfica.
- Si la conversación trata de un problema real y serio, escribe con sobriedad y sin acusar a personas
  reales con nombre y apellido.
- Sin Markdown ni listas: solo párrafos de prosa.
- {titulo}

{datos}"""


def _limpiar(texto: str) -> str:
    texto = re.sub(r"[*_#>`]+", "", texto or "")
    return " ".join(texto.split())


def conversacion_para_watson(mensajes: list[dict]) -> str:
    """Lo visible de la conversación, recortado, con quién dijo cada cosa."""
    visibles = [m for m in mensajes if not m.get("oculto") and (m.get("texto") or "").strip()]
    lineas = []
    for m in visibles[-MAX_MENSAJES:]:
        quien = "Holmes" if m["rol"] == "model" else "Visitante"
        texto = _limpiar(m["texto"])
        if len(texto) > MAX_CARACTERES_MENSAJE:
            texto = texto[:MAX_CARACTERES_MENSAJE].rstrip() + "…"
        lineas.append(f"{quien}: {texto}")
    resultado = "\n".join(lineas)
    return resultado[-MAX_CARACTERES_TOTAL:]


def datos_modo_b(caso: Caso, acusacion: dict | None, pistas_cifradas, pistas_anotadas: list[int],
                 puntaje: int | None) -> str:
    lineas = [
        f"Caso: «{caso.titulo}», en {caso.lugar}, el {caso.fecha}.",
        f"Víctima: {caso.victima.nombre} ({caso.victima.descripcion}).",
        "Sospechosos: " + "; ".join(f"{s.nombre}, {s.ocupacion}" for s in caso.sospechosos) + ".",
        f"Solución: el culpable era {caso.culpable}. Móvil: {caso.movil} Método: {caso.metodo}",
        f"Lo que ocurrió: {caso.crimen}",
    ]
    halladas = [caso.pistas[n - 1].descripcion for n in sorted(pistas_anotadas) if 1 <= n <= len(caso.pistas)]
    lineas.append(f"Pistas que descubrió el visitante ({len(halladas)} de {len(caso.pistas)}): "
                  + ("; ".join(halladas) if halladas else "ninguna") + ".")
    for i, p in enumerate(pistas_cifradas, 1):
        if p.estado == "oculta":
            continue
        estado = {"resuelta": "lo descifró", "rendida": "se rindió", "activa": "no llegó a descifrarlo"}[p.estado]
        ayudas = f", con {p.ayudas} pista(s) de Holmes" if p.ayudas else ""
        lineas.append(f"Mensaje cifrado {i} ({p.cifrado.nombre}, decía «{p.cifrado.mensaje}»): {estado}{ayudas}.")
    if acusacion:
        lineas.append(
            f"Acusación del visitante: acusó a {acusacion['culpable']} "
            f"({'acertó' if acusacion['culpable_bien'] else 'se equivocó'}); móvil propuesto: "
            f"«{acusacion['movil'] or 'ninguno'}» ({'correcto' if acusacion['movil_bien'] else 'incorrecto'}).")
    if puntaje is not None:
        lineas.append(f"Puntaje final: {puntaje}.")
    return "\n".join(lineas)


def datos_modo_a(notas: list[str]) -> str:
    if not notas:
        return "El visitante trajo su propio misterio a Baker Street."
    return "El visitante trajo su propio misterio. Datos que Holmes anotó: " + "; ".join(notas) + "."


def generar_relato(motor, datos: str, mensajes: list[dict], titulo: str | None = None) -> RelatoWatson:
    regla_titulo = (f"Titula el relato «{titulo}»." if titulo else
                    "Inventa un título al estilo de Conan Doyle a partir del misterio que trajo el visitante.")
    instruccion = INSTRUCCION.format(
        titulo=regla_titulo,
        datos=f"DATOS DEL CASO\n{datos}\n\nCONVERSACIÓN\n{conversacion_para_watson(mensajes)}")
    relato: RelatoWatson = motor.generar_json(instruccion, RelatoWatson, temperatura=0.9)
    return reparar_relato(relato, titulo)


def reparar_relato(relato: RelatoWatson, titulo: str | None = None) -> RelatoWatson:
    parrafos = [_limpiar(p) for p in relato.parrafos]
    parrafos = [p for p in parrafos if p][:8]
    if not parrafos:
        raise ValueError("Watson no escribió nada.")
    return RelatoWatson(titulo=titulo or _limpiar(relato.titulo) or "Una noche en Baker Street", parrafos=parrafos)


def relato_como_texto(relato: RelatoWatson) -> str:
    """El relato listo para descargar (texto simple, se abre en cualquier computador o celular)."""
    cuerpo = "\n\n".join(relato.parrafos)
    return (f"{relato.titulo.upper()}\n\nUn relato del Dr. John H. Watson\n\n{cuerpo}\n\n"
            "—\n221B Baker Street, un chatbot de Sherlock Holmes\n")


def nombre_archivo(relato: RelatoWatson) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", _sin_tildes(relato.titulo.lower())).strip("_")[:60]
    return f"relato_watson_{base or 'baker_street'}.txt"


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
