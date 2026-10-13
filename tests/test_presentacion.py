"""Pruebas de la presentación del caso, el expediente, las pistas anotadas, los avisos y los botones."""

import io
import random

import pytest
from google.genai import errors
from PIL import Image
from streamlit.testing.v1 import AppTest

from juego import fichas, motor, partida
from juego.caso import Caso, Persona, Pista, Sospechoso, Veredicto, caso_para_holmes


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "sienna").save(buffer, "PNG")
    return buffer.getvalue()


def caso_de_prueba(nombre_raro: str = "Ada Lowe") -> Caso:
    def s(nombre, motivo):
        return Sospechoso(nombre=nombre, ocupacion="institutriz", relacion_con_victima="empleada de la casa",
                          motivo_sospecha=motivo, coartada="dormía en su cuarto",
                          secreto="SECRETO-PERSONAL de " + nombre)
    return Caso(
        titulo="La aventura del candelabro torcido", lugar="Belgravia", fecha="enero de 1895",
        resumen="Lestrade envía un telegrama.", hechos_conocidos="El rubí desapareció de la vitrina cerrada.",
        victima=Persona(nombre="Sir Hugh Pemberton", descripcion="coleccionista de joyas"),
        escena_nombre="El salón de Pemberton House",
        crimen="CRIMEN-SECRETO: duplicó la llave con cera.",
        sospechosos=[s("Tom Briggs", "Fue el último en ver a Sir Hugh."),
                     s(nombre_raro, "Tenía una copia de la llave."),
                     s("Ned Carr", "Discutió con Sir Hugh esa noche.")],
        culpable="Ada Lowe", movil="MOVIL-SECRETO deudas de juego", metodo="METODO-SECRETO",
        pistas=[Pista(descripcion="Restos de cera en la cerradura", ubicacion="la vitrina",
                      que_revela="REVELA-SECRETO-1"),
                Pista(descripcion="Un guante con olor a tabaco turco", ubicacion="bajo el sofá",
                      que_revela="REVELA-SECRETO-2"),
                Pista(descripcion="Tom tartamudea al hablar de la hora", ubicacion="al interrogar a Tom",
                      que_revela="REVELA-SECRETO-3")],
        mensajes_secretos=["La llave esta en el reloj", "Huya antes del alba"],
        soportes_mensajes=["una nota <b>bajo</b> la alfombra", "un telegrama sin firma"],
        escena_visual="ESCENA-VISUAL a dark drawing room with an open display case",
    )


SECRETOS = ["REVELA-SECRETO", "MOVIL-SECRETO", "METODO-SECRETO", "CRIMEN-SECRETO", "SECRETO-PERSONAL",
            "ESCENA-VISUAL"]


# ---------------------------------------------------------------------------
# Piezas sin interfaz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("medio", list(partida.MEDIOS))
def test_ficha_muestra_todos_los_sospechosos_con_su_motivo(medio):
    caso = caso_de_prueba()
    html = fichas.ficha_caso(caso, medio)
    assert f"ficha-{medio}" in html and caso.titulo in html
    for s in caso.sospechosos:
        assert s.nombre in html and s.motivo_sospecha in html and s.ocupacion in html
    assert "Sir Hugh Pemberton" in html and "El rubí desapareció" in html and "Pemberton House" in html
    assert not any(secreto in html for secreto in SECRETOS)
    assert ("STOP" in html) == (medio == "telegrama")


def test_ficha_y_expediente_escapan_el_html_de_la_ia():
    caso = caso_de_prueba(nombre_raro="<script>alert(1)</script>")
    assert "<script>" not in fichas.ficha_caso(caso, "carta")
    assert "<script>" not in fichas.expediente_markdown(caso, [])


def test_expediente_sin_secretos_y_con_pistas_anotadas():
    caso = caso_de_prueba()
    vacio = fichas.expediente_markdown(caso, [])
    assert "Pistas anotadas (0/3)" in vacio and "Ninguna todavía" in vacio
    sospechosos = fichas.sospechosos_markdown(caso)
    for s in caso.sospechosos:
        assert s.nombre in sospechosos and s.motivo_sospecha in sospechosos
    assert not any(secreto in sospechosos for secreto in SECRETOS)
    con_pistas = fichas.expediente_markdown(caso, [2, 1])
    assert "Pistas anotadas (2/3)" in con_pistas
    assert "Un guante con olor a tabaco turco" in con_pistas and "Restos de cera" in con_pistas
    assert "Tom tartamudea" not in con_pistas
    assert not any(secreto in con_pistas for secreto in SECRETOS)


def test_holmes_recibe_motivos_y_numeros_de_pista():
    texto = caso_para_holmes(caso_de_prueba())
    assert "Por qué es sospechoso (público): Fue el último en ver a Sir Hugh." in texto
    assert "[[PISTA: n]]" in texto and "2. Un guante" in texto
    assert "Hechos conocidos (públicos)" in texto


def test_instruccion_de_presentacion_corta():
    texto = partida.instruccion_presentacion(caso_de_prueba(), "periodico")
    assert "The Times" in texto and "3 o 4 frases" in texto
    assert "ficha" in texto and "No solicites imágenes" in texto and "pregunta" in texto


def test_el_medio_cambia_de_un_caso_al_siguiente():
    rng = random.Random(0)
    for anterior in partida.MEDIOS:
        assert partida.elegir_medio(anterior, rng) != anterior


def test_etiquetas_de_pistas_e_imagen_con_pie():
    e = partida.extraer_etiquetas("Mire la cerradura. [[PISTA: 1]]\n[[PISTAS: 2 y 3]]\n"
                                  "[[IMAGEN: a cane by the fire | El bastón junto al fuego]]")
    assert e.pistas == [1, 2, 3] and e.texto == "Mire la cerradura."
    assert e.imagenes[0].pie == "El bastón junto al fuego" and not e.imagenes[0].es_escena
    assert partida.extraer_etiquetas("[[IMAGEN: ESCENA]]").imagenes[0].es_escena


@pytest.mark.parametrize("texto, esperado", [
    ("Acuso a Ada Lowe", True), ("El culpable es Tom", True), ("Fue ella, estoy seguro", True),
    ("Creo que ya sé quién fue, señor Holmes.", True), ("¿Quién lo hizo?", False),
    ("¿Es culpable el mayordomo?", False), ("¿Puedo acusar ya?", True),
    ("Vamos a la escena del crimen", False), ("Quiero interrogar a Ned Carr.", False),
])
def test_deteccion_de_acusaciones_en_el_chat(texto, esperado):
    assert partida.quiere_acusar(texto) is esperado


def test_cuando_sugerir_la_acusacion():
    assert not partida.toca_sugerir_acusacion([1], 3)
    assert partida.toca_sugerir_acusacion([1, 2], 3)  # 60 % de 3 → 2 pistas
    assert not partida.toca_sugerir_acusacion([], 0)


# ---------------------------------------------------------------------------
# Recorridos de la interfaz con Gemini simulado
# ---------------------------------------------------------------------------

class Sim:
    def __init__(self):
        self.instrucciones, self.pedidos_imagen, self.medios = [], [], []
        self.falla_presentacion = False


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("USAR_MCP", "0")
    estado = Sim()

    def responder(self, mensajes, instruccion):
        estado.instrucciones.append(instruccion)
        turno = []  # todo lo que llegó desde la última respuesta de Holmes (visitante + notas)
        for m in reversed(mensajes):
            if m["rol"] == "model":
                break
            turno.insert(0, m.get("para_ia") or m["texto"])
        ultimo = "\n".join(turno)
        if "opción B" in ultimo:
            return "¡Excelente!\n[[MODO: B]]"
        if "opción A" in ultimo:
            return "Cuénteme.\n[[MODO: A]]"
        if "[INICIO CASO]" in ultimo:
            if estado.falla_presentacion:
                raise errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})
            return "Lestrade escribe desesperado. Lea usted mismo.\n[[IMAGEN: something]]"
        if "escena" in ultimo.lower():
            return "Hay cera en la cerradura y un guante bajo el sofá.\n[[IMAGEN: ESCENA]]\n[[PISTA: 1, 2]]"
        if "bastón" in ultimo:
            return "¡Un bastón!\n[[IMAGEN: a silver cane | El bastón de plata]]"
        if "Tom" in ultimo:
            return "Tom tartamudea.\n[[PISTA: 3]]\n[[PISTA: 99]]"
        return "Interesante."

    def generar_json(self, instruccion, esquema, temperatura=1.0):
        if esquema is Caso:
            estado.medios.append(instruccion)
            return caso_de_prueba()
        return Veredicto(movil_correcto=True, comentario="Bien.")

    def generar_imagen(self, descripcion):
        estado.pedidos_imagen.append(descripcion)
        return png(), "image/png"

    monkeypatch.setattr(motor.Motor, "responder", responder)
    monkeypatch.setattr(motor.Motor, "generar_json", generar_json)
    monkeypatch.setattr(motor.Motor, "generar_imagen", generar_imagen)
    return estado


def abrir_caso_b() -> AppTest:
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    at.chat_input[0].set_value("Buenas noches").run()
    next(b for b in at.sidebar.button if "Ayudar a Holmes" in b.label).click().run()
    assert not at.exception and at.session_state.modo == "B"
    return at


def html_del_chat(at) -> str:
    return " ".join(m.value for m in at.markdown)


def seccion(at, titulo: str) -> str:
    exp = next(e for e in at.sidebar.expander if titulo in e.label)
    return " ".join(m.value for m in exp.markdown)


def expediente(at) -> str:
    return seccion(at, "Expediente")


def boton_principal(at, texto):
    return next(b for b in at.main.button if texto in b.label)


def test_presentacion_con_ficha_guia_y_sin_imagen(sim):
    at = abrir_caso_b()
    presentacion = at.session_state.mensajes[-1]
    assert presentacion["texto"].startswith("Lestrade escribe desesperado")
    assert presentacion["imagenes"] == [] and sim.pedidos_imagen == []
    chat = html_del_chat(at)
    for nombre in ["Tom Briggs", "Ada Lowe", "Ned Carr", "Fue el último en ver a Sir Hugh."]:
        assert nombre in chat
    assert "Cómo investigar" in chat and "Acusación final" in chat
    assert f"ficha-{at.session_state.medio}" in chat
    assert partida.MEDIOS[at.session_state.medio]["descripcion"] in sim.medios[-1]
    assert "Pistas anotadas (0/3)" in expediente(at)
    assert "Ada Lowe" in seccion(at, "Sospechosos") and "Tenía una copia de la llave." in seccion(at, "Sospechosos")


def test_si_gemini_falla_en_la_presentacion_la_ficha_aparece_igual(sim):
    sim.falla_presentacion = True
    at = abrir_caso_b()
    chat = html_del_chat(at)
    assert "telégrafo" in at.session_state.mensajes[-1]["texto"]
    assert "Tom Briggs" in chat and "Cómo investigar" in chat


def test_escena_dibujada_con_los_datos_del_caso_y_pistas_anotadas(sim):
    at = abrir_caso_b()
    boton_principal(at, "Ir a la escena").click().run()
    assert not at.exception
    assert sim.pedidos_imagen[0].startswith("ESCENA-VISUAL")  # no la descripción de Holmes
    assert at.session_state.escena_dibujada and at.session_state.pistas_anotadas == [1, 2]
    imagen = at.session_state.mensajes[-1]["imagenes"][0]
    assert imagen[2] == "El salón de Pemberton House"
    assert "Anotado en la libreta: Restos de cera" in html_del_chat(at)
    assert "Pistas anotadas (2/3)" in expediente(at) and "Un guante" in expediente(at)
    assert any("Examinar la escena" in b.label for b in at.main.button)

    # Otra imagen: con la descripción de Holmes y su pie
    at.chat_input[0].set_value("Mire ese bastón").run()
    assert sim.pedidos_imagen[1].startswith("a silver cane")
    assert at.session_state.mensajes[-1]["imagenes"][0][2] == "El bastón de plata"


def test_interrogar_con_boton_y_numeros_de_pista_invalidos(sim):
    at = abrir_caso_b()
    boton_principal(at, "Tom Briggs, institutriz").click().run()  # opción del menú «Interrogar a…»
    assert not at.exception
    assert at.session_state.mensajes[-2]["texto"] == "Quiero interrogar a Tom Briggs."
    assert at.session_state.pistas_anotadas == [3]  # el 99 no existe y se ignora


def test_acusar_en_el_chat_muestra_el_aviso_y_abre_el_panel(sim):
    at = abrir_caso_b()
    acusacion = next(e for e in at.sidebar.expander if "Acusación" in e.label)
    assert not acusacion.proto.expanded
    at.chat_input[0].set_value("Acuso a Ada Lowe, tenía la llave").run()
    assert not at.exception
    assert "¿Listo para acusar?" in html_del_chat(at)
    assert at.session_state.mensajes[-1].get("aviso_acusacion")
    assert any("[AVISO ACUSACION]" in (m.get("para_ia") or "") for m in at.session_state.mensajes)
    acusacion = next(e for e in at.sidebar.expander if "Acusación" in e.label)
    assert acusacion.proto.expanded
    assert not at.session_state.terminado  # acusar en el chat no cierra el caso


def test_una_pregunta_no_dispara_el_aviso(sim):
    at = abrir_caso_b()
    at.chat_input[0].set_value("¿Quién cree usted que lo hizo?").run()
    assert not at.session_state.mensajes[-1].get("aviso_acusacion")


def test_holmes_sugiere_acusar_una_sola_vez(sim):
    at = abrir_caso_b()
    at.chat_input[0].set_value("Vamos a la escena").run()  # 2 de 3 pistas
    at.chat_input[0].set_value("Sigamos").run()
    assert at.session_state.acusacion_sugerida
    assert any("[SUGERIR ACUSACION]" in (m.get("para_ia") or "") for m in at.session_state.mensajes)
    assert at.session_state.mensajes[-1].get("aviso_acusacion")
    at.chat_input[0].set_value("Y ahora qué").run()
    assert not at.session_state.mensajes[-1].get("aviso_acusacion")


def test_botones_solo_durante_el_caso(sim):
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    at.chat_input[0].set_value("Hola").run()
    assert not any("Repasar" in b.label for b in at.main.button)
    next(b for b in at.sidebar.button if "Traigo un caso" in b.label).click().run()
    assert at.session_state.modo == "A"
    assert not any("Repasar" in b.label for b in at.main.button)

    at = abrir_caso_b()
    boton_principal(at, "Repasar").click().run()
    assert at.session_state.mensajes[-2]["texto"].startswith("Repasemos")
    at.sidebar.selectbox[-1].set_value("Ada Lowe")
    at.sidebar.text_area[0].set_value("deudas de juego")
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert at.session_state.terminado
    assert not any("Repasar" in b.label for b in at.main.button)


def test_el_soporte_del_mensaje_cifrado_se_escapa(sim):
    at = abrir_caso_b()
    at.chat_input[0].set_value("Uno").run()
    at.chat_input[0].set_value("Dos").run()
    assert at.session_state.pistas[0].estado == "activa"
    assert "una nota &lt;b&gt;bajo&lt;/b&gt; la alfombra" in html_del_chat(at)
