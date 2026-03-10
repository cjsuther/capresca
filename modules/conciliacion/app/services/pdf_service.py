from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_boleta(record, template_config=None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                             leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=16, spaceAfter=12)
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    value_style = ParagraphStyle("value", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold")

    if template_config and template_config.header_text:
        story.append(Paragraph(template_config.header_text, styles["Normal"]))
        story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("BOLETA DE CONCILIACIÓN", title_style))
    story.append(Spacer(1, 0.3*cm))

    info_data = [
        ["Fecha:", str(record.reconciliation_date)],
        ["Agencia:", f"{record.agency_number or '—'} — {record.agency_legal_name}"],
        ["CUIT:", record.agency_tax_id or "—"],
        ["Estado:", record.status],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Importes", styles["Heading2"]))
    amounts_data = [
        ["Importe Adeudado:", f"$ {record.importe_adeudado:,.2f}"],
        ["Importe Premios:", f"$ {record.importe_premios:,.2f}"],
        ["Importe Depositado:", f"$ {record.importe_depositado:,.2f}"],
        ["Importe Neto:", f"$ {record.importe_neto:,.2f}"],
    ]
    amounts_table = Table(amounts_data, colWidths=[6*cm, 6*cm])
    amounts_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(amounts_table)

    if template_config and template_config.footer_text:
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(template_config.footer_text, label_style))

    doc.build(story)
    return buffer.getvalue()
