"""Pruebas del puente MCP → Gemini con un Gemini simulado (sin red ni clave real)."""

from types import SimpleNamespace

from google.genai import types

from juego import motor


class GeminiSimulado:
    """Primero pide usar el índice; cuando recibe el resultado, responde con texto."""

    def __init__(self):
        self.llamadas = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generar))

    async def _generar(self, model, contents, config):
        self.llamadas.append((contents, config))
        ultima = contents[-1].parts[0]
        if ultima.function_response is not None:
            resultado = ultima.function_response.response["resultado"]
            return SimpleNamespace(function_calls=None, text=f"Consulté mi índice: {resultado[:40]}")
        llamada = types.FunctionCall(name="listar_relatos", args={})
        contenido = types.Content(role="model", parts=[types.Part(function_call=llamada)])
        return SimpleNamespace(function_calls=[llamada], text=None,
                               candidates=[SimpleNamespace(content=contenido)])


def test_puente_mcp_ejecuta_la_herramienta_y_devuelve_texto():
    m = motor.Motor(motor.Configuracion(api_key="clave-de-prueba"))
    m.cliente = GeminiSimulado()
    texto = m.responder([{"rol": "user", "texto": "¿Qué casos guarda?"}], "Eres Holmes.")
    assert texto.startswith("Consulté mi índice")
    assert m.mcp_fallo is None
    # Gemini recibió las herramientas del servidor MCP como funciones
    config = m.cliente.llamadas[0][1]
    nombres = {d.name for d in config.tools[0].function_declarations}
    assert {"buscar_en_mis_archivos", "listar_relatos"} <= nombres


def test_esquema_compatible_quita_campos_no_soportados():
    esquema = {"type": "object", "additionalProperties": False, "title": "X",
               "properties": {"title": {"type": "string", "title": "Title"}}}
    assert motor._esquema_compatible(esquema) == {
        "type": "object", "properties": {"title": {"type": "string"}}}


def test_a_contenidos_une_roles_y_empieza_por_usuario():
    mensajes = [
        {"rol": "model", "texto": "Bienvenida previa"},
        {"rol": "user", "texto": "Hola"},
        {"rol": "user", "texto": "[NOTA] oculta", "oculto": True},
        {"rol": "model", "texto": "Buenas noches"},
    ]
    contenidos = motor.a_contenidos(mensajes)
    assert [c.role for c in contenidos] == ["user", "model"]
    assert len(contenidos[0].parts) == 2


# ---------------------------------------------------------------------------
# Errores encontrados al usar la app con Gemini real
# ---------------------------------------------------------------------------

import asyncio

import pytest
from google.genai import errors


def error_503():
    return errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE",
                                              "message": "This model is currently experiencing high demand."}})


class GeminiAtadoAlBucle:
    """Imita al cliente asíncrono real: guarda conexiones atadas al primer bucle de eventos.

    Si se le llama desde otro bucle (lo que hacía asyncio.run en cada mensaje),
    falla igual que en la app: «Event loop is closed».
    """

    def __init__(self):
        self.bucle = None
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generar))

    async def _generar(self, model, contents, config):
        actual = asyncio.get_running_loop()
        if self.bucle is not None and self.bucle is not actual:
            raise RuntimeError("Event loop is closed")
        self.bucle = actual
        return SimpleNamespace(function_calls=None, text="Elemental… pero no para Lestrade.")


def test_varios_mensajes_seguidos_con_el_indice_mcp():
    m = motor.Motor(motor.Configuracion(api_key="clave-de-prueba"))
    m.cliente = GeminiAtadoAlBucle()
    for _ in range(3):
        assert m.responder([{"rol": "user", "texto": "Hola"}], "Eres Holmes.").startswith("Elemental")
    assert m.mcp_fallo is None


class GeminiSaturado:
    """El modelo principal responde 503 siempre; el de respaldo funciona."""

    def __init__(self, principal):
        self.principal = principal
        self.intentos = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generar))

    async def _generar(self, model, contents, config):
        self.intentos.append(model)
        if model == self.principal:
            raise error_503()
        return SimpleNamespace(function_calls=None, text=f"Respondo con {model}.")


def test_reintenta_y_usa_el_modelo_de_respaldo(monkeypatch):
    monkeypatch.setattr(motor, "ESPERAS_REINTENTO", [0, 0])
    config = motor.Configuracion(api_key="x", modelo_texto="principal", modelo_respaldo="respaldo")
    m = motor.Motor(config)
    m.cliente = GeminiSaturado("principal")
    assert m.responder([{"rol": "user", "texto": "Hola"}], "Eres Holmes.") == "Respondo con respaldo."
    assert m.cliente.intentos == ["principal"] * 3 + ["respaldo"]
    assert m.ultimo_modelo == "respaldo"
    assert m.mcp_fallo is None  # un 503 de Google no es culpa del índice


def test_si_todos_fallan_se_informa_el_error(monkeypatch):
    monkeypatch.setattr(motor, "ESPERAS_REINTENTO", [0, 0])
    config = motor.Configuracion(api_key="x", modelo_texto="a", modelo_respaldo="a")
    m = motor.Motor(config)
    m.cliente = GeminiSaturado("a")
    with pytest.raises(errors.ServerError):
        m.responder([{"rol": "user", "texto": "Hola"}], "Eres Holmes.")
    assert m.cliente.intentos == ["a"] * 3


def test_errores_no_transitorios_no_se_reintentan():
    m = motor.Motor(motor.Configuracion(api_key="x"))
    llamadas = []

    def llamada(modelo):
        llamadas.append(modelo)
        raise errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid"}})

    with pytest.raises(errors.ClientError):
        m._con_reintentos(llamada, ["a", "b"])
    assert llamadas == ["a"]


def error_sin_cuota():
    return errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message":
        "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
        "limit: 0, model: gemini-3.1-flash-image"}})


def test_imagenes_sin_cuota_no_se_reintentan():
    m = motor.Motor(motor.Configuracion(api_key="x"))
    intentos = []

    def falla(**kwargs):
        intentos.append(kwargs["model"])
        raise error_sin_cuota()

    m.cliente = SimpleNamespace(models=SimpleNamespace(generate_content=falla))
    with pytest.raises(errors.ClientError) as info:
        m.generar_imagen("a foggy alley")
    assert intentos == ["gemini-3.1-flash-image"]  # un solo intento: esperar no lo arregla
    assert motor.imagen_no_disponible(info.value)
    assert motor.sin_cuota(error_sin_cuota())
    assert not motor.es_transitorio(error_sin_cuota())


def test_429_por_minuto_si_se_reintenta():
    por_minuto = errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded, limit: 10"}})
    assert motor.es_transitorio(por_minuto) and not motor.sin_cuota(por_minuto)


def test_un_503_de_imagen_no_apaga_las_imagenes():
    assert not motor.imagen_no_disponible(error_503())
