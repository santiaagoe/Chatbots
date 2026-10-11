"""
221B Baker Street — un chatbot de Sherlock Holmes.

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from juego import cifrados, partida
from juego.caso import evaluar_movil, generar_caso
from juego.motor import Motor, leer_configuracion
from juego.partida import PistaCifrada

load_dotenv()

RAIZ = Path(__file__).parent
PROMPT = (RAIZ / "personaje" / "prompt_sistema.md").read_text(encoding="utf-8")
MAX_MENSAJES = int(os.getenv("MAX_MENSAJES_POR_SESION", "80"))
ZONA = ZoneInfo(os.getenv("ZONA_HORARIA", "America/Santiago"))
ESTILO_IMAGEN = "Victorian London, 1895, detailed engraving illustration style, sepia tones"

st.set_page_config(page_title="221B Baker Street", page_icon="🔍", layout="centered")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&family=IM+Fell+English+SC&display=swap');
    h1, h2, h3, .titulo-221b { font-family: 'IM Fell English SC', Georgia, serif !important; }
    .stChatMessage p, .stMarkdown p { font-family: 'IM Fell English', Georgia, serif; font-size: 1.08rem; }
    .titulo-221b { text-align: center; font-size: 2.6rem; margin-bottom: 0; color: #3b2412; }
    .subtitulo-221b { text-align: center; font-style: italic; color: #6b4a2b; margin-top: 0; }
    .nota-cifrada { background: #fbf5e6; border: 1px solid #b89b6a; border-radius: 4px;
                    padding: 14px 16px; margin: 6px 0 4px; box-shadow: 2px 3px 0 #d8c7a3; }
    .nota-cifrada .soporte { font-style: italic; color: #6b4a2b; margin-bottom: 8px; }
    .nota-cifrada pre { white-space: pre-wrap; word-break: break-word; background: transparent;
                        font-size: 1.05rem; color: #2b1d0e; margin: 0; }
    .ayuda { border-left: 3px solid #8a5a2b; padding: 6px 12px; margin: 6px 0; color: #4a3220; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Estado de la sesión
# ---------------------------------------------------------------------------

def estado_inicial() -> dict:
    return {
        "mensajes": [],          # historial (visible y oculto)
        "modo": None,            # None, "A" o "B"
        "caso": None,
        "pistas": [],            # list[PistaCifrada]
        "mensajes_en_caso": 0,
        "imagenes_usadas": 0,
        "terminado": False,
        "puntaje_final": None,
        "titulos_jugados": [],
        "enviados": 0,
    }


for clave, valor in estado_inicial().items():
    st.session_state.setdefault(clave, valor)
st.session_state.setdefault("dificultad", "medio")
S = st.session_state


def reiniciar(conservar_titulos: bool = True) -> None:
    titulos = S.titulos_jugados if conservar_titulos else []
    for clave, valor in estado_inicial().items():
        S[clave] = valor
    S.titulos_jugados = titulos


# ---------------------------------------------------------------------------
# Conexión con Gemini
# ---------------------------------------------------------------------------

def _secretos() -> dict:
    try:
        return dict(st.secrets)
    except Exception:  # noqa: BLE001 — no hay archivo de secrets en local
        return {}


@st.cache_resource(show_spinner=False)
def obtener_motor(api_key: str, modelo_texto: str, modelo_imagen: str, usar_mcp: bool) -> Motor:
    config = leer_configuracion(_secretos())
    config.api_key, config.modelo_texto, config.modelo_imagen, config.usar_mcp = (
        api_key, modelo_texto, modelo_imagen, usar_mcp)
    return Motor(config)


config = leer_configuracion(_secretos())
if not config.api_key:
    st.markdown('<p class="titulo-221b">221B Baker Street</p>', unsafe_allow_html=True)
    st.error(
        "Falta la clave de Gemini. Crea un archivo `.env` con `GEMINI_API_KEY=tu_clave` "
        "(mira `.env.example`) o agrégala en los *secrets* de Streamlit Cloud."
    )
    st.stop()
motor = obtener_motor(config.api_key, config.modelo_texto, config.modelo_imagen, config.usar_mcp)


# ---------------------------------------------------------------------------
# Turnos
# ---------------------------------------------------------------------------

def nota_oculta(texto: str) -> None:
    """Mensaje que solo ve Gemini (resultados, pistas, avisos de la app)."""
    S.mensajes.append({"rol": "user", "texto": "", "para_ia": texto, "oculto": True})


def turno_holmes(adjuntos: dict | None = None) -> dict | None:
    """Pide la respuesta a Holmes, procesa sus etiquetas y la agrega al historial."""
    instruccion = partida.instruccion_sistema(
        PROMPT, S.modo, S.caso, S.pistas, S.terminado, S.imagenes_usadas)
    try:
        with st.spinner("Holmes medita, la pipa entre los dientes…"):
            respuesta = motor.responder(S.mensajes[-40:], instruccion)
    except Exception as error:  # noqa: BLE001
        S.mensajes.append({
            "rol": "model", "oculto": False, "para_ia": "(Holmes no pudo responder.)",
            "texto": "*La señora Hudson asoma la cabeza: «Disculpe, el telégrafo ha dejado de "
                     "funcionar». Holmes suspira con fastidio. Inténtelo de nuevo en un momento.*",
            "error": f"{type(error).__name__}: {error}",
        })
        return None

    etiquetas = partida.extraer_etiquetas(respuesta)
    mensaje = {"rol": "model", "texto": etiquetas.texto, "oculto": False, "imagenes": []}
    mensaje.update(adjuntos or {})

    puede_dibujar = S.modo == "B" and S.caso is not None and not S.terminado
    if etiquetas.imagenes and puede_dibujar and S.imagenes_usadas < partida.MAX_IMAGENES_POR_CASO:
        descripcion = etiquetas.imagenes[0]
        if "victorian" not in descripcion.lower():
            descripcion = f"{descripcion}. {ESTILO_IMAGEN}"
        try:
            with st.spinner("Un dibujante de la Strand Magazine bosqueja la escena…"):
                imagen = motor.generar_imagen(descripcion)
            if imagen:
                mensaje["imagenes"].append(imagen)
                S.imagenes_usadas += 1
        except Exception as error:  # noqa: BLE001
            mensaje["error"] = f"Imagen no disponible ({type(error).__name__}: {error})"

    S.mensajes.append(mensaje)
    if etiquetas.modo and S.modo is None:
        elegir_modo(etiquetas.modo)
    return mensaje


def elegir_modo(modo: str) -> None:
    S.modo = modo
    if modo != "B":
        return
    try:
        with st.spinner("Holmes revuelve el montón de cartas sobre la repisa…"):
            caso = generar_caso(motor, S.dificultad, S.titulos_jugados)
    except Exception as error:  # noqa: BLE001
        S.modo = None
        S.mensajes.append({"rol": "model", "oculto": False, "error": f"{type(error).__name__}: {error}",
                           "texto": "*Holmes busca el expediente, pero la Sra. Hudson parece haberlo "
                                    "ordenado.* ¡Inaceptable! Elija de nuevo en un momento."})
        return
    S.caso = caso
    S.titulos_jugados.append(caso.titulo)
    usados: list[str] = []
    S.pistas = []
    for texto, soporte in zip(caso.mensajes_secretos, caso.soportes_mensajes):
        cifrado = cifrados.cifrar_al_azar(texto, S.dificultad, evitar=usados)
        usados.append(cifrado.tipo)
        S.pistas.append(PistaCifrada(cifrado, soporte))
    nota_oculta("[INICIO CASO] El expediente ha llegado. Presenta el caso.")
    turno_holmes()


def procesar_mensaje(texto: str) -> None:
    S.enviados += 1
    ahora = datetime.now(ZONA)
    S.mensajes.append({"rol": "user", "texto": texto, "oculto": False,
                       "para_ia": f"{partida.contexto_hora(ahora)}\n{texto}"})
    adjuntos = {}
    if S.modo == "B" and S.caso is not None and not S.terminado:
        S.mensajes_en_caso += 1
        indice = partida.pista_a_revelar(S.pistas, S.mensajes_en_caso)
        if indice is not None:
            pista = S.pistas[indice]
            pista.estado = "activa"
            nota_oculta(f"[PISTA CIFRADA] Aparece el mensaje cifrado número {indice + 1}, "
                        f"en {pista.soporte}. Narra el hallazgo sin escribir el mensaje. [/PISTA CIFRADA]")
            adjuntos["pista"] = indice
    turno_holmes(adjuntos)


# ---------------------------------------------------------------------------
# Dibujo de los mensajes
# ---------------------------------------------------------------------------

def mostrar_nota_cifrada(indice: int) -> None:
    pista = S.pistas[indice]
    contenido = pista.cifrado.svg or f"<pre>{pista.cifrado.cifrado}</pre>"
    st.markdown(
        f'<div class="nota-cifrada"><div class="soporte">📜 Mensaje {indice + 1} · {pista.soporte}</div>'
        f"{contenido}</div>",
        unsafe_allow_html=True,
    )


def mostrar_mensaje(m: dict) -> None:
    avatar = "🕵️" if m["rol"] == "model" else "🧑"
    with st.chat_message("assistant" if m["rol"] == "model" else "user", avatar=avatar):
        st.markdown(m["texto"])
        for datos, _mime in m.get("imagenes", []):
            try:
                st.image(datos, width="stretch")
            except Exception:  # noqa: BLE001 — una imagen dañada no debe romper el chat
                st.caption("(La ilustración se ha emborronado con la lluvia.)")
        if "pista" in m:
            mostrar_nota_cifrada(m["pista"])
        if m.get("ayuda"):
            st.markdown(f'<div class="ayuda">💡 {m["ayuda"]}</div>', unsafe_allow_html=True)
        if m.get("ayuda_svg"):
            st.markdown(f'<div class="nota-cifrada">{m["ayuda_svg"]}</div>', unsafe_allow_html=True)
        if m.get("error"):
            st.caption(f"Detalle técnico: {m['error']}")


# ---------------------------------------------------------------------------
# Panel lateral: la libreta de Holmes
# ---------------------------------------------------------------------------

def panel_pistas() -> None:
    for i, pista in enumerate(S.pistas):
        if pista.estado == "oculta":
            continue
        with st.sidebar.expander(f"📜 Mensaje cifrado {i + 1}", expanded=pista.estado == "activa"):
            if pista.estado != "activa":
                resultado = "✅ Resuelto" if pista.estado == "resuelta" else "🏳️ Se rindió"
                st.markdown(f"{resultado} · **{pista.cifrado.nombre}**  \n«{pista.cifrado.mensaje}» "
                            f"· {pista.puntos} puntos")
                continue
            if pista.tipo_ok:
                st.success(f"Código identificado: {pista.cifrado.nombre}")
            with st.form(f"solucion_{i}", clear_on_submit=False):
                tipo = st.selectbox("¿Qué código es?", cifrados.nombres_para_elegir(), key=f"tipo_{i}")
                texto = st.text_input("¿Qué dice?", key=f"texto_{i}")
                enviar = st.form_submit_button("Proponer solución")
            col1, col2 = st.columns(2)
            ayuda = col1.button(f"Pedir pista ({pista.ayudas}/3)", key=f"ayuda_{i}",
                                disabled=pista.ayudas >= 3)
            rendirse = col2.button("Rendirse", key=f"rendirse_{i}")

            if enviar:
                tipo_bien, texto_bien = pista.proponer(tipo, texto)
                S.mensajes.append({"rol": "user", "oculto": False, "texto": f"📝 Propongo: *{tipo}* — «{texto}»",
                                   "para_ia": f"(El visitante propone para el mensaje {i + 1}: {tipo} — «{texto}»)"})
                if pista.estado == "resuelta":
                    resumen = f"¡Resuelto! Decía «{pista.cifrado.mensaje}». Puntos: {pista.puntos}."
                else:
                    resumen = (f"Tipo de código {'correcto' if tipo_bien else 'incorrecto'}; "
                               f"mensaje {'correcto' if texto_bien else 'incorrecto'}. No reveles la solución.")
                nota_oculta(f"[RESULTADO] Mensaje cifrado {i + 1}: {resumen} [/RESULTADO]")
                turno_holmes()
                st.rerun()
            if ayuda:
                texto_ayuda = pista.siguiente_ayuda()
                adjuntos = {"ayuda": texto_ayuda}
                if pista.cifrado.tipo == "bailarines" and pista.ayudas == 3:
                    adjuntos["ayuda_svg"] = cifrados.bailarines_leyenda()
                S.mensajes.append({"rol": "user", "oculto": False, "texto": "🤔 ¿Alguna pista, señor Holmes?"})
                nota_oculta(f"[AYUDA CIFRADO] {texto_ayuda} [/AYUDA CIFRADO] "
                            "(La aplicación mostrará el texto exacto de la pista bajo tu respuesta.)")
                turno_holmes(adjuntos)
                st.rerun()
            if rendirse:
                pista.rendirse()
                S.mensajes.append({"rol": "user", "oculto": False, "texto": "🏳️ Me rindo con este mensaje."})
                nota_oculta(f"[RESULTADO] El visitante se rindió con el mensaje {i + 1}. Era "
                            f"{pista.cifrado.nombre} y decía «{pista.cifrado.mensaje}». Explícale cómo "
                            "descifrarlo y qué significa para el caso. [/RESULTADO]")
                turno_holmes()
                st.rerun()


def panel_acusacion() -> None:
    caso = S.caso
    with st.sidebar.expander("⚖️ Acusación final", expanded=False):
        if S.terminado:
            st.markdown(f"Culpable: **{caso.culpable}**  \nMóvil: {caso.movil}")
            return
        st.caption("Es definitiva: piénsela bien.")
        with st.form("acusacion"):
            culpable = st.selectbox("Culpable", [s.nombre for s in caso.sospechosos])
            movil = st.text_area("Móvil", placeholder="¿Por qué lo hizo?")
            acusar = st.form_submit_button("Acusar")
        if acusar:
            S.mensajes.append({"rol": "user", "oculto": False,
                               "texto": f"⚖️ Acuso a **{culpable}**. Móvil: {movil}"})
            try:
                with st.spinner("Holmes cierra los ojos y junta las yemas de los dedos…"):
                    veredicto = evaluar_movil(motor, caso, movil)
                movil_bien, comentario = veredicto.movil_correcto, veredicto.comentario
            except Exception:  # noqa: BLE001
                movil_bien, comentario = False, "No se pudo evaluar el móvil."
            culpable_bien = culpable == caso.culpable
            puntos_pistas = sum(p.puntos for p in S.pistas)
            S.puntaje_final = (puntos_pistas + partida.PUNTOS_CULPABLE * culpable_bien
                               + partida.PUNTOS_MOVIL * movil_bien)
            S.terminado = True
            nota_oculta(
                f"[RESULTADO] ACUSACIÓN FINAL. Culpable propuesto: {culpable} "
                f"({'CORRECTO' if culpable_bien else 'INCORRECTO'}). Móvil "
                f"{'CORRECTO' if movil_bien else 'INCORRECTO'} ({comentario}). Puntaje final: "
                f"{S.puntaje_final}. El caso ha terminado: revela la solución completa con tu "
                "razonamiento, como en el final de tus relatos. [/RESULTADO]")
            turno_holmes()
            st.rerun()


with st.sidebar:
    st.markdown("## 🔍 La libreta de Holmes")
    if S.modo is None:
        S.dificultad = st.select_slider("Dificultad de los casos", cifrados.DIFICULTADES, value=S.dificultad)
        if S.mensajes:
            st.caption("Elija su camino:")
            if st.button("🔎 A · Traigo un caso", width="stretch"):
                procesar_mensaje("Elijo la opción A: le traigo un caso.")
                st.rerun()
            if st.button("🕵️ B · Ayudar a Holmes", width="stretch"):
                procesar_mensaje("Elijo la opción B: quiero ayudarle con su caso.")
                st.rerun()
    elif S.modo == "A":
        st.markdown("**Modo A** · Usted trae el caso.")
    else:
        st.markdown(f"**Modo B** · Dificultad {S.dificultad}")
        if S.caso:
            st.markdown(f"*{S.caso.titulo}*")
            st.caption(f"Imágenes: {S.imagenes_usadas}/{partida.MAX_IMAGENES_POR_CASO}")
            puntos = sum(p.puntos for p in S.pistas)
            st.metric("Puntaje", S.puntaje_final if S.terminado else puntos)

    if S.modo == "B" and S.caso:
        panel_pistas()
        panel_acusacion()
        if S.terminado and st.button("📬 Nuevo caso", width="stretch"):
            reiniciar()
            st.rerun()

    st.divider()
    if st.button("🚪 Salir de Baker Street (reiniciar)", width="stretch"):
        reiniciar()
        st.rerun()
    if motor.mcp_fallo:
        st.caption(f"Índice MCP no disponible: {motor.mcp_fallo}")
    st.caption(f"Modelo: {config.modelo_texto} · Índice MCP: {'activo' if config.usar_mcp else 'apagado'}")


# ---------------------------------------------------------------------------
# Conversación
# ---------------------------------------------------------------------------

st.markdown('<p class="titulo-221b">221B Baker Street</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo-221b">Londres, 1895 · Sherlock Holmes, detective consultor</p>',
            unsafe_allow_html=True)

if not S.mensajes:
    st.markdown(
        "> *La niebla se pega a los cristales. Sube usted los diecisiete escalones y llama a la puerta. "
        "Desde dentro llega el gemido de un violín que se interrumpe de golpe.*\n\n"
        "Escriba su primer mensaje para entrar. Holmes deducirá algo sobre usted… "
        "y le ofrecerá traerle un caso o ayudarle con uno suyo."
    )

for m in S.mensajes:
    if not m.get("oculto"):
        mostrar_mensaje(m)

limite = S.enviados >= MAX_MENSAJES
if limite:
    st.info("Holmes consulta su reloj: «Me temo que debo atender a otro cliente». "
            "Se alcanzó el límite de mensajes de esta sesión; reinicie para continuar.")

if entrada := st.chat_input("Hable con Holmes…", disabled=limite):
    procesar_mensaje(entrada)
    st.rerun()
