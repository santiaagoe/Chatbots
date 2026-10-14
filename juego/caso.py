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
    apunta_a: str = Field(default="", description="SECRETO: nombre EXACTO del sospechoso al que se refiere esta "
                                                  "pista: el culpable si lo incrimina, o un inocente si lo descarta")
    efecto: str = Field(default="incrimina", description="SECRETO: «incrimina» si señala a ese sospechoso como "
                                                         "culpable, o «descarta» si demuestra que es inocente")


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
- En cada pista, apunta_a es el nombre exacto del sospechoso al que se refiere y efecto dice si lo
  «incrimina» (solo puede incriminar al culpable) o lo «descarta» (demuestra que un inocente no fue).
  Una pista falsa que alguien dejó para culpar a un inocente lo «descarta», porque al entenderla se ve
  que fue puesta a propósito.
- El caso debe poder resolverse razonando, sin información oculta al lector.
- Un crimen al estilo de los relatos: robo, chantaje, desaparición, fraude o asesinato
  narrado con sobriedad, sin violencia gráfica.
- Exactamente 2 mensajes secretos breves (3 a 8 palabras, solo palabras en español,
  sin números) y 2 soportes donde aparecen.
- El campo culpable debe ser idéntico al nombre de uno de los sospechosos.
- Todo en español, salvo escena_visual (en inglés, sin personas reales ni texto legible).
{evitar}"""


class OpcionCaso(BaseModel):
    """Lo que se ve de un expediente antes de abrirlo."""
    titulo: str = Field(description="Al estilo de Conan Doyle, p. ej. 'La aventura del...'")
    tipo_crimen: str = Field(description="Una o dos palabras: robo, chantaje, desaparición, envenenamiento…")
    lugar: str = Field(description="Lugar de Inglaterra, breve")
    gancho: str = Field(description="Una sola frase intrigante que invite a abrirlo, sin revelar la solución")
    muestra: bool = Field(default=False, description="Siempre false")


class OpcionesCaso(BaseModel):
    opciones: list[OpcionCaso]


INSTRUCCION_OPCIONES = """Eres un autor experto en los relatos de Sherlock Holmes de Arthur Conan Doyle.
Propón exactamente {cantidad} casos NUEVOS y originales, ambientados en Inglaterra en 1895, para que un lector
elija uno. Dificultad: {dificultad}. Que sean variados entre sí: tipos de crimen distintos, lugares
distintos (Londres y el campo) y tonos distintos (por ejemplo, uno inquietante y otro ingenioso).
Que ninguno trate de {reservado} (ese caso ya existe).
Todo en español. {evitar}"""


def generar_opciones(motor, dificultad: str = "medio", titulos_anteriores: list[str] | None = None,
                     cantidad: int = 2, reservado: str = "el robo de una joya en una vitrina") -> list[OpcionCaso]:
    """Expedientes cerrados para elegir, inventados por Gemini en una sola consulta.

    La app agrega además el caso de muestra (juego/caso_muestra.py), que no depende de Gemini.
    """
    evitar = ("No repitas estos casos ya jugados: " + "; ".join(titulos_anteriores)) if titulos_anteriores else ""
    resultado: OpcionesCaso = motor.generar_json(
        INSTRUCCION_OPCIONES.format(dificultad=dificultad, evitar=evitar, cantidad=cantidad,
                                    reservado=reservado), OpcionesCaso)
    opciones = [o for o in resultado.opciones if o.titulo.strip()][:cantidad]
    for o in opciones:
        o.muestra = False
    if not opciones:
        raise ValueError("Gemini no propuso ningún expediente.")
    return opciones


def generar_caso(motor, dificultad: str = "medio", titulos_anteriores: list[str] | None = None,
                 medio: str = "un telegrama urgente del inspector Lestrade",
                 semilla: OpcionCaso | None = None) -> Caso:
    evitar = ""
    if titulos_anteriores:
        evitar = "- No repitas estos casos ya jugados: " + "; ".join(titulos_anteriores)
    if semilla is not None:
        evitar += (f"\n- Desarrolla ESTE caso, que el lector eligió: título «{semilla.titulo}» (úsalo tal cual), "
                   f"{semilla.tipo_crimen} en {semilla.lugar}. Punto de partida: {semilla.gancho}")
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
    for p in caso.pistas:
        p.apunta_a, p.efecto = _relacion_pista(p, nombres, caso.culpable)
    return caso


_TRATAMIENTOS = {"sir", "lady", "lord", "señor", "señora", "señorita", "mr", "mrs", "miss", "dr", "doctor",
                 "don", "doña", "el", "la", "de", "del", "the", "srta", "sra", "sr"}


def _palabras_nombre(texto: str) -> list[str]:
    limpio = "".join(c if c.isalpha() else " " for c in texto.lower())
    return [p for p in limpio.split() if p not in _TRATAMIENTOS and len(p) > 1]


def _nombre_parecido(texto: str, nombres: list[str]) -> str | None:
    """El sospechoso al que se refiere un nombre escrito a medias («Ada», «la señorita Lowe»…)."""
    texto = " ".join(texto.split())
    if not texto:
        return None
    if texto in nombres:
        return texto
    escritas = set(_palabras_nombre(texto))
    coincidencias = [(len(escritas & set(_palabras_nombre(n))), n) for n in nombres]
    mejor = max((c for c, _ in coincidencias), default=0)
    candidatos = [n for c, n in coincidencias if c == mejor]
    if mejor > 0 and len(candidatos) == 1:
        return candidatos[0]
    parecido = difflib.get_close_matches(texto, nombres, n=1, cutoff=0.6)
    return parecido[0] if parecido else None


def _relacion_pista(pista: Pista, nombres: list[str], culpable: str) -> tuple[str, str]:
    """(a quién se refiere, «incrimina» o «descarta»), corregido para que el hilo rojo sea coherente.

    Si el modelo no dijo a quién apunta, la pista se une al culpable. Una pista no puede «descartar»
    al culpable ni «incriminar» a un inocente: en esos casos se corrige al sentido que sí tiene.
    """
    nombre = _nombre_parecido(pista.apunta_a, nombres) or culpable
    efecto = "descarta" if "descart" in pista.efecto.lower() else "incrimina"
    if nombre == culpable:
        return culpable, "incrimina"
    if efecto == "incrimina":  # «incrimina» a un inocente: es una pista que lo descarta o una falsa
        return nombre, "descarta"
    return nombre, efecto


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
