"""Más recorridos de la interfaz con Gemini simulado: errores, pistas, rendirse, modo A, límites."""

import io

import pytest
from google.genai import errors
from PIL import Image
from streamlit.testing.v1 import AppTest

from conftest import abrir_primer_expediente, opciones_falsas
from juego import cifrados, motor
from juego.caso import Caso, OpcionesCaso, Persona, Pista, Sospechoso, Veredicto


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "sienna").save(buffer, "PNG")
    return buffer.getvalue()


def caso_falso() -> Caso:
    s = lambda n: Sospechoso(nombre=n, ocupacion="criado", relacion_con_victima="empleado", motivo_sospecha="tenía la llave",
                             coartada="dormía", secreto="juega a las cartas")
    return Caso(
        titulo="La aventura del candelabro torcido", lugar="Belgravia", fecha="enero de 1895",
        resumen="Llega un telegrama.", hechos_conocidos="El rubí desapareció de la vitrina.",
        escena_nombre="El salón de Sir Hugh", victima=Persona(nombre="Sir Hugh", descripcion="coleccionista"),
        crimen="Robo de un rubí.", sospechosos=[s("Tom Briggs"), s("Ada Lowe"), s("Ned Carr")],
        culpable="Ada Lowe", movil="deudas de juego", metodo="duplicó la llave",
        pistas=[Pista(descripcion="cera en la cerradura", ubicacion="vitrina", que_revela="molde")],
        mensajes_secretos=["La llave esta en el reloj", "Huya antes del alba"],
        soportes_mensajes=["una nota bajo la alfombra", "un telegrama sin firma"],
        escena_visual="a dark drawing room with an open display case",
    )


def error_503():
    return errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def error_sin_cuota():
    return errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded, limit: 0, model: x"}})


class Simulacion:
    """Estado compartido para controlar lo que «responde Gemini» en cada prueba."""

    def __init__(self):
        self.instrucciones = []
        self.falla_texto = None
        self.falla_caso = None
        self.falla_opciones = None
        self.falla_imagen = None


@pytest.fixture
def simulacion(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("USAR_MCP", "0")
    sim = Simulacion()

    def responder(self, mensajes, instruccion, **_):
        sim.instrucciones.append(instruccion)
        if sim.falla_texto:
            raise sim.falla_texto
        ultimo = mensajes[-1].get("para_ia") or mensajes[-1]["texto"]
        if "opción B" in ultimo:
            return "¡Excelente!\n[[MODO: B]]"
        if "opción A" in ultimo:
            return "Cuénteme su caso, con todos los detalles.\n[[MODO: A]]"
        if "[INICIO CASO]" in ultimo:
            return "Lestrade escribe desesperado.\n[[IMAGEN: a dark drawing room]]"
        if "escena" in ultimo.lower():
            return "El salón está en penumbra.\n[[IMAGEN: ESCENA]]\n[[PISTA: 1]]"
        return "Interesante."

    def generar_json(self, instruccion, esquema, temperatura=1.0):
        if esquema is OpcionesCaso:
            if sim.falla_opciones:
                raise sim.falla_opciones
            return opciones_falsas()
        if esquema is Caso:
            if sim.falla_caso:
                raise sim.falla_caso
            return caso_falso()
        return Veredicto(movil_correcto=False, comentario="Faltó la deuda.")

    def generar_imagen(self, descripcion):
        if sim.falla_imagen:
            raise sim.falla_imagen
        return png(), "image/png"

    monkeypatch.setattr(motor.Motor, "responder", responder)
    monkeypatch.setattr(motor.Motor, "generar_json", generar_json)
    monkeypatch.setattr(motor.Motor, "generar_imagen", generar_imagen)
    return sim


def estado_actual(instruccion: str) -> str:
    """Solo la parte de la instrucción que arma la app (sin el prompt fijo de Holmes)."""
    return instruccion.split("# ESTADO ACTUAL", 1)[1]


def abrir() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def boton(at, texto):
    return next(b for b in at.sidebar.button if texto in b.label)


def textos_detalle(at) -> str:
    return " ".join(c.value for c in at.caption)


def entrar_al_caso_b(at):
    at.chat_input[0].set_value("Buenas noches").run()
    boton(at, "Ayudar a Holmes").click().run()
    assert at.session_state.modo == "B"
    abrir_primer_expediente(at)
    assert at.session_state.caso is not None


def test_modo_a(simulacion):
    at = abrir()
    at.chat_input[0].set_value("Buenas noches").run()
    boton(at, "Traigo un caso").click().run()
    assert not at.exception
    assert at.session_state.modo == "A" and at.session_state.caso is None
    at.chat_input[0].set_value("Alguien se comió mi yogur").run()
    assert not at.exception
    assert "Modo A" in estado_actual(simulacion.instrucciones[-1])
    assert "[CASO SECRETO]" not in estado_actual(simulacion.instrucciones[-1])


def test_gemini_caido_no_rompe_la_app(simulacion):
    at = abrir()
    simulacion.falla_texto = error_503()
    at.chat_input[0].set_value("Hola").run()
    assert not at.exception
    assert "telégrafo" in at.chat_message[-1].markdown[0].value
    assert "saturados (503)" in textos_detalle(at)
    # Cuando Google vuelve, la conversación sigue normal
    simulacion.falla_texto = None
    at.chat_input[0].set_value("¿Sigue ahí?").run()
    assert not at.exception
    assert at.chat_message[-1].markdown[0].value == "Interesante."


def test_imagen_sin_cuota_se_explica_y_holmes_deja_de_pedirlas(simulacion):
    simulacion.falla_imagen = error_sin_cuota()
    at = abrir()
    entrar_al_caso_b(at)
    at.chat_input[0].set_value("Vamos a la escena").run()
    assert not at.exception
    assert at.session_state.imagenes_usadas == 0
    assert "nivel gratuito" in textos_detalle(at)
    at.chat_input[0].set_value("Examino la vitrina").run()
    assert "NO escribas [[IMAGEN" in estado_actual(simulacion.instrucciones[-1])
    assert not at.session_state.imagenes_activas
    assert any("imágenes desactivadas" in m.value for m in at.sidebar.markdown)

    # Otro visitante (otra sesión) no debe quedar sin imágenes por culpa del primero
    simulacion.falla_imagen = None
    otro = abrir()
    entrar_al_caso_b(otro)
    otro.chat_input[0].set_value("Vamos a la escena").run()
    assert otro.session_state.imagenes_activas
    assert otro.session_state.imagenes_usadas == 1


def test_un_fallo_temporal_de_imagen_no_las_apaga(simulacion):
    simulacion.falla_imagen = error_503()
    at = abrir()
    entrar_al_caso_b(at)
    at.chat_input[0].set_value("Vamos a la escena").run()
    assert not at.exception
    assert at.session_state.imagenes_activas  # se volverá a intentar
    assert not at.session_state.escena_dibujada


def test_pedir_pistas_y_rendirse_con_los_bailarines(simulacion, monkeypatch):
    original = cifrados.cifrar_al_azar
    monkeypatch.setattr(cifrados, "cifrar_al_azar",
                        lambda texto, dificultad, evitar=None, rng=None:
                        cifrados.cifrar(texto, "bailarines") if not evitar else original(texto, dificultad, evitar))
    at = abrir()
    entrar_al_caso_b(at)
    at.chat_input[0].set_value("Vamos").run()
    at.chat_input[0].set_value("Miro la alfombra").run()
    pista = at.session_state.pistas[0]
    assert pista.estado == "activa" and pista.cifrado.tipo == "bailarines"

    for n in range(1, 4):
        at.sidebar.button(key="ayuda_0").click().run()
        assert not at.exception
        assert at.session_state.pistas[0].ayudas == n
    assert any("<svg" in m.value for m in at.markdown)  # la tabla de figuras se muestra
    assert at.sidebar.button(key="ayuda_0").disabled

    at.sidebar.button(key="rendirse_0").click().run()
    assert not at.exception
    assert at.session_state.pistas[0].estado == "rendida"
    assert "decía «LA LLAVE ESTA EN EL RELOJ»" in estado_actual(simulacion.instrucciones[-1])

    # La segunda pista aparece más adelante en la investigación
    for texto in ["Interrogo a Tom", "Interrogo a Ada", "Reviso el jardín"]:
        at.chat_input[0].set_value(texto).run()
    assert at.session_state.pistas[1].estado == "activa"
    assert not at.exception


def test_si_gemini_no_puede_crear_casos_quedan_los_del_archivo(simulacion):
    simulacion.falla_opciones = error_503()
    at = abrir()
    at.chat_input[0].set_value("Buenas noches").run()
    boton(at, "Ayudar a Holmes").click().run()
    assert not at.exception
    assert at.session_state.modo == "B"
    opciones = at.session_state.opciones_caso
    assert len(opciones) == 3 and all(o.muestra for o in opciones)  # los tres casos del archivo
    assert opciones[0].titulo == "La aventura del candelabro torcido"  # primero el de su dificultad
    assert "saturados (503)" in textos_detalle(at)
    llamadas_antes = len(simulacion.instrucciones)
    abrir_primer_expediente(at)
    assert not at.exception
    caso = at.session_state.caso
    assert caso.titulo == "La aventura del candelabro torcido" and caso.culpable == "Ada Lowe"
    assert len(caso.pistas) == 6 and len(at.session_state.pistas) == 2
    assert len(simulacion.instrucciones) == llamadas_antes + 1  # solo la presentación de Holmes


def test_si_falla_un_caso_nuevo_se_puede_abrir_otro(simulacion):
    simulacion.falla_caso = error_503()
    at = abrir()
    at.chat_input[0].set_value("Buenas noches").run()
    boton(at, "Ayudar a Holmes").click().run()
    abrir_primer_expediente(at)
    assert not at.exception
    assert at.session_state.caso is None and all(o.muestra for o in at.session_state.opciones_caso)
    assert "faltan páginas" in at.session_state.mensajes[-1]["texto"]
    at.button(key="expediente_0").click().run()  # los casos del archivo no dependen de Gemini
    assert at.session_state.caso is not None and not at.exception


def test_acusacion_equivocada_y_nuevo_caso(simulacion):
    at = abrir()
    entrar_al_caso_b(at)
    at.sidebar.selectbox[-1].set_value("Tom Briggs")
    at.sidebar.text_area[0].set_value("celos")
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert not at.exception
    assert at.session_state.terminado and at.session_state.puntaje_final == 0
    nota = at.session_state.mensajes[-2]["para_ia"]  # resultado oculto que recibe Holmes
    assert "ACUSACIÓN FINAL" in nota and "(INCORRECTO)" in nota

    boton(at, "Nuevo caso").click().run()
    assert not at.exception
    assert at.session_state.modo is None and at.session_state.caso is None
    assert at.session_state.titulos_jugados == ["La aventura del candelabro torcido"]


def test_limite_de_mensajes(simulacion, monkeypatch):
    monkeypatch.setenv("MAX_MENSAJES_POR_SESION", "2")
    at = abrir()
    at.chat_input[0].set_value("Uno").run()
    at.chat_input[0].set_value("Dos").run()
    assert not at.exception
    assert at.chat_input[0].disabled
    assert any("límite de mensajes" in i.value for i in at.info)
    # El botón de reiniciar no sirve para saltarse el límite
    boton(at, "Salir de Baker Street").click().run()
    assert at.chat_input[0].disabled


def test_sin_clave_muestra_instrucciones(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert "Falta la clave de Gemini" in at.error[0].value
