"""
Holmes descifra los mensajes que le manda el visitante.

El trabajo lo hace el código, no Gemini (que se equivocaría): se prueban todos los
cifrados del juego y se elige el resultado que más parece español. Luego se le
entregan a Holmes el resultado y observaciones reales del análisis (qué letra se
repite más, cuántos rieles tiene la cerca…) para que las cuente como deducciones suyas.

También sirve al revés: si el visitante no sabe cifrar a mano, la app cifra su mensaje
con el código que elija y Holmes tiene que descubrir cuál fue, sin saber la respuesta.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field

from juego import cifrados
from juego.bigramas import BIGRAMAS
from juego.cifrados import ALFABETO, CIFRADOS, CLAVES_VIGENERE, normalizar, solo_letras

# ---------------------------------------------------------------------------
# ¿Parece español?
# ---------------------------------------------------------------------------

# Palabras frecuentes (sin tildes, como quedan al normalizar). Escritas a mano para este juego.
_PALABRAS = """
a al algo alguien algun alguna algunas alguno algunos alla alli ante antes aqui asi aun aunque ayer
bajo bien cada casi como con contra cual cuales cualquier cuando cuanto de del desde donde dos durante
e el ella ellas ello ellos en entonces entre era eran eres es esa esas ese eso esos esta estaba estado
estamos estan estar estas este esto estos estoy fue fueron fui ha habia hace hacia han has hasta hay he
hemos hoy la las le les lo los mas me mi mis mucho muchos muy nada nadie ni no nos nosotros nuestra
nuestro nunca o os otra otras otro otros para pero poco por porque pues que quien quienes se sea segun
ser si siempre sin sino sobre solo son soy su sus tal tambien tan tanto te tengo tiene tienen todo todos
tu tus un una unas uno unos usted ustedes va vamos van ver vez y ya yo
abajo abierta abierto abra abre abril acaso acuerdo adentro adios agua ahora alto amigo amiga amor
anoche ano anos aparato arriba asunto atras aviso ayuda azul banco barco barrio baul biblioteca blanco
boca bolsa bolsillo bosque botella brazo buen buena bueno buscar busque busca caballo cabeza cadena caja
calle cama camino campo cancion cara carbon carcel carta cartas casa caso castillo cena cerca cerrada
cerrado cielo cinco ciudad clave club cochero codigo colegio comida conde copia copiar corazon corona
correo cosa cosas crimen cuarto cuatro cuchillo culpa culpable dama dar debajo deber debe debo decir
dejar deje dejo detras dia diamante diario dias diez dinero dios doctor dolar domingo dona dormir dueno
duque ejercito el elemental embajada encontrar enero entrada entrar entregue envie envio equipaje
escalera escondido espada espejo espera esperar espere esposa esposo estacion estrella estudio familia
favor febrero fin flor fuego fuera fuerte gato gente gracias gran grande guante guarda guardia guerra
habitacion hablar hacer hambre hermana hermano hija hijo hilo historia hombre hombres hora horas hotel
hueco huella iglesia ingles inspector invierno ir isla jamas jardin joven joya joyas jueves juez junio
junto jurado lado ladron largo lejos lento letra libro libros lista listo listos llave llaves llega
llegada llegar llego lleve lluvia londres lord luego lugar luna lunes luz madre maestro mal malo manana
mano manos mapa mar marco martes marzo matar mayo medianoche medico mejor mensaje mes mesa miedo
miercoles mil minuto mio misma mismo momento moneda morir muerte muerto mujer mundo museo musica nada
negro niebla nina nino noche nombre norte nota noticia noticias nueve nuevo numero ojo ojos oro oscuro
otono padre pagar pago pais palabra papel paquete parque partitura pasado paso patio pelo pena pequeno
perro persona piedra plan plata plaza pluma pobre policia poner primera primero prisa pronto
pruebe puerta puerto punto quiero quince rapido reina reloj rey rio robo rojo ropa rubi sabado sabe
sala salga salir salud sangre secreto seguro seis semana senal senor senora senorita servicio siete
silencio sobre sol soldado sombra sombrero sospechoso sotano sur tarde tarjeta te teatro telegrama
temprano tiempo tienda tierra tio torre trabajo tren tres tumba ultimo uno vacio venga veneno venir
ventana verdad verde viaje viejo viento viernes vino visita vitrina vivo volver vuelva zapato
holmes watson sherlock baker street hudson lestrade mycroft moriarty adler irene scotland yard soho
abogado abuela abuelo amo amas ama acaba acabo acepta acerca actor adivina adivinar agosto ahi alegre alegria alma
almuerzo amable amarillo amiga amigas amigos ancho angel animal antiguo anillo aparece aprender arbol arena
arma armario arte asesino asesina atrapar aventura avion avisa avise bailar baja bajar banco bano barba
basta bebe beber bebida besa beso biblia bicicleta billete boda bolso bonita bonito borracho bota botas
brillante broma bruja buenas buenos busco cabello cabo cadaver cae caer cafe calor cama camara cambia
cambio caminar camisa campana canta cantar capitan capitulo carcel carne caro carro casada casado casas
castigo causa cayo celos cerro cerveza chico chica chocolate cien ciencia cierra cierto cine claro cliente
cobre coche cocina cocinero coger colegio color come comer comio comprar compro conocer conoce consejo
contar conto contesta copa correr corre corrio corto costa crea creo creer criada criado cruz cuadro
cuchara cuello cuenta cuento cuerpo cuidado cuidar culpa cumpleanos cura dame danza debes decide dedo
dejame dentro deprisa derecha descubre descubrir desde deseo despacio despues detective dice dicen dientes
diga digo dijo dime dinero direccion disparo doce dolor dormido duda dulce duro edad edificio ejemplo
enemigo enfermo engano enorme enterrado entrega escapa escapo escondio escribe escribir escuela escucha
espalda espejo esperanza esquina estrella estudiante examen explica falso falta familia famoso fecha feliz
feo fiesta fila final fiscal flores fondo fortuna foto frio fruta fuente gana ganar garaje gatos general
gente gordo grita gritar guarde guardar gusta gusto habla hablo hace hacen hacer hago halla hallar harina
hecho helado herida hermosa hermoso hielo hierro hija hijos hoja hola hombro honor hospital hubo huevo
huir humo idea iglesia igual imposible importa importante inocente isla izquierda jefe juego jugar juguete
juntos justicia ladra ladrones lago lapiz largo leche leer leon lengua lento libre limpio linea llama
llamar llegan llegue lleno llevar llevo llora llorar lobo loco luna madera maleta mama manda mandar
manera mantel manzana maquina marido mata mato mayor mayordomo medio memoria menor menos mente mentira
mercado mesa metal mete miente mientras minutos mira mirar misterio mitad moneda monte morado mostrar
motivo mover mucha muchas muere muerta mueve mujeres muro nacio nadar navidad necesito negocio nervioso
nieve ninguno nino ninos nivel noble nombres novia novio nube nueva nuevos oficina oido oir olvida olvido
orden oreja oscura otono paciencia padres pagina pajaro palacio pan pantalon papa papeles par parece pared
pareja parte partido pasa pasar paseo pastel pata paz pecho pedir pedro pelea peligro peligroso pensar
pequena perdido perdon periodico permiso pero perros pesca pez piano pie piel piensa pierna piso pistola
plano playa pocos poder policia pollo polvo pone popular precio pregunta premio preso primavera prima primo
principe prisa prision problema profesor prometo propio proximo prueba pueblo puede pueden puedo puente
quedar queda queso quiere quieren quita radio rata rato raton razon real recuerda recuerdo regalo regla
reir reloj respuesta resto retrato reunion revela revisa rico rio risa robar robado robaron roble roca
rodilla rompe rosa rueda ruido saber sabes saca sacar salida salio salon saltar salvar santo secretaria
sed seda seguir senda sentado sentir senores serio sigue silla simple sitio sobrino sociedad sofa sola
solamente soltero sombrero sonrisa sopa sorpresa sospecha subir sucio sueno suerte suelo tabaco tambor
tarea taza techo telefono tema temer tenia terminar tesoro testigo tia tienes tijeras tinta tipo tira
tirar toca tocar toma tomar tonto trae traer traje trampa tranquilo trato triste tropa tumba unico
universidad vaca valiente vaso vecino vela vende vender veneno ventana vera verano verdadero vestido
viaja vida vidrio vieja vinieron violin violeta visto viuda vive vivir volvio voz vuelo zapatos
""".split()

PALABRAS = {normalizar(p) for p in _PALABRAS} | {normalizar(p) for p in cifrados.RELLENO}
_LETRAS_SUELTAS = {"A", "E", "O", "U", "Y"}
_LARGO_MAXIMO = max(len(p) for p in PALABRAS)


def segmentar(letras: str) -> tuple[float, list[str]]:
    """Divide letras sin espacios en palabras conocidas. Devuelve (cobertura 0-1, trozos).

    Las palabras largas valen más que las cortas, para que un texto sin sentido no gane
    juntando «de», «la» y «se».
    """
    n = len(letras)
    if n == 0:
        return 0.0, []
    mejor = [0.0] * (n + 1)
    corte: list[tuple[int, bool]] = [(0, False)] * (n + 1)
    for i in range(1, n + 1):
        mejor[i], corte[i] = mejor[i - 1], (i - 1, False)  # la letra i queda sin palabra
        for largo in range(1, min(_LARGO_MAXIMO, i) + 1):
            trozo = letras[i - largo:i]
            if largo == 1:
                peso = .3 if trozo in _LETRAS_SUELTAS else None
            elif trozo in PALABRAS:
                peso = largo * (.6 if largo == 2 else 1.0)
            else:
                peso = None
            if peso is not None and mejor[i - largo] + peso > mejor[i]:
                mejor[i], corte[i] = mejor[i - largo] + peso, (i - largo, True)
    trozos, i, suelto = [], n, ""
    while i > 0:
        j, es_palabra = corte[i]
        if es_palabra:
            if suelto:
                trozos.append(suelto)
                suelto = ""
            trozos.append(letras[j:i])
        else:
            suelto = letras[j:i] + suelto
        i = j
    if suelto:
        trozos.append(suelto)
    return mejor[n] / n, trozos[::-1]


def pares_de_letras(texto: str) -> float:
    """0 a 1: qué tan naturales son las parejas de letras (en español «QU» es normal y «QK» no)."""
    normal = normalizar(texto)
    palabras = normal.split()
    con_espacios = len(palabras) > 1 and max(map(len, palabras)) < 16
    if con_espacios:
        trozos, (bueno, malo) = [f"^{p}$" for p in palabras], (-2.3, -4.6)
    else:
        trozos, (bueno, malo) = [normal.replace(" ", "")], (-2.8, -4.8)
    valores = [BIGRAMAS.get(a + b, -9.0) for t in trozos for a, b in zip(t, t[1:])]
    if not valores:
        return 0.0
    promedio = sum(valores) / len(valores)
    return min(max((promedio - malo) / (bueno - malo), 0.0), 1.0)


def parecido_espanol(texto: str) -> float:
    """Cuánto se parece a español (0 a 1): palabras conocidas y parejas de letras naturales."""
    letras = solo_letras(texto)
    if not letras:
        return 0.0
    cobertura, _ = segmentar(letras)
    return .55 * min(cobertura, 1.0) + .45 * pares_de_letras(texto)


def legible(texto: str) -> str:
    """Si el texto viene sin espacios (cerca, grupos de cinco), lo separa en palabras.

    Solo lo separa si casi todo queda en palabras conocidas; si no, lo deja como estaba
    (un nombre propio o una palabra rara no deben quedar partidos en trozos).
    """
    palabras = texto.split()
    if len(palabras) > 1 and sum(p in PALABRAS for p in palabras) >= len(palabras) / 2:
        return texto
    letras = solo_letras(texto)
    cobertura, trozos = segmentar(letras)
    if len(letras) < 8 or cobertura < .7:
        return texto
    return " ".join(trozos)


# ---------------------------------------------------------------------------
# Resultado del análisis
# ---------------------------------------------------------------------------

@dataclass
class Hallazgo:
    tipo: str | None                 # clave de CIFRADOS, "sin_cifrar" o None si no se pudo
    mensaje: str = ""                # el texto descifrado, legible
    detalle: str = ""                # p. ej. «desplazamiento 4», «clave WATSON», «3 rieles»
    observaciones: list[str] = field(default_factory=list)
    seguro: bool = False             # True si el método no deja dudas (Morse, Bacon, Polibio, bailarines)
    pedir_clave: bool = False        # parece Vigenère y no se encontró la clave

    @property
    def nombre(self) -> str:
        if self.tipo in CIFRADOS:
            return CIFRADOS[self.tipo]["nombre"]
        return "sin cifrar" if self.tipo == "sin_cifrar" else "desconocido"


VENTAJA_TEXTO = .08  # si el texto tal cual ya es español, no se «descifra»


def umbral(letras: int) -> float:
    """Parecido mínimo para dar por bueno un descifrado. Un texto corto se parece a español por
    casualidad con más facilidad (hay 27 desplazamientos de César para probar), así que se exige más."""
    if letras < 8:
        return .78
    return .66 if letras < 12 else .6

# Mucha gente cifra a mano con el alfabeto inglés de 26 letras (sin Ñ): también se prueba
ALFABETO_26 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _sustituir(texto: str, alfabeto: str, cambio) -> str:
    """Aplica cambio(posición) a cada letra del alfabeto dado; lo demás queda igual."""
    return "".join(alfabeto[cambio(alfabeto.index(c)) % len(alfabeto)] if c in alfabeto else c for c in texto)


def cesar_26(texto: str, n: int) -> str:
    return _sustituir(texto, ALFABETO_26, lambda i: i - n)


def atbash_26(texto: str) -> str:
    return _sustituir(texto, ALFABETO_26, lambda i: 25 - i)


def vigenere_26(texto: str, clave: str) -> str:
    clave = [ALFABETO_26.index(c) for c in clave if c in ALFABETO_26]
    if not clave:
        return texto
    resultado, j = [], 0
    for c in texto:
        if c in ALFABETO_26:
            resultado.append(ALFABETO_26[(ALFABETO_26.index(c) - clave[j % len(clave)]) % 26])
            j += 1
        else:
            resultado.append(c)
    return "".join(resultado)


_MORSE = re.compile(r"^[.\-/|\s]+$")
_BACON = re.compile(r"^[ABab/|\s]+$")
_POLIBIO = re.compile(r"^[\d/|\s]+$")


def _normalizar_signos(texto: str) -> str:
    texto = texto.strip().strip("«»\"“”'")
    for raya in "—–_−":
        texto = texto.replace(raya, "-")
    for punto in "·•∙":
        texto = texto.replace(punto, ".")
    return texto


def _palabras_de_simbolos(texto: str) -> list[list[str]]:
    """Separa en palabras (por / o |, o por dos espacios) y en grupos de símbolos."""
    if "/" in texto or "|" in texto:
        palabras = re.split(r"[/|]", texto)
    elif re.search(r"\s{2,}", texto.strip()):
        palabras = re.split(r"\s{2,}", texto.strip())
    else:
        palabras = [texto]
    return [p.split() for p in palabras if p.split()]


def _morse(texto: str) -> str | None:
    if not _MORSE.match(texto) or texto.count(".") + texto.count("-") < 3:
        return None
    palabras = _palabras_de_simbolos(texto)
    try:
        return " ".join("".join(cifrados.MORSE_INV[g] for g in p) for p in palabras)
    except KeyError:
        return None


def _bacon(texto: str) -> str | None:
    if not _BACON.match(texto):
        return None
    resultado = []
    for palabra in _palabras_de_simbolos(texto.upper()):
        seguido = "".join(palabra)
        if len(seguido) % 5 or not seguido:
            return None
        letras = []
        for i in range(0, len(seguido), 5):
            valor = int(seguido[i:i + 5].replace("A", "0").replace("B", "1"), 2)
            if valor >= len(ALFABETO):
                return None
            letras.append(ALFABETO[valor])
        resultado.append("".join(letras))
    return " ".join(resultado) if resultado and sum(map(len, resultado)) >= 2 else None


def _polibio(texto: str) -> str | None:
    if not _POLIBIO.match(texto):
        return None
    resultado = []
    for palabra in _palabras_de_simbolos(texto):
        seguido = "".join(palabra)
        if len(seguido) % 2 or not seguido:
            return None
        letras = []
        for i in range(0, len(seguido), 2):
            fila, columna = int(seguido[i]), int(seguido[i + 1])
            indice = (fila - 1) * 5 + columna - 1
            if not (1 <= fila <= 6 and 1 <= columna <= 5) or indice >= len(ALFABETO):
                return None
            letras.append(ALFABETO[indice])
        resultado.append("".join(letras))
    return " ".join(resultado) if resultado and sum(map(len, resultado)) >= 2 else None


def _letra_mas_repetida(texto: str) -> tuple[str, int]:
    conteo = Counter(solo_letras(texto))
    return conteo.most_common(1)[0] if conteo else ("", 0)


def _tercera(texto: str) -> str | None:
    """«El Gloria Scott»: palabras de relleno y el mensaje en una de cada tres."""
    palabras = normalizar(texto).split()
    if len(palabras) < 6:
        return None
    relleno = {normalizar(p) for p in cifrados.RELLENO}
    otras = [p for i, p in enumerate(palabras) if i % 3 != 2]
    if sum(p in relleno for p in otras) < .75 * len(otras):
        return None
    return " ".join(palabras[2::3])


def analizar(texto: str, claves_extra: list[str] | None = None, clave_dada: str | None = None) -> Hallazgo:
    """Descubre qué cifrado usó el visitante y qué dice. Nunca inventa: si no hay certeza, lo dice.

    claves_extra son palabras que podrían ser la clave de un Vigenère (de la conversación); clave_dada
    es la que el visitante dijo explícitamente («la clave es…»).
    """
    crudo = _normalizar_signos(texto)
    if not crudo:
        return Hallazgo(None, observaciones=["El papel está en blanco."])

    for tipo, funcion, observacion in (
        ("morse", _morse, "Solo hay puntos y rayas: es el alfabeto de los telegrafistas."),
        ("bacon", _bacon, "Solo aparecen dos letras, A y B, siempre en grupos de cinco: el método de Bacon."),
        ("polibio", _polibio, "Son pares de cifras y ninguna pasa de 6: una rejilla de Polibio de seis filas."),
    ):
        resultado = funcion(crudo)
        if resultado:
            cantidad = len(solo_letras(resultado))
            return Hallazgo(tipo, legible(resultado), seguro=True,
                            observaciones=[observacion, f"El mensaje tiene {cantidad} letras."])

    normal = normalizar(crudo)
    letras = solo_letras(crudo)
    if len(letras) < 6:
        if normal in PALABRAS or (len(normal.split()) > 1 and tiene_palabras(normal)):
            return Hallazgo("sin_cifrar", normal, observaciones=["Se lee tal cual: este mensaje no está cifrado."])
        return Hallazgo(None, observaciones=["Es demasiado breve para sacar conclusiones: con tan pocas letras, "
                                             "cualquier método daría algo con sentido."])

    oculto = _tercera(crudo)
    if oculto:
        return Hallazgo("tercera", oculto, detalle="una de cada tres palabras", seguro=True, observaciones=[
            "Las palabras no guardan relación entre sí: nadie escribe así, salvo para esconder algo.",
            "Leyendo solo una de cada tres, empezando por la tercera, aparece el mensaje.",
        ])

    candidatos: list[tuple[float, str, str, str]] = []  # (puntaje, tipo, texto, detalle)
    candidatos.append((parecido_espanol(normal), "sin_cifrar", normal, ""))
    candidatos.append((parecido_espanol(normal[::-1]), "espejo", normal[::-1], ""))
    candidatos.append((parecido_espanol(cifrados.atbash(normal)), "atbash", cifrados.atbash(normal), ""))
    for n in range(1, len(ALFABETO)):
        texto_n = cifrados.cesar_descifrar(normal, n)
        candidatos.append((parecido_espanol(texto_n), "cesar", texto_n, f"desplazamiento {n}"))
    sin_enie = "Ñ" not in normal  # con Ñ en el mensaje, el alfabeto tiene que ser el español
    if sin_enie:
        for n in range(1, 26):
            texto_n = cesar_26(normal, n)
            candidatos.append((parecido_espanol(texto_n), "cesar", texto_n, f"desplazamiento {n}, alfabeto sin Ñ"))
        candidatos.append((parecido_espanol(atbash_26(normal)), "atbash", atbash_26(normal), "alfabeto sin Ñ"))
    for rieles in range(2, 6):
        if len(letras) > rieles:
            texto_r = cifrados.cerca_descifrar(letras, rieles)
            candidatos.append((parecido_espanol(texto_r), "cerca", texto_r, f"{rieles} rieles"))
    claves = [solo_letras(clave_dada)] if clave_dada and len(solo_letras(clave_dada)) >= 2 else []
    # Una clave que no alcanza a repetirse puede «descifrar» cualquier cosa, así que con las palabras de la
    # conversación (muchas) se exige que se repita; con las pocas claves de siempre basta un poco de margen.
    for clave, margen in [(c, 2.0) for c in claves_extra or []] + [(c, 1.0) for c in CLAVES_VIGENERE]:
        clave = solo_letras(clave)
        if 2 <= len(clave) <= 20 and clave not in claves and len(letras) >= margen * len(clave) + 3:
            claves.append(clave)
    for clave in claves:
        texto_v = cifrados.vigenere_descifrar(normal, clave)
        # una clave de una sola letra repetida es un César: ya está probado
        if len(set(clave)) > 1:
            candidatos.append((parecido_espanol(texto_v), "vigenere", texto_v, f"clave «{clave}»"))
            if sin_enie and "Ñ" not in clave:
                texto_v = vigenere_26(normal, clave)
                candidatos.append((parecido_espanol(texto_v), "vigenere", texto_v, f"clave «{clave}», alfabeto sin Ñ"))

    candidatos = [c for c in candidatos if c[1] == "sin_cifrar" or tiene_palabras(c[2])]
    candidatos.sort(key=lambda c: c[0], reverse=True)
    if not candidatos:
        return _sin_resultado(normal, letras)
    puntaje, tipo, resultado, detalle = candidatos[0]
    puntaje_texto = candidatos_por_tipo(candidatos, "sin_cifrar")
    minimo = umbral(len(letras))
    if puntaje_texto >= minimo and puntaje_texto >= puntaje - VENTAJA_TEXTO:
        return Hallazgo("sin_cifrar", normal, observaciones=["Se lee tal cual: este mensaje no está cifrado."])
    if puntaje < minimo:
        return _sin_resultado(normal, letras)
    return Hallazgo(tipo, legible(resultado), detalle=detalle,
                    observaciones=_observaciones(tipo, normal, resultado, detalle, claves_extra or [], clave_dada))


def tiene_palabras(texto: str) -> bool:
    """Un descifrado de verdad tiene palabras reconocibles, no solo letras con buen aspecto."""
    palabras = [p for p in texto.split() if len(p) >= 2]
    if len(palabras) >= 2:
        conocidas = [p for p in palabras if p in PALABRAS]
        return len(conocidas) * 2 >= len(palabras) and any(len(p) >= 3 for p in conocidas)
    cobertura, trozos = segmentar(solo_letras(texto))  # sin espacios (cerca) o una sola palabra
    return cobertura >= .6 and any(len(t) >= 3 and t in PALABRAS for t in trozos)


def candidatos_por_tipo(candidatos, tipo: str) -> float:
    return max((c[0] for c in candidatos if c[1] == tipo), default=0.0)


def indice_coincidencia(letras: str) -> float:
    """Probabilidad de que dos letras al azar sean iguales: ~0,07 en español, ~0,04 en un Vigenère."""
    n = len(letras)
    if n < 2:
        return 0.0
    return sum(k * (k - 1) for k in Counter(letras).values()) / (n * (n - 1))


def _sin_resultado(normal: str, letras: str) -> Hallazgo:
    letra, veces = _letra_mas_repetida(normal)
    observaciones = [f"El mensaje tiene {len(letras)} letras; la más repetida es la {letra} ({veces} veces)."]
    pedir_clave = len(letras) >= 12 and indice_coincidencia(letras) < .055
    if pedir_clave:
        observaciones.append("Las letras están demasiado repartidas para una sustitución simple: huele a una "
                             "palabra clave, como en el cifrado de Vigenère.")
    else:
        observaciones.append("No coincide con ninguno de los métodos que conozco.")
    return Hallazgo(None, observaciones=observaciones, pedir_clave=pedir_clave)


def _observaciones(tipo: str, cifrado: str, descifrado: str, detalle: str, claves_extra: list[str],
                   clave_dada: str | None = None) -> list[str]:
    letra, veces = _letra_mas_repetida(cifrado)
    ingles = "sin Ñ" in detalle
    nota_alfabeto = (["Usó el alfabeto inglés, sin la Ñ: un detalle que delata a quien aprendió el truco en "
                      "un libro extranjero."] if ingles else [])
    if tipo == "cesar":
        n = int(re.search(r"\d+", detalle).group())
        original = (cesar_26(letra, n) if ingles else cifrados.cesar_descifrar(letra, n)) if letra else ""
        return [f"La letra más repetida del mensaje es la {letra} ({veces} veces).",
                f"Si esa {letra} fuese en realidad una {original}, todas las letras estarían corridas el mismo "
                f"número de posiciones ({n}): un truco digno de Julio César."] + nota_alfabeto
    if tipo == "atbash":
        espejo = atbash_26(letra) if ingles else cifrados.atbash(letra)
        return [f"La letra más repetida es la {letra} ({veces} veces), que en el alfabeto al revés corresponde "
                f"a la {espejo}.",
                "El alfabeto se ha doblado sobre sí mismo: la A vale Z, la B vale Y. Es el Atbash de los escribas "
                "hebreos."] + nota_alfabeto
    if tipo == "espejo":
        return ["No falta ni sobra ninguna letra; leído de atrás hacia adelante, el texto cobra sentido."]
    if tipo == "cerca":
        return ["Están todas las letras de un mensaje en español, solo que desordenadas.",
                f"Escritas en zigzag sobre {detalle.split()[0]} líneas, como los listones de una cerca, se ordenan solas."]
    if tipo == "vigenere":
        clave = detalle.split("«")[1].split("»")[0]
        origen = ("una palabra que apareció en nuestra conversación"
                  if any(solo_letras(c) == clave for c in claves_extra) else "una de las claves que suelo sospechar")
        if clave_dada and solo_letras(clave_dada) == clave:
            origen = "la clave que usted mismo me dio"
        return ["La misma letra no siempre se transforma igual: hay una palabra clave de por medio.",
                f"Probé con «{clave}», {origen}, y el mensaje se rindió."] + nota_alfabeto
    return []


def claves_de_conversacion(textos: list[str], maximo: int = 150) -> list[str]:
    """Palabras de la conversación que podrían servir de clave para un Vigenère."""
    vistas: list[str] = []
    for texto in reversed(textos):
        for palabra in normalizar(texto).split():
            if 3 <= len(palabra) <= 12 and palabra not in vistas:
                vistas.append(palabra)
                if len(vistas) >= maximo:
                    return vistas
    return vistas


# ---------------------------------------------------------------------------
# Cuándo un mensaje del chat es un desafío
# ---------------------------------------------------------------------------

_PEDIDO = re.compile(
    r"(descifr\w*|decodifi\w*|traduzc\w*|traduc\w*|mensaje\s+(?:cifrado|secreto|en\s+clave)|en\s+clave|"
    r"c[oó]digo\s+secreto)[^:«\"“\n]*[:«\"“\n]\s*(?P<mensaje>.+)$", re.IGNORECASE | re.DOTALL)
_CLAVE = re.compile(r"\bclave\b(?P<resto>.{0,60})", re.IGNORECASE | re.DOTALL)
_NO_CLAVE = {"ES", "ERA", "SERA", "LA", "EL", "UNA", "UN", "PALABRA", "MI", "SU", "DE", "QUE", "SECRETA", "USADA"}


def extraer_desafio(texto: str) -> str | None:
    """El mensaje cifrado dentro de lo que escribió el visitante, o None si no le pide descifrar nada."""
    coincidencia = _PEDIDO.search(texto)
    if coincidencia:
        mensaje = coincidencia.group("mensaje").strip().strip("«»\"“”'¿?¡! \n")
        if not _parece_simbolos(mensaje):
            mensaje = mensaje.rstrip(".").strip("«»\"“”' ")
        if len(solo_letras(mensaje)) >= 3 or _parece_simbolos(mensaje):
            return mensaje
    if _parece_simbolos(texto):
        return texto.strip()
    return None


def _parece_simbolos(texto: str) -> bool:
    """Morse, Bacon o Polibio escritos tal cual en el chat."""
    t = _normalizar_signos(texto)
    if _MORSE.match(t) and t.count(".") + t.count("-") >= 6 and len(t.split()) >= 3:
        return True
    if _BACON.match(t) and len(solo_letras(t)) >= 10 and len(solo_letras(t)) % 5 == 0 and len(t.split()) >= 2:
        return True
    return bool(_POLIBIO.match(t) and len(re.sub(r"\D", "", t)) >= 6 and len(t.split()) >= 3)


def extraer_clave(texto: str) -> str | None:
    """«La clave es LONDRES» → LONDRES."""
    coincidencia = _CLAVE.search(texto)
    if not coincidencia:
        return None
    for palabra in normalizar(coincidencia.group("resto")).split()[:5]:
        if palabra in ("NO", "NI"):
            return None
        if palabra not in _NO_CLAVE and len(palabra) >= 2:
            return palabra
    return None


# ---------------------------------------------------------------------------
# Cifrar por el visitante (para que desafíe a Holmes sin saber cifrar a mano)
# ---------------------------------------------------------------------------

@dataclass
class Desafio:
    cifrado: str                 # lo que se muestra y lo que analiza Holmes
    svg: str | None = None       # los bailarines se dibujan
    indices: list | None = None  # los bailarines, para descifrarlos sin ambigüedad


TIPOS_DESAFIO = ["ya_cifrado"] + list(CIFRADOS)
NOMBRES_DESAFIO = {"ya_cifrado": "Ya está cifrado (lo escribí yo)", **{t: d["nombre"] for t, d in CIFRADOS.items()}}


def cifrar_desafio(texto: str, tipo: str, clave: str = "", rng: random.Random | None = None) -> Desafio:
    """Cifra el mensaje del visitante con el método que eligió. «ya_cifrado» lo deja tal cual."""
    if tipo == "ya_cifrado":
        return Desafio(texto.strip())
    if not normalizar(texto):
        raise ValueError("El mensaje no tiene letras para cifrar.")
    rng = rng or random.Random()
    if tipo == "vigenere":
        palabra = solo_letras(clave) or rng.choice(CLAVES_VIGENERE)
        return Desafio(cifrados.vigenere_cifrar(texto, palabra))
    mensaje = cifrados.cifrar(texto, tipo, rng)
    if tipo == "bailarines":
        return Desafio(mensaje.cifrado, svg=mensaje.svg, indices=mensaje.clave["indices"])
    return Desafio(mensaje.cifrado)


def analizar_desafio(desafio: Desafio, claves_extra: list[str] | None = None,
                     clave_dada: str | None = None) -> Hallazgo:
    if desafio.indices:
        mensaje = cifrados.bailarines_descifrar([tuple(i) for i in desafio.indices])
        return Hallazgo("bailarines", mensaje, seguro=True, observaciones=[
            "Son mis viejos amigos, los bailarines de Ridling Thorpe: cada figura es una letra.",
            "Las que sostienen una bandera marcan el final de cada palabra.",
        ])
    return analizar(desafio.cifrado, claves_extra, clave_dada)


def es_mensaje_del_caso(hallazgo: Hallazgo, cifrado: str, pistas) -> int | None:
    """¿El visitante le pide a Holmes descifrar uno de los mensajes del caso? Así no se lo resuelve él."""
    for i, pista in enumerate(pistas):
        if pista.estado in ("resuelta", "rendida"):
            continue
        mismo_texto = solo_letras(cifrado) and solo_letras(cifrado) == solo_letras(pista.cifrado.cifrado)
        misma_solucion = hallazgo.mensaje and solo_letras(hallazgo.mensaje) == solo_letras(pista.cifrado.mensaje)
        mismos_signos = re.sub(r"\s", "", _normalizar_signos(cifrado)) == re.sub(r"\s", "", pista.cifrado.cifrado)
        if mismo_texto or misma_solucion or mismos_signos:
            return i
    return None


# ---------------------------------------------------------------------------
# Lo que se le cuenta a Holmes
# ---------------------------------------------------------------------------

def instruccion_para_holmes(hallazgo: Hallazgo, indice_caso: int | None = None) -> str:
    """Bloque [DESAFIO] para Gemini: el resultado exacto y las observaciones reales del análisis."""
    if indice_caso is not None:
        return ("[DESAFIO] El visitante te pide descifrar el mensaje cifrado número "
                f"{indice_caso + 1} de nuestro caso. NO lo descifres ni digas qué código es: eso le toca a él. "
                "Recházalo con elegancia y anímalo a resolverlo en tu libreta, donde puede pedirte pistas. [/DESAFIO]")
    observaciones = " ".join(hallazgo.observaciones)
    if hallazgo.tipo == "sin_cifrar":
        return (f"[DESAFIO] El visitante te entrega un mensaje, pero no está cifrado: se lee tal cual "
                f"«{hallazgo.mensaje}». Señálalo con ironía y comenta lo que dice. [/DESAFIO]")
    if hallazgo.tipo is None:
        pedir = (" Pídele la palabra clave: puede decírtela en el chat («la clave es…»)." if hallazgo.pedir_clave
                 else " Pídele que revise el mensaje o que te dé alguna pista sobre el método.")
        return ("[DESAFIO] El visitante te desafía con un mensaje cifrado y la aplicación NO pudo descifrarlo. "
                f"Observaciones reales: {observaciones} No inventes una traducción ni adivines el código. "
                f"Reconoce, con orgullo herido, que el mensaje se te resiste por ahora.{pedir} [/DESAFIO]")
    detalle = f" ({hallazgo.detalle})" if hallazgo.detalle else ""
    return ("[DESAFIO] El visitante te desafía con un mensaje cifrado. La aplicación lo analizó por ti y el "
            f"resultado es exacto, no lo contradigas. Código: {hallazgo.nombre}{detalle}. Dice: «{hallazgo.mensaje}». "
            f"Observaciones reales que puedes contar como deducciones tuyas: {observaciones} "
            "Cuenta brevemente, con tu voz, cómo lo descifraste (una o dos observaciones), revela lo que dice y "
            "coméntalo con ingenio. La aplicación mostrará la solución bajo tu respuesta. [/DESAFIO]")
