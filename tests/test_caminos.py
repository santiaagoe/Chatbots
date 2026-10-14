"""Elección de camino, libreta según el modo, carpetas de expedientes, caso de muestra y ahorro de consultas.

El Gemini simulado aquí NUNCA escribe [[MODO: …]]: así se comportó el Gemini real, y la app
tiene que funcionar igual.
"""

import random

import pytest
from streamlit.testing.v1 import AppTest

from conftest import abrir_primer_expediente, opciones_falsas
from juego import cifrados, motor, partida
from juego.caso import Caso, OpcionesCaso, Veredicto, reparar_caso
from juego.caso_muestra import OPCION_MUESTRA, caso_muestra


class Sim:
    def __init__(self):
        self.llamadas = []      # (instrucción, usar_indice)
        self.opciones_pedidas = 0


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("USAR_MCP", "0")
    estado = Sim()

    def responder(self, mensajes, instruccion, usar_indice=True):
        estado.llamadas.append((instruccion, usar_indice))
        turno = []
        for m in reversed(mensajes):
            if m["rol"] == "model":
                break
            turno.insert(0, m.get("para_ia") or m["texto"])
        texto = "\n".join(turno)
        if "yogur" in texto:
            return "Fascinante. ¿Dónde estaba el yogur?\n[[NOTA: El yogur desapareció del refrigerador]]"
        if "[INICIO CASO]" in texto:
            return "Lestrade escribe desesperado. Lea usted mismo."
        return "Hmm. Prosiga."  # nunca escribe [[MODO: …]]

    def generar_json(self, instruccion, esquema, temperatura=1.0):
        if esquema is OpcionesCaso:
            estado.opciones_pedidas += 1
            return opciones_falsas()
        if esquema is Caso:
            return caso_muestra()
        return Veredicto(movil_correcto=True, comentario="Bien.")

    monkeypatch.setattr(motor.Motor, "responder", responder)
    monkeypatch.setattr(motor.Motor, "generar_json", generar_json)
    monkeypatch.setattr(motor.Motor, "generar_imagen", lambda self, d: None)
    return estado


def abrir() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def textos_libreta(at) -> str:
    return " ".join(m.value for m in at.sidebar.markdown) + " ".join(e.label for e in at.sidebar.expander)


# ---------------------------------------------------------------------------
# El modo lo decide la app
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto, modo", [
    ("Elijo la opción A: le traigo un caso.", "A"), ("Elijo la opción B: quiero ayudarle con su caso.", "B"),
    ("B", "B"), ("a.", "A"), ("opcion b por favor", "B"), ("Tengo un caso para usted", "A"),
    ("quiero ayudarle", "B"), ("¿me puede ayudar con un misterio?", None), ("Buenas noches", None),
    ("Ayúdeme, señor Holmes", "A"),
])
def test_detectar_modo(texto, modo):
    assert partida.detectar_modo(texto) == modo


def test_botones_para_elegir_camino_en_el_chat(sim):
    at = abrir()
    assert not any(b.key == "camino_A" for b in at.button)  # aún no saluda
    at.chat_input[0].set_value("Buenas noches").run()
    assert at.session_state.modo is None
    assert {"camino_A", "camino_B"} <= {b.key for b in at.button}
    at.button(key="camino_B").click().run()
    assert not at.exception
    assert at.session_state.modo == "B"  # aunque Holmes no escribió la etiqueta
    assert "Elija un expediente" in textos_libreta(at)
    assert not any(b.key == "camino_A" for b in at.button)


def test_escribir_la_opcion_b_cambia_el_modo_y_muestra_carpetas(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    llamadas = len(sim.llamadas)
    at.chat_input[0].set_value("opción b").run()
    assert at.session_state.modo == "B"
    assert len(sim.llamadas) == llamadas  # Holmes presenta las carpetas sin gastar otra consulta
    assert sim.opciones_pedidas == 1
    ofertas = [m for m in at.session_state.mensajes if m.get("expedientes")]
    assert len(ofertas) == 1 and len(ofertas[0]["expedientes"]) == 3
    assert ofertas[0]["expedientes"][-1]["muestra"]
    chat = " ".join(m.value for m in at.markdown)
    assert "El misterio del faro apagado" in chat and "Caso de muestra" in chat

    abrir_primer_expediente(at)
    assert at.session_state.caso is not None
    libreta = textos_libreta(at)
    assert "Expediente" in libreta and "Sospechosos" in libreta and "Ada Lowe" in libreta
    assert "Tom Briggs" in " ".join(m.value for m in at.markdown)  # el informe breve (ficha) en el chat
    ofertas = [m for m in at.session_state.mensajes if m.get("expedientes")]
    assert ofertas[0]["elegido"] == 0
    assert not any(b.key == "expediente_1" for b in at.button)  # ya no se puede elegir otra


def test_ver_otros_expedientes(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    at.button(key="otros_expedientes").click().run()
    assert sim.opciones_pedidas == 2
    ofertas = [m for m in at.session_state.mensajes if m.get("expedientes")]
    assert [m.get("elegido") for m in ofertas] == [-1, None]  # la oferta anterior queda apagada


def test_modo_a_con_notas_en_la_libreta(sim):
    at = abrir()
    at.chat_input[0].set_value("Buenas tardes").run()
    at.chat_input[0].set_value("Le traigo un caso").run()
    assert at.session_state.modo == "A"
    assert "Notas del caso" in textos_libreta(at) and "Cuéntele su caso" in textos_libreta(at)
    at.chat_input[0].set_value("Alguien se comió mi yogur").run()
    assert at.session_state.notas_a == ["El yogur desapareció del refrigerador"]
    assert "El yogur desapareció del refrigerador" in textos_libreta(at)
    assert "[[NOTA" not in at.session_state.mensajes[-1]["texto"]
    assert "Expediente" not in textos_libreta(at)


def test_cambiar_de_camino_sin_borrar_la_conversacion(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_A").click().run()
    antes = len([m for m in at.session_state.mensajes if not m.get("oculto")])
    at.button(key="cambiar_camino").click().run()
    assert not at.exception
    assert at.session_state.modo is None
    assert len([m for m in at.session_state.mensajes if not m.get("oculto")]) == antes + 1
    assert {"camino_A", "camino_B"} <= {b.key for b in at.button}
    at.button(key="camino_B").click().run()
    abrir_primer_expediente(at)
    assert at.session_state.caso is not None
    at.button(key="cambiar_camino").click().run()  # abandonar el caso también funciona
    assert at.session_state.modo is None and at.session_state.caso is None


# ---------------------------------------------------------------------------
# Idea 1: el índice solo cuando hace falta
# ---------------------------------------------------------------------------

def test_el_indice_solo_se_ofrece_si_se_habla_de_los_libros(sim):
    at = abrir()
    at.chat_input[0].set_value("Buenas noches, señor Holmes").run()
    at.chat_input[0].set_value("¿Qué fue de Moriarty?").run()
    assert [usar for _, usar in sim.llamadas] == [False, True]


def test_el_motor_no_usa_mcp_si_no_hace_falta(monkeypatch):
    m = motor.Motor(motor.Configuracion(api_key="x", usar_mcp=True))
    usados = []
    monkeypatch.setattr(m, "_responder_con_mcp", lambda *a: usados.append("mcp"))

    class SinIndice:
        class models:
            @staticmethod
            def generate_content(**kw):
                usados.append("directo")
                return type("R", (), {"text": "Hola"})()
    m.cliente = SinIndice()
    assert m.responder([{"rol": "user", "texto": "Hola"}], "Eres Holmes.", usar_indice=False) == "Hola"
    assert usados == ["directo"]


# ---------------------------------------------------------------------------
# Idea 2: el caso de muestra
# ---------------------------------------------------------------------------

def test_el_caso_de_muestra_es_completo_y_coherente():
    caso = caso_muestra()
    reparado = reparar_caso(caso_muestra())
    assert reparado.culpable == caso.culpable == "Ada Lowe"
    assert caso.culpable in [s.nombre for s in caso.sospechosos]
    assert reparado.mensajes_secretos == caso.mensajes_secretos and len(caso.soportes_mensajes) == 2
    assert all(s.motivo_sospecha for s in caso.sospechosos)
    assert len(caso.pistas) >= 4 and any("interrogar" in p.ubicacion for p in caso.pistas)
    for texto in caso.mensajes_secretos:
        for tipo in cifrados.CIFRADOS:
            assert cifrados.cifrar(texto, tipo, random.Random(1)).mensaje == cifrados.normalizar(texto)
    assert caso_muestra() is not caso_muestra()  # cada partida recibe su propia copia
    assert OPCION_MUESTRA.muestra and OPCION_MUESTRA.titulo == caso.titulo


def test_los_casos_nuevos_nunca_quedan_marcados_como_muestra(monkeypatch):
    from juego.caso import OpcionCaso, generar_opciones

    class Motor:
        def generar_json(self, instruccion, esquema, temperatura=1.0):
            assert "exactamente 2" in instruccion
            return OpcionesCaso(opciones=[OpcionCaso(titulo="X", tipo_crimen="robo", lugar="Y", gancho="Z", muestra=True)])
    assert [o.muestra for o in generar_opciones(Motor())] == [False]


# ---------------------------------------------------------------------------
# Frases de espera
# ---------------------------------------------------------------------------

def test_las_frases_de_espera_varian():
    rng = random.Random(5)
    vistas = {partida.frase("pensar", rng) for _ in range(40)}
    assert len(vistas) >= 8 and all(f in partida.FRASES["pensar"] for f in vistas)
    for tipo in ("expedientes", "caso", "dibujo", "juicio"):
        assert partida.frase(tipo) in partida.FRASES[tipo]
