"""
221B Baker Street — un chatbot de Sherlock Holmes.

Ejecutar:  streamlit run app.py
"""

from __future__ import annotations

import os
import random
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from juego import cifrados, descifrador, fichas, partida, relato
from juego.caso import evaluar_movil, generar_caso, generar_opciones
from juego.caso_muestra import CASOS_MUESTRA, buscar_muestra, elegir_muestra
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
st.markdown(  # vela decorativa del escritorio; el CSS la oculta en pantallas pequeñas
    '<div class="velas" aria-hidden="true">'
    '<div class="vela der"><div class="halo"></div><div class="llama"></div><div class="cuerpo"></div>'
    '<div class="base"></div></div></div>', unsafe_allow_html=True)


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
        "opciones_caso": None,     # los tres expedientes que se ofrecen en el modo B
        "notas_a": [],             # datos que Holmes anota en el modo A
        "acusacion_hecha": None,   # lo que acusó el visitante: culpable, móvil y si acertó
        "mensajes_en_a": 0,        # mensajes del visitante contando su caso (modo A)
        "relato_escrito": False,   # Watson ya escribió el relato de este caso
        "desafio_pendiente": None, # mensaje cifrado del visitante que Holmes no pudo leer (espera la clave)
    }


for clave, valor in estado_inicial().items():
    st.session_state.setdefault(clave, valor)
st.session_state.setdefault("dificultad", "medio")
st.session_state.setdefault("ultimo_medio", None)
S = st.session_state


def reiniciar(conservar_titulos: bool = True, conservar_mensajes: bool = False) -> None:
    titulos = S.titulos_jugados if conservar_titulos else []
    enviados = S.enviados  # el límite de mensajes no se reinicia con el botón
    mensajes = S.mensajes
    for clave, valor in estado_inicial().items():
        S[clave] = valor
    S.titulos_jugados = titulos
    S.enviados = enviados
    if conservar_mensajes:
        S.mensajes = mensajes


def cambiar_camino() -> None:
    """Vuelve a la elección A/B sin borrar la conversación."""
    reiniciar(conservar_mensajes=True)
    nota_oculta("[CONTEXTO] El visitante decidió cambiar de camino. El caso anterior quedó cerrado.")
    S.mensajes.append({"rol": "model", "oculto": False, "camino": True,
                       "texto": "*Holmes cierra la carpeta y la devuelve a la repisa.* "
                                "Muy bien. ¿Qué camino prefiere ahora, colega?"})


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
        ultimo = next((m["texto"] for m in reversed(S.mensajes) if m["rol"] == "user" and not m.get("oculto")), "")
        with st.spinner(partida.frase("pensar")):
            respuesta = motor.responder(S.mensajes[-40:], instruccion,
                                        usar_indice=partida.necesita_indice(ultimo))
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

    if S.modo == "A":
        for nota in etiquetas.notas:
            if nota and nota not in S.notas_a:
                S.notas_a.append(nota)
        S.notas_a = S.notas_a[-20:]

    S.mensajes.append(mensaje)
    if etiquetas.modo and S.modo is None:  # respaldo: la app ya detecta la elección por su cuenta
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
        with st.spinner(partida.frase("dibujo")):
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
    if modo == "B":
        ofrecer_expedientes()


def ofrecer_expedientes() -> None:
    """Holmes pone tres expedientes sobre la mesa: dos nuevos (una sola consulta a Gemini) y uno de muestra.

    Si Gemini falla, igual queda el caso de muestra para jugar.
    """
    error_generacion = None
    muestra = elegir_muestra(S.dificultad, S.titulos_jugados)
    try:
        with st.spinner(partida.frase("expedientes")):
            opciones = generar_opciones(motor, S.dificultad, S.titulos_jugados, reservado=muestra.tema)
    except Exception as error:  # noqa: BLE001
        opciones, error_generacion = [], error
    opciones = opciones + [muestra.opcion.model_copy()]
    for m in S.mensajes:  # una oferta anterior ya no se puede elegir
        if m.get("expedientes") and m.get("elegido") is None:
            m["elegido"] = -1
    S.opciones_caso = opciones
    resumen = "; ".join(f"{i + 1}) «{o.titulo}», {o.tipo_crimen} en {o.lugar}" for i, o in enumerate(opciones))
    mensaje = {
        "rol": "model", "oculto": False, "texto": random.choice(partida.PRESENTA_EXPEDIENTES),
        "para_ia": f"(Muestras al visitante expedientes para elegir: {resumen}.)",
        "expedientes": [o.model_dump() for o in opciones],
    }
    if error_generacion is not None:
        mensaje["texto"] = ("*Holmes rebusca en vano: la Sra. Hudson ha ordenado sus papeles.* «Solo encuentro "
                            "este expediente, colega, pero le aseguro que es de lo más singular.»")
        mensaje["error"] = f"No se pudieron crear casos nuevos. {explicar_error(error_generacion)}"
    S.mensajes.append(mensaje)


def abrir_expediente(indice: int) -> None:
    """El visitante eligió un expediente: se genera el caso completo y se presenta."""
    opcion = S.opciones_caso[indice]
    S.enviados += 1
    S.mensajes.append({"rol": "user", "oculto": False, "texto": f"Abro el expediente «{opcion.titulo}»."})
    try:
        if opcion.muestra:  # caso escrito a mano: no gasta consultas y siempre funciona
            muestra = buscar_muestra(opcion.titulo) or CASOS_MUESTRA[1]
            medio, caso = muestra.medio, muestra.crear()
        else:
            medio = partida.elegir_medio(S.ultimo_medio)
            with st.spinner(partida.frase("caso")):
                caso = generar_caso(motor, S.dificultad, S.titulos_jugados,
                                    medio=partida.MEDIOS[medio]["descripcion"], semilla=opcion)
    except Exception as error:  # noqa: BLE001
        S.mensajes.append({"rol": "model", "oculto": False, "error": explicar_error(error),
                           "texto": "*Holmes abre la carpeta y frunce el ceño: faltan páginas.* "
                                    "Inténtelo de nuevo en un momento, o abra el caso de muestra, "
                                    "que está completo."})
        return
    for m in S.mensajes:  # marca la carpeta elegida y retira los botones
        if m.get("expedientes") and m.get("elegido") is None:
            m["elegido"] = indice
    S.opciones_caso = None
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
    contaba_su_caso = S.modo == "A"  # el mensaje con el que elige el camino A no cuenta
    if S.modo is None:
        modo = partida.detectar_modo(texto)
        if modo == "B":  # Holmes saca los expedientes sin gastar una consulta extra
            elegir_modo("B")
            return
        if modo == "A":
            S.modo = "A"
    if responder_desafio_en_chat(texto):
        return
    if contaba_su_caso:
        S.mensajes_en_a += 1
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
# El visitante desafía a Holmes con un mensaje cifrado
# ---------------------------------------------------------------------------

def textos_visibles() -> list[str]:
    return [m["texto"] for m in S.mensajes if not m.get("oculto") and m.get("texto")]


def analizar_desafio(desafio: descifrador.Desafio, clave: str | None = None) -> descifrador.Hallazgo:
    with st.spinner(partida.frase("descifrar")):
        return descifrador.analizar_desafio(
            desafio, descifrador.claves_de_conversacion(textos_visibles()[:-1]), clave_dada=clave)


def resolver_desafio(desafio: descifrador.Desafio, hallazgo: descifrador.Hallazgo) -> None:
    """El código ya descifró (Holmes no se equivoca); Holmes lo cuenta con su voz."""
    indice = None
    if S.modo == "B" and S.caso is not None and not S.terminado:
        indice = descifrador.es_mensaje_del_caso(hallazgo, desafio.cifrado, S.pistas)
    nota_oculta(descifrador.instruccion_para_holmes(hallazgo, indice))
    adjuntos = {}
    if indice is None:
        S.desafio_pendiente = vars(desafio) if hallazgo.tipo is None else None
        if hallazgo.tipo is not None:
            adjuntos["descifrado_html"] = fichas.nota_descifrada(hallazgo.tipo, hallazgo.nombre, hallazgo.mensaje,
                                                                  hallazgo.detalle)
    turno_holmes(adjuntos, permitir_imagen=False)


def responder_desafio_en_chat(texto: str) -> bool:
    """«Descifre esto: …», Morse pegado en el chat o la clave de un desafío pendiente. True si lo atendió."""
    mensaje = descifrador.extraer_desafio(texto)
    if mensaje:
        desafio = descifrador.Desafio(mensaje)
        hallazgo = analizar_desafio(desafio)
        if hallazgo.tipo == "sin_cifrar":  # «el mensaje cifrado: no lo entiendo» es conversación, no un desafío
            return False
        resolver_desafio(desafio, hallazgo)
        return True
    clave = descifrador.extraer_clave(texto) if S.desafio_pendiente else None
    if clave:
        desafio = descifrador.Desafio(**S.desafio_pendiente)
        resolver_desafio(desafio, analizar_desafio(desafio, clave))
        return True
    return False


def entregar_desafio(texto: str, tipo: str, clave: str) -> None:
    """Desde el formulario: la app cifra el mensaje (si hace falta) y se lo entrega a Holmes."""
    desafio = descifrador.cifrar_desafio(texto, tipo, clave)
    S.enviados += 1
    S.mensajes.append({
        "rol": "user", "oculto": False, "texto": "Le dejo un mensaje cifrado, señor Holmes. ¿Sabrá leerlo?",
        "desafio_html": fichas.desafio_html(desafio.cifrado, desafio.svg),
        "para_ia": "(El visitante te entrega un mensaje cifrado para que lo descifres: "
                   f"{'[figuras danzantes]' if desafio.svg else desafio.cifrado})",
    })
    resolver_desafio(desafio, analizar_desafio(desafio))


def formulario_desafio(lugar: str) -> None:
    """Escribir un mensaje y elegir cómo cifrarlo; Holmes no sabe cuál se eligió."""
    with st.form(f"desafio_{lugar}", clear_on_submit=True):
        texto = st.text_area("Su mensaje secreto", max_chars=200, key=f"desafio_texto_{lugar}",
                             placeholder="Escríbalo en claro y yo lo cifro, o péguelo ya cifrado")
        tipo = st.selectbox("¿Cómo lo cifro?", descifrador.TIPOS_DESAFIO, key=f"desafio_tipo_{lugar}",
                            format_func=descifrador.NOMBRES_DESAFIO.get)
        clave = st.text_input("Palabra clave (solo para Vigenère)", key=f"desafio_clave_{lugar}", max_chars=20)
        enviar = st.form_submit_button("Entregárselo a Holmes")
    st.caption("Holmes no sabrá qué código eligió: tendrá que descubrirlo.")
    if enviar:
        if not cifrados.normalizar(texto) and not texto.strip():
            st.warning("Escriba primero el mensaje.")
            return
        try:
            entregar_desafio(texto, tipo, clave)
        except ValueError:
            st.warning("Ese mensaje no tiene letras que cifrar.")
            return
        st.rerun()


# ---------------------------------------------------------------------------
# El relato de Watson
# ---------------------------------------------------------------------------

def puede_pedir_relato() -> bool:
    if S.relato_escrito or S.enviados >= MAX_MENSAJES:
        return False
    if S.modo == "B":
        return S.caso is not None and S.terminado
    return S.modo == "A" and S.mensajes_en_a >= 3


def pedir_relato() -> None:
    S.enviados += 1
    S.mensajes.append({"rol": "user", "oculto": False, "texto": "✒️ ¿Y si Watson escribiera este caso?"})
    if S.modo == "B":
        datos = relato.datos_modo_b(S.caso, S.acusacion_hecha, S.pistas, S.pistas_anotadas, S.puntaje_final)
        titulo = S.caso.titulo
    else:
        datos, titulo = relato.datos_modo_a(S.notas_a), None
    try:
        with st.spinner(partida.frase("relato")):
            escrito = relato.generar_relato(motor, datos, S.mensajes, titulo)
    except Exception as error:  # noqa: BLE001
        S.mensajes.append({"rol": "model", "oculto": False, "error": explicar_error(error),
                           "para_ia": "(El relato de Watson no llegó.)",
                           "texto": "*Holmes mira por la ventana.* «El mensajero de Watson se retrasa. "
                                    "Pídamelo de nuevo en un momento.»"})
        return
    S.relato_escrito = True
    S.mensajes.append({"rol": "model", "oculto": False, "texto": random.choice(partida.ENTREGA_RELATO),
                       "para_ia": f"(Watson envió su relato «{escrito.titulo}» y el visitante lo está leyendo.)",
                       "relato": escrito.model_dump()})


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


def mostrar_expedientes(m: dict) -> None:
    """Las tres carpetas sobre el tablero; solo la oferta vigente tiene botones."""
    vigente = S.modo == "B" and S.caso is None and S.opciones_caso is not None and m.get("elegido") is None
    columnas = st.columns(len(m["expedientes"]))
    for i, (columna, opcion) in enumerate(zip(columnas, m["expedientes"])):
        with columna:
            st.markdown(fichas.carpeta_expediente(opcion, elegida=m.get("elegido") == i,
                                                  apagada=m.get("elegido") not in (None, i)),
                        unsafe_allow_html=True)
            if vigente and st.button("Abrir este expediente", key=f"expediente_{i}", width="stretch"):
                abrir_expediente(i)
                st.rerun()
    if vigente and st.button("Ver otros expedientes", key="otros_expedientes"):
        S.enviados += 1
        ofrecer_expedientes()
        st.rerun()


def mostrar_mensaje(m: dict, indice: int = 0) -> None:
    avatar = AVATAR_HOLMES if m["rol"] == "model" else "user"
    with st.chat_message("assistant" if m["rol"] == "model" else "user", avatar=avatar):
        st.markdown(m["texto"])
        if m.get("desafio_html"):
            st.markdown(m["desafio_html"], unsafe_allow_html=True)
        if m.get("descifrado_html"):
            st.markdown(m["descifrado_html"], unsafe_allow_html=True)
        if m.get("relato"):
            st.markdown(fichas.pagina_strand(m["relato"]), unsafe_allow_html=True)
            escrito = relato.RelatoWatson(**m["relato"])
            st.download_button("Descargar el relato", relato.relato_como_texto(escrito),
                               file_name=relato.nombre_archivo(escrito), mime="text/plain",
                               key=f"descargar_relato_{indice}", icon=":material/download:", on_click="ignore")
        if m.get("expedientes"):
            mostrar_expedientes(m)
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
        if m.get("hilo_html"):
            st.markdown(m["hilo_html"], unsafe_allow_html=True)
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
        nota = st.sidebar.container(key=f"nota_cifrado_{i}")
        with nota.expander(f"Mensaje cifrado {i + 1}", expanded=pista.estado == "activa",
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
            if pista.ayudas:
                st.markdown(fichas.nota_adhesiva(pista.cifrado.pistas[pista.ayudas - 1]), unsafe_allow_html=True)

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
    # st.expander (no st.sidebar.expander) para que quede dentro de la nota de papel que lo envuelve
    with st.expander("Acusación final", expanded=S.abrir_acusacion or S.terminado, icon=":material/balance:"):
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
                with st.spinner(partida.frase("juicio")):
                    veredicto = evaluar_movil(motor, caso, movil)
                movil_bien, comentario = veredicto.movil_correcto, veredicto.comentario
            except Exception:  # noqa: BLE001
                movil_bien, comentario = False, "No se pudo evaluar el móvil."
            culpable_bien = culpable == caso.culpable
            puntos_pistas = sum(p.puntos for p in S.pistas)
            S.puntaje_final = (puntos_pistas + partida.PUNTOS_CULPABLE * culpable_bien
                               + partida.PUNTOS_MOVIL * movil_bien)
            S.terminado = True
            S.acusacion_hecha = {"culpable": culpable, "movil": movil, "culpable_bien": culpable_bien,
                           "movil_bien": movil_bien}
            nota_oculta(
                f"[RESULTADO] ACUSACIÓN FINAL. Culpable propuesto: {culpable} "
                f"({'CORRECTO' if culpable_bien else 'INCORRECTO'}). Móvil "
                f"{'CORRECTO' if movil_bien else 'INCORRECTO'} ({comentario}). Puntaje final: "
                f"{S.puntaje_final}. El caso ha terminado: revela la solución completa con tu "
                "razonamiento, como en el final de tus relatos. [/RESULTADO]")
            # El tablero con el hilo rojo se arma ahora y queda guardado en el mensaje (no depende de Gemini)
            turno_holmes({"hilo_html": fichas.hilo_rojo(caso, S.pistas_anotadas, culpable)})
            st.rerun()


def boton_cambiar_camino() -> None:
    if st.button("Cambiar de camino", icon=":material/alt_route:", width="stretch", key="cambiar_camino",
                 help="Vuelve a elegir entre traer un caso o ayudar a Holmes, sin borrar la conversación."):
        cambiar_camino()
        st.rerun()


with st.sidebar:
    st.markdown('<div class="libreta-pinza" aria-hidden="true"></div>'
                '<div class="libreta-titulo">La libreta<br>de Holmes</div>', unsafe_allow_html=True)
    if S.modo is None:
        st.markdown('<div class="insignia">Baker Street, 221B</div>', unsafe_allow_html=True)
        with st.container(key="nota_camino"):
            st.markdown("**Elija su camino**")
            S.dificultad = st.select_slider("Dificultad de los casos", cifrados.DIFICULTADES, value=S.dificultad)
            if S.mensajes:
                if st.button("A · Traigo un caso", icon=":material/search:", width="stretch", key="lateral_A"):
                    procesar_mensaje("Elijo la opción A: le traigo un caso.")
                    st.rerun()
                if st.button("B · Ayudar a Holmes", icon=":material/person_search:", width="stretch",
                             key="lateral_B"):
                    procesar_mensaje("Elijo la opción B: quiero ayudarle con su caso.")
                    st.rerun()
            else:
                st.caption("Salude a Holmes en el chat para empezar.")
    elif S.modo == "A":
        st.markdown('<div class="insignia">Modo A • Usted trae el caso</div>', unsafe_allow_html=True)
        with st.container(key="nota_notas"):
            with st.expander("Notas del caso", expanded=True, icon=":material/edit_note:"):
                st.markdown(fichas.notas_markdown(S.notas_a))
        boton_cambiar_camino()
    else:
        st.markdown(f'<div class="insignia">Modo B • Dificultad {escape(S.dificultad)}</div>',
                    unsafe_allow_html=True)
        if S.caso is None:
            with st.container(key="nota_eleccion"):
                st.markdown("**Elija un expediente**")
                st.caption("Holmes dejó tres carpetas sobre el tablero. Abra la que más le intrigue.")
        else:
            puntos = S.puntaje_final if S.terminado else sum(p.puntos for p in S.pistas)
            imagenes = (f"imágenes {S.imagenes_usadas} de {partida.MAX_IMAGENES_POR_CASO}" if S.imagenes_activas
                        else "imágenes desactivadas")
            st.markdown(f'<div class="estado-caso">Puntaje {puntos}, {imagenes}</div>', unsafe_allow_html=True)
            with st.container(key="nota_expediente"):
                with st.expander("Expediente", expanded=True, icon=":material/folder_open:"):
                    st.markdown(fichas.expediente_markdown(S.caso, S.pistas_anotadas))
            with st.container(key="nota_sospechosos"):
                with st.expander("Sospechosos", expanded=True, icon=":material/groups:"):
                    st.markdown(fichas.sospechosos_markdown(S.caso))
            panel_pistas()
            with st.container(key="nota_acusacion"):
                panel_acusacion()
            if S.terminado and st.button("Nuevo caso", icon=":material/mail:", width="stretch", key="nuevo_caso"):
                reiniciar()
                st.rerun()
        boton_cambiar_camino()

    en_caso = S.modo == "B" and S.caso is not None and not S.terminado  # durante un caso, la libreta es del caso
    if S.mensajes and S.enviados < MAX_MENSAJES and not en_caso:
        with st.container(key="nota_desafio"):
            with st.expander("Desafiar a Holmes", icon=":material/mail_lock:"):
                st.caption("Escríbale un mensaje secreto y vea si Holmes descubre el código.")
                formulario_desafio("libreta")
    st.divider()
    if st.button("Salir de Baker Street (reiniciar)", icon=":material/door_open:", width="stretch", key="salir"):
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

st.markdown(fichas.CABECERA, unsafe_allow_html=True)

if not S.mensajes:
    st.markdown(fichas.BIENVENIDA, unsafe_allow_html=True)

for i, m in enumerate(S.mensajes):
    if not m.get("oculto"):
        mostrar_mensaje(m, i)

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


def elegir_camino_en_chat() -> None:
    """Los dos caminos también en el tablero, no solo en la libreta (en el celular está escondida)."""
    st.markdown('<p class="titulo-acciones">Elija su camino:</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    if col_a.button("A · Le traigo un caso", key="camino_A", width="stretch"):
        procesar_mensaje("Elijo la opción A: le traigo un caso.")
        st.rerun()
    if col_b.button("B · Quiero ayudarle con su caso", key="camino_B", width="stretch"):
        procesar_mensaje("Elijo la opción B: quiero ayudarle con su caso.")
        st.rerun()


def acciones_modo_a() -> None:
    """Modo A: desafiar a Holmes con un mensaje cifrado y, cuando ya contó su caso, pedir el relato."""
    st.markdown('<p class="titulo-acciones">¿Qué hacemos ahora?</p>', unsafe_allow_html=True)
    columnas = st.columns(2)
    with columnas[0].popover("Desafiarlo con un mensaje cifrado", key="accion_desafio", width="stretch"):
        formulario_desafio("tablero")
    if puede_pedir_relato() and columnas[1].button("Pedirle a Watson que lo escriba", key="accion_relato",
                                                   width="stretch"):
        pedir_relato()
        st.rerun()


def acciones_fin_de_caso() -> None:
    st.markdown('<p class="titulo-acciones">El caso está cerrado.</p>', unsafe_allow_html=True)
    columnas = st.columns(2)
    if columnas[0].button("Pedirle a Watson que lo escriba", key="accion_relato", width="stretch"):
        pedir_relato()
        st.rerun()


if S.modo is None and S.mensajes and not limite:
    elegir_camino_en_chat()
if S.modo == "A" and not limite:
    acciones_modo_a()
if S.modo == "B" and S.caso is not None and not S.terminado and not limite:
    acciones_rapidas()
if S.modo == "B" and S.terminado and puede_pedir_relato():
    acciones_fin_de_caso()

if entrada := st.chat_input("Hable con Holmes...", disabled=limite):
    procesar_mensaje(entrada)
    st.rerun()
