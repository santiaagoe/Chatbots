"""Casos escritos a mano, hilo rojo, relato de Watson, desafíos cifrados y costumbres de Holmes."""

import random
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from conftest import opciones_falsas
from juego import cifrados, descifrador, fichas, motor, partida, relato
from juego.caso import Caso, OpcionesCaso, Pista, Veredicto, generar_opciones, reparar_caso
from juego.caso_muestra import CASOS_MUESTRA, buscar_muestra, caso_muestra, elegir_muestra
from juego.relato import RelatoWatson

PROMPT = (Path(__file__).parent.parent / "personaje" / "prompt_sistema.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Gemini simulado
# ---------------------------------------------------------------------------

class Sim:
    def __init__(self):
        self.turnos = []          # lo que vio Holmes en cada turno (texto del visitante + notas)
        self.json = []            # (instrucción, esquema) de cada consulta JSON
        self.relato_falla = False


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("USAR_MCP", "0")
    estado = Sim()

    def responder(self, mensajes, instruccion, usar_indice=True):
        turno = []
        for m in reversed(mensajes):
            if m["rol"] == "model":
                break
            turno.insert(0, m.get("para_ia") or m["texto"])
        texto = "\n".join(turno)
        estado.turnos.append(texto)
        if "[DESAFIO]" in texto:
            return "Un juego de niños.\n[DESAFIO] eco [/DESAFIO]"
        if "[INICIO CASO]" in texto:
            return "Lestrade está desesperado."
        if "yogur" in texto:
            return "¿Dónde estaba el yogur?\n[[NOTA: El yogur estaba en el refrigerador]]"
        return "Hmm. Prosiga."

    def generar_json(self, instruccion, esquema, temperatura=1.0):
        estado.json.append((instruccion, esquema))
        if esquema is OpcionesCaso:
            return opciones_falsas()
        if esquema is Caso:
            return caso_muestra()
        if esquema is RelatoWatson:
            if estado.relato_falla:
                raise RuntimeError("sin red")
            return RelatoWatson(titulo="cualquiera", parrafos=["Era una noche de **niebla**.", "", "Holmes sonrió."])
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


def html_visible(at) -> str:
    return " ".join(m.value for m in at.markdown)


def claves_de_botones(at) -> set:
    return {b.key for b in at.button}


def jugar_hasta_acusar(at, culpable="Ada Lowe"):
    """Modo B con el caso del candelabro, hasta la acusación final."""
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    at.button(key="expediente_2").click().run()  # el caso de muestra
    assert at.session_state.caso.titulo == "La aventura del candelabro torcido"
    seleccion = [s for s in at.sidebar.selectbox if s.label == "Culpable"][0]
    seleccion.set_value(culpable)
    [t for t in at.sidebar.text_area if t.label == "Móvil"][0].set_value("Deudas de su hermano")
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert at.session_state.terminado and not at.exception
    return at


# ---------------------------------------------------------------------------
# 5 · Casos escritos a mano
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("muestra", CASOS_MUESTRA, ids=lambda c: c.dificultad)
def test_cada_caso_de_muestra_es_completo_y_coherente(muestra):
    caso = muestra.crear()
    nombres = [s.nombre for s in caso.sospechosos]
    assert muestra.opcion.titulo == caso.titulo and muestra.opcion.muestra
    assert muestra.medio in partida.MEDIOS
    assert caso.culpable in nombres and 3 <= len(nombres) <= 4
    assert all(s.motivo_sospecha and s.coartada and s.secreto for s in caso.sospechosos)
    assert len(caso.pistas) >= 5
    escena = [p for p in caso.pistas if not p.ubicacion.startswith("al interrogar")]
    assert len(escena) >= 2 and len(caso.pistas) - len(escena) >= 1
    for p in caso.pistas:  # el hilo rojo necesita saber a quién apunta cada pista
        assert p.apunta_a in nombres
        assert p.efecto in ("incrimina", "descarta")
        assert (p.efecto == "incrimina") == (p.apunta_a == caso.culpable)
        if p.ubicacion.startswith("al interrogar a "):
            assert p.ubicacion.removeprefix("al interrogar a ") in nombres
    assert any(p.efecto == "descarta" for p in caso.pistas)
    reparado = reparar_caso(muestra.crear())
    assert [(p.apunta_a, p.efecto) for p in reparado.pistas] == [(p.apunta_a, p.efecto) for p in caso.pistas]
    assert reparado.mensajes_secretos == caso.mensajes_secretos and len(caso.soportes_mensajes) == 2
    for texto in caso.mensajes_secretos:
        assert 3 <= len(texto.split()) <= 8 and texto == cifrados.normalizar(texto)
        for tipo in cifrados.CIFRADOS:
            assert cifrados.cifrar(texto, tipo, random.Random(2)).mensaje == texto
    assert muestra.crear() is not muestra.crear()


def test_hay_un_caso_de_muestra_por_dificultad():
    assert sorted(c.dificultad for c in CASOS_MUESTRA) == sorted(cifrados.DIFICULTADES)
    assert len({c.opcion.titulo for c in CASOS_MUESTRA}) == 3
    for dificultad in cifrados.DIFICULTADES:
        assert elegir_muestra(dificultad).dificultad == dificultad
    jugado = elegir_muestra("fácil").opcion.titulo
    assert elegir_muestra("fácil", [jugado]).opcion.titulo != jugado  # ofrece otro que no haya jugado
    todos = [c.opcion.titulo for c in CASOS_MUESTRA]
    assert elegir_muestra("difícil", todos).dificultad == "difícil"  # si jugó todos, vuelve al suyo
    assert buscar_muestra("La aventura del telegrafista de Whitehall").medio == "carta"
    assert buscar_muestra("No existe") is None


def test_en_facil_se_ofrece_y_abre_la_partitura(sim):
    at = abrir()
    at.sidebar.select_slider[0].set_value("fácil").run()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    oferta = [m for m in at.session_state.mensajes if m.get("expedientes")][-1]["expedientes"]
    assert oferta[-1]["titulo"] == "El caso de la partitura robada" and oferta[-1]["muestra"]
    pedido = [i for i, e in sim.json if e is OpcionesCaso][-1]
    assert "partitura" in pedido  # Gemini no debe proponer un caso parecido
    casos_pedidos = sum(e is Caso for _, e in sim.json)
    at.button(key="expediente_2").click().run()
    assert at.session_state.caso.titulo == "El caso de la partitura robada"
    assert at.session_state.medio == "periodico"
    assert sum(e is Caso for _, e in sim.json) == casos_pedidos  # no gastó una consulta
    assert "Henry Pike" in html_visible(at)


def test_la_instruccion_de_opciones_reserva_el_tema():
    class Motor:
        def generar_json(self, instruccion, esquema, temperatura=1.0):
            self.instruccion = instruccion
            return opciones_falsas()
    m = Motor()
    generar_opciones(m, reservado="el robo de un documento secreto del gobierno")
    assert "el robo de un documento secreto del gobierno" in m.instruccion


def test_reparar_corrige_a_quien_apunta_cada_pista():
    caso = caso_muestra()
    caso.pistas = [
        Pista(descripcion="a", ubicacion="x", que_revela="r", apunta_a="la señorita Lowe", efecto="incrimina"),
        Pista(descripcion="b", ubicacion="x", que_revela="r", apunta_a="Ada", efecto="Descarta"),  # no puede descartar al culpable
        Pista(descripcion="c", ubicacion="x", que_revela="r", apunta_a="Ned", efecto="incrimina"),  # un inocente
        Pista(descripcion="d", ubicacion="x", que_revela="r", apunta_a="", efecto=""),
        Pista(descripcion="e", ubicacion="x", que_revela="r", apunta_a="Sir Hugh", efecto="descarta"),  # la víctima
        Pista(descripcion="f", ubicacion="x", que_revela="r"),  # sin los campos (casos viejos)
    ]
    reparado = reparar_caso(caso)
    assert [(p.apunta_a, p.efecto) for p in reparado.pistas] == [
        ("Ada Lowe", "incrimina"), ("Ada Lowe", "incrimina"), ("Ned Carr", "descarta"),
        ("Ada Lowe", "incrimina"), ("Ada Lowe", "incrimina"), ("Ada Lowe", "incrimina")]


# ---------------------------------------------------------------------------
# 1 · El hilo rojo
# ---------------------------------------------------------------------------

def test_hilo_rojo_une_cada_pista_con_quien_senala():
    caso = caso_muestra()
    html = fichas.hilo_rojo(caso, [1, 3], acusado="Tom Briggs")
    svg = html[html.index("<svg"):html.index("</svg>")]
    assert svg.count('class="hilo-incrimina"') == 4 and svg.count('class="hilo-descarta"') == 2
    assert svg.count("stroke-dasharray") == 4 + 1  # 4 pistas no halladas y la leyenda
    assert svg.count(">CULPABLE<") == 1 and svg.count(">DESCARTADO<") == 1 and svg.count(">INOCENTE<") == 1
    assert "Usted lo acusó" in svg
    for s in caso.sospechosos:
        assert s.nombre.upper() in svg.upper()
    lista = html[html.index("hilo-lista"):]
    assert lista.count("<li") == len(caso.sospechosos) + len(caso.pistas)
    assert lista.count("se le pasó por alto") == 4
    assert "descarta a Ned Carr" in lista and "señala a Ada Lowe" in lista
    assert re.search(r"<[^>]*\n", html) is None  # sin saltos de línea dentro de etiquetas (Markdown)
    assert "\n\n" not in html  # una línea en blanco cortaría el bloque HTML en Markdown


def test_hilo_rojo_escapa_los_textos_y_se_adapta_al_caso(monkeypatch):
    caso = caso_muestra()
    caso.sospechosos[0].nombre = "<script>alert(1)</script>"
    caso.pistas[0].descripcion = "Un <b>trozo</b> & cera " * 6  # largo: se corta con «…»
    caso.sospechosos = caso.sospechosos[:2] + [caso.sospechosos[2]] * 2  # 4 sospechosos
    html = fichas.hilo_rojo(reparar_caso(caso), [])
    assert "<script>" not in html and "&lt;script&gt;" in html and "<b>trozo" not in html
    assert "…" in html
    assert fichas.hilo_rojo(caso_muestra(), [1, 2, 3, 4, 5, 6]).count("se le pasó por alto") == 0


def test_el_hilo_rojo_aparece_solo_despues_de_acusar(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    at.button(key="expediente_2").click().run()
    at.chat_input[0].set_value("Vamos a la escena").run()
    assert "class='hilo-rojo'" not in html_visible(at)
    assert not any(m.get("hilo_html") for m in at.session_state.mensajes)
    at.session_state.pistas_anotadas = [1, 2]
    seleccion = [s for s in at.sidebar.selectbox if s.label == "Culpable"][0]
    seleccion.set_value("Ned Carr")
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert not at.exception
    final = at.session_state.mensajes[-1]
    assert final["rol"] == "model" and "hilo-rojo" in final["hilo_html"]
    assert "Usted lo acusó" in final["hilo_html"] and "class='hilo-rojo'" in html_visible(at)
    # Al cambiar de camino (la conversación se conserva), el tablero sigue igual: quedó guardado en el mensaje
    guardado = final["hilo_html"]
    at.sidebar.button(key="cambiar_camino").click().run()
    assert at.session_state.caso is None
    assert any(m.get("hilo_html") == guardado for m in at.session_state.mensajes)
    assert "class='hilo-rojo'" in html_visible(at)


def test_si_gemini_falla_al_revelar_igual_se_ve_el_tablero(sim, monkeypatch):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    at.button(key="expediente_2").click().run()

    def caido(*a, **k):
        raise RuntimeError("Google caído")
    monkeypatch.setattr(motor.Motor, "responder", caido)
    at.sidebar.button(key="FormSubmitter:acusacion-Acusar").click().run()
    assert not at.exception
    assert at.session_state.mensajes[-1].get("error") and at.session_state.mensajes[-1].get("hilo_html")


# ---------------------------------------------------------------------------
# 2 · El relato de Watson
# ---------------------------------------------------------------------------

def test_watson_recibe_la_solucion_y_solo_la_conversacion_visible():
    class Motor:
        def generar_json(self, instruccion, esquema, temperatura=1.0):
            self.instruccion = instruccion
            return RelatoWatson(titulo="Otro", parrafos=["# Uno", "  ", "Dos *tres*"])
    caso = caso_muestra()
    datos = relato.datos_modo_b(caso, {"culpable": "Ned Carr", "movil": "", "culpable_bien": False,
                                       "movil_bien": False}, [], [1], 120)
    mensajes = [{"rol": "user", "texto": "Hola Holmes", "oculto": False},
                {"rol": "user", "texto": "", "para_ia": "[CASO SECRETO] no lo veas", "oculto": True},
                {"rol": "model", "texto": "Buenas noches.", "oculto": False}]
    m = Motor()
    escrito = relato.generar_relato(m, datos, mensajes, titulo=caso.titulo)
    assert escrito.titulo == caso.titulo and escrito.parrafos == ["Uno", "Dos tres"]
    assert "Ada Lowe" in m.instruccion and "acusó a Ned Carr (se equivocó)" in m.instruccion
    assert "Visitante: Hola Holmes" in m.instruccion and "Holmes: Buenas noches." in m.instruccion
    assert "CASO SECRETO" not in m.instruccion
    texto = relato.relato_como_texto(escrito)
    assert texto.startswith("LA AVENTURA DEL CANDELABRO TORCIDO") and "Dr. John H. Watson" in texto
    assert relato.nombre_archivo(escrito) == "relato_watson_la_aventura_del_candelabro_torcido.txt"
    with pytest.raises(ValueError):
        relato.reparar_relato(RelatoWatson(titulo="x", parrafos=["  ", "**"]))


def test_la_conversacion_para_watson_se_recorta():
    largos = [{"rol": "user", "texto": "x" * 900, "oculto": False} for _ in range(80)]
    texto = relato.conversacion_para_watson(largos)
    assert len(texto) <= relato.MAX_CARACTERES_TOTAL
    assert texto.count("Visitante:") <= relato.MAX_MENSAJES and "…" in texto


def test_relato_al_terminar_el_caso(sim):
    at = jugar_hasta_acusar(abrir())
    assert "accion_relato" in claves_de_botones(at)
    enviados = at.session_state.enviados
    at.button(key="accion_relato").click().run()
    assert not at.exception
    ultimo = at.session_state.mensajes[-1]
    assert ultimo["relato"]["titulo"] == "La aventura del candelabro torcido"
    assert ultimo["relato"]["parrafos"] == ["Era una noche de niebla.", "Holmes sonrió."]
    assert "The Strand Magazine" in html_visible(at)
    assert at.session_state.relato_escrito and at.session_state.enviados == enviados + 1
    assert "accion_relato" not in claves_de_botones(at)  # una vez por caso
    pedido = [i for i, e in sim.json if e is RelatoWatson][-1]
    assert "el culpable era Ada Lowe" in pedido and "acusó a Ada Lowe (acertó)" in pedido
    descargas = at.get("download_button")
    assert len(descargas) == 1 and "Descargar el relato" in descargas[0].proto.label


def test_si_el_relato_falla_se_puede_pedir_otra_vez(sim):
    at = jugar_hasta_acusar(abrir())
    sim.relato_falla = True
    at.button(key="accion_relato").click().run()
    assert not at.exception and at.session_state.mensajes[-1].get("error")
    assert not at.session_state.relato_escrito and "accion_relato" in claves_de_botones(at)


def test_relato_en_modo_a_tras_contar_el_caso(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_A").click().run()
    at.chat_input[0].set_value("Alguien se comió mi yogur").run()
    at.chat_input[0].set_value("Estaba en el refrigerador de la oficina").run()
    assert "accion_relato" not in claves_de_botones(at)
    at.chat_input[0].set_value("Solo tres personas tienen llave").run()
    assert "accion_relato" in claves_de_botones(at)
    at.button(key="accion_relato").click().run()
    pedido = [i for i, e in sim.json if e is RelatoWatson][-1]
    assert "El yogur estaba en el refrigerador" in pedido and "Inventa un título" in pedido
    assert at.session_state.mensajes[-1]["relato"]["titulo"] == "cualquiera"


# ---------------------------------------------------------------------------
# 4 · Holmes descifra los mensajes del visitante
# ---------------------------------------------------------------------------

FRASES = ["el martes en soho", "nos vemos en la estacion a medianoche", "el mayordomo miente",
          "te espero en el parque", "quien robo mi yogur", "la reina llega el viernes",
          "busque bajo la escalera", "feliz cumpleanos"]


@pytest.mark.parametrize("tipo", list(cifrados.CIFRADOS))
def test_holmes_descifra_cada_codigo(tipo):
    rng = random.Random(7)
    for frase in FRASES:
        hallazgo = descifrador.analizar_desafio(descifrador.cifrar_desafio(frase, tipo, rng=rng))
        assert hallazgo.tipo == tipo, (frase, hallazgo)
        assert cifrados.solo_letras(hallazgo.mensaje) == cifrados.solo_letras(frase)
        assert hallazgo.observaciones


def test_holmes_no_inventa_si_no_hay_mensaje():
    assert descifrador.analizar("Hola señor Holmes, buenas noches").tipo == "sin_cifrar"
    for basura in ["xkqz wvbt jjfl", "asdf qwer zxcv", "pqowieurytlaksjdh", "E T  VSS", "ghjk"]:
        assert descifrador.analizar(basura).tipo is None, basura
    rng = random.Random(11)
    claves = descifrador.claves_de_conversacion([PROMPT])
    falsos = 0
    for _ in range(200):
        g = "".join(rng.choice(cifrados.ALFABETO + "    ") for _ in range(rng.randint(8, 30)))
        falsos += descifrador.analizar(g, claves).tipo is not None
    assert falsos <= 2


def test_tambien_entiende_el_alfabeto_ingles_sin_enie():
    hallazgo = descifrador.analizar("JQ RFDTWITRT RNJSYJ")  # César 5 hecho a mano con 26 letras
    assert hallazgo.tipo == "cesar" and hallazgo.mensaje == "EL MAYORDOMO MIENTE"
    assert "sin Ñ" in hallazgo.detalle and any("alfabeto inglés" in o for o in hallazgo.observaciones)
    assert descifrador.analizar("VO NZBLIWLNL NRVMGV").mensaje == "EL MAYORDOMO MIENTE"  # Atbash de 26
    a26 = descifrador.ALFABETO_26
    clave = "WATSON"
    cifrado, j = [], 0
    for c in "NOS VEMOS EN LA ESTACION A MEDIANOCHE":
        if c in a26:
            cifrado.append(a26[(a26.index(c) + a26.index(clave[j % 6])) % 26])
            j += 1
        else:
            cifrado.append(c)
    vigenere = descifrador.analizar("".join(cifrado))
    assert vigenere.tipo == "vigenere" and vigenere.mensaje == "NOS VEMOS EN LA ESTACION A MEDIANOCHE"


def test_vigenere_con_clave_desconocida_pide_la_clave():
    desafio = descifrador.cifrar_desafio("nos vemos en la estacion a medianoche", "vigenere", clave="NIEBLA")
    sin_clave = descifrador.analizar_desafio(desafio)
    assert sin_clave.tipo is None and sin_clave.pedir_clave
    de_la_charla = descifrador.analizar_desafio(desafio, ["niebla"])
    assert de_la_charla.tipo == "vigenere" and "NIEBLA" in de_la_charla.detalle
    assert "apareció en nuestra conversación" in " ".join(de_la_charla.observaciones)
    dada = descifrador.analizar_desafio(desafio, clave_dada="Niebla")
    assert dada.tipo == "vigenere" and "usted mismo me dio" in " ".join(dada.observaciones)
    # una clave más larga que medio mensaje no se prueba sola: podría «descifrar» cualquier cosa
    corto = descifrador.cifrar_desafio("hola amigo", "vigenere", clave="INSOPORTABLE")
    assert descifrador.analizar_desafio(corto, ["insoportable"]).tipo is None
    assert descifrador.analizar_desafio(corto, clave_dada="insoportable").mensaje == "HOLA AMIGO"


def test_morse_bacon_y_polibio_escritos_a_mano():
    assert descifrador.analizar("... --- ...").mensaje == "SOS"
    assert descifrador.analizar("-.-. .- ... .-").mensaje == "CASA"
    assert descifrador.analizar("—·—· ·— ··· ·—").mensaje == "CASA"  # rayas y puntos tipográficos
    assert descifrador.analizar(cifrados.bacon_cifrar("hola holmes")).mensaje == "HOLA HOLMES"
    assert descifrador.analizar(cifrados.polibio_cifrar("hola holmes")).mensaje == "HOLA HOLMES"
    assert descifrador.analizar("... --- ... ---.---.-.-.-").tipo is None  # un grupo que no existe


@pytest.mark.parametrize("texto, mensaje", [
    ("Descifre esto: KQ RGEUXJURU", "KQ RGEUXJURU"),
    ("¿Puede descifrar «ETNEIM OMODROYAM LE»?", "ETNEIM OMODROYAM LE"),
    ("Holmes, traduzca este mensaje en clave:\n... --- ...", "... --- ..."),
    ("... --- ... .- -.--", "... --- ... .- -.--"),
    ("15 32 34 11 41 44", "15 32 34 11 41 44"),
    ("Quiero descifrar el mensaje", None),
    ("¿Qué es un mensaje cifrado?", None),
    ("Le traigo un caso", None),
    ("Son las 10 30", None),
])
def test_cuando_un_mensaje_del_chat_es_un_desafio(texto, mensaje):
    assert descifrador.extraer_desafio(texto) == mensaje


@pytest.mark.parametrize("texto, clave", [
    ("la clave es LONDRES", "LONDRES"), ("La clave es la palabra niebla", "NIEBLA"),
    ("La clave: «violín»", "VIOLIN"), ("no tengo la clave", None), ("la clave no la sé", None), ("Hola", None),
])
def test_extraer_clave(texto, clave):
    assert descifrador.extraer_clave(texto) == clave


def test_desafio_en_el_chat(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    cifrado = cifrados.cesar_cifrar("el mayordomo miente", 5)
    at.chat_input[0].set_value(f"Descifre esto: {cifrado}").run()
    assert not at.exception
    nota = sim.turnos[-1]
    assert "[DESAFIO]" in nota and "Cifrado César (desplazamiento 5)" in nota and "EL MAYORDOMO MIENTE" in nota
    ultimo = at.session_state.mensajes[-1]
    assert "EL MAYORDOMO MIENTE" in ultimo["descifrado_html"]
    assert "[DESAFIO]" not in ultimo["texto"] and "eco" not in ultimo["texto"]  # las etiquetas no se ven
    assert at.session_state.modo is None  # un desafío no elige camino


def test_frases_de_conversacion_no_se_toman_por_desafios(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.chat_input[0].set_value("El mensaje cifrado: no lo entiendo").run()
    assert "[DESAFIO]" not in sim.turnos[-1]


def test_desafio_desde_la_libreta_con_bailarines(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.sidebar.text_area(key="desafio_texto_libreta").set_value("te espero en el parque")
    at.sidebar.selectbox(key="desafio_tipo_libreta").set_value("bailarines")
    at.sidebar.button(key="FormSubmitter:desafio_libreta-Entregárselo a Holmes").click().run()
    assert not at.exception
    visitante = [m for m in at.session_state.mensajes if m.get("desafio_html")][-1]
    assert "<svg" in visitante["desafio_html"] and "PARQUE" not in visitante["para_ia"].upper()
    assert "Los bailarines" in sim.turnos[-1] and "TE ESPERO EN EL PARQUE" in sim.turnos[-1]
    assert "TE ESPERO EN EL PARQUE" in at.session_state.mensajes[-1]["descifrado_html"]


def test_vigenere_pendiente_hasta_que_el_visitante_da_la_clave(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.sidebar.text_area(key="desafio_texto_libreta").set_value("nos vemos en la estacion a medianoche")
    at.sidebar.selectbox(key="desafio_tipo_libreta").set_value("vigenere")
    at.sidebar.text_input(key="desafio_clave_libreta").set_value("niebla")
    at.sidebar.button(key="FormSubmitter:desafio_libreta-Entregárselo a Holmes").click().run()
    assert "NO pudo descifrarlo" in sim.turnos[-1] and "palabra clave" in sim.turnos[-1]
    assert "NOS VEMOS" not in sim.turnos[-1].upper()  # Holmes no ve la respuesta
    assert at.session_state.desafio_pendiente and "descifrado_html" not in at.session_state.mensajes[-1]
    at.chat_input[0].set_value("La clave es niebla").run()
    assert "NOS VEMOS EN LA ESTACION A MEDIANOCHE" in sim.turnos[-1]
    assert at.session_state.desafio_pendiente is None
    assert "MEDIANOCHE" in at.session_state.mensajes[-1]["descifrado_html"]


def test_holmes_no_resuelve_los_mensajes_del_caso(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_B").click().run()
    at.button(key="expediente_2").click().run()
    pista = at.session_state.pistas[0]
    at.chat_input[0].set_value(f"Descifre esto: {pista.cifrado.cifrado}").run()
    assert not at.exception
    assert "NO lo descifres" in sim.turnos[-1] and pista.cifrado.mensaje not in sim.turnos[-1]
    assert "descifrado_html" not in at.session_state.mensajes[-1]
    assert "nota_desafio" not in str(at.sidebar)  # durante el caso la libreta es solo del caso


def test_desafio_desde_el_tablero_en_modo_a(sim):
    at = abrir()
    at.chat_input[0].set_value("Hola").run()
    at.button(key="camino_A").click().run()
    at.text_area(key="desafio_texto_tablero").set_value("Hola señor Holmes, buenas noches")
    at.button(key="FormSubmitter:desafio_tablero-Entregárselo a Holmes").click().run()
    assert not at.exception and "no está cifrado" in sim.turnos[-1]
    assert "No estaba cifrado" in at.session_state.mensajes[-1]["descifrado_html"]


def test_las_etiquetas_desafio_no_se_muestran():
    assert partida.extraer_etiquetas("Listo.\n[DESAFIO] instrucciones [/DESAFIO]").texto == "Listo."
    assert partida.extraer_etiquetas("Dice [RESULTADO] algo [/RESULTADO] así.").texto == "Dice así."


# ---------------------------------------------------------------------------
# 6 · Costumbres de Holmes
# ---------------------------------------------------------------------------

def test_el_prompt_tiene_las_costumbres_de_los_libros():
    seccion = PROMPT[PROMPT.index("## Pequeñas costumbres"):PROMPT.index("## Tu índice")]
    for tema in ["Elemental, mi querido Watson", "violín", "Mendelssohn", "conductor de la luz", "Moriarty",
                 "Napoleón del crimen", "ático", "estancamiento", "Sra. Hudson", "detective consultor", "Lestrade"]:
        assert tema in seccion, tema
    assert "solo cuando el visitante las provoque" in seccion and "sin repetir" in seccion


def test_el_prompt_explica_los_desafios():
    assert "[DESAFIO]" in PROMPT and "nunca inventes una traducción" in PROMPT


def test_la_tabla_de_parejas_de_letras_se_puede_recalcular():
    import importlib.util
    ruta = Path(__file__).parent.parent / "scripts" / "calcular_bigramas.py"
    spec = importlib.util.spec_from_file_location("calcular_bigramas", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    tabla, palabras = modulo.calcular()
    from juego.bigramas import BIGRAMAS
    assert set(tabla) == set(BIGRAMAS) and palabras > 5000
    assert BIGRAMAS["QU"] > BIGRAMAS["QK"] and BIGRAMAS["DE"] > BIGRAMAS["DX"]
