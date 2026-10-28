"""Documentación de las solicitudes de sucursal en los tests: para enviar a evaluación hay que adjuntar lo
que pide la línea, igual que en el portal."""
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def adjuntar_pedidos(client, headers, sid: str) -> list[str]:
    """Adjunta un archivo por cada documento obligatorio que pide la línea. Devuelve los tipos adjuntados."""
    d = client.get(f"/api/creditos/solicitudes/{sid}/documentos", headers=headers).json()
    tipos = [p["tipo"] for p in d["pedidos"] if p["obligatorio"]]
    for t in tipos:
        r = client.post(f"/api/creditos/solicitudes/{sid}/documentos", headers=headers,
                        files={"archivo": (f"{t.lower()}.png", PNG, "image/png")}, data={"tipo": t})
        assert r.status_code == 201, r.text
    return tipos
