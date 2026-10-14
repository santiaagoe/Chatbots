"""
Casos completos escritos a mano, uno por dificultad.

Siempre aparece uno como carpeta del modo B: el de la dificultad elegida (si el
visitante ya lo jugó, otro que no haya jugado). No necesitan que Gemini invente
nada, así que funcionan aunque la API esté saturada o se haya acabado la cuota
del día (Holmes igual necesita a Gemini para conversar). Están revisados y se
pueden resolver razonando, así que también sirven para mostrar el juego.

Cada pista dice a quién apunta (apunta_a) y si lo incrimina o lo descarta:
con eso se dibuja el hilo rojo al final del caso.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from juego.caso import Caso, OpcionCaso, Persona, Pista, Sospechoso


# ---------------------------------------------------------------------------
# Fácil: La partitura robada
# ---------------------------------------------------------------------------

def _partitura() -> Caso:
    return Caso(
        titulo="El caso de la partitura robada",
        lugar="Covent Garden, Londres",
        fecha="jueves 7 de marzo de 1895",
        resumen="The Times anuncia esta mañana que el estreno de «La dama de Lucerna», la nueva ópera del "
                "maestro Julius Brandt, peligra: la única partitura completa desapareció de su camerino.",
        hechos_conocidos="El maestro Brandt guardó la partitura en el cajón de su escritorio antes de salir a "
                         "almorzar, a la una. Cuando volvió, a las tres, el cajón seguía cerrado con llave y la "
                         "partitura ya no estaba. La llave cuelga siempre de un gancho junto a la puerta del camerino.",
        victima=Persona(nombre="Julius Brandt",
                        descripcion="compositor y director de orquesta alemán, irascible y meticuloso"),
        escena_nombre="El camerino del maestro Brandt en la Royal Opera House",
        crimen="Henry Pike, el copista, debía dinero de apuestas en las carreras. Un empresario del Lyceum, el "
               "teatro rival, le ofreció cien libras por la partitura para estrenar la ópera antes. A la una y "
               "media, mientras el maestro almorzaba, Pike entró al camerino, tomó la llave del gancho y abrió el "
               "cajón con las manos todavía manchadas de la tinta violeta que usan los copistas. Se llevó la "
               "partitura escondida entre las partes de violín, volvió a cerrar y colgó la llave. Con la prisa se "
               "le cayó un programa del Lyceum que llevaba en el bolsillo.",
        sospechosos=[
            Sospechoso(
                nombre="Clara Weiss", ocupacion="primera soprano",
                relacion_con_victima="canta el papel principal de la ópera",
                motivo_sospecha="Discutió a gritos con el maestro porque le recortó su aria principal.",
                coartada="Dice que ensayó con el pianista en la sala B toda la tarde.",
                secreto="Tiene una oferta para cantar en París y piensa dejar la compañía después del estreno."),
            Sospechoso(
                nombre="Arthur Finch", ocupacion="primer violín",
                relacion_con_victima="toca en la orquesta del maestro desde hace diez años",
                motivo_sospecha="El maestro lo humilló esa misma mañana delante de toda la orquesta.",
                coartada="Asegura que salió a fumar al callejón y que no volvió a entrar hasta las tres.",
                secreto="Está escribiendo su propia ópera y teme que el maestro se burle de ella."),
            Sospechoso(
                nombre="Henry Pike", ocupacion="copista de la orquesta",
                relacion_con_victima="copia a mano las partes de cada músico a partir de la partitura del maestro",
                motivo_sospecha="Es el único, además del maestro, que sabe dónde se guarda la llave del cajón.",
                coartada="Dice que pasó la tarde en la sala de copistas, copiando las partes de los violines.",
                secreto="Debe dinero a un corredor de apuestas de las carreras de caballos."),
        ],
        culpable="Henry Pike",
        movil="Pagar sus deudas de apuestas: un empresario del teatro Lyceum le ofreció cien libras por la partitura.",
        metodo="Tomó la llave del gancho mientras el maestro almorzaba, abrió el cajón, se llevó la partitura "
               "escondida entre las partes de violín y volvió a cerrar con llave.",
        pistas=[
            Pista(descripcion="Manchas frescas de tinta violeta en el tirador del cajón",
                  ubicacion="el escritorio del camerino",
                  que_revela="En el teatro solo los copistas usan tinta violeta: quien abrió el cajón venía de copiar.",
                  apunta_a="Henry Pike", efecto="incrimina"),
            Pista(descripcion="Un programa doblado del Lyceum Theatre, el teatro rival, caído bajo el escritorio",
                  ubicacion="el suelo del camerino",
                  que_revela="El ladrón tiene tratos con el teatro rival, que querría estrenar la ópera antes.",
                  apunta_a="Henry Pike", efecto="incrimina"),
            Pista(descripcion="El pianista confirma que Clara ensayó con él sin interrupción de una a tres",
                  ubicacion="al interrogar a Clara Weiss",
                  que_revela="Clara no pudo estar en el camerino: queda descartada.",
                  apunta_a="Clara Weiss", efecto="descarta"),
            Pista(descripcion="El portero vio a Finch fumando en el callejón toda esa hora; no volvió a entrar hasta las tres",
                  ubicacion="al interrogar a Arthur Finch",
                  que_revela="Finch tampoco pudo entrar al camerino: queda descartado.",
                  apunta_a="Arthur Finch", efecto="descarta"),
            Pista(descripcion="Las partes de violín que Pike dice haber copiado esa tarde están a medio hacer y "
                              "la tinta está seca desde hace horas",
                  ubicacion="al interrogar a Henry Pike",
                  que_revela="Pike miente: no estuvo copiando toda la tarde, así que su coartada no vale.",
                  apunta_a="Henry Pike", efecto="incrimina"),
        ],
        mensajes_secretos=["LLEVE LA PARTITURA AL LYCEUM", "PAGO EL SABADO A LAS NUEVE"],
        soportes_mensajes=[
            "una tarjeta sin firma escondida en un atril de la orquesta",
            "un telegrama arrugado en la papelera de la sala de copistas",
        ],
        escena_visual="A Victorian opera house dressing room, a wooden writing desk with a closed drawer stained "
                      "with violet ink on its brass handle, a key hanging on a hook beside the door, a folded "
                      "theatre programme on the floor under the desk, a mirror framed with gas lamps, sheet music "
                      "scattered on a chair, warm gaslight",
    )


# ---------------------------------------------------------------------------
# Medio: El candelabro torcido
# ---------------------------------------------------------------------------

def _candelabro() -> Caso:
    return Caso(
        titulo="La aventura del candelabro torcido",
        lugar="Belgravia, Londres",
        fecha="martes 12 de febrero de 1895",
        resumen="El inspector Lestrade pide ayuda: la Estrella de Bengala, el rubí más preciado de "
                "Sir Hugh Pemberton, desapareció durante la noche de su casa de Belgravia.",
        hechos_conocidos="Sir Hugh guardó el rubí en su vitrina a las diez de la noche y cerró con la única "
                         "llave, que lleva colgada de la cadena del reloj. Al amanecer la vitrina seguía "
                         "cerrada, sin marcas de haber sido forzada, pero el cojín de terciopelo estaba vacío. "
                         "Junto a la vitrina, el candelabro de bronce del salón apareció torcido.",
        victima=Persona(nombre="Sir Hugh Pemberton",
                        descripcion="coleccionista de joyas, viudo y de sueño pesado"),
        escena_nombre="El salón de Pemberton House",
        crimen="Una semana antes, mientras Sir Hugh dormía la siesta en su sillón, Ada Lowe presionó la llave "
               "de la vitrina contra un trozo de cera de vela y obtuvo un molde. El martes anterior llevó el "
               "molde a un cerrajero de Soho, que le hizo una copia. La noche del robo esperó a que todos "
               "durmieran, bajó en zapatillas con una vela, abrió la vitrina con la copia, tomó el rubí y volvió "
               "a cerrar. Al girar la llave nueva, aún áspera, quedaron restos de cera en la cerradura. Con prisa, "
               "tropezó con el candelabro y lo torció. Para desviar las sospechas, dejó bajo el sofá un guante "
               "que había impregnado con el tabaco turco que fuma Ned Carr.",
        sospechosos=[
            Sospechoso(
                nombre="Tom Briggs", ocupacion="mayordomo",
                relacion_con_victima="lleva veinte años al servicio de Sir Hugh",
                motivo_sospecha="Fue el último en ver a Sir Hugh antes de que cerrara la vitrina.",
                coartada="Dice que se acostó a las once y solo se levantó a las dos al ver luz bajo la puerta del salón.",
                secreto="Bebe a escondidas el oporto de su amo y por eso no quiso entrar al salón a esa hora."),
            Sospechoso(
                nombre="Ada Lowe", ocupacion="institutriz",
                relacion_con_victima="educa a la nieta de Sir Hugh y vive en la casa",
                motivo_sospecha="Su habitación es la única contigua al salón.",
                coartada="Asegura que durmió toda la noche y que el martes solo fue a Soho a comprar cintas.",
                secreto="Su hermano debe una fortuna a unos prestamistas que lo amenazan."),
            Sospechoso(
                nombre="Ned Carr", ocupacion="sobrino y heredero",
                relacion_con_victima="sobrino de Sir Hugh, vive de la asignación que le da su tío",
                motivo_sospecha="Discutió a gritos con su tío por dinero esa misma noche.",
                coartada="Dice que pasó la noche jugando a las cartas en su club de Pall Mall hasta las tres.",
                secreto="Perdió mucho dinero en las cartas y había pedido a su tío que le adelantara la herencia."),
        ],
        culpable="Ada Lowe",
        movil="Pagar las deudas de juego de su hermano, amenazado por prestamistas.",
        metodo="Hizo un molde de cera de la llave, encargó una copia a un cerrajero de Soho y de madrugada "
               "abrió y volvió a cerrar la vitrina; dejó un guante con tabaco turco para inculpar a Ned.",
        pistas=[
            Pista(descripcion="Restos de cera blanca de vela en el interior de la cerradura de la vitrina",
                  ubicacion="la vitrina del salón",
                  que_revela="La cerradura se abrió con una llave copiada a partir de un molde de cera: el ladrón "
                             "no forzó nada y tuvo acceso a la llave de Sir Hugh durante días.",
                  apunta_a="Ada Lowe", efecto="incrimina"),
            Pista(descripcion="Un guante de cabritilla de talla pequeña, con fuerte olor a tabaco turco",
                  ubicacion="bajo el sofá del salón",
                  que_revela="El tabaco apunta a Ned, pero el guante es de mano pequeña, de mujer: alguien quiso "
                             "inculparlo.",
                  apunta_a="Ned Carr", efecto="descarta"),
            Pista(descripcion="Gotas de cera en la alfombra que van desde la vitrina hasta la puerta del cuarto contiguo",
                  ubicacion="la alfombra del salón",
                  que_revela="Quien llevaba la vela salió hacia la habitación contigua al salón: la de Ada Lowe.",
                  apunta_a="Ada Lowe", efecto="incrimina"),
            Pista(descripcion="Tom oyó a las dos de la madrugada pasos muy ligeros, como de zapatillas, no de botas",
                  ubicacion="al interrogar a Tom Briggs",
                  que_revela="El ladrón era liviano y estaba dentro de la casa: no alguien que llegaba de la calle con botas.",
                  apunta_a="Ada Lowe", efecto="incrimina"),
            Pista(descripcion="El portero del club de Pall Mall confirma que Ned jugó a las cartas hasta las tres y media",
                  ubicacion="al interrogar a Ned Carr",
                  que_revela="Ned no pudo estar en el salón a las dos: queda descartado.",
                  apunta_a="Ned Carr", efecto="descarta"),
            Pista(descripcion="Ada se contradice: dice que fue a Soho por cintas, pero no trae ninguna y se pone nerviosa",
                  ubicacion="al interrogar a Ada Lowe",
                  que_revela="Su visita a Soho tenía otro propósito: encargar la copia de la llave.",
                  apunta_a="Ada Lowe", efecto="incrimina"),
        ],
        mensajes_secretos=["EL MARTES EN SOHO", "LA COPIA ESTA LISTA"],
        soportes_mensajes=[
            "una tarjeta de visita de un cerrajero de Soho, olvidada en el costurero del salón",
            "un telegrama sin firma, a medio quemar en la chimenea",
        ],
        escena_visual="An elegant Victorian drawing room at grey dawn, a glass display cabinet with an empty red "
                      "velvet cushion, a bent brass candlestick on a side table, drops of white candle wax on a "
                      "patterned carpet leading to a side door, a sofa with a small lady's glove peeking from "
                      "underneath, tall windows with fog outside",
    )


# ---------------------------------------------------------------------------
# Difícil: El telegrafista de Whitehall
# ---------------------------------------------------------------------------

def _telegrafista() -> Caso:
    return Caso(
        titulo="La aventura del telegrafista de Whitehall",
        lugar="Whitehall, Londres",
        fecha="lunes 18 de noviembre de 1895",
        resumen="Sir Edmund Hale, subsecretario del Foreign Office, escribe una carta angustiada que la Sra. Hudson "
                "entrega en mano: Mycroft le aseguró que solo su hermano puede ayudarlo sin que estalle un escándalo.",
        hechos_conocidos="El viernes a las once de la noche llegó a la sala de telégrafos del Foreign Office un "
                         "telegrama secreto con las condiciones de un tratado naval. El telegrafista de guardia lo "
                         "transcribió y lo entregó sellado a Sir Edmund. El domingo, un diario de Berlín publicó las "
                         "condiciones palabra por palabra. Esa noche, cuatro personas pudieron entrar a la sala.",
        victima=Persona(nombre="Sir Edmund Hale",
                        descripcion="subsecretario del Foreign Office, responsable de que el telegrama no saliera de allí"),
        escena_nombre="La sala de telégrafos del Foreign Office",
        crimen="Oliver Penrose, el secretario de Sir Edmund, había perdido mucho dinero especulando en la Bolsa, y un "
               "agente extranjero le ofreció quinientas libras por las condiciones del tratado. Penrose sabía que el "
               "telegrafista copia cada telegrama con una hoja de papel carbónico que luego tira a la papelera. Se fue "
               "a su casa de Craven Street a las nueve y media, a la vista de su casera, pero volvió a salir a las once "
               "y entró por la escalera de servicio, con las botas manchadas del barro rojizo de las zanjas que abren "
               "en su calle. Encontró a Walter Gray dormitando junto al aparato, sacó de la papelera la hoja de carbón "
               "usada, que muestra el texto invertido, y dejó en su lugar un pañuelo nuevo con las iniciales de Lady "
               "Margaret para que sospecharan de ella. En casa leyó el carbón con un espejo y copió el texto.",
        sospechosos=[
            Sospechoso(
                nombre="Walter Gray", ocupacion="telegrafista de guardia",
                relacion_con_victima="recibe y transcribe los telegramas secretos del ministerio desde hace seis años",
                motivo_sospecha="Fue el único que tuvo en sus manos el telegrama completo.",
                coartada="Dice que transcribió el telegrama, lo selló y se lo entregó a Sir Edmund sin apartarse del aparato.",
                secreto="Duerme a ratos durante el turno de noche, algo que el reglamento castiga con el despido."),
            Sospechoso(
                nombre="Lady Margaret Hale", ocupacion="esposa de Sir Edmund",
                relacion_con_victima="esposa de Sir Edmund; esa noche le llevó la cena al ministerio",
                motivo_sospecha="Estuvo en la sala esa noche y es íntima amiga de la esposa del agregado alemán.",
                coartada="Asegura que estuvo diez minutos y que nunca se acercó al aparato.",
                secreto="Juega a las cartas con la esposa del agregado y le ha perdido una pequeña suma."),
            Sospechoso(
                nombre="Oliver Penrose", ocupacion="secretario particular de Sir Edmund",
                relacion_con_victima="lleva la agenda de Sir Edmund; vive en Craven Street, donde están abriendo "
                                     "zanjas para el alcantarillado",
                motivo_sospecha="Sabía que el telegrama llegaría esa noche y tiene llave del despacho de Sir Edmund.",
                coartada="Dice que se fue a casa a las nueve y media y no volvió a salir; su casera lo vio llegar.",
                secreto="Perdió sus ahorros especulando en la Bolsa y debe dinero a varios corredores."),
            Sospechoso(
                nombre="Samuel Reed", ocupacion="mozo de limpieza nocturno",
                relacion_con_victima="limpia cada noche la sala de telégrafos y vacía sus papeleras",
                motivo_sospecha="Vacía las papeleras de la sala y nadie revisa lo que se lleva.",
                coartada="Dice que limpió la sala a medianoche, como siempre, y que no vio a nadie.",
                secreto="Vende el papel usado de las papeleras a un trapero por unos peniques."),
        ],
        culpable="Oliver Penrose",
        movil="Pagar sus deudas de la Bolsa: un agente extranjero le ofreció quinientas libras por el tratado.",
        metodo="Volvió de noche por la escalera de servicio mientras Gray dormitaba, se llevó de la papelera la "
               "hoja de papel carbónico con el texto invertido, la leyó con un espejo y dejó un pañuelo con las "
               "iniciales de Lady Margaret para culparla.",
        pistas=[
            Pista(descripcion="El taco de formularios del telegrafista tiene marcas de papel carbónico, pero no queda "
                              "ninguna hoja de carbón usada en la sala",
                  ubicacion="la mesa del aparato telegráfico",
                  que_revela="El texto salió en la hoja de carbón, no en el original sellado: el ladrón no tuvo el "
                             "original y necesitó la copia que queda en la papelera.",
                  apunta_a="Oliver Penrose", efecto="incrimina"),
            Pista(descripcion="Un pañuelo de seda nuevo, con los dobleces de la tienda y las iniciales «M. H.», en la "
                              "papelera junto al aparato",
                  ubicacion="la papelera de la sala",
                  que_revela="Un pañuelo que nunca se ha usado ni lavado no se pierde: lo dejaron a propósito para "
                             "culpar a Lady Margaret.",
                  apunta_a="Lady Margaret Hale", efecto="descarta"),
            Pista(descripcion="Huellas de barro rojizo en la escalera de servicio, que de noche solo se abre desde dentro",
                  ubicacion="la escalera de servicio",
                  que_revela="Alguien llegó de la calle por la escalera de servicio; el barro rojizo es el de las "
                             "zanjas de Craven Street, donde vive Penrose.",
                  apunta_a="Oliver Penrose", efecto="incrimina"),
            Pista(descripcion="Reed anotó en su libreta de turno, a medianoche, que la papelera del aparato ya estaba "
                              "vacía, algo que nunca ocurre",
                  ubicacion="al interrogar a Samuel Reed",
                  que_revela="La hoja de carbón desapareció antes de que llegara Reed, y él lo dejó por escrito antes "
                             "de saber del robo: queda descartado.",
                  apunta_a="Samuel Reed", efecto="descarta"),
            Pista(descripcion="Gray admite que dormitó entre las once y media y medianoche, y que al despertar la "
                              "puerta de servicio estaba entornada",
                  ubicacion="al interrogar a Walter Gray",
                  que_revela="Gray tuvo el original en sus manos toda la noche: no necesitaba robar una copia. Su "
                             "descuido abrió la puerta al ladrón.",
                  apunta_a="Walter Gray", efecto="descarta"),
            Pista(descripcion="Penrose jura que no salió de casa, pero comenta sin querer que la puerta de servicio "
                              "«chirría como un alma en pena», y esa puerta solo se cierra de noche",
                  ubicacion="al interrogar a Oliver Penrose",
                  que_revela="Solo quien usó esa puerta de noche sabe que chirría: Penrose estuvo allí y miente.",
                  apunta_a="Oliver Penrose", efecto="incrimina"),
        ],
        mensajes_secretos=["EL CARBON GUARDA LA COPIA", "LA PUERTA DE SERVICIO ESTARA ABIERTA"],
        soportes_mensajes=[
            "un anuncio sin firma en la sección personal de The Times",
            "una nota doblada en el bolsillo de un abrigo olvidado en el guardarropa del ministerio",
        ],
        escena_visual="A Victorian government telegraph room at night, a brass telegraph apparatus on a heavy desk, "
                      "a pad of telegram forms beside it, an empty wicker wastepaper basket with a folded silk "
                      "handkerchief inside, a narrow service staircase door left ajar with reddish muddy footprints "
                      "on the steps, green-shaded lamps, tall windows over a foggy Whitehall",
    )


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CasoMuestra:
    dificultad: str
    opcion: OpcionCaso
    crear: Callable[[], Caso]
    medio: str          # cómo llega a Baker Street (clave de partida.MEDIOS)
    tema: str           # para que Gemini no proponga un caso parecido


CASOS_MUESTRA: list[CasoMuestra] = [
    CasoMuestra(
        "fácil",
        OpcionCaso(titulo="El caso de la partitura robada", tipo_crimen="robo", lugar="Covent Garden, Londres",
                   gancho="La única copia de una ópera desaparece de un cajón cerrado dos días antes del estreno.",
                   muestra=True),
        _partitura, "periodico", "el robo de una partitura o de un manuscrito"),
    CasoMuestra(
        "medio",
        OpcionCaso(titulo="La aventura del candelabro torcido", tipo_crimen="robo", lugar="Belgravia, Londres",
                   gancho="Un rubí desaparece de una vitrina que a la mañana siguiente sigue cerrada con llave.",
                   muestra=True),
        _candelabro, "telegrama", "el robo de una joya en una vitrina"),
    CasoMuestra(
        "difícil",
        OpcionCaso(titulo="La aventura del telegrafista de Whitehall", tipo_crimen="espionaje",
                   lugar="Whitehall, Londres",
                   gancho="Un telegrama secreto llega sellado a su destino, y aun así un diario de Berlín lo publica "
                          "palabra por palabra.",
                   muestra=True),
        _telegrafista, "carta", "el robo de un documento secreto del gobierno"),
]


def elegir_muestra(dificultad: str, jugados: list[str] | None = None) -> CasoMuestra:
    """El caso de muestra que se ofrece: el de la dificultad elegida, salvo que ya se haya jugado."""
    jugados = jugados or []
    propio = next((c for c in CASOS_MUESTRA if c.dificultad == dificultad), CASOS_MUESTRA[1])
    if propio.opcion.titulo not in jugados:
        return propio
    return next((c for c in CASOS_MUESTRA if c.opcion.titulo not in jugados), propio)


def buscar_muestra(titulo: str) -> CasoMuestra | None:
    return next((c for c in CASOS_MUESTRA if c.opcion.titulo == titulo), None)


# Compatibilidad: el caso de muestra «de siempre» (dificultad media)
OPCION_MUESTRA = CASOS_MUESTRA[1].opcion


def caso_muestra() -> Caso:
    """Devuelve una copia nueva del caso medio (cada partida puede modificar la suya)."""
    return _candelabro()
