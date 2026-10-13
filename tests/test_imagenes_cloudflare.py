"""Pruebas del generador de imágenes de Cloudflare con un servidor simulado (sin red)."""

import base64
import json

import httpx
import pytest

from juego import imagenes_cloudflare as cf
from juego import motor

JPEG = b"\xff\xd8\xff\xe0" + b"imagen-de-prueba"


def cliente_simulado(respuestas: list[httpx.Response], pedidos: list):
    def manejar(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        return respuestas.pop(0)
    return httpx.Client(transport=httpx.MockTransport(manejar))


def exito() -> httpx.Response:
    cuerpo = {"result": {"image": base64.b64encode(JPEG).decode()}, "success": True, "errors": []}
    return httpx.Response(200, json=cuerpo)


def test_genera_la_imagen_y_envia_lo_correcto():
    pedidos = []
    datos, tipo = cf.generar("cuenta123", "token-secreto", "a foggy alley" * 300,
                             cliente=cliente_simulado([exito()], pedidos))
    assert datos == JPEG and tipo == "image/jpeg"
    pedido = pedidos[0]
    assert pedido.url.path.endswith("/accounts/cuenta123/ai/run/@cf/black-forest-labs/flux-1-schnell")
    assert pedido.headers["Authorization"] == "Bearer token-secreto"
    assert len(json.loads(pedido.content)["prompt"]) == cf.LARGO_MAXIMO_PROMPT


def test_reintenta_si_cloudflare_falla_por_su_lado():
    pedidos = []
    cliente = cliente_simulado([httpx.Response(503, json={"errors": []}), exito()], pedidos)
    assert cf.generar("c", "t", "x", cliente=cliente, esperas=(0,))[0] == JPEG
    assert len(pedidos) == 2


@pytest.mark.parametrize("codigo", [401, 429])
def test_errores_definitivos(codigo):
    respuesta = httpx.Response(codigo, json={"errors": [{"message": "no permitido"}]})
    with pytest.raises(cf.ErrorCloudflare) as info:
        cf.generar("c", "t", "x", cliente=cliente_simulado([respuesta], []))
    assert info.value.code == codigo and info.value.es_definitivo
    assert "no permitido" in str(info.value)


def test_el_motor_elige_cloudflare_si_hay_credenciales(monkeypatch):
    config = motor.Configuracion(api_key="x", cloudflare_account_id="c", cloudflare_api_token="t")
    assert config.usa_cloudflare
    assert not motor.Configuracion(api_key="x").usa_cloudflare
    assert not motor.Configuracion(api_key="x", cloudflare_account_id="c", cloudflare_api_token="t",
                                   proveedor_imagenes="gemini").usa_cloudflare

    m = motor.Motor(config)
    monkeypatch.setattr(cf, "generar", lambda *a, **k: (JPEG, "image/jpeg"))
    assert m.generar_imagen("a study") == (JPEG, "image/jpeg")


def test_cuota_agotada_cuenta_como_imagen_no_disponible(monkeypatch):
    m = motor.Motor(motor.Configuracion(api_key="x", cloudflare_account_id="c", cloudflare_api_token="t"))

    def agotada(*a, **k):
        raise cf.ErrorCloudflare(429, "daily free allocation exceeded")

    monkeypatch.setattr(cf, "generar", agotada)
    with pytest.raises(cf.ErrorCloudflare) as info:
        m.generar_imagen("a study")
    assert motor.imagen_no_disponible(info.value)
    assert not motor.imagen_no_disponible(cf.ErrorCloudflare(503, "temporal"))
