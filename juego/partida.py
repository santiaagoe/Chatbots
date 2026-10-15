"""
Reglas del juego que no dependen de la interfaz: etiquetas que escribe Holmes,
instrucción de sistema de cada turno, momentos en que aparecen las pistas
cifradas y puntaje. Separado de app.py para poder probarlo.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from datetime import datetime

from juego.caso import Caso, caso_para_holmes
from juego.cifrados import MensajeCifrado, respuestas_coinciden, tipo_por_nombre

MAX_IMAGENES_POR_CASO = 3
REVELAR_PISTA_TRAS = [2, 5]  # mensajes del visitante dentro del caso para cada pista cifrada
PUNTOS_CULPABLE = 200
PUNTOS_MOVIL = 100
FRACCION_PISTAS_PARA_SUGERIR = 0.6  # con esta parte de las pistas, Holmes sugiere acusar

# Cómo llega el caso a Baker Street. Cada caso usa uno al azar y la ficha toma su aspecto.
MEDIOS = {
    "telegrama": {"descripcion": "un telegrama urgente del inspector Lestrade",
                  "icono": "📨", "titulo": "Telegrama"},
    "periodico": {"descripcion": "un recorte del diario The Times de esta mañana",
                  "icono": "📰", "titulo": "The Times"},
    "carta": {"descripcion": "la carta angustiada de un cliente, entregada en mano por la Sra. Hudson",
              "icono": "✉️", "titulo": "Carta para el señor Holmes"},
    "irregular": {"descripcion": "Wiggins, el jefe de los Irregulares de Baker Street, que llega sin aliento con una nota",
                  "icono": "🧢", "titulo": "Nota de Wiggins"},
}


def elegir_medio(anterior: str | None = None, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    opciones = [m for m in MEDIOS if m != anterior] or list(MEDIOS)
    return rng.choice(opciones)


_IMAGEN = re.compile(r"\[\[\s*IMAGEN\s*:\s*(.+?)\s*\]\]", re.IGNORECASE | re.DOTALL)
_PISTA = re.compile(r"\[\[\s*PISTAS?\s*:\s*([\d,\sy]+?)\s*\]\]", re.IGNORECASE)
# Frases con las que el visitante intenta acusar en el chat
_ACUSACION = re.compile(
    r"\b(acuso|acusamos|acusar|acusación|culpable|asesin[oa]|fue (él|ella|el|la)\b|"
    r"(lo|la) (hizo|mató|robó)|ya s[eé] qui[eé]n fue)", re.IGNORECASE)
_MODO = re.compile(r"\[\[\s*MODO\s*:\s*([AB])\s*\]\]", re.IGNORECASE)
_NOTA = re.compile(r"\[\[\s*NOTA\s*:\s*(.+?)\s*\]\]", re.IGNORECASE | re.DOTALL)

# Cómo elige el visitante su camino, escrito con sus palabras
_ELIGE_A = re.compile(
    r"(\bopci[oó]n\s*a\b|\bcamino\s*a\b|\b(le\s+)?traigo\s+un\s+(caso|misterio)|"
    r"\btengo\s+un\s+(caso|misterio|problema)|\bquiero\s+contarle|\bay[uú]d(arme|eme)\b|\bme\s+ayude\b|"
    r"^\s*a\s*[.!)]?\s*$)", re.IGNORECASE)
_ELIGE_B = re.compile(
    r"(\bopci[oó]n\s*b\b|\bcamino\s*b\b|\bayudar(le|lo)\b|\ble\s+ayudo\b|\bayudar\s+a\s+holmes\b|"
    r"\bsu\s+caso\b|\bcaso\s+suyo\b|"
    r"\bacompañarl[eo]\b|^\s*b\s*[.!)]?\s*$)", re.IGNORECASE)


# Temas de los libros originales: solo entonces vale la pena que Holmes consulte su índice MCP
_CANON = re.compile(
    r"(moriarty|irene|adler|lestrade|gregson|mycroft|hudson|wiggins|irregulares|baskerville|sabueso|"
    r"reichenbach|bohemia|pelirroj|banda de lunares|speckled|escarlata|scarlet|signo de los cuatro|"
    r"valle del miedo|gloria scott|bailarines|dancing men|milverton|moran|mary morstan|"
    r"\bwatson\b.*\b(conoci|primer|afganist)|afganist|tus casos|sus casos|caso antiguo|casos antiguos|"
    r"aventura de|recuerda (el|la|cuando)|cu[eé]nteme (de|sobre) (su|el) caso|\bcanon\b|conan doyle|"
    r"en sus libros|sus relatos|sus memorias|cita textual|c[oó]mo muri[oó]|cataratas)", re.IGNORECASE)


def necesita_indice(texto: str) -> bool:
    """¿El mensaje habla de algo de los libros? Si no, Holmes responde sin su índice y ahorra una consulta."""
    return bool(_CANON.search(texto or ""))


def detectar_modo(texto: str) -> str | None:
    """¿El visitante eligió un camino? La app lo decide sola, sin depender de Holmes."""
    a, b = bool(_ELIGE_A.search(texto)), bool(_ELIGE_B.search(texto))
    if a and not b:
        return "A"
    if b and not a:
        return "B"
    return None


# Frases mientras se espera a Gemini: una al azar para que no se repita siempre la misma
FRASES = {
    "pensar": [
        "Holmes medita, la pipa entre los dientes…",
        "Holmes junta las yemas de los dedos y cierra los ojos…",
        "Un acorde de violín rompe el silencio mientras Holmes reflexiona…",
        "Holmes camina de un lado a otro frente a la chimenea…",
        "La Sra. Hudson sube el té; Holmes ni siquiera lo nota…",
        "Holmes examina sus notas con la lupa…",
        "Holmes enciende la pipa y la habitación se llena de humo…",
        "Holmes hojea su índice de recortes con impaciencia…",
        "Holmes contempla la niebla por la ventana…",
        "Holmes murmura algo sobre cenizas de tabaco…",
        "Holmes tamborilea con los dedos sobre la repisa…",
        "Holmes se hunde en su sillón, la mirada perdida…",
    ],
    "expedientes": [
        "Holmes revuelve el montón de cartas sobre la repisa…",
        "Holmes saca tres carpetas del cajón de su escritorio…",
        "Holmes rebusca entre los telegramas de la semana…",
        "Holmes sopla el polvo de unos expedientes olvidados…",
    ],
    "caso": [
        "Holmes abre el expediente y extiende los papeles sobre la mesa…",
        "Holmes lee el expediente con una ceja levantada…",
        "Holmes clava el expediente en el tablero de corcho…",
        "Holmes repasa el expediente línea por línea…",
    ],
    "dibujo": [
        "Un dibujante de la Strand Magazine bosqueja la escena…",
        "El fotógrafo de Scotland Yard prepara su cámara…",
        "Watson toma apuntes y hace un boceto del lugar…",
    ],
    "juicio": [
        "Holmes cierra los ojos y junta las yemas de los dedos…",
        "Holmes repasa cada pista en silencio antes de hablar…",
        "Holmes se pone de pie, listo para revelar la verdad…",
    ],
    "descifrar": [
        "Holmes acerca la lupa al papel…",
        "Holmes cuenta las letras en voz baja…",
        "Holmes anota columnas de letras en el margen del Times…",
        "Holmes sostiene el papel a contraluz frente a la lámpara…",
    ],
    "relato": [
        "Watson moja la pluma en el tintero…",
        "Un mensajero sube la escalera con las cuartillas de Watson…",
        "Watson escribe con su letra apresurada de médico…",
    ],
}

# Cómo entrega Holmes el relato de Watson (no gasta consultas: el relato ya la gastó)
ENTREGA_RELATO = [
    "*Holmes le tiende unas cuartillas escritas a mano.* «Le conté el caso a Watson y ya me ha enviado su "
    "versión. Exagera mis méritos, como siempre, pero esta vez reconozco que usted sale muy bien parado.»",
    "*Llega un mensajero con un sobre a nombre del visitante.* «La letra de Watson», dice Holmes con media "
    "sonrisa. «Insiste en convertir la ciencia de la deducción en un folletín. Léalo usted mismo.»",
    "*Holmes deja unas hojas sobre la mesa.* «Watson no pudo resistirse. Le advierto que adorna los hechos; "
    "es su único vicio literario.»",
]


def frase(tipo: str, rng: random.Random | None = None) -> str:
    return (rng or random).choice(FRASES[tipo])


PRESENTA_EXPEDIENTES = [
    "Holmes despeja la mesa de un manotazo y deja caer tres carpetas. «Elija usted, colega. Cada una es un misterio distinto, y todas me aburren menos que el silencio.»",
    "«Tengo tres asuntos pendientes», dice Holmes, extendiendo tres carpetas sobre la alfombra. «Escoja el que más le intrigue.»",
    "Holmes saca tres expedientes del cajón y los alinea con precisión. «Lestrade me ha traído estos esta semana. ¿Cuál le parece más singular?»",
]
_RESTOS = re.compile(r"\[/?(CASO SECRETO|PISTA CIFRADA|AYUDA CIFRADO|RESULTADO|INICIO CASO|CONTEXTO|"
                     r"AVISO ACUSACION|SUGERIR ACUSACION|DESAFIO)\]?", re.IGNORECASE)

_BLOQUES = re.compile(r"\[(CASO SECRETO|PISTA CIFRADA|AYUDA CIFRADO|RESULTADO|INICIO CASO|AVISO ACUSACION|"
                      r"SUGERIR ACUSACION|DESAFIO)\].*?\[/\1\]", re.IGNORECASE | re.DOTALL)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class PedidoImagen:
    descripcion: str          # en inglés, para el ilustrador
    pie: str = ""             # en español, se muestra bajo la imagen

    @property
    def es_escena(self) -> bool:
        return self.descripcion.strip().upper() in ("ESCENA", "SCENE", "ESCENA DEL CRIMEN")


@dataclass
class Etiquetas:
    texto: str
    modo: str | None = None
    imagenes: list[PedidoImagen] = field(default_factory=list)
    pistas: list[int] = field(default_factory=list)   # números de pista (desde 1) reveladas
    notas: list[str] = field(default_factory=list)    # datos que Holmes anota en el modo A


def extraer_etiquetas(respuesta: str) -> Etiquetas:
    """Separa el texto visible de las órdenes que Holmes deja para la aplicación."""
    imagenes = []
    for contenido in _IMAGEN.findall(respuesta):
        descripcion, _, pie = contenido.partition("|")
        imagenes.append(PedidoImagen(descripcion.strip(), pie.strip()))
    pistas: list[int] = []
    for grupo in _PISTA.findall(respuesta):
        for numero in re.findall(r"\d+", grupo):
            if int(numero) not in pistas:
                pistas.append(int(numero))
    modo = _MODO.search(respuesta)
    notas = [" ".join(n.split()) for n in _NOTA.findall(respuesta)]
    texto = _NOTA.sub("", _PISTA.sub("", _MODO.sub("", _IMAGEN.sub("", respuesta))))
    texto = _BLOQUES.sub("", texto)  # un bloque de la app que Holmes repitió entero
    texto = _RESTOS.sub("", texto)
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"(?<=\S) {2,}(?=\S)", " ", texto)  # espacios que dejan las etiquetas quitadas
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return Etiquetas(texto=texto, modo=modo.group(1).upper() if modo else None,
                     imagenes=imagenes, pistas=pistas, notas=notas)


def quiere_acusar(texto: str) -> bool:
    """¿El visitante intenta acusar a alguien en el chat (en vez de en los Archivos)?

    Una pregunta («¿quién lo hizo?», «¿es culpable el mayordomo?») no es una acusación,
    salvo que use explícitamente la palabra acusar.
    """
    if "?" in texto or "¿" in texto:
        return bool(re.search(r"\bacus", texto, re.IGNORECASE))
    return bool(_ACUSACION.search(texto))


def toca_sugerir_acusacion(pistas_anotadas: list[int], total_pistas: int) -> bool:
    if total_pistas <= 0:
        return False
    return len(pistas_anotadas) >= math.ceil(FRACCION_PISTAS_PARA_SUGERIR * total_pistas)


def instruccion_presentacion(caso: Caso, medio: str) -> str:
    datos = MEDIOS[medio]
    return (
        f"[INICIO CASO] El expediente acaba de llegar: {datos['descripcion']}. "
        "Escribe SOLO el gancho de la presentación, en 3 o 4 frases dramáticas y breves: cómo te llega "
        "el caso y el detalle más intrigante de los hechos conocidos. NO enumeres a la víctima, el lugar "
        "ni los sospechosos: la aplicación mostrará justo debajo de tu mensaje una ficha con todos esos "
        "datos (puedes aludir a ella, por ejemplo «Lea usted mismo»). Termina con una pregunta al "
        "visitante: ¿empezamos por la escena del crimen o por los sospechosos? "
        "No solicites imágenes en este mensaje.")


def contexto_hora(ahora: datetime) -> str:
    return f"[CONTEXTO] Hora local del visitante: {ahora:%H:%M} ({DIAS[ahora.weekday()]})"


@dataclass
class PistaCifrada:
    cifrado: MensajeCifrado
    soporte: str
    estado: str = "oculta"   # oculta → activa → resuelta / rendida
    ayudas: int = 0
    fallos: int = 0
    tipo_ok: bool = False
    puntos: int = 0

    def proponer(self, nombre_tipo: str, mensaje: str) -> tuple[bool, bool]:
        """Revisa una propuesta. Devuelve (¿tipo correcto?, ¿mensaje correcto?)."""
        tipo_bien = tipo_por_nombre(nombre_tipo) == self.cifrado.tipo
        mensaje_bien = respuestas_coinciden(mensaje, self.cifrado.mensaje)
        self.tipo_ok = self.tipo_ok or tipo_bien
        if self.tipo_ok and mensaje_bien:
            self.estado = "resuelta"
            self.puntos = max(10, 100 - 20 * self.ayudas - 10 * self.fallos)
        else:
            self.fallos += 1
        return tipo_bien, mensaje_bien

    def siguiente_ayuda(self) -> str | None:
        if self.ayudas >= len(self.cifrado.pistas):
            return None
        self.ayudas += 1
        return self.cifrado.pistas[self.ayudas - 1]

    def rendirse(self) -> None:
        self.estado = "rendida"
        self.puntos = 0


def pista_a_revelar(pistas: list[PistaCifrada], mensajes_en_caso: int) -> int | None:
    """Índice de la pista cifrada que debe aparecer ahora, si corresponde."""
    for i, pista in enumerate(pistas):
        if pista.estado != "oculta":
            continue
        anterior_cerrada = i == 0 or pistas[i - 1].estado in ("resuelta", "rendida")
        umbral = REVELAR_PISTA_TRAS[min(i, len(REVELAR_PISTA_TRAS) - 1)]
        if anterior_cerrada and mensajes_en_caso >= umbral:
            return i
        return None
    return None


def instruccion_sistema(prompt: str, modo: str | None, caso: Caso | None,
                        pistas: list[PistaCifrada], terminado: bool, imagenes_usadas: int,
                        imagenes_activas: bool = True, pistas_anotadas: list[int] | None = None,
                        escena_dibujada: bool = False) -> str:
    partes = [prompt, "\n\n---\n\n# ESTADO ACTUAL (información de la aplicación)"]
    if modo is None:
        partes.append("El visitante aún no ha elegido un camino.")
    elif modo == "A":
        partes.append("Modo A: el visitante te trae un caso. No solicites imágenes. Cuando el visitante "
                      "te dé un dato importante del caso, anótalo al final con [[NOTA: dato breve]].")
    elif caso is None:
        partes.append("Modo B: el visitante está eligiendo uno de tres expedientes que la aplicación "
                      "le muestra. Si te pregunta, comenta brevemente y anímalo a elegir uno.")
    else:
        partes.append("Modo B: el visitante te ayuda con tu caso.")
    if modo == "B" and caso is not None:
        estado = "TERMINADO: la acusación ya se hizo; puedes hablar de la solución." if terminado \
            else "EN CURSO: no reveles la solución."
        partes.append(f"[CASO SECRETO]\nEstado del caso: {estado}\n{caso_para_holmes(caso)}\n[/CASO SECRETO]")
        for i, p in enumerate(pistas, 1):
            if p.estado == "oculta":
                continue
            linea = f"Mensaje cifrado {i} ({p.soporte}): {p.estado}"
            if p.estado in ("resuelta", "rendida"):
                linea += f"; decía «{p.cifrado.mensaje}» y estaba en {p.cifrado.nombre}"
            partes.append(linea)
        anotadas = sorted(pistas_anotadas or [])
        if anotadas:
            partes.append("Pistas ya reveladas y anotadas en los archivos del visitante: "
                          + ", ".join(map(str, anotadas)) + ". No vuelvas a etiquetarlas.")
        else:
            partes.append("El visitante aún no ha descubierto ninguna pista.")
        if imagenes_activas:
            restantes = MAX_IMAGENES_POR_CASO - imagenes_usadas
            partes.append(f"Imágenes disponibles para este caso: {max(restantes, 0)}.")
            partes.append("La escena del crimen ya fue ilustrada." if escena_dibujada else
                          "Cuando el visitante llegue a la escena del crimen, escribe [[IMAGEN: ESCENA]].")
        else:
            partes.append("Las imágenes están desactivadas: NO escribas [[IMAGEN: ...]]. "
                          "Describe las escenas con palabras, con todo el detalle visual que harían falta.")
    return "\n".join(partes)
