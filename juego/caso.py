"""
El caso secreto del Modo B.

Gemini inventa el caso UNA vez, al inicio, en formato JSON. La aplicación lo
guarda y se lo recuerda a Holmes en cada turno, así la solución nunca cambia
aunque el visitante haga mil preguntas.
"""

from __future__ import annotations

import difflib

from pydantic import BaseModel, Field

from juego.cifrados import normalizar


class Persona(BaseModel):
    nombre: str
    descripcion: str


class Sospechoso(BaseModel):
    nombre: str = Field(description="Nombre completo de época victoriana")
    ocupacion: str
    relacion_con_victima: str
    motivo_sospecha: str = Field(
        description="PÚBLICO: por qué es sospechoso, en una frase concreta y verificable "
                    "(p. ej. «Fue el último en ver a la víctima con vida»). No revela si es culpable.")
    coartada: str = Field(description="Lo que declara; el culpable miente aquí")
    secreto: str = Field(description="Algo que oculta, sea o no el culpable")


class Pista(BaseModel):
    descripcion: str = Field(description="PÚBLICO cuando se descubre: qué se observa, con detalle concreto")
    ubicacion: str = Field(description="Dónde se encuentra: un lugar de la escena o un sospechoso al interrogarlo")
    que_revela: str = Field(description="SECRETO: qué conclusión permite")


class Caso(BaseModel):
    titulo: str = Field(description="Al estilo de Conan Doyle, p. ej. 'La aventura del...'")
    lugar: str
    fecha: str
    resumen: str = Field(description="Cómo llega el caso a Baker Street, 2-3 frases, por el medio indicado")
    hechos_conocidos: str = Field(
        description="PÚBLICO: lo que sabe la policía, 2-3 frases (qué pasó, cuándo, qué se descubrió). "
                    "Sin la solución.")
    victima: Persona
    escena_nombre: str = Field(description="PÚBLICO: nombre breve de la escena del crimen, p. ej. «La biblioteca de Ashby Hall»")
    crimen: str = Field(description="SECRETO: qué ocurrió realmente, paso a paso")
    sospechosos: list[Sospechoso]
    culpable: str = Field(description="Nombre EXACTO de uno de los sospechosos")
    movil: str
    metodo: str
    pistas: list[Pista]
    mensajes_secretos: list[str] = Field(
        description="2 mensajes breves en español (3 a 8 palabras) que el culpable u otro "
                    "personaje escribió en clave; deben ayudar a resolver el caso sin nombrar al culpable"
    )
    soportes_mensajes: list[str] = Field(
        description="Para cada mensaje secreto, dónde aparece: una nota, un telegrama, un grabado..."
    )
    escena_visual: str = Field(
        description="Descripción visual de la escena del crimen EN INGLÉS para un ilustrador: lugar, "
                    "muebles y objetos clave visibles (los mismos de las pistas encontradas allí), "
                    "iluminación y punto de vista. Sin personas reales ni texto legible.")


INSTRUCCION = """Eres un autor experto en los relatos de Sherlock Holmes de Arthur Conan Doyle.
Inventa un caso NUEVO y original (no copies un relato existente) ambientado en Inglaterra en 1895.

Requisitos:
- Dificultad para el lector: {dificultad}.
- El caso llega a Baker Street mediante {medio}; el campo resumen debe contarlo así.
- Entre 3 y 4 sospechosos con móviles plausibles; solo uno es culpable.
- Cada sospechoso tiene un motivo_sospecha PÚBLICO, concreto y distinto (por ejemplo: fue el último
  en ver a la víctima, discutió con ella esa noche, tenía la llave, heredaba su fortuna).
  El culpable NO debe ser el sospechoso con el motivo más evidente.
- Entre 4 y 6 pistas físicas o testimoniales que, combinadas con lógica, permitan deducir
  al culpable y el móvil. Al menos una pista debe descartar a un sospechoso inocente.
- Al menos 2 pistas se encuentran en la escena del crimen y al menos 1 al interrogar a un sospechoso.
- El caso debe poder resolverse razonando, sin información oculta al lector.
- Un crimen al estilo de los relatos: robo, chantaje, desaparición, fraude o asesinato
  narrado con sobriedad, sin violencia gráfica.
- Exactamente 2 mensajes secretos breves (3 a 8 palabras, solo palabras en español,
  sin números) y 2 soportes donde aparecen.
- El campo culpable debe ser idéntico al nombre de uno de los sospechosos.
- Todo en español, salvo escena_visual (en inglés, sin personas reales ni texto legible).
{evitar}"""


def generar_caso(motor, dificultad: str = "medio", titulos_anteriores: list[str] | None = None,
                 medio: str = "un telegrama urgente del inspector Lestrade") -> Caso:
    evitar = ""
    if titulos_anteriores:
        evitar = "- No repitas estos casos ya jugados: " + "; ".join(titulos_anteriores)
    instruccion = INSTRUCCION.format(dificultad=dificultad, evitar=evitar, medio=medio)
    caso: Caso = motor.generar_json(instruccion, Caso)
    return reparar_caso(caso)


def reparar_caso(caso: Caso) -> Caso:
    """Corrige los descuidos típicos del modelo para que el juego no se rompa."""
    nombres = [s.nombre for s in caso.sospechosos]
    if caso.culpable not in nombres:
        parecido = difflib.get_close_matches(caso.culpable, nombres, n=1, cutoff=0)
        caso.culpable = parecido[0] if parecido else nombres[0]

    mensajes = []
    for m in caso.mensajes_secretos:
        palabras = normalizar(m).split()[:8]
        if len(palabras) >= 2:
            mensajes.append(" ".join(palabras))
    caso.mensajes_secretos = mensajes[:2] or ["BUSQUE EN EL ESTUDIO"]
    while len(caso.soportes_mensajes) < len(caso.mensajes_secretos):
        caso.soportes_mensajes.append("una nota arrugada hallada en la escena")
    for s in caso.sospechosos:
        if not s.motivo_sospecha.strip():
            s.motivo_sospecha = f"Su relación con la víctima: {s.relacion_con_victima}."
    if not caso.escena_nombre.strip():
        caso.escena_nombre = caso.lugar
    return caso


def caso_para_holmes(caso: Caso) -> str:
    """Texto del bloque [CASO SECRETO] (sin los mensajes cifrados: esos los maneja la app)."""
    datos = caso.model_dump(exclude={"mensajes_secretos", "soportes_mensajes", "escena_visual"})
    lineas = [f"Título: {datos['titulo']}", f"Lugar y fecha: {datos['lugar']}, {datos['fecha']}",
              f"Cómo llegó el caso: {caso.resumen}",
              f"Hechos conocidos (públicos): {caso.hechos_conocidos}",
              f"Víctima: {caso.victima.nombre} — {caso.victima.descripcion}",
              f"Escena del crimen: {caso.escena_nombre}",
              f"Lo que realmente ocurrió (SECRETO): {caso.crimen}", "Sospechosos:"]
    for s in caso.sospechosos:
        lineas.append(f"  - {s.nombre} ({s.ocupacion}; {s.relacion_con_victima}). "
                      f"Por qué es sospechoso (público): {s.motivo_sospecha}. "
                      f"Coartada que declara: {s.coartada}. Secreto: {s.secreto}")
    lineas += [f"CULPABLE: {caso.culpable}", f"MÓVIL: {caso.movil}", f"MÉTODO: {caso.metodo}",
               "Pistas (usa su número en [[PISTA: n]] al revelarlas):"]
    for i, p in enumerate(caso.pistas, 1):
        lineas.append(f"  {i}. {p.descripcion} (se encuentra en: {p.ubicacion}) → revela (SECRETO): {p.que_revela}")
    lineas.append(f"Descripción visual de la escena (para pedir la imagen): {caso.escena_visual}")
    return "\n".join(lineas)


class Veredicto(BaseModel):
    movil_correcto: bool = Field(description="¿La explicación del móvil coincide en lo esencial?")
    comentario: str = Field(description="Una frase breve explicando qué acertó o qué faltó")


def evaluar_movil(motor, caso: Caso, movil_propuesto: str) -> Veredicto:
    if not movil_propuesto.strip():
        return Veredicto(movil_correcto=False, comentario="El visitante no propuso ningún móvil.")
    instruccion = (
        "Eres un juez imparcial de un juego de detectives. Compara el móvil real con el que "
        "propone el jugador. Considera correcto si coincide en lo esencial, aunque use otras "
        "palabras o le falten detalles menores.\n\n"
        f"Móvil real: {caso.movil}\nMóvil propuesto por el jugador: {movil_propuesto}"
    )
    return motor.generar_json(instruccion, Veredicto, temperatura=0.0)
