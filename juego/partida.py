"""
Reglas del juego que no dependen de la interfaz: etiquetas que escribe Holmes,
instrucción de sistema de cada turno, momentos en que aparecen las pistas
cifradas y puntaje. Separado de app.py para poder probarlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from juego.caso import Caso, caso_para_holmes
from juego.cifrados import MensajeCifrado, respuestas_coinciden, tipo_por_nombre

MAX_IMAGENES_POR_CASO = 3
REVELAR_PISTA_TRAS = [2, 5]  # mensajes del visitante dentro del caso para cada pista cifrada
PUNTOS_CULPABLE = 200
PUNTOS_MOVIL = 100

_IMAGEN = re.compile(r"\[\[\s*IMAGEN\s*:\s*(.+?)\s*\]\]", re.IGNORECASE | re.DOTALL)
_MODO = re.compile(r"\[\[\s*MODO\s*:\s*([AB])\s*\]\]", re.IGNORECASE)
_RESTOS = re.compile(r"\[/?(CASO SECRETO|PISTA CIFRADA|AYUDA CIFRADO|RESULTADO|INICIO CASO|CONTEXTO)\]?",
                     re.IGNORECASE)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class Etiquetas:
    texto: str
    modo: str | None = None
    imagenes: list[str] = field(default_factory=list)


def extraer_etiquetas(respuesta: str) -> Etiquetas:
    """Separa el texto visible de las órdenes que Holmes deja para la aplicación."""
    imagenes = _IMAGEN.findall(respuesta)
    modo = _MODO.search(respuesta)
    texto = _MODO.sub("", _IMAGEN.sub("", respuesta))
    texto = _RESTOS.sub("", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return Etiquetas(texto=texto, modo=modo.group(1).upper() if modo else None, imagenes=imagenes)


def contexto_hora(ahora: datetime) -> str:
    return f"[CONTEXTO] Hora local del visitante: {ahora:%H:%M} ({DIAS[ahora.weekday()]})"


@dataclass
class PistaCifrada:
    cifrado: MensajeCifrado
    soporte: str
    estado: str = "oculta"   # oculta → activa → resuelta / rendida
    ayudas: int = 0
    fallos: int = 0
    tipo_ok: bool = False
    puntos: int = 0

    def proponer(self, nombre_tipo: str, mensaje: str) -> tuple[bool, bool]:
        """Revisa una propuesta. Devuelve (¿tipo correcto?, ¿mensaje correcto?)."""
        tipo_bien = tipo_por_nombre(nombre_tipo) == self.cifrado.tipo
        mensaje_bien = respuestas_coinciden(mensaje, self.cifrado.mensaje)
        self.tipo_ok = self.tipo_ok or tipo_bien
        if self.tipo_ok and mensaje_bien:
            self.estado = "resuelta"
            self.puntos = max(10, 100 - 20 * self.ayudas - 10 * self.fallos)
        else:
            self.fallos += 1
        return tipo_bien, mensaje_bien

    def siguiente_ayuda(self) -> str | None:
        if self.ayudas >= len(self.cifrado.pistas):
            return None
        self.ayudas += 1
        return self.cifrado.pistas[self.ayudas - 1]

    def rendirse(self) -> None:
        self.estado = "rendida"
        self.puntos = 0


def pista_a_revelar(pistas: list[PistaCifrada], mensajes_en_caso: int) -> int | None:
    """Índice de la pista cifrada que debe aparecer ahora, si corresponde."""
    for i, pista in enumerate(pistas):
        if pista.estado != "oculta":
            continue
        anterior_cerrada = i == 0 or pistas[i - 1].estado in ("resuelta", "rendida")
        umbral = REVELAR_PISTA_TRAS[min(i, len(REVELAR_PISTA_TRAS) - 1)]
        if anterior_cerrada and mensajes_en_caso >= umbral:
            return i
        return None
    return None


def instruccion_sistema(prompt: str, modo: str | None, caso: Caso | None,
                        pistas: list[PistaCifrada], terminado: bool, imagenes_usadas: int) -> str:
    partes = [prompt, "\n\n---\n\n# ESTADO ACTUAL (información de la aplicación)"]
    if modo is None:
        partes.append("El visitante aún no ha elegido un camino.")
    elif modo == "A":
        partes.append("Modo A: el visitante te trae un caso. No solicites imágenes.")
    else:
        partes.append("Modo B: el visitante te ayuda con tu caso.")
    if modo == "B" and caso is not None:
        estado = "TERMINADO: la acusación ya se hizo; puedes hablar de la solución." if terminado \
            else "EN CURSO: no reveles la solución."
        partes.append(f"[CASO SECRETO]\nEstado del caso: {estado}\n{caso_para_holmes(caso)}\n[/CASO SECRETO]")
        for i, p in enumerate(pistas, 1):
            if p.estado == "oculta":
                continue
            linea = f"Mensaje cifrado {i} ({p.soporte}): {p.estado}"
            if p.estado in ("resuelta", "rendida"):
                linea += f"; decía «{p.cifrado.mensaje}» y estaba en {p.cifrado.nombre}"
            partes.append(linea)
        restantes = MAX_IMAGENES_POR_CASO - imagenes_usadas
        partes.append(f"Imágenes disponibles para este caso: {max(restantes, 0)}.")
    return "\n".join(partes)
