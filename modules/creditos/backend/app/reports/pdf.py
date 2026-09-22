"""Generación de reportes en PDF (ReportLab, sin dependencias de sistema).

Reemplaza la reportería VFP (FoxyPreviewer / pdf3.prg). Primer reporte: el
recibo de cobranza (equivalente a rpt225050000recibo del sistema original).
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

AZUL = colors.HexColor("#14428a")


def _money(v) -> str:
    return f"$ {Decimal(v):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _encabezado(c, w, h, subtitulo: str):
    """Franja institucional superior. Devuelve la Y inicial del contenido."""
    c.setFillColor(AZUL)
    c.rect(0, h - 20 * mm, w, 20 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, h - 13 * mm, "C.C. y P.P. — Ca.Pre.S.Ca.")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 20 * mm, h - 13 * mm, subtitulo)
    c.setFillColor(colors.black)
    return h - 30 * mm


def _pie(c):
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(20 * mm, 12 * mm,
                 "Documento generado por el sistema CCyPP (migración desde Visual FoxPro).")
    c.setFillColor(colors.black)


def tabla_pdf(titulo: str, subtitulo: str, columnas, filas, anchos=None,
              totales_fila=None) -> bytes:
    """Reporte tabular genérico. `columnas`=[(nombre, alineación)], filas=list[list].

    alineación: 'l' izquierda, 'r' derecha. `totales_fila`: lista opcional final.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = _encabezado(c, w, h, subtitulo)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, titulo)
    y -= 8 * mm

    n = len(columnas)
    if not anchos:
        anchos = [(w - 40 * mm) / n] * n
    xs, acc = [], 20 * mm
    for a in anchos:
        xs.append(acc)
        acc += a

    def dibujar_fila(vals, x_off_bold=False):
        c.setFont("Helvetica-Bold" if x_off_bold else "Helvetica", 8)
        for (nombre, al), x, a, v in zip(columnas, xs, anchos, vals):
            if al == "r":
                c.drawRightString(x + a - 2, y, str(v))
            else:
                c.drawString(x, y, str(v)[:60])

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(AZUL)
    for (nombre, al), x, a in zip(columnas, xs, anchos):
        if al == "r":
            c.drawRightString(x + a - 2, y, nombre)
        else:
            c.drawString(x, y, nombre)
    c.setFillColor(colors.black)
    y -= 2 * mm
    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 5 * mm

    for fila in filas:
        if y < 25 * mm:  # salto de página
            _pie(c)
            c.showPage()
            y = _encabezado(c, w, h, subtitulo)
            y -= 5 * mm
        dibujar_fila(fila)
        y -= 5 * mm

    if totales_fila:
        y -= 1 * mm
        c.line(20 * mm, y, w - 20 * mm, y)
        y -= 5 * mm
        dibujar_fila(totales_fila, x_off_bold=True)

    _pie(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def pendientes_cobro_pdf(data) -> bytes:
    """Listado de cuotas pendientes de cobro con mora."""
    filas = [[i["cliente"], f"#{i['credito_id']}-{i['cuota_numero']}",
              str(i["vencimiento"]), str(i["dias_mora"]),
              _money(i["importe_cuota"]), _money(i["mora"]), _money(i["total"])]
             for i in data["items"]]
    cols = [("Cliente", "l"), ("Crédito/Cuota", "l"), ("Vto", "l"),
            ("Días", "r"), ("Cuota", "r"), ("Mora", "r"), ("Total", "r")]
    anchos = [55 * mm, 28 * mm, 22 * mm, 12 * mm, 24 * mm, 20 * mm, 24 * mm]
    tot = ["", "", "", "TOTAL", _money(data["total_cuota"]),
           _money(data["total_mora"]), _money(data["total"])]
    return tabla_pdf(f"Pendientes de cobro al {data['fecha_corte']}",
                     "Caja", cols, filas, anchos, totales_fila=tot)


def cartera_pdf(data) -> bytes:
    """Informe de cartera de créditos por línea."""
    filas = [[l["linea"], str(l["cartera"]), str(l["cantidad"]),
              _money(l["capital_otorgado"]), _money(l["saldo"])]
             for l in data["por_linea"]]
    cols = [("Línea", "l"), ("Cartera", "r"), ("Cantidad", "r"),
            ("Capital otorgado", "r"), ("Saldo", "r")]
    anchos = [70 * mm, 20 * mm, 22 * mm, 32 * mm, 32 * mm]
    tot = ["TOTAL", "", str(data["creditos_activos"]),
           _money(data["capital_otorgado_total"]), _money(data["saldo_total"])]
    return tabla_pdf("Cartera de créditos por línea", "Créditos", cols, filas, anchos,
                     totales_fila=tot)


def por_cartera_pdf(data) -> bytes:
    """Resumen ejecutivo: cantidades y situación de créditos por cartera."""
    filas = [[f"{c['nombre']} ({c['cartera']})", str(c["activos"]), str(c["cancelados"]),
              _money(c["capital"]), _money(c["saldo"])]
             for c in data["por_cartera"]]
    cols = [("Cartera", "l"), ("Activos", "r"), ("Cancelados", "r"),
            ("Capital otorgado", "r"), ("Saldo (activos)", "r")]
    anchos = [66 * mm, 20 * mm, 24 * mm, 32 * mm, 34 * mm]
    t = data["total"]
    tot = ["TOTAL", str(t["activos"]), str(t["cancelados"]),
           _money(t["capital"]), _money(t["saldo"])]
    sub = "Créditos"
    if data.get("anomalias_saldo_negativo"):
        sub = f"Créditos — {data['anomalias_saldo_negativo']} crédito(s) con saldo negativo excluidos (H-023)"
    return tabla_pdf("Créditos por cartera", sub, cols, filas, anchos, totales_fila=tot)


def recibo_pdf(recibo, pagos, cliente_nombre: str) -> bytes:
    """Genera el PDF de un recibo de cobranza. Devuelve los bytes del PDF."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 25 * mm

    # Encabezado institucional
    c.setFillColor(AZUL)
    c.rect(0, h - 20 * mm, w, 20 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, h - 13 * mm, "C.C. y P.P. — Ca.Pre.S.Ca.")
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 20 * mm, h - 13 * mm, "Recibo de cobranza")

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, f"Recibo N° {recibo.numero}")
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 20 * mm, y, f"Fecha: {recibo.fecha_pago}")
    y -= 8 * mm
    c.drawString(20 * mm, y, f"Cliente: {cliente_nombre}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Crédito N°: {recibo.credito_id}    "
                             f"Vía de pago: {recibo.via_pago}    Cajero: {recibo.cajero}")
    y -= 10 * mm

    # Tabla de conceptos
    cols = ["Capital", "Interés", "IVA int.", "Seguro", "Gastos", "Punitorio", "IVA pun.", "Total"]
    xs = [20, 45, 68, 90, 110, 130, 152, 175]
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(AZUL)
    for col, x in zip(cols, xs):
        c.drawRightString((x + 18) * mm, y, col)
    c.setFillColor(colors.black)
    y -= 2 * mm
    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica", 8)
    for p in pagos:
        vals = [p.capital, p.interes, p.iva_interes, p.seguro, p.gastos_adm,
                p.interes_punitorio, p.iva_punitorio, p.total_pagado]
        for v, x in zip(vals, xs):
            c.drawRightString((x + 18) * mm, y, _money(v))
        y -= 5 * mm

    y -= 2 * mm
    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(w - 20 * mm, y, f"TOTAL: {_money(recibo.total)}")

    # Pie
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(20 * mm, 15 * mm,
                 "Documento generado por el sistema CCyPP (migración desde Visual FoxPro).")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def contrato_pdf(cto: dict) -> bytes:
    """Contrato de préstamo pp: cabecera (cliente/condiciones/liquidación) + cronograma."""
    snap = cto.get("snapshot") or {}
    liq = cto.get("liquidacion") or {}
    da = cto.get("datos_adicionales") or {}
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = _encabezado(c, w, h, "Contrato de préstamo")

    c.setFont("Helvetica-Bold", 13)
    c.drawString(20 * mm, y, f"Contrato {cto.get('numero_contrato', '')} — {cto.get('cliente_nombre', '')}")
    y -= 7 * mm

    # Bloque de datos en dos columnas
    pares = [
        ("Línea", f"{snap.get('producto', '')} ({snap.get('codigo', '')})"),
        ("Sistema / TNA", f"{cto.get('sistema', '')} · {snap.get('tna', '')}%"),
        ("Monto / plazo", f"{_money(cto.get('monto_original', 0))} · {cto.get('plazo', '')} cuotas"),
        ("Estado", str(cto.get("estado", ""))),
    ]
    if liq:
        pares.append(("Cargos al desembolso", _money(liq.get("cargosDesembolso", 0))))
        pares.append(("Neto a acreditar", _money(liq.get("neto", 0))))
    if da.get("destino"):
        pares.append(("Destino", str(da["destino"])))
    if da.get("cbu"):
        pares.append(("CBU de acreditación", str(da["cbu"])))
    if da.get("garante"):
        pares.append(("Garante", str(da["garante"])))
    col_x = [20 * mm, 118 * mm]
    for i, (k, v) in enumerate(pares):
        x = col_x[i % 2]
        if i % 2 == 0 and i > 0:
            y -= 5.5 * mm
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.grey)
        c.drawString(x, y, k.upper())
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(x + 38 * mm, y, str(v)[:34])
    y -= 9 * mm

    columnas = [("#", "l"), ("Vencimiento", "l"), ("Capital", "r"), ("Interés", "r"),
                ("Cargos", "r"), ("Cuota", "r"), ("Saldo", "r")]
    anchos = [10 * mm, 28 * mm, 27 * mm, 27 * mm, 25 * mm, 28 * mm, 25 * mm]
    xs, acc = [], 20 * mm
    for a in anchos:
        xs.append(acc); acc += a

    def fila(vals, y0, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 8)
        for (nom, al), x, a, v in zip(columnas, xs, anchos, vals):
            (c.drawRightString(x + a - 2, y0, str(v)) if al == "r" else c.drawString(x, y0, str(v)))

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(AZUL)
    for (nom, al), x, a in zip(columnas, xs, anchos):
        (c.drawRightString(x + a - 2, y, nom) if al == "r" else c.drawString(x, y, nom))
    c.setFillColor(colors.black)
    y -= 2 * mm
    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 5 * mm
    for q in cto.get("cuotas", []):
        if y < 25 * mm:
            _pie(c); c.showPage(); y = _encabezado(c, w, h, "Contrato de préstamo") - 5 * mm
        fila([q["numero_cuota"], q["fecha_vencimiento"], _money(q["capital"]), _money(q["interes"]),
              _money(q["cargos"]), _money(q["total"]), _money(q["saldo_final"])], y)
        y -= 5 * mm
    tot_int = sum(float(q["interes"]) for q in cto.get("cuotas", []))
    tot_car = sum(float(q["cargos"]) for q in cto.get("cuotas", []))
    tot_tot = sum(float(q["total"]) for q in cto.get("cuotas", []))
    y -= 1 * mm
    c.line(20 * mm, y, w - 20 * mm, y)
    y -= 5 * mm
    fila(["", "TOTALES", _money(cto.get("monto_original", 0)), _money(tot_int), _money(tot_car), _money(tot_tot), ""], y, bold=True)
    _pie(c)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
