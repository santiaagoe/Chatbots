"""
Generador de imágenes gratuito: Cloudflare Workers AI.

El nivel gratuito de la API de Gemini no incluye imágenes. Cloudflare
Workers AI sí ofrece una cuota diaria gratuita (10.000 «neuronas» al día),
que alcanza para más de un centenar de imágenes con FLUX.1 [schnell].

Se necesita una cuenta gratuita de Cloudflare y dos datos en el .env:
    CLOUDFLARE_ACCOUNT_ID=...
    CLOUDFLARE_API_TOKEN=...   (token con permiso «Workers AI»)
"""

from __future__ import annotations

import base64
import time

import httpx

MODELO_POR_DEFECTO = "@cf/black-forest-labs/flux-1-schnell"
URL = "https://api.cloudflare.com/client/v4/accounts/{cuenta}/ai/run/{modelo}"
LARGO_MAXIMO_PROMPT = 2048


class ErrorCloudflare(Exception):
    def __init__(self, codigo: int, mensaje: str):
        super().__init__(f"Cloudflare {codigo}: {mensaje}")
        self.code = codigo
        self.mensaje = mensaje

    @property
    def es_definitivo(self) -> bool:
        """Credenciales malas o cuota diaria agotada: no sirve reintentar en esta sesión."""
        return self.code in (400, 401, 403, 429)


def _tipo_imagen(datos: bytes) -> str:
    if datos.startswith(b"\x89PNG"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def generar(cuenta: str, token: str, descripcion: str, modelo: str = MODELO_POR_DEFECTO,
            cliente: httpx.Client | None = None, esperas: tuple[float, ...] = (2,)) -> tuple[bytes, str]:
    """Devuelve (bytes, tipo MIME). Reintenta una vez si Cloudflare falla por su lado (5xx)."""
    cliente = cliente or httpx.Client(timeout=90)
    url = URL.format(cuenta=cuenta, modelo=modelo)
    cuerpo = {"prompt": descripcion[:LARGO_MAXIMO_PROMPT], "steps": 6}
    cabeceras = {"Authorization": f"Bearer {token}"}

    for intento in range(len(esperas) + 1):
        respuesta = cliente.post(url, json=cuerpo, headers=cabeceras)
        if respuesta.status_code >= 500 and intento < len(esperas):
            time.sleep(esperas[intento])
            continue
        break

    if respuesta.status_code != 200:
        try:
            errores = respuesta.json().get("errors") or []
            mensaje = "; ".join(str(e.get("message", e)) for e in errores) or respuesta.text[:300]
        except ValueError:
            mensaje = respuesta.text[:300]
        raise ErrorCloudflare(respuesta.status_code, mensaje)

    datos = respuesta.json()
    resultado = datos.get("result", datos) if isinstance(datos, dict) else {}
    imagen_b64 = resultado.get("image") if isinstance(resultado, dict) else None
    if not imagen_b64:
        raise ErrorCloudflare(502, "La respuesta no trae ninguna imagen.")
    imagen = base64.b64decode(imagen_b64)
    return imagen, _tipo_imagen(imagen)
