"""
Piezas visuales que arma la aplicación (no Gemini): la ficha del caso con el
aspecto del medio por el que llegó, la guía «Cómo investigar» y el expediente.

Como los datos salen del caso guardado y no de lo que escriba Holmes, la
información nunca falta. Todo texto que viene de la IA se escapa antes de
meterlo en HTML.
"""

from __future__ import annotations

from html import escape

from juego.caso import Caso
from juego.partida import MEDIOS

ESTILOS = """
<style>
.ficha { position: relative; border-radius: 2px; padding: 16px 18px 14px; margin: 12px 0 6px; color: #E8DCC0;
         background: linear-gradient(180deg, #2E2820, #221D16); border: 1px solid rgba(212,175,97,.45);
         box-shadow: 0 10px 24px rgba(0,0,0,.5), inset 0 0 50px rgba(0,0,0,.35); line-height: 1.5; }
.ficha .encabezado { font-family: 'Cinzel', Georgia, serif; font-weight: 600; font-size: .9rem; letter-spacing: .14em;
                     color: #D4AF61; margin-bottom: 4px; padding-right: 64px; }
.ficha h4 { margin: 0 0 10px; font-family: 'Cinzel', Georgia, serif !important; font-weight: 600; font-size: 1.12rem;
            color: #F3DC9A !important; padding-right: 64px; }
.ficha .dato { margin: 2px 0; }
.ficha .dato b { color: #F3DC9A; }
.ficha .hechos { margin: 9px 0; font-style: italic; color: #D9CDB0; }
.ficha ul { margin: 6px 0 0; padding-left: 0; list-style: none; }
.ficha li { margin-bottom: 7px; padding-left: 12px; border-left: 2px solid rgba(212,175,97,.45); }
.ficha li b { color: #F3DC9A; }
.ficha .motivo { font-style: italic; color: #C9BC9C; }
.ficha .sello { position: absolute; top: 14px; right: 16px; width: 46px; height: 54px; transform: rotate(4deg);
                background: radial-gradient(circle at 50% 42%, #8E6A9A 0, #5C3F68 60%, #3B2744 100%);
                border: 3px dotted #2E2820; outline: 1px solid rgba(232,220,192,.35); opacity: .9; }
.ficha .sello::after { content: ""; position: absolute; inset: 9px 8px; border-radius: 50%;
                       border: 1px solid rgba(255,240,220,.45); }
.ficha .matasellos { position: absolute; top: 20px; right: 50px; width: 46px; height: 46px; border-radius: 50%;
                     border: 2px solid rgba(232,220,192,.35); }
.ficha-telegrama { font-family: 'Special Elite', 'Courier New', monospace; font-size: .92rem;
                   background: linear-gradient(180deg, #2A2A27, #1C1C1A); }
.ficha-telegrama .encabezado { font-size: 1.05rem; letter-spacing: .3em; }
.ficha-telegrama .dato, .ficha-telegrama .hechos, .ficha-telegrama li { font-family: 'Special Elite', 'Courier New', monospace; }
.ficha-periodico { background: linear-gradient(180deg, #2B2822, #1F1C17); border-top: 4px double #D4AF61;
                   border-bottom: 4px double #D4AF61; }
.ficha-periodico .encabezado { text-align: center; font-family: 'Cinzel Decorative', 'Cinzel', serif; font-size: 1.2rem;
                               letter-spacing: .08em; padding-right: 0; }
.ficha-periodico h4 { text-align: center; padding-right: 0; }
.ficha-periodico .sello, .ficha-periodico .matasellos { display: none; }
.ficha-carta { font-style: italic; }
.ficha-carta h4 { font-family: 'Pinyon Script', cursive !important; font-weight: 400; font-size: 1.7rem; }
.ficha-irregular { transform: rotate(-.35deg); border-style: dashed; }
.ficha-irregular .sello, .ficha-irregular .matasellos { display: none; }
.guia { border: 1px solid rgba(212,175,97,.45); border-left: 3px solid #D4AF61; background: rgba(14,15,13,.72);
        padding: 11px 15px; margin: 10px 0 4px; border-radius: 2px; color: #E8DCC0; font-size: .97rem; }
.guia b { color: #F3DC9A; }
.guia ul { margin: 6px 0 0; padding-left: 1.1rem; }
.guia li { margin-bottom: 3px; }
.aviso-acusacion { border: 1px solid #D4AF61; background: radial-gradient(circle at 0 50%, rgba(122,30,26,.55), rgba(14,15,13,.8) 60%);
                   padding: 10px 14px; margin: 10px 0 4px; border-radius: 3px; color: #E8DCC0; }
.aviso-acusacion b { color: #F3DC9A; }
.pista-anotada { font-size: .9rem; color: #D4AF61; margin: 5px 0 0; font-style: italic; }
</style>
"""


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
        cuerpo = cuerpo.replace("</div>", " STOP</div>", 3)
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
