"""
Piezas visuales que arma la aplicación (no Gemini): la ficha del caso con el
aspecto del medio por el que llegó, la guía «Cómo investigar» y el expediente.

Como los datos salen del caso guardado y no de lo que escriba Holmes, la
información nunca falta. Todo texto que viene de la IA se escapa antes de
meterlo en HTML.
"""

from __future__ import annotations

import textwrap
from html import escape

from juego.caso import Caso
from juego.partida import MEDIOS



def _sospechosos_html(caso: Caso) -> str:
    filas = []
    for s in caso.sospechosos:
        filas.append(
            f"<li><b>{escape(s.nombre)}</b> — {escape(s.ocupacion)}; {escape(s.relacion_con_victima)}.<br>"
            f"<span class='motivo'>Sospechoso porque: {escape(s.motivo_sospecha)}</span></li>")
    return "<ul>" + "".join(filas) + "</ul>"


def ficha_caso(caso: Caso, medio: str) -> str:
    """Ficha HTML con todos los datos públicos del caso, con el aspecto del medio."""
    datos = MEDIOS.get(medio, MEDIOS["telegrama"])
    cuerpo = (
        f"<div class='dato'><b>Víctima:</b> {escape(caso.victima.nombre)} — {escape(caso.victima.descripcion)}</div>"
        f"<div class='dato'><b>Lugar:</b> {escape(caso.escena_nombre)}, {escape(caso.lugar)}</div>"
        f"<div class='dato'><b>Fecha:</b> {escape(caso.fecha)}</div>"
        f"<div class='hechos'>{escape(caso.hechos_conocidos)}</div>"
        f"<div class='dato'><b>Sospechosos:</b></div>{_sospechosos_html(caso)}"
    )
    if medio == "telegrama":
        cuerpo = cuerpo.replace("</div>", " <span class='stop'>stop</span></div>", 3)
    adornos = "<span class='matasellos'></span><span class='sello'></span>"
    return (
        f"<div class='ficha ficha-{escape(medio)}'>{adornos}"
        f"<div class='encabezado'>{escape(datos['titulo'])}</div>"
        f"<h4>{escape(caso.titulo)}</h4>{cuerpo}</div>"
    )


GUIA = (
    "<div class='guia'><b>🔍 Cómo investigar</b><ul>"
    "<li>💬 <b>Investigue conversando</b> en el chat: examine lugares, interrogue a los sospechosos "
    "y pregúntele a Holmes. Los botones bajo el chat le sugieren por dónde seguir.</li>"
    "<li>📁 El <b>expediente</b> y las <b>pistas</b> que descubra se anotan solos en la libreta "
    "(la barra lateral; en el celular, ábrala con la flecha de arriba a la izquierda).</li>"
    "<li>📜 Los <b>mensajes cifrados</b> se resuelven en la libreta.</li>"
    "<li>⚖️ Cuando sepa quién fue y por qué, haga la acusación en <b>⚖️ Acusación final</b>, "
    "en la libreta. Solo hay una oportunidad.</li>"
    "</ul></div>"
)

AVISO_ACUSACION = (
    "<div class='aviso-acusacion'>⚖️ <b>¿Listo para acusar?</b> La acusación formal se hace en "
    "<b>⚖️ Acusación final</b>, en la libreta (barra lateral): elija al culpable y escriba el móvil. "
    "Es definitiva, así que repase antes el expediente.</div>"
)


def pista_anotada(caso: Caso, numero: int) -> str:
    pista = caso.pistas[numero - 1]
    return (f"<div class='pista-anotada'>📝 Anotado en la libreta: {escape(pista.descripcion)} "
            f"<i>({escape(pista.ubicacion)})</i></div>")


def md(texto: str) -> str:
    """Escapa HTML y los símbolos de Markdown que vienen en el texto de la IA."""
    return escape(texto).replace("*", "\\*").replace("_", "\\_")


def sospechosos_markdown(caso: Caso) -> str:
    """Sección «Sospechosos» de la libreta: nombre, ocupación y por qué se sospecha de cada uno."""
    return "\n".join(f"- **{md(s.nombre)}**, {md(s.ocupacion)}. *{md(s.motivo_sospecha)}*"
                     for s in caso.sospechosos)


def expediente_markdown(caso: Caso, pistas_anotadas: list[int]) -> str:
    """Contenido del expediente en la barra lateral (Markdown, sin datos secretos)."""

    lineas = [
        f"**{md(caso.titulo)}**",
        "",
        f"📍 {md(caso.escena_nombre)}, {md(caso.lugar)} · {md(caso.fecha)}",
        "",
        f"**Víctima:** {md(caso.victima.nombre)} — {md(caso.victima.descripcion)}",
        "",
        md(caso.hechos_conocidos),
        "",
        f"**Pistas anotadas ({len(pistas_anotadas)}/{len(caso.pistas)})**",
    ]
    if pistas_anotadas:
        for n in pistas_anotadas:
            p = caso.pistas[n - 1]
            lineas.append(f"- {md(p.descripcion)} *({md(p.ubicacion)})*")
    else:
        lineas.append("*Ninguna todavía. Empiece por examinar la escena.*")
    return "\n".join(lineas)


def carpeta_expediente(opcion: dict, elegida: bool = False, apagada: bool = False) -> str:
    """Una carpeta de papel manila clavada en el corcho, con lo que se ve antes de abrirla."""
    clases = "carpeta" + (" elegida" if elegida else "") + (" apagada" if apagada else "")
    sello = ("<div class='carpeta-sello'>Caso de muestra · siempre disponible</div>"
             if opcion.get("muestra") else "")
    return (
        f"<div class='{clases}'><span class='chinche ch-rojo'></span>"
        f"<div class='carpeta-pestana'>{escape(opcion.get('tipo_crimen', '')).capitalize()}</div>"
        f"<div class='carpeta-titulo'>{escape(opcion.get('titulo', ''))}</div>"
        f"<div class='carpeta-lugar'>{escape(opcion.get('lugar', ''))}</div>"
        f"<div class='carpeta-gancho'>{escape(opcion.get('gancho', ''))}</div>{sello}"
        + ("<div class='carpeta-abierta'>Expediente abierto</div>" if elegida else "")
        + "</div>"
    )


def notas_markdown(notas: list[str]) -> str:
    if not notas:
        return "*Cuéntele su caso a Holmes. Los datos importantes se irán anotando aquí.*"
    return "\n".join(f"- {md(n)}" for n in notas)


def nota_adhesiva(texto: str) -> str:
    return f"<div class='adhesiva'><b>Pista de Holmes:</b> {escape(texto).replace(chr(10), '<br>')}</div>"


CABECERA = """
<div class="cabecera-tablero">
  <div class="recorte diario" aria-hidden="true"><span class="chinche ch-bronce"></span><span class="diario-nombre">The Times</span></div>
  <div class="recorte mapa" aria-hidden="true"><span class="chinche ch-bronce"></span>
    <svg viewBox="0 0 196 124" fill="none" stroke="#6E5B40" stroke-width="1">
      <path d="M0 30h196M0 72h196M0 104h196M30 0v124M84 0v124M140 0v124M0 10l196 60M12 124L120 0" stroke-opacity=".55"/>
      <path d="M0 88 C40 70 70 96 110 80 S170 60 196 76" stroke="#5E7B8C" stroke-width="5" stroke-opacity=".5"/>
      <circle cx="96" cy="52" r="5" stroke="#B3221C" stroke-width="2"/>
    </svg>
  </div>
  <svg class="hilo" viewBox="0 0 900 230" preserveAspectRatio="none" aria-hidden="true">
    <path d="M120 22 C 230 250, 640 250, 762 18" fill="none" stroke="#7A1410" stroke-width="2.4" opacity=".35" transform="translate(2 3)"/>
    <path d="M120 22 C 230 250, 640 250, 762 18" fill="none" stroke="#B3221C" stroke-width="2.4"/>
  </svg>
  <div class="placa">
    <span class="tornillo i"></span><span class="tornillo d"></span>
    <div class="placa-titulo">221B Baker Street</div>
    <div class="placa-sub">Londres, 1895 • Sherlock Holmes, detective consultor</div>
  </div>
</div>
"""

BIENVENIDA = """
<div class="bienvenida">
  <div class="foto foto-bienvenida"><span class="chinche ch-rojo"></span>
    <img src="app/static/calle_londres.jpg" alt="Una calle de Londres en la niebla, 1895">
    <div class="foto-pie">Baker Street, una noche de niebla</div>
  </div>
  <div class="papel-bienvenida"><span class="chinche ch-bronce"></span>
    <p>La niebla se pega a los cristales. Sube usted los diecisiete escalones y llama a la puerta.
       Desde dentro llega el gemido de un violín que se interrumpe de golpe.</p>
    <p><b>Escriba su primer mensaje para entrar:</b> Holmes deducirá algo sobre usted y le ofrecerá
       traerle un caso o ayudarle con uno suyo.</p>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# El hilo rojo: el tablero de Holmes al final del caso
# ---------------------------------------------------------------------------

_ANCHO = 760
_TARJETA = (150, 178)
_NOTA = (220, 132)
_FILA_NOTAS = 292
_SALTO_NOTAS = 158
_HILO = {"incrimina": "#B3221C", "descarta": "#2A4F9C"}


def _lineas(texto: str, ancho: int, maximo: int) -> list[str]:
    """Corta un texto en renglones para el SVG; si sobra, el último termina en «…»."""
    renglones = textwrap.wrap(" ".join(texto.split()), ancho) or [""]
    if len(renglones) > maximo:
        renglones = renglones[:maximo]
        renglones[-1] = renglones[-1][: max(ancho - 1, 1)].rstrip(" ,.;:") + "…"
    return renglones


def _texto_svg(x: float, y: float, renglones: list[str], tam: float, salto: float, clase: str,
               centrado: bool = True) -> str:
    ancla = ' text-anchor="middle"' if centrado else ""
    tspans = "".join(f'<tspan x="{x:.0f}" dy="{0 if i == 0 else salto}">{escape(r)}</tspan>'
                     for i, r in enumerate(renglones))
    return f'<text class="{clase}" x="{x:.0f}" y="{y:.0f}" font-size="{tam}"{ancla}>{tspans}</text>'


def _posiciones_tarjetas(cantidad: int) -> list[float]:
    ancho = _TARJETA[0]
    if cantidad <= 1:
        return [(_ANCHO - ancho) / 2]
    margen = 30 if cantidad >= 4 else 70
    paso = (_ANCHO - 2 * margen - ancho) / (cantidad - 1)
    return [margen + i * paso for i in range(cantidad)]


def _datos_tablero(caso: Caso, pistas_anotadas: list[int]):
    """Para cada sospechoso, su sello; para cada pista, a quién se une y si se descubrió."""
    nombres = [s.nombre for s in caso.sospechosos]
    pistas = []
    for n, p in enumerate(caso.pistas, 1):
        destino = p.apunta_a if p.apunta_a in nombres else caso.culpable
        efecto = "descarta" if p.efecto == "descarta" and destino != caso.culpable else "incrimina"
        pistas.append((n, p, destino, efecto, n in pistas_anotadas))
    descartados = {destino for _, _, destino, efecto, _ in pistas if efecto == "descarta"}
    return nombres, pistas, descartados


def _tarjeta_svg(sospechoso, x: float, y: float, giro: float, culpable: bool, descartado: bool,
                 acusado: bool) -> str:
    w, h = _TARJETA
    cx = x + w / 2
    sello = ("CULPABLE", "sello-culpable") if culpable else (
        ("DESCARTADO", "sello-inocente") if descartado else ("INOCENTE", "sello-inocente"))
    partes = [
        f'<g class="tarjeta{" es-culpable" if culpable else ""}" transform="rotate({giro} {cx:.0f} {y + h / 2:.0f})">',
        f'<rect class="papel-tarjeta" x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}"/>',
        f'<rect class="retrato" x="{cx - 31:.0f}" y="{y + 16:.0f}" width="62" height="66"/>',
        f'<circle class="silueta" cx="{cx:.0f}" cy="{y + 40:.0f}" r="12"/>',
        f'<path class="silueta" d="M{cx - 24:.0f} {y + 82:.0f} Q{cx - 22:.0f} {y + 56:.0f} {cx:.0f} {y + 56:.0f} '
        f'Q{cx + 22:.0f} {y + 56:.0f} {cx + 24:.0f} {y + 82:.0f} Z"/>',
        _texto_svg(cx, y + 102, _lineas(sospechoso.nombre, 17, 2), 14, 16, "nombre-tarjeta"),
        _texto_svg(cx, y + 140, _lineas(sospechoso.ocupacion, 22, 2), 12, 14, "oficio-tarjeta"),
        f'<g transform="rotate(-11 {cx:.0f} {y + 52:.0f})">'
        f'<rect class="{sello[1]}" x="{cx - 52:.0f}" y="{y + 40:.0f}" width="104" height="24" rx="3"/>'
        f'<text class="{sello[1]}-texto" x="{cx:.0f}" y="{y + 57:.0f}" font-size="12.5" text-anchor="middle">'
        f'{sello[0]}</text></g>',
        f'<circle class="chinche-svg ch-bronce-svg" cx="{cx:.0f}" cy="{y + 2:.0f}" r="7"/>',
        f'<circle class="chinche-svg ch-bronce-svg" cx="{cx:.0f}" cy="{y + h - 2:.0f}" r="5"/>',
        "</g>",
    ]
    if acusado:
        texto = "Usted lo acusó: acertó" if culpable else "Usted lo acusó"
        partes.append(f'<text class="acusado" x="{cx:.0f}" y="{y + h + 22:.0f}" font-size="12.5" '
                      f'text-anchor="middle">⚖ {texto}</text>')
    return "".join(partes)


def _nota_svg(numero: int, pista, x: float, y: float, giro: float, efecto: str, hallada: bool) -> str:
    w, h = _NOTA
    renglones = _lineas(pista.descripcion, 30, 5 if hallada else 4)
    pie = "" if hallada else (f'<text class="perdida" x="{x + w / 2:.0f}" y="{y + h - 9:.0f}" font-size="11" '
                              'text-anchor="middle">se le pasó por alto</text>')
    color = "ch-rojo-svg" if efecto == "incrimina" else "ch-azul-svg"
    return (
        f'<g class="nota-svg{"" if hallada else " no-hallada"}" transform="rotate({giro} {x + w / 2:.0f} {y + h / 2:.0f})">'
        f"<title>{escape(pista.que_revela)}</title>"
        f'<rect class="papel-nota" x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}"/>'
        f'<text class="numero-nota" x="{x + 12:.0f}" y="{y + 24:.0f}" font-size="12">PISTA {numero}</text>'
        + _texto_svg(x + 12, y + 44, renglones, 13, 16, "texto-nota", centrado=False)
        + pie
        + f'<circle class="chinche-svg {color}" cx="{x + w / 2:.0f}" cy="{y + 3:.0f}" r="7"/></g>'
    )


def hilo_rojo(caso: Caso, pistas_anotadas: list[int], acusado: str | None = None) -> str:
    """El tablero final: sospechosos arriba, pistas abajo y un hilo de cada pista a quien señala.

    En el computador es un dibujo (SVG); en el celular, una lista que se lee sin hacer zoom.
    Se arma solo con los datos del caso guardado, así que no gasta consultas ni imágenes.
    """
    nombres, pistas, descartados = _datos_tablero(caso, pistas_anotadas)
    xs = _posiciones_tarjetas(len(nombres))
    giros_t = [-2, 1.5, -1, 2, -1.5]
    y_t = 26
    anclas = {n: (x + _TARJETA[0] / 2, y_t + _TARJETA[1] - 2) for n, x in zip(nombres, xs)}

    columnas = [30, (_ANCHO - _NOTA[0]) / 2, _ANCHO - 30 - _NOTA[0]]
    giros_n = [-1.5, 1, -.5, 1.8, -1.2, .6]
    notas, hilos = [], []
    for i, (n, pista, destino, efecto, hallada) in enumerate(pistas):
        x = columnas[i % 3]
        y = _FILA_NOTAS + (i // 3) * _SALTO_NOTAS
        px, py = x + _NOTA[0] / 2, y + 3
        ax, ay = anclas[destino]
        cx, cy = (px + ax) / 2, (py + ay) / 2 + 34  # el hilo cuelga un poco
        trazo = f"M{px:.0f} {py:.0f} Q{cx:.0f} {cy:.0f} {ax:.0f} {ay:.0f}"
        estilo = "" if hallada else ' stroke-dasharray="6 5" opacity=".55"'
        hilos.append(f'<path d="{trazo}" class="sombra-hilo" transform="translate(2 3)"/>'
                     f'<path d="{trazo}" class="hilo-{efecto}" stroke="{_HILO[efecto]}"{estilo}/>')
        notas.append(_nota_svg(n, pista, x, y, giros_n[i % len(giros_n)], efecto, hallada))
    tarjetas = [
        _tarjeta_svg(s, x, y_t, giros_t[i % len(giros_t)], s.nombre == caso.culpable,
                     s.nombre in descartados, s.nombre == acusado)
        for i, (s, x) in enumerate(zip(caso.sospechosos, xs))
    ]
    filas = max(1, -(-len(pistas) // 3))
    y_leyenda = _FILA_NOTAS + filas * _SALTO_NOTAS + 4
    leyenda = (
        f'<g class="leyenda" font-size="12">'
        f'<line x1="40" y1="{y_leyenda}" x2="80" y2="{y_leyenda}" stroke="{_HILO["incrimina"]}" stroke-width="3"/>'
        f'<text x="88" y="{y_leyenda + 4}">señala al culpable</text>'
        f'<line x1="250" y1="{y_leyenda}" x2="290" y2="{y_leyenda}" stroke="{_HILO["descarta"]}" stroke-width="3"/>'
        f'<text x="298" y="{y_leyenda + 4}">descarta a un inocente</text>'
        f'<line x1="480" y1="{y_leyenda}" x2="520" y2="{y_leyenda}" stroke="#5A4630" stroke-width="3" '
        f'stroke-dasharray="6 5"/><text x="528" y="{y_leyenda + 4}">pista que no encontró</text></g>'
    )
    alto = y_leyenda + 22
    resumen = f"Tablero del caso: el culpable era {caso.culpable}."
    svg = (
        f'<svg class="hilo-svg" viewBox="0 0 {_ANCHO} {alto}" role="img" aria-label="{escape(resumen)}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<g class="hilos" fill="none" stroke-width="2.4" stroke-linecap="round">{"".join(hilos)}</g>'
        f'{"".join(tarjetas)}{"".join(notas)}{leyenda}</svg>'
    )
    return (
        "<div class='hilo-rojo'><div class='hilo-titulo'>El tablero de Holmes</div>"
        "<div class='hilo-sub'>Cada hilo une una pista con la persona que señala.</div>"
        f"{svg}{_hilo_lista(caso, pistas, descartados, acusado)}</div>"
    )


def _hilo_lista(caso: Caso, pistas, descartados: set[str], acusado: str | None) -> str:
    """La misma información en una lista, para pantallas angostas."""
    personas = []
    for s in caso.sospechosos:
        if s.nombre == caso.culpable:
            estado, clase = "Culpable", "culpable"
        else:
            estado, clase = ("Descartado" if s.nombre in descartados else "Inocente"), "inocente"
        marca = " · <i>usted lo acusó</i>" if s.nombre == acusado else ""
        personas.append(f"<li class='{clase}'><b>{escape(s.nombre)}</b>, {escape(s.ocupacion)} — "
                        f"<span class='estado'>{estado}</span>{marca}</li>")
    filas = []
    for n, p, destino, efecto, hallada in pistas:
        verbo = "señala a" if efecto == "incrimina" else "descarta a"
        perdida = "" if hallada else " <span class='perdida'>(se le pasó por alto)</span>"
        filas.append(
            f"<li class='{efecto}{'' if hallada else ' no-hallada'}'><b>Pista {n}.</b> {escape(p.descripcion)}"
            f"{perdida}<br><span class='destino'>→ {verbo} {escape(destino)}</span>"
            f"<div class='revela'>{escape(p.que_revela)}</div></li>")
    return (f"<div class='hilo-lista'><ul class='personas'>{''.join(personas)}</ul>"
            f"<ul class='pistas'>{''.join(filas)}</ul></div>")


# ---------------------------------------------------------------------------
# El relato de Watson
# ---------------------------------------------------------------------------

def pagina_strand(relato: dict) -> str:
    """Una página de la Strand Magazine con el relato (los textos vienen de la IA: se escapan)."""
    parrafos = "".join(f"<p>{escape(p)}</p>" for p in relato.get("parrafos", []))
    return (
        "<div class='strand'><div class='strand-cabecera'>The Strand Magazine</div>"
        "<div class='strand-sub'>Ilustrada mensualmente · Londres, 1895</div>"
        f"<h3 class='strand-titulo'>{escape(relato.get('titulo', ''))}</h3>"
        "<div class='strand-autor'>Un relato del Dr. John H. Watson</div>"
        f"<div class='strand-cuerpo'>{parrafos}</div></div>"
    )


# ---------------------------------------------------------------------------
# Los desafíos del visitante
# ---------------------------------------------------------------------------

def desafio_html(cifrado: str, svg: str | None = None) -> str:
    """El mensaje cifrado que el visitante le entrega a Holmes."""
    contenido = svg or f"<pre>{escape(cifrado)}</pre>"
    return f"<div class='nota-cifrada desafio'><div class='soporte'>✉️ Mensaje para el señor Holmes</div>{contenido}</div>"


def nota_descifrada(tipo: str | None, nombre: str, mensaje: str, detalle: str = "") -> str:
    """Bajo la respuesta de Holmes: la solución exacta, calculada por la aplicación."""
    if tipo is None:
        return ""
    if tipo == "sin_cifrar":
        return f"<div class='descifrado'>🔍 <b>No estaba cifrado:</b> «{escape(mensaje)}»</div>"
    extra = f" ({escape(detalle)})" if detalle else ""
    return (f"<div class='descifrado'>🔍 <b>Descifrado:</b> «{escape(mensaje)}»"
            f"<span class='metodo'>{escape(nombre)}{extra}</span></div>")
