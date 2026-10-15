"""Ayudas compartidas por las pruebas de la interfaz."""

from juego.caso import OpcionCaso, OpcionesCaso


def opciones_falsas() -> OpcionesCaso:
    return OpcionesCaso(opciones=[
        OpcionCaso(titulo="La aventura del candelabro torcido", tipo_crimen="robo", lugar="Belgravia",
                   gancho="Un rubí desaparece de una vitrina cerrada."),
        OpcionCaso(titulo="El misterio del faro apagado", tipo_crimen="desaparición", lugar="Cornualles",
                   gancho="El farero se esfuma y la luz se apaga en plena tormenta."),
        OpcionCaso(titulo="El enigma del reloj parado", tipo_crimen="chantaje", lugar="Oxford",
                   gancho="Un profesor recibe cartas que anuncian, al minuto, lo que hará al día siguiente."),
    ])


def abrir_primer_expediente(at):
    """Elige la primera carpeta que Holmes deja sobre el tablero."""
    at.button(key="expediente_0").click().run()
    return at
