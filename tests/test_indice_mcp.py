"""Pruebas del servidor MCP con un texto de ejemplo (escrito para la prueba)."""

import asyncio

from fastmcp import Client

from indice_mcp import servidor

TEXTO = """The violin lay upon the table beside a slipper full of tobacco.

Holmes examined the muddy boots and declared that the visitor had walked from the
station in the rain.

A note written in red ink spoke of a speckled band and a whistle in the night.
"""


def test_busqueda_encuentra_el_fragmento(tmp_path):
    (tmp_path / "ejemplo.txt").write_text(TEXTO, encoding="utf-8")
    servidor._indice.cache_clear()
    resultados = servidor.buscar("speckled band whistle", carpeta=str(tmp_path))
    assert resultados and "speckled band" in resultados[0]["texto"]
    assert servidor.buscar("", carpeta=str(tmp_path)) == []
    servidor._indice.cache_clear()


def test_herramientas_por_protocolo_mcp(tmp_path, monkeypatch):
    (tmp_path / "ejemplo.txt").write_text(TEXTO, encoding="utf-8")
    monkeypatch.setattr(servidor, "CARPETA_TEXTOS", tmp_path)
    servidor._indice.cache_clear()

    async def probar():
        async with Client(servidor.mcp) as cliente:
            herramientas = {h.name for h in await cliente.list_tools()}
            assert {"buscar_en_mis_archivos", "listar_relatos"} <= herramientas
            relatos = await cliente.call_tool("listar_relatos", {})
            busqueda = await cliente.call_tool("buscar_en_mis_archivos", {"consulta": "muddy boots rain"})
            return relatos.content[0].text, busqueda.content[0].text

    relatos, busqueda = asyncio.run(probar())
    assert "Ejemplo" in relatos
    assert "muddy boots" in busqueda
    servidor._indice.cache_clear()
