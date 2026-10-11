"""Pruebas: cada cifrado debe poder descifrarse y devolver el mensaje original."""

import random

import pytest

from juego import cifrados as c

MENSAJES = [
    "El culpable usa botas de montar",
    "Busque bajo el tercer escalón",
    "La señora Ñuñoa miente",
    "Veneno en el té de las cinco",
]


def test_normalizar_quita_tildes_y_conserva_enie():
    assert c.normalizar("¡Él comió piña, señor!") == "EL COMIO PIÑA SEÑOR"


def test_respuestas_coinciden_es_tolerante():
    assert c.respuestas_coinciden("el  culpable, USÓ botas", "EL CULPABLE USO BOTAS")
    assert not c.respuestas_coinciden("", "ALGO")
    assert not c.respuestas_coinciden("otra cosa", "ALGO")


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_morse(mensaje):
    assert c.morse_descifrar(c.morse_cifrar(mensaje)) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_espejo(mensaje):
    assert c.espejo_descifrar(c.espejo_cifrar(mensaje)) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_atbash_es_su_propio_inverso(mensaje):
    assert c.atbash(c.atbash(mensaje)) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
@pytest.mark.parametrize("n", [3, 5, 9])
def test_cesar(mensaje, n):
    assert c.cesar_descifrar(c.cesar_cifrar(mensaje, n), n) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_vigenere(mensaje):
    for clave in c.CLAVES_VIGENERE:
        assert c.vigenere_descifrar(c.vigenere_cifrar(mensaje, clave), clave) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_bacon(mensaje):
    assert c.bacon_descifrar(c.bacon_cifrar(mensaje)) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_polibio(mensaje):
    assert c.polibio_descifrar(c.polibio_cifrar(mensaje)) == c.normalizar(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_cerca(mensaje):
    assert c.cerca_descifrar(c.cerca_cifrar(mensaje)) == c.solo_letras(mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_tercera_palabra(mensaje):
    oculto = c.tercera_cifrar(mensaje, random.Random(1))
    assert c.respuestas_coinciden(c.tercera_descifrar(oculto), mensaje)


@pytest.mark.parametrize("mensaje", MENSAJES)
def test_bailarines(mensaje):
    indices = c.bailarines_indices(mensaje)
    assert c.bailarines_descifrar(indices) == c.normalizar(mensaje)
    assert c.bailarines_svg(mensaje).startswith("<svg")


def test_las_27_figuras_son_distintas():
    assert len({c._figura(i, 0, 0, False) for i in range(27)}) == 27
    assert c.bailarines_leyenda().count("<text") == 27


@pytest.mark.parametrize("tipo", list(c.CIFRADOS))
def test_cifrar_entrega_tres_pistas(tipo):
    resultado = c.cifrar("La llave está en el reloj", tipo, random.Random(7))
    assert resultado.mensaje == "LA LLAVE ESTA EN EL RELOJ"
    assert len(resultado.pistas) == 3
    assert resultado.cifrado


def test_cifrar_al_azar_respeta_dificultad_y_evita_repetir():
    rng = random.Random(3)
    for dificultad in c.DIFICULTADES:
        resultado = c.cifrar_al_azar("hola", dificultad, rng=rng)
        assert c.CIFRADOS[resultado.tipo]["dificultad"] == dificultad
    resultado = c.cifrar_al_azar("hola", "fácil", evitar=["morse", "espejo"], rng=rng)
    assert resultado.tipo == "atbash"


def test_nombres_y_tipos():
    for nombre in c.nombres_para_elegir():
        assert c.tipo_por_nombre(nombre) in c.CIFRADOS
