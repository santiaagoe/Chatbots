"""
Conexión con Gemini.

Aquí está todo lo que habla con la API de Google:
  - responder(): la voz de Holmes (con acceso al índice MCP si está activado).
  - generar_json(): respuestas estructuradas (el caso secreto, el juicio del móvil).
  - generar_imagen(): ilustraciones de la escena del crimen.

Si Google está saturado (errores 500/503/504), cada llamada se reintenta con
esperas crecientes y, si el modelo principal sigue sin responder, se usa un
modelo de respaldo. Si se acabó la cuota (429), se pasa directo al respaldo.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors, types

MAX_CONSULTAS_INDICE = 3            # veces que Holmes puede consultar su índice por respuesta
CODIGOS_TRANSITORIOS = {429, 500, 503, 504}
ESPERAS_REINTENTO = [2, 5]          # segundos entre intentos con el mismo modelo
PAUSA_MODELO_AGOTADO = 30 * 60      # sin cuota diaria: el modelo se salta durante este tiempo


def _esquema_compatible(esquema: dict) -> dict:
    """Quita campos de JSON Schema que la API de Gemini no acepta en funciones."""
    if isinstance(esquema, dict):
        limpio = {}
        for clave, valor in esquema.items():
            if clave in ("additionalProperties", "$schema", "title"):
                continue
            if clave == "properties":  # aquí las claves son nombres de parámetros
                limpio[clave] = {n: _esquema_compatible(v) for n, v in valor.items()}
            else:
                limpio[clave] = _esquema_compatible(valor)
        return limpio
    if isinstance(esquema, list):
        return [_esquema_compatible(v) for v in esquema]
    return esquema


def sin_cuota(error: Exception) -> bool:
    """¿El plan de la clave no incluye este modelo? (429 con «limit: 0»)

    Pasa, por ejemplo, con los modelos de imágenes en el nivel gratuito de
    Gemini: la cuota no se agotó, simplemente es cero. Esperar no lo arregla.
    """
    return (isinstance(error, errors.APIError) and getattr(error, "code", None) == 429
            and "limit: 0" in str(error).lower())


def imagen_no_disponible(error: Exception) -> bool:
    """¿Este error significa que no habrá imágenes por un buen rato (no vale la pena reintentar)?

    Cuota cero del nivel gratuito de Gemini, credenciales de Cloudflare malas
    o cuota diaria de Cloudflare agotada.
    """
    from juego.imagenes_cloudflare import ErrorCloudflare

    return sin_cuota(error) or (isinstance(error, ErrorCloudflare) and error.es_definitivo)


def es_cuota_agotada(error: Exception) -> bool:
    """¿Error 429 (cuota)? Con el mismo modelo, reintentar enseguida no sirve: se pasa al de respaldo."""
    return isinstance(error, errors.APIError) and getattr(error, "code", None) == 429


def es_cuota_diaria(error: Exception) -> bool:
    """¿Se acabó la cuota del día (o el plan no incluye el modelo)? Entonces se salta ese modelo un buen rato."""
    texto = str(error).lower().replace(" ", "").replace("_", "")
    return es_cuota_agotada(error) and ("perday" in texto or "limit:0" in texto)


def es_transitorio(error: Exception) -> bool:
    """¿Es un error de Google que se arregla esperando (saturación, cuota por minuto)?"""
    return (isinstance(error, errors.APIError) and getattr(error, "code", None) in CODIGOS_TRANSITORIOS
            and not sin_cuota(error))


class _BucleAsincrono:
    """Un único bucle de eventos que vive en un hilo aparte durante toda la app.

    Streamlit no es asíncrono, pero el cliente MCP sí. Antes se usaba
    asyncio.run(), que crea y CIERRA un bucle en cada mensaje; el cliente
    asíncrono de Gemini guardaba conexiones atadas al bucle anterior y desde
    el segundo mensaje fallaba con «Event loop is closed». Con un bucle
    permanente, las conexiones siempre encuentran su bucle vivo.
    """

    def __init__(self):
        self.bucle = asyncio.new_event_loop()
        threading.Thread(target=self.bucle.run_forever, daemon=True, name="bucle-mcp").start()

    def ejecutar(self, corrutina, limite_segundos: float = 180):
        return asyncio.run_coroutine_threadsafe(corrutina, self.bucle).result(limite_segundos)


@dataclass
class Configuracion:
    api_key: str
    modelo_texto: str = "gemini-3.5-flash"
    modelo_respaldo: str = "gemini-3.1-flash-lite"
    modelo_imagen: str = "gemini-3.1-flash-image"
    generar_imagenes: bool = True
    usar_mcp: bool = True
    temperatura: float = 0.9
    # Generador de imágenes gratuito alternativo (ver juego/imagenes_cloudflare.py)
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    modelo_imagen_cloudflare: str = "@cf/black-forest-labs/flux-1-schnell"
    proveedor_imagenes: str = "auto"   # "auto", "cloudflare" o "gemini"

    @property
    def usa_cloudflare(self) -> bool:
        if self.proveedor_imagenes == "gemini":
            return False
        tiene_credenciales = bool(self.cloudflare_account_id and self.cloudflare_api_token)
        return tiene_credenciales or self.proveedor_imagenes == "cloudflare"


def leer_configuracion(secretos: dict | None = None) -> Configuracion:
    """Lee la configuración desde variables de entorno (.env) o los secrets de Streamlit."""
    secretos = secretos or {}

    def valor(nombre: str, defecto: str = "") -> str:
        return os.getenv(nombre) or str(secretos.get(nombre, "")) or defecto

    return Configuracion(
        api_key=valor("GEMINI_API_KEY"),
        modelo_texto=valor("MODELO_TEXTO", Configuracion.modelo_texto),
        modelo_respaldo=valor("MODELO_RESPALDO", Configuracion.modelo_respaldo),
        modelo_imagen=valor("MODELO_IMAGEN", Configuracion.modelo_imagen),
        generar_imagenes=valor("GENERAR_IMAGENES", "1").lower() not in ("0", "false", "no"),
        usar_mcp=valor("USAR_MCP", "1").lower() not in ("0", "false", "no"),
        cloudflare_account_id=valor("CLOUDFLARE_ACCOUNT_ID"),
        cloudflare_api_token=valor("CLOUDFLARE_API_TOKEN"),
        modelo_imagen_cloudflare=valor("MODELO_IMAGEN_CLOUDFLARE", Configuracion.modelo_imagen_cloudflare),
        proveedor_imagenes=valor("PROVEEDOR_IMAGENES", "auto").lower(),
    )


def a_contenidos(mensajes: list[dict]) -> list[types.Content]:
    """Convierte el historial de la app al formato de Gemini.

    Une mensajes consecutivos del mismo rol (por ejemplo, el mensaje del
    visitante y una nota oculta de la aplicación) y asegura que empiece el
    usuario, como exige la API.
    """
    contenidos: list[types.Content] = []
    for m in mensajes:
        texto = m.get("para_ia") or m["texto"]
        if not texto:
            continue
        rol = "model" if m["rol"] == "model" else "user"
        if contenidos and contenidos[-1].role == rol:
            contenidos[-1].parts.append(types.Part.from_text(text=texto))
        else:
            contenidos.append(types.Content(role=rol, parts=[types.Part.from_text(text=texto)]))
    while contenidos and contenidos[0].role != "user":
        contenidos.pop(0)
    return contenidos


class Motor:
    def __init__(self, config: Configuracion):
        if not config.api_key:
            raise ValueError("Falta la clave GEMINI_API_KEY.")
        self.config = config
        self.cliente = genai.Client(api_key=config.api_key)
        self.bucle = _BucleAsincrono()
        self.mcp_fallo: str | None = None      # último error del índice MCP, para mostrarlo
        self._por_visitante = threading.local()  # Streamlit atiende cada visitante en su propio hilo
        self._agotados: dict[str, float] = {}    # modelo → hasta cuándo se salta (cuota diaria agotada)
        # Ojo: este objeto es compartido por TODOS los visitantes de la app
        # (Streamlit lo guarda con cache_resource). Nada que dependa de un
        # visitante debe guardarse aquí; eso va en st.session_state.

    @property
    def ultimo_modelo(self) -> str | None:
        """Qué modelo respondió el último mensaje de ESTE visitante (no el de otro)."""
        return getattr(self._por_visitante, "modelo", None)

    @ultimo_modelo.setter
    def ultimo_modelo(self, modelo: str | None) -> None:
        self._por_visitante.modelo = modelo

    # ------------------------------------------------------------- reintentos
    def _modelos_de_texto(self) -> list[str]:
        modelos = [self.config.modelo_texto]
        if self.config.modelo_respaldo and self.config.modelo_respaldo != self.config.modelo_texto:
            modelos.append(self.config.modelo_respaldo)
        ahora = time.time()
        disponibles = [m for m in modelos if self._agotados.get(m, 0) <= ahora]
        return disponibles or modelos  # si todos están agotados, se intenta igual

    def _con_reintentos(self, llamada, modelos: list[str]):
        """Ejecuta llamada(modelo) reintentando si Google está saturado.

        Prueba el modelo principal varias veces y luego el de respaldo.
        Los errores que no son de saturación (clave inválida, etc.) se
        lanzan de inmediato.
        """
        ultimo_error: Exception | None = None
        for modelo in modelos:
            for intento in range(len(ESPERAS_REINTENTO) + 1):
                try:
                    resultado = llamada(modelo)
                    self.ultimo_modelo = modelo
                    return resultado
                except Exception as error:  # noqa: BLE001
                    if es_cuota_agotada(error):
                        # Sin cuota: esperar unos segundos no sirve. Se pasa al siguiente modelo y, si
                        # se acabó la del día, este modelo se salta en los próximos mensajes.
                        ultimo_error = error
                        if es_cuota_diaria(error):
                            self._agotados[modelo] = time.time() + PAUSA_MODELO_AGOTADO
                        break
                    if not es_transitorio(error):
                        raise
                    ultimo_error = error
                    if intento < len(ESPERAS_REINTENTO):
                        time.sleep(ESPERAS_REINTENTO[intento])
        raise ultimo_error

    # ------------------------------------------------------------------ texto
    def responder(self, mensajes: list[dict], instruccion_sistema: str, usar_indice: bool = True) -> str:
        """Respuesta de Holmes. Con usar_indice=False no se le ofrece el índice MCP: si el mensaje no
        trata de los libros, así se ahorra la consulta extra que gasta buscar en ellos."""
        contenidos = a_contenidos(mensajes)
        return self._con_reintentos(
            lambda modelo: self._responder_con(modelo, contenidos, instruccion_sistema, usar_indice),
            self._modelos_de_texto(),
        )

    def _responder_con(self, modelo: str, contenidos, instruccion_sistema: str, usar_indice: bool = True) -> str:
        if self.config.usar_mcp and usar_indice:
            try:
                return self.bucle.ejecutar(
                    self._responder_con_mcp(modelo, contenidos, instruccion_sistema))
            except Exception as error:  # noqa: BLE001
                if isinstance(error, errors.APIError):
                    raise  # es un problema de Google, no del índice: que lo maneje el reintento
                # Si el índice falla, Holmes sigue hablando sin él.
                self.mcp_fallo = f"{type(error).__name__}: {error}"
        respuesta = self.cliente.models.generate_content(
            model=modelo,
            contents=contenidos,
            config=types.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=self.config.temperatura,
            ),
        )
        return respuesta.text or ""

    async def _responder_con_mcp(self, modelo: str, contenidos, instruccion_sistema: str) -> str:
        """Puente MCP → Gemini.

        1. Se conecta al servidor MCP del índice y le pide su lista de herramientas.
        2. Se las declara a Gemini como funciones.
        3. Si Gemini pide usar una, la ejecuta en el servidor MCP y le devuelve el
           resultado; repite hasta que Gemini responde con texto.

        (El SDK de Gemini trae un soporte MCP experimental, pero hacer el puente a
        mano es más robusto y deja claro cómo funciona el protocolo.)
        """
        from fastmcp import Client

        from indice_mcp.servidor import mcp as indice

        contenidos = list(contenidos)
        async with Client(indice) as cliente_mcp:
            herramientas_mcp = await cliente_mcp.list_tools()
            declaraciones = [
                types.FunctionDeclaration(
                    name=h.name,
                    description=h.description or "",
                    parameters_json_schema=_esquema_compatible(
                        getattr(h, "input_schema", None) or h.inputSchema),
                )
                for h in herramientas_mcp
            ]
            config = types.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=self.config.temperatura,
                tools=[types.Tool(function_declarations=declaraciones)],
            )
            for _ in range(MAX_CONSULTAS_INDICE):
                respuesta = await self.cliente.aio.models.generate_content(
                    model=modelo, contents=contenidos, config=config
                )
                llamadas = respuesta.function_calls or []
                if not llamadas:
                    self.mcp_fallo = None
                    return respuesta.text or ""
                contenidos.append(respuesta.candidates[0].content)
                partes = []
                for llamada in llamadas:
                    resultado = await cliente_mcp.call_tool(llamada.name, dict(llamada.args or {}))
                    texto = "\n".join(getattr(c, "text", "") for c in resultado.content)
                    partes.append(types.Part.from_function_response(
                        name=llamada.name, response={"resultado": texto}))
                contenidos.append(types.Content(role="user", parts=partes))

            # Demasiadas consultas: se le pide que responda sin herramientas.
            respuesta = await self.cliente.aio.models.generate_content(
                model=modelo,
                contents=contenidos,
                config=types.GenerateContentConfig(
                    system_instruction=instruccion_sistema, temperature=self.config.temperatura),
            )
            return respuesta.text or ""

    # ------------------------------------------------------------------- JSON
    def generar_json(self, instruccion: str, esquema, temperatura: float = 1.0):
        """Devuelve un objeto del tipo `esquema` (un modelo de Pydantic)."""

        def llamada(modelo: str):
            respuesta = self.cliente.models.generate_content(
                model=modelo,
                contents=instruccion,
                config=types.GenerateContentConfig(
                    temperature=temperatura,
                    response_mime_type="application/json",
                    response_schema=esquema,
                ),
            )
            if respuesta.parsed is not None:
                return respuesta.parsed
            return esquema.model_validate_json(respuesta.text)

        return self._con_reintentos(llamada, self._modelos_de_texto())

    # --------------------------------------------------------------- imágenes
    def generar_imagen(self, descripcion: str) -> tuple[bytes, str] | None:
        """Devuelve (bytes, tipo MIME) de la imagen, o None si no se pudo.

        Usa Cloudflare (gratis) si está configurado; si no, el modelo de imágenes de Gemini.
        """
        if self.config.usa_cloudflare:
            return self._imagen_cloudflare(descripcion)

        def llamada(modelo: str):
            respuesta = self.cliente.models.generate_content(
                model=modelo,
                contents=descripcion,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
            for candidato in respuesta.candidates or []:
                for parte in (candidato.content.parts if candidato.content else None) or []:
                    if parte.inline_data and parte.inline_data.data:
                        return parte.inline_data.data, parte.inline_data.mime_type or "image/png"
            return None

        return self._con_reintentos(llamada, [self.config.modelo_imagen])

    def _imagen_cloudflare(self, descripcion: str) -> tuple[bytes, str]:
        from juego import imagenes_cloudflare

        return imagenes_cloudflare.generar(
            self.config.cloudflare_account_id, self.config.cloudflare_api_token,
            descripcion, self.config.modelo_imagen_cloudflare)
