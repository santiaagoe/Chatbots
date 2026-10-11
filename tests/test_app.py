"""Prueba de punta a punta de la interfaz con un Gemini simulado (sin red)."""

import io

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from juego import motor
from juego.caso import Caso, Persona, Pista, Sospechoso, Veredicto


def png_de_prueba() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "sienna").save(buffer, "PNG")
    return buffer.getvalue()


def caso_falso() -> Caso:
    s = lambda n: Sospechoso(nombre=n, ocupacion="criado", relacion_con_victima="empleado",
                             coartada="dormía", secreto="juega a las cartas")
    return Caso(
        titulo="La aventura del candelabro torcido", lugar="Belgravia", fecha="enero de 1895",
        resumen="Llega un telegrama.", victima=Persona(nombre="Sir Hugh", descripcion="coleccionista"),
        crimen="Robo de un rubí.", sospechosos=[s("Tom Briggs"), s("Ada Lowe"), s("Ned Carr")],
        culpable="Ada Lowe", movil="deudas de juego", metodo="duplicó la llave",
        pistas=[Pista(descripcion="cera en la cerradura", ubicacion="vitrina", que_revela="molde")],
        mensajes_secretos=["La llave esta en el reloj", "Huya antes del alba"],
        soportes_mensajes=["una nota bajo la alfombra", "un telegrama sin firma"],
        escena_visual="a dark drawing room with an open display case",
    )


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("USAR_MCP", "0")
    respuestas = []

    def responder(self, mensajes, instruccion):
        ultimo = mensajes[-1].get("para_ia") or mensajes[-1]["texto"]
        respuestas.append(instruccion)
        if "opción B" in ultimo:
            return "¡Excelente! Buscaré el expediente.\n[[MODO: B]]"
        if "[INICIO CASO]" in ultimo:
            return "El caso del candelabro.\n[[IMAGEN: a dark drawing room]]"
        return "Interesante. Usted escribe de noche."

    def generar_json(self, instruccion, esquema, temperatura=1.0):
        return caso_falso() if esquema is Caso else Veredicto(movil_correcto=True, comentario="Bien.")

    monkeypatch.setattr(motor.Motor, "responder", responder)
    monkeypatch.setattr(motor.Motor, "generar_json", generar_json)
    monkeypatch.setattr(motor.Motor, "generar_imagen", lambda self, d: (png_de_prueba(), "image/png"))
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    return at, respuestas


def test_partida_completa(app):
    at, respuestas = app
    assert not at.exception
    at.chat_input[0].set_value("Buenas noches, señor Holmes").run()
    assert "Usted escribe de noche" in at.chat_message[-1].markdown[0].value

    boton_b = next(b for b in at.sidebar.button if "Ayudar a Holmes" in b.label)
    boton_b.click().run()  # elige el camino B desde la libreta
    assert at.session_state.modo == "B"
    assert at.session_state.caso.titulo.startswith("La aventura")
    assert at.session_state.imagenes_usadas == 1
    assert "[CASO SECRETO]" in respuestas[-1]

    # Tras dos mensajes en el caso aparece el primer mensaje cifrado
    at.chat_input[0].set_value("Vamos a la escena").run()
    at.chat_input[0].set_value("Examino la vitrina").run()
    pista = at.session_state.pistas[0]
    assert pista.estado == "activa"

    # Se resuelve desde la libreta
    at.sidebar.selectbox(key="tipo_0").set_value(pista.cifrado.nombre)
    at.sidebar.text_input(key="texto_0").set_value("la llave está en el reloj")
    at.sidebar.button(key="FormSubmitter:solucion_0-Proponer solución").click().run()
    assert at.session_state.pistas[0].estado == "resuelta"
    assert not at.exception

    # Acusación final
    at.sidebar.selectbox[-1].set_value("Ada Lowe")
    at.sidebar.text_area[0].set_value("Tenía deudas de juego")
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert at.session_state.terminado
    assert at.session_state.puntaje_final == 100 + 200 + 100
    assert not at.exception
