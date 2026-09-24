"""Generación del .docx de resoluciones y disposiciones.

Reemplaza la generación vía Word del sistema anterior. El documento sigue la estructura formal de un
acto administrativo y rinde el HTML que produce el editor de la pantalla (títulos, negrita, listas).

El número que sale impreso es el REAL si ya está cargado, y si no el correlativo: hasta que Despacho
carga el oficial, el papel circula con el número de trabajo.
"""
from __future__ import annotations

from decimal import Decimal
from html.parser import HTMLParser
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


def _pesos(monto) -> str:
    """Formato argentino: miles con punto, decimales con coma."""
    return f"{Decimal(str(monto or 0)):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")

TIPO_NOMBRE = {"RES": "RESOLUCIÓN", "DIS": "DISPOSICIÓN"}
INSTITUCION = "CAJA DE CRÉDITO Y PRESTACIONES PROVINCIAL — Ca.Pre.S.Ca."


class _HtmlToDocx(HTMLParser):
    """Vuelca el HTML del editor mini-Word a párrafos de docx: h1-h3 (títulos), p/div (cuerpo
    justificado), ul/ol/li (viñetas), y runs b/strong, i/em, u dentro del párrafo."""
    _BLOCK = {"p", "div", "h1", "h2", "h3", "h4", "li"}
    _HEAD = {"h1": 15, "h2": 13, "h3": 12, "h4": 12}

    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.par = None
        self.bold = self.italic = self.under = False
        self.head = None

    def _flush(self):
        self.par = None

    _ALIGN = {"center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT,
              "justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            if self.par is not None:
                self.par.add_run().add_break()
        elif tag in self._BLOCK:
            self.par = self.doc.add_paragraph()
            style = dict(attrs).get("style", "") or ""
            al = ""
            if "text-align:" in style:
                al = style.split("text-align:")[1].split(";")[0].strip()
            if tag in self._HEAD:
                self.head = self._HEAD[tag]
                self.par.alignment = self._ALIGN.get(al, WD_ALIGN_PARAGRAPH.CENTER if tag in ("h1", "h2") else WD_ALIGN_PARAGRAPH.LEFT)
            else:
                self.head = None
                self.par.alignment = self._ALIGN.get(al, WD_ALIGN_PARAGRAPH.JUSTIFY)
            if tag == "li":
                self.par.style = "List Bullet"
        elif tag in ("b", "strong"):
            self.bold = True
        elif tag in ("i", "em"):
            self.italic = True
        elif tag == "u":
            self.under = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._BLOCK:
            self._flush(); self.head = None
        elif tag in ("b", "strong"):
            self.bold = False
        elif tag in ("i", "em"):
            self.italic = False
        elif tag == "u":
            self.under = False

    def handle_data(self, data):
        text = data.replace("\r", "").strip("\n")
        if not text.strip():
            return
        if self.par is None:
            self.par = self.doc.add_paragraph()
            self.par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = self.par.add_run(text)
        run.bold = self.bold or (self.head is not None)
        run.italic = self.italic
        run.underline = self.under
        if self.head:
            run.font.size = Pt(self.head)


def _cuerpo(doc, texto: str) -> None:
    """Renderiza el cuerpo: HTML (editor mini-Word) → párrafos con formato; texto plano → líneas."""
    t = (texto or "").strip()
    if not t:
        return
    if "<" in t and ">" in t and any(f"<{x}" in t.lower() for x in ("p", "div", "h1", "h2", "h3", "br", "ul", "ol", "b", "i", "u")):
        parser = _HtmlToDocx(doc)
        parser.feed(t)
        parser.close()
    else:
        for parrafo in t.split("\n"):
            p = parrafo.rstrip()
            par = doc.add_paragraph(p)
            par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def resolucion_docx(resolucion) -> bytes:
    """Genera el .docx de una resolución/disposición. Devuelve los bytes."""
    doc = Document()

    # Encabezado institucional (nombre correcto de la Caja).
    enc = doc.add_paragraph(); enc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = enc.add_run(INSTITUCION)
    run.bold = True; run.font.size = Pt(12); run.font.color.rgb = RGBColor(0x14, 0x42, 0x8A)

    # Título del acto: tipo + Nº (real si está, si no correlativo).
    tipo = TIPO_NOMBRE.get(resolucion.tipo, "RESOLUCIÓN")
    nro = resolucion.numero_real or resolucion.numero
    titulo = doc.add_paragraph(); titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = titulo.add_run(f"{tipo} N° {nro}/{resolucion.anio}")
    r.bold = True; r.font.size = Pt(14)

    # Motivo como subtítulo (no el "asunto" derivado del texto, que quedaba feo).
    if getattr(resolucion, "motivo", ""):
        sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.add_run(resolucion.motivo).italic = True

    doc.add_paragraph()

    # Cuerpo (el texto del instrumento ya trae VISTO/CONSIDERANDO/RESUELVE; puede ser HTML del editor).
    texto = (resolucion.texto or "").strip()
    if texto:
        _cuerpo(doc, texto)
    else:
        doc.add_paragraph("VISTO:").runs[0].bold = True
        doc.add_paragraph(f"El expediente relativo a: {resolucion.motivo or resolucion.asunto};")
        doc.add_paragraph("CONSIDERANDO:").runs[0].bold = True
        doc.add_paragraph("Que corresponde dictar el presente acto administrativo;")
        p = doc.add_paragraph()
        p.add_run("Por ello, EL DIRECTORIO de la Ca.Pre.S.Ca.").bold = True
        p.add_run(" RESUELVE:")
        doc.add_paragraph("ARTÍCULO 1°.- Aprobar lo actuado conforme a los considerandos precedentes.")
        doc.add_paragraph("ARTÍCULO 2°.- Regístrese, comuníquese y archívese.")

    # Estado
    doc.add_paragraph()
    estado = doc.add_paragraph(); estado.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    txt = "— OFICIAL —" if resolucion.estado == "F" else "— BORRADOR (sin firma) —"
    estado.add_run(txt).italic = True

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def anexo_docx(resolucion, filas) -> bytes:
    """Anexo de la resolución: el listado de solicitudes que otorga, con su total."""
    doc = Document()
    tipo = TIPO_NOMBRE.get(resolucion.tipo, "RESOLUCIÓN")
    nro = resolucion.numero_real or resolucion.numero

    enc = doc.add_paragraph(); enc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = enc.add_run(INSTITUCION)
    run.bold = True; run.font.size = Pt(12); run.font.color.rgb = RGBColor(0x14, 0x42, 0x8A)

    titulo = doc.add_paragraph(); titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = titulo.add_run(f"ANEXO — {tipo} N° {nro}/{resolucion.anio}")
    r.bold = True; r.font.size = Pt(13)
    if resolucion.motivo:
        sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub.add_run(resolucion.motivo).italic = True
    doc.add_paragraph()

    tabla = doc.add_table(rows=1, cols=5)
    tabla.style = "Table Grid"
    for celda, titulo_col in zip(tabla.rows[0].cells,
                                 ("Solicitud", "CUIL", "Apellido y nombre", "Línea", "Importe")):
        celda.paragraphs[0].add_run(titulo_col).bold = True

    # Las filas llegan de Créditos como diccionarios; se acepta también un objeto con atributos.
    def dato(f, campo):
        return f.get(campo) if isinstance(f, dict) else getattr(f, campo, None)

    filas = list(filas)
    total = Decimal("0")
    for f in filas:
        monto_fila = Decimal(str(dato(f, "monto") or 0))
        c = tabla.add_row().cells
        c[0].text = str(dato(f, "id") or "")
        c[1].text = dato(f, "cuil") or ""
        c[2].text = dato(f, "apellido_nombre") or ""
        c[3].text = dato(f, "linea_nombre") or str(dato(f, "linea") or "")
        c[4].text = _pesos(monto_fila)
        c[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        total += monto_fila

    doc.add_paragraph()
    pie = doc.add_paragraph(); pie.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    pie.add_run(f"{len(filas)} solicitud(es) — Total: $ {_pesos(total)}").bold = True

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()

