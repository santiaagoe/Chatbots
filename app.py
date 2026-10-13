"""
221B Baker Street — un chatbot de Sherlock Holmes.

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import os
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from juego import cifrados, fichas, partida
from juego.caso import evaluar_movil, generar_caso
from juego.imagenes_cloudflare import ErrorCloudflare
from juego.motor import Motor, imagen_no_disponible, leer_configuracion, sin_cuota
from juego.partida import PistaCifrada

load_dotenv()

RAIZ = Path(__file__).parent
PROMPT = (RAIZ / "personaje" / "prompt_sistema.md").read_text(encoding="utf-8")
MAX_MENSAJES = int(os.getenv("MAX_MENSAJES_POR_SESION", "80"))
ZONA = ZoneInfo(os.getenv("ZONA_HORARIA", "America/Santiago"))
ESTILO_IMAGEN = ("Victorian London, 1895, detailed engraving illustration style, sepia tones, "
                 "no text, no lettering")

st.set_page_config(page_title="221B Baker Street", page_icon="🔍", layout="centered")

TEMA = (RAIZ / "estilo" / "tema.css").read_text(encoding="utf-8")
AVATAR_HOLMES = str(RAIZ / "static" / "avatar_holmes.png")
st.markdown(f"<style>{TEMA}</style>", unsafe_allow_html=True)
st.markdown(fichas.ESTILOS, unsafe_allow_html=True)
st.markdown(  # velas decorativas; el CSS las oculta en pantallas pequeñas
    '<div class="velas" aria-hidden="true">'
    '<div class="vela der2"><div class="halo"></div><div class="llama"></div><div class="cuerpo"></div></div>'
    '<div class="vela der"><div class="halo"></div><div class="llama"></div><div class="cuerpo"></div></div>'
    "</div>", unsafe_allow_html=True)


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
        "medio": None,             # cómo llegó el caso: telegrama, periódico, carta o Irregular
        "pistas_anotadas": [],     # números (desde 1) de las pistas del caso ya descubiertas
        "escena_dibujada": False,
        "acusacion_sugerida": False,
        "abrir_acusacion": False,  # abre el panel ⚖️ cuando el visitante intenta acusar
    }


for clave, valor in estado_inicial().items():
    st.session_state.setdefault(clave, valor)
st.session_state.setdefault("dificultad", "medio")
st.session_state.setdefault("ultimo_medio", None)
S = st.session_state


def reiniciar(conservar_titulos: bool = True) -> None:
    titulos = S.titulos_jugados if conservar_titulos else []
    enviados = S.enviados  # el límite de mensajes no se reinicia con el botón
    for clave, valor in estado_inicial().items():
        S[clave] = valor
    S.titulos_jugados = titulos
    S.enviados = enviados


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
    st.markdown('<div class="cabecera"><div class="titulo-221b">221B Baker Street</div></div>', unsafe_allow_html=True)
    st.error(
        "Falta la clave de Gemini. Crea un archivo `.env` con `GEMINI_API_KEY=tu_clave` "
        "(mira `.env.example`) o agrégala en los *secrets* de Streamlit Cloud."
    )
    st.stop()
# Estado por visitante que depende de la configuración (no se borra al reiniciar el caso)
S.setdefault("imagenes_activas", config.generar_imagenes)
S.setdefault("ultimo_modelo", None)
motor = obtener_motor(config.api_key, config.modelo_texto, config.modelo_imagen, config.usar_mcp)


# ---------------------------------------------------------------------------
# Turnos
# ---------------------------------------------------------------------------

def nota_oculta(texto: str) -> None:
    """Mensaje que solo ve Gemini (resultados, pistas, avisos de la app)."""
    S.mensajes.append({"rol": "user", "texto": "", "para_ia": texto, "oculto": True})


def explicar_error(error: Exception) -> str:
    """Texto del «detalle técnico» que se muestra bajo el mensaje."""
    codigo = getattr(error, "code", None)
    if isinstance(error, ErrorCloudflare):
        if codigo in (401, 403):
            return ("Cloudflare rechazó las credenciales. Revisa CLOUDFLARE_ACCOUNT_ID y "
                    "CLOUDFLARE_API_TOKEN en el .env (el token necesita el permiso «Workers AI»).")
        if codigo == 429:
            return ("Se agotó la cuota gratuita diaria de imágenes de Cloudflare. "
                    "Se renueva cada día a las 00:00 UTC (21:00 en Chile).")
        return f"El generador de imágenes de Cloudflare falló ({error})."
    if codigo in (500, 503, 504):
        return (f"Los servidores de Google están saturados ({codigo}). No es un error de la app: "
                "se reintentó varias veces, también con el modelo de respaldo. Espera un minuto y vuelve a escribir.")
    if sin_cuota(error):
        return ("Tu clave de Gemini está en el nivel gratuito, que no incluye este modelo (límite 0). "
                "No es un límite que se agote: esperar no lo arregla. Para tener imágenes hay que "
                "activar la facturación en Google AI Studio. Mientras tanto, Holmes seguirá sin imágenes.")
    if codigo == 429:
        return ("Se alcanzó el límite de uso de la clave de Gemini (429). En el nivel gratuito "
                "hay un máximo de mensajes por minuto y por día; espera un poco.")
    if codigo in (400, 401, 403) and "key" in str(error).lower():
        return "La clave de Gemini no es válida. Revisa GEMINI_API_KEY en el archivo .env."
    return f"{type(error).__name__}: {error}"


def turno_holmes(adjuntos: dict | None = None, permitir_imagen: bool = True) -> dict | None:
    """Pide la respuesta a Holmes, procesa sus etiquetas y la agrega al historial.

    Los `adjuntos` (ficha, guía, nota cifrada, avisos) los arma la aplicación y se muestran
    bajo el mensaje aunque Gemini falle.
    """
    instruccion = partida.instruccion_sistema(
        PROMPT, S.modo, S.caso, S.pistas, S.terminado, S.imagenes_usadas, S.imagenes_activas,
        S.pistas_anotadas, S.escena_dibujada)
    try:
        with st.spinner("Holmes medita, la pipa entre los dientes…"):
            respuesta = motor.responder(S.mensajes[-40:], instruccion)
        S.ultimo_modelo = motor.ultimo_modelo
    except Exception as error:  # noqa: BLE001
        S.mensajes.append({
            "rol": "model", "oculto": False, "para_ia": "(Holmes no pudo responder.)",
            "texto": "*La señora Hudson asoma la cabeza: «Disculpe, el telégrafo ha dejado de "
                     "funcionar». Holmes suspira con fastidio. Inténtelo de nuevo en un momento.*",
            "error": explicar_error(error),
            **(adjuntos or {}),
        })
        return None

    etiquetas = partida.extraer_etiquetas(respuesta)
    mensaje = {"rol": "model", "texto": etiquetas.texto, "oculto": False, "imagenes": []}
    mensaje.update(adjuntos or {})

    en_caso = S.modo == "B" and S.caso is not None and not S.terminado
    if en_caso:
        nuevas = [n for n in etiquetas.pistas
                  if 1 <= n <= len(S.caso.pistas) and n not in S.pistas_anotadas]
        if nuevas:
            S.pistas_anotadas.extend(nuevas)
            mensaje["pistas_html"] = "".join(fichas.pista_anotada(S.caso, n) for n in nuevas)

    puede_dibujar = (permitir_imagen and en_caso and S.imagenes_activas
                     and S.imagenes_usadas < partida.MAX_IMAGENES_POR_CASO)
    if etiquetas.imagenes and puede_dibujar:
        dibujar_imagen(etiquetas.imagenes[0], mensaje)

    S.mensajes.append(mensaje)
    if etiquetas.modo and S.modo is None:
        elegir_modo(etiquetas.modo)
    return mensaje


def dibujar_imagen(pedido: partida.PedidoImagen, mensaje: dict) -> None:
    """La primera imagen del caso es siempre la escena, dibujada con los datos del caso."""
    if not S.escena_dibujada:
        descripcion, pie, es_escena = S.caso.escena_visual, S.caso.escena_nombre, True
    elif pedido.es_escena:
        return  # la escena ya se dibujó; no se gasta otra imagen en lo mismo
    else:
        descripcion, pie, es_escena = pedido.descripcion, pedido.pie, False
    try:
        with st.spinner("Un dibujante de la Strand Magazine bosqueja la escena…"):
            imagen = motor.generar_imagen(f"{descripcion}. {ESTILO_IMAGEN}")
        if imagen:
            datos, mime = imagen[0], imagen[1]
            mensaje["imagenes"].append((datos, mime, pie))
            S.imagenes_usadas += 1
            S.escena_dibujada = S.escena_dibujada or es_escena
    except Exception as error:  # noqa: BLE001
        mensaje["error"] = f"Imagen no disponible. {explicar_error(error)}"
        if imagen_no_disponible(error):
            S.imagenes_activas = False  # solo para este visitante


def elegir_modo(modo: str) -> None:
    S.modo = modo
    if modo != "B":
        return
    try:
        medio = partida.elegir_medio(S.ultimo_medio)
        with st.spinner("Holmes revuelve el montón de cartas sobre la repisa…"):
            caso = generar_caso(motor, S.dificultad, S.titulos_jugados,
                                medio=partida.MEDIOS[medio]["descripcion"])
    except Exception as error:  # noqa: BLE001
        S.modo = None
        S.mensajes.append({"rol": "model", "oculto": False, "error": explicar_error(error),
                           "texto": "*Holmes busca el expediente, pero la Sra. Hudson parece haberlo "
                                    "ordenado.* ¡Inaceptable! Elija de nuevo en un momento."})
        return
    S.caso = caso
    S.medio = S.ultimo_medio = medio
    S.titulos_jugados.append(caso.titulo)
    usados: list[str] = []
    S.pistas = []
    for texto, soporte in zip(caso.mensajes_secretos, caso.soportes_mensajes):
        cifrado = cifrados.cifrar_al_azar(texto, S.dificultad, evitar=usados)
        usados.append(cifrado.tipo)
        S.pistas.append(PistaCifrada(cifrado, soporte))
    nota_oculta(partida.instruccion_presentacion(caso, medio))
    turno_holmes({"ficha_html": fichas.ficha_caso(caso, medio), "guia": True}, permitir_imagen=False)


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
        if partida.quiere_acusar(texto):
            S.abrir_acusacion = True
            adjuntos["aviso_acusacion"] = True
            nota_oculta("[AVISO ACUSACION] El visitante intenta acusar en el chat. Responde a su "
                        "razonamiento sin confirmar ni negar si acierta, y recuérdale con tu voz que la "
                        "acusación formal se escribe en tu libreta, en «Acusación final» (la barra lateral), "
                        "donde elegirá al culpable y escribirá el móvil. [/AVISO ACUSACION]")
        elif not S.acusacion_sugerida and partida.toca_sugerir_acusacion(S.pistas_anotadas, len(S.caso.pistas)):
            S.acusacion_sugerida = True
            adjuntos["aviso_acusacion"] = True
            nota_oculta("[SUGERIR ACUSACION] El visitante ya reunió la mayoría de las pistas. Al final de "
                        "tu respuesta sugiérele que, cuando esté seguro, haga la acusación en tu libreta, "
                        "en «Acusación final» (la barra lateral). [/SUGERIR ACUSACION]")
    turno_holmes(adjuntos)


# ---------------------------------------------------------------------------
# Dibujo de los mensajes
# ---------------------------------------------------------------------------

def mostrar_nota_cifrada(indice: int) -> None:
    pista = S.pistas[indice]
    contenido = pista.cifrado.svg or f"<pre>{escape(pista.cifrado.cifrado)}</pre>"
    st.markdown(
        f'<div class="nota-cifrada"><div class="soporte">📜 Mensaje {indice + 1} · {escape(pista.soporte)}</div>'
        f"{contenido}</div>",
        unsafe_allow_html=True,
    )


def mostrar_mensaje(m: dict) -> None:
    avatar = AVATAR_HOLMES if m["rol"] == "model" else "user"
    with st.chat_message("assistant" if m["rol"] == "model" else "user", avatar=avatar):
        st.markdown(m["texto"])
        if m.get("ficha_html"):
            st.markdown(m["ficha_html"], unsafe_allow_html=True)
        for imagen in m.get("imagenes", []):
            datos, pie = imagen[0], (imagen[2] if len(imagen) > 2 else None)
            try:
                st.image(datos, caption=pie or None, width="stretch")
            except Exception:  # noqa: BLE001 — una imagen dañada no debe romper el chat
                st.caption("(La ilustración se ha emborronado con la lluvia.)")
        if "pista" in m:
            mostrar_nota_cifrada(m["pista"])
        if m.get("pistas_html"):
            st.markdown(m["pistas_html"], unsafe_allow_html=True)
        if m.get("guia"):
            st.markdown(fichas.GUIA, unsafe_allow_html=True)
        if m.get("aviso_acusacion"):
            st.markdown(fichas.AVISO_ACUSACION, unsafe_allow_html=True)
        if m.get("ayuda"):
            st.markdown(f'<div class="ayuda">💡 {escape(m["ayuda"]).replace(chr(10), "<br>")}</div>',
                        unsafe_allow_html=True)
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
        with st.sidebar.expander(f"Mensaje cifrado {i + 1}", expanded=pista.estado == "activa",
                                 icon=":material/description:"):
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
    with st.sidebar.expander("Acusación final", expanded=S.abrir_acusacion or S.terminado,
                             icon=":material/balance:"):
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
    if S.modo is None:
        st.markdown('<div class="insignia">Baker Street, 221B</div>', unsafe_allow_html=True)
        S.dificultad = st.select_slider("Dificultad de los casos", cifrados.DIFICULTADES, value=S.dificultad)
        if S.mensajes:
            st.caption("Elija su camino:")
            if st.button("A · Traigo un caso", icon=":material/search:", width="stretch"):
                procesar_mensaje("Elijo la opción A: le traigo un caso.")
                st.rerun()
            if st.button("B · Ayudar a Holmes", icon=":material/person_search:", width="stretch"):
                procesar_mensaje("Elijo la opción B: quiero ayudarle con su caso.")
                st.rerun()
    elif S.modo == "A":
        st.markdown('<div class="insignia">Modo A · Usted trae el caso</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="insignia">Modo B · Dificultad {escape(S.dificultad)}</div>',
                    unsafe_allow_html=True)
        if S.caso:
            puntos = S.puntaje_final if S.terminado else sum(p.puntos for p in S.pistas)
            imagenes = (f"imágenes {S.imagenes_usadas} de {partida.MAX_IMAGENES_POR_CASO}" if S.imagenes_activas
                        else "imágenes desactivadas")
            st.markdown(f'<div class="estado-caso">Puntaje {puntos}, {imagenes}</div>', unsafe_allow_html=True)

    if S.modo == "B" and S.caso:
        with st.expander("Expediente", expanded=True, icon=":material/folder_open:"):
            st.markdown(fichas.expediente_markdown(S.caso, S.pistas_anotadas))
        with st.expander("Sospechosos", expanded=True, icon=":material/groups:"):
            st.markdown(fichas.sospechosos_markdown(S.caso))
        panel_pistas()
        panel_acusacion()
        if S.terminado and st.button("Nuevo caso", icon=":material/mail:", width="stretch"):
            reiniciar()
            st.rerun()

    st.divider()
    if st.button("Salir de Baker Street (reiniciar)", icon=":material/door_open:", width="stretch"):
        reiniciar()
        st.rerun()
    if motor.mcp_fallo:
        st.caption(f"Índice MCP no disponible: {motor.mcp_fallo}")
    if S.ultimo_modelo and S.ultimo_modelo != config.modelo_texto:
        st.caption(f"⚠️ {config.modelo_texto} estaba saturado; respondió el modelo de respaldo "
                   f"({S.ultimo_modelo}).")
    st.caption(f"Modelo: {config.modelo_texto} · Índice MCP: {'activo' if config.usar_mcp else 'apagado'} · "
               f"Imágenes: {'Cloudflare' if config.usa_cloudflare else 'Gemini'}")


# ---------------------------------------------------------------------------
# Conversación
# ---------------------------------------------------------------------------

ORNAMENTO = (  # filigrana dorada del encabezado
    '<svg viewBox="0 0 420 36" aria-hidden="true" fill="none" stroke="#D4AF61" stroke-width="1.4">'
    '<path d="M10 18h140M270 18h140"/><path d="M150 18c14 0 18-12 30-12 10 0 14 7 14 12s-4 12-14 12c-12 0-16-12-30-12z"/>'
    '<path d="M270 18c-14 0-18-12-30-12-10 0-14 7-14 12s4 12 14 12c12 0 16-12 30-12z"/>'
    '<path d="M196 18c4-9 10-13 14-13s10 4 14 13c-4 9-10 13-14 13s-10-4-14-13z" fill="#D4AF61" fill-opacity=".25"/>'
    '<circle cx="210" cy="18" r="3.2" fill="#D4AF61"/><circle cx="6" cy="18" r="2.4" fill="#D4AF61"/>'
    '<circle cx="414" cy="18" r="2.4" fill="#D4AF61"/></svg>'
)
st.markdown(
    f'<div class="cabecera">{ORNAMENTO}<div class="titulo-221b">221B Baker Street</div>'
    '<div class="subtitulo-221b">Londres, 1895 • Sherlock Holmes, detective consultor</div>'
    f'<div style="transform: scaleY(-1)">{ORNAMENTO}</div></div>',
    unsafe_allow_html=True)

if not S.mensajes:
    st.markdown(
        '<p class="entrada-escena">La niebla se pega a los cristales. Sube usted los diecisiete escalones y '
        "llama a la puerta. Desde dentro llega el gemido de un violín que se interrumpe de golpe.</p>"
        '<p class="entrada-escena">Escriba su primer mensaje para entrar: Holmes deducirá algo sobre usted '
        "y le ofrecerá traerle un caso o ayudarle con uno suyo.</p>",
        unsafe_allow_html=True)

for m in S.mensajes:
    if not m.get("oculto"):
        mostrar_mensaje(m)

limite = S.enviados >= MAX_MENSAJES
if limite:
    st.info("Holmes consulta su reloj: «Me temo que debo atender a otro cliente». "
            "Se alcanzó el límite de mensajes de esta sesión.")

def acciones_rapidas() -> None:
    """Botones con sello de lacre que sugieren el siguiente paso de la investigación."""
    st.markdown('<p class="titulo-acciones">¿Qué hacemos ahora?</p>', unsafe_allow_html=True)
    escena = ("Ir a la escena del crimen", "Vamos a la escena del crimen, señor Holmes.") \
        if not S.escena_dibujada else ("Examinar la escena", "Examinemos la escena con más detalle.")
    acciones = [
        ("escena", *escena),
        ("repasar", "Repasar lo que sabemos", "Repasemos lo que sabemos hasta ahora, señor Holmes."),
        ("acusar", "Creo que ya sé quién fue", "Creo que ya sé quién fue, señor Holmes."),
    ]
    columnas = st.columns(len(acciones) + 1)
    for columna, (clave, etiqueta, texto) in zip(columnas, acciones):
        if columna.button(etiqueta, key=f"accion_{clave}", width="stretch"):
            procesar_mensaje(texto)
            st.rerun()
    with columnas[-1].popover("Interrogar a…", key="interrogar", width="stretch"):
        for i, s in enumerate(S.caso.sospechosos):
            if st.button(f"{s.nombre}, {s.ocupacion}", key=f"sospechoso_{i}", width="stretch"):
                procesar_mensaje(f"Quiero interrogar a {s.nombre}.")
                st.rerun()


if S.modo == "B" and S.caso is not None and not S.terminado and not limite:
    acciones_rapidas()

if entrada := st.chat_input("Hable con Holmes...", disabled=limite):
    procesar_mensaje(entrada)
    st.rerun()
