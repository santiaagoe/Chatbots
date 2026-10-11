"""
Conexión con Gemini.

Aquí está todo lo que habla con la API de Google:
  - responder(): la voz de Holmes (con acceso al índice MCP si está activado).
  - generar_json(): respuestas estructuradas (el caso secreto, el juicio del móvil).
  - generar_imagen(): ilustraciones de la escena del crimen.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from google import genai
from google.genai import types


MAX_CONSULTAS_INDICE = 3  # veces que Holmes puede consultar su índice por respuesta


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


@dataclass
class Configuracion:
    api_key: str
    modelo_texto: str = "gemini-3.5-flash"
    modelo_imagen: str = "gemini-3.1-flash-image"
    usar_mcp: bool = True
    temperatura: float = 0.9


def leer_configuracion(secretos: dict | None = None) -> Configuracion:
    """Lee la configuración desde variables de entorno (.env) o los secrets de Streamlit."""
    secretos = secretos or {}

    def valor(nombre: str, defecto: str = "") -> str:
        return os.getenv(nombre) or str(secretos.get(nombre, "")) or defecto

    return Configuracion(
        api_key=valor("GEMINI_API_KEY"),
        modelo_texto=valor("MODELO_TEXTO", Configuracion.modelo_texto),
        modelo_imagen=valor("MODELO_IMAGEN", Configuracion.modelo_imagen),
        usar_mcp=valor("USAR_MCP", "1").lower() not in ("0", "false", "no"),
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
        self.mcp_fallo: str | None = None  # último error del índice MCP, para mostrarlo

    # ------------------------------------------------------------------ texto
    def responder(self, mensajes: list[dict], instruccion_sistema: str) -> str:
        contenidos = a_contenidos(mensajes)
        if self.config.usar_mcp:
            try:
                return asyncio.run(self._responder_con_mcp(contenidos, instruccion_sistema))
            except Exception as error:  # noqa: BLE001 — si el índice falla, Holmes sigue hablando
                self.mcp_fallo = f"{type(error).__name__}: {error}"
        respuesta = self.cliente.models.generate_content(
            model=self.config.modelo_texto,
            contents=contenidos,
            config=types.GenerateContentConfig(
                system_instruction=instruccion_sistema,
                temperature=self.config.temperatura,
            ),
        )
        return respuesta.text or ""

    async def _responder_con_mcp(self, contenidos, instruccion_sistema: str) -> str:
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
                    model=self.config.modelo_texto, contents=contenidos, config=config
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
                model=self.config.modelo_texto,
                contents=contenidos,
                config=types.GenerateContentConfig(
                    system_instruction=instruccion_sistema, temperature=self.config.temperatura),
            )
            return respuesta.text or ""

    # ------------------------------------------------------------------- JSON
    def generar_json(self, instruccion: str, esquema, temperatura: float = 1.0):
        """Devuelve un objeto del tipo `esquema` (un modelo de Pydantic)."""
        respuesta = self.cliente.models.generate_content(
            model=self.config.modelo_texto,
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

    # --------------------------------------------------------------- imágenes
    def generar_imagen(self, descripcion: str) -> tuple[bytes, str] | None:
        """Devuelve (bytes, tipo MIME) de la imagen, o None si no se pudo."""
        respuesta = self.cliente.models.generate_content(
            model=self.config.modelo_imagen,
            contents=descripcion,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        for candidato in respuesta.candidates or []:
            for parte in (candidato.content.parts if candidato.content else None) or []:
                if parte.inline_data and parte.inline_data.data:
                    return parte.inline_data.data, parte.inline_data.mime_type or "image/png"
        return None
