import random
from datetime import datetime

from juego import partida
from juego.caso import Caso, Persona, Pista, Sospechoso, reparar_caso
from juego.cifrados import cifrar


def caso_de_prueba() -> Caso:
    sospechoso = lambda n: Sospechoso(nombre=n, ocupacion="mayordomo", relacion_con_victima="empleado", motivo_sospecha="tenía la llave",
                                      coartada="estaba en la cocina", secreto="debe dinero")
    return Caso(
        titulo="La aventura del reloj detenido", lugar="Kensington", fecha="marzo de 1895",
        resumen="Un telegrama urgente.", hechos_conocidos="Lo hallaron muerto en su estudio.",
        escena_nombre="El estudio de Lord Ashby", victima=Persona(nombre="Lord Ashby", descripcion="anciano"),
        crimen="Fue envenenado.", sospechosos=[sospechoso("Arthur Pell"), sospechoso("Mary Stone")],
        culpable="Mary Ston", movil="herencia", metodo="arsénico en el té",
        pistas=[Pista(descripcion="taza", ubicacion="estudio", que_revela="veneno")],
        mensajes_secretos=["La herencia cambia el lunes", "x"], soportes_mensajes=[],
        escena_visual="a dark study",
    )


def test_extraer_etiquetas():
    respuesta = ("¡Excelente! Vamos allá.\n\n[[IMAGEN: a foggy alley, Victorian London]]\n"
                 "Coja su abrigo.\n[[MODO: b]]")
    e = partida.extraer_etiquetas(respuesta)
    assert e.modo == "B"
    assert [i.descripcion for i in e.imagenes] == ["a foggy alley, Victorian London"]
    assert "[[" not in e.texto and "Coja su abrigo." in e.texto


def test_reparar_caso_corrige_culpable_y_mensajes():
    caso = reparar_caso(caso_de_prueba())
    assert caso.culpable == "Mary Stone"
    assert caso.mensajes_secretos == ["LA HERENCIA CAMBIA EL LUNES"]
    assert len(caso.soportes_mensajes) == 1


def test_pistas_aparecen_en_orden():
    pistas = [partida.PistaCifrada(cifrar("hola mundo", "morse"), "una nota") for _ in range(2)]
    assert partida.pista_a_revelar(pistas, 1) is None
    assert partida.pista_a_revelar(pistas, 2) == 0
    pistas[0].estado = "activa"
    assert partida.pista_a_revelar(pistas, 9) is None  # la primera sigue sin resolver
    pistas[0].estado = "resuelta"
    assert partida.pista_a_revelar(pistas, 4) is None
    assert partida.pista_a_revelar(pistas, 5) == 1


def test_proponer_y_puntaje():
    pista = partida.PistaCifrada(cifrar("veneno en el te", "cesar", random.Random(1)), "un telegrama")
    pista.estado = "activa"
    assert pista.proponer("Código Morse", "veneno en el té") == (False, True)
    assert pista.estado == "activa"
    pista.siguiente_ayuda()
    assert pista.proponer("Cifrado César", "veneno en el té") == (True, True)
    assert pista.estado == "resuelta" and pista.puntos == 100 - 20 - 10


def test_instruccion_no_filtra_mensajes_sin_resolver():
    caso = reparar_caso(caso_de_prueba())
    pista = partida.PistaCifrada(cifrar(caso.mensajes_secretos[0], "atbash"), "una nota")
    pista.estado = "activa"
    texto = partida.instruccion_sistema("PROMPT", "B", caso, [pista], False, 1)
    assert "[CASO SECRETO]" in texto and "CULPABLE: Mary Stone" in texto
    assert "LA HERENCIA CAMBIA EL LUNES" not in texto
    pista.rendirse()
    assert "LA HERENCIA CAMBIA EL LUNES" in partida.instruccion_sistema("P", "B", caso, [pista], False, 1)


def test_contexto_hora():
    assert partida.contexto_hora(datetime(2026, 10, 10, 23, 36)).endswith("23:36 (sábado)")


def test_instruccion_sin_imagenes():
    caso = reparar_caso(caso_de_prueba())
    texto = partida.instruccion_sistema("P", "B", caso, [], False, 0, imagenes_activas=False)
    assert "NO escribas [[IMAGEN" in texto
