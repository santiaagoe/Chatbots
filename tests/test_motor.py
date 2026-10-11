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
