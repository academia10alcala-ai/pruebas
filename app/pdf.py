from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from xml.sax.saxutils import escape
from reportlab.lib.utils import ImageReader

from .models import DEFAULT_BRAND_COLOR, DEFAULT_BRAND_COLOR2
from .money import fmt


def _logo(company, max_w=55 * mm, max_h=22 * mm):
    """Logo de la empresa escalado para caber en la cabecera (o None)."""
    if not company.logo:
        return None
    try:
        w, h = ImageReader(BytesIO(company.logo)).getSize()
        scale = min(max_w / w, max_h / h)
        img = Image(BytesIO(company.logo), width=w * scale, height=h * scale)
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def _color(value, fallback):
    try:
        return colors.HexColor(value or fallback)
    except Exception:
        return colors.HexColor(fallback)


def _p(text, style):
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def render_document_pdf(doc, company) -> bytes:
    buf = BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=doc.label)
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=9, leading=12)
    right = ParagraphStyle("right", parent=small, alignment=2)
    title = ParagraphStyle("title", parent=ss["Title"], alignment=0, fontSize=20,
                           textColor=_color(company.brand_color, DEFAULT_BRAND_COLOR))
    kind = doc.kind_name.upper()

    story = []
    logo = _logo(company)
    if logo:
        story += [logo, Spacer(1, 4 * mm)]
    story.append(Paragraph(kind, title))
    if doc.is_rectifying and doc.rectifies_id:
        orig = doc.original
        ref = f"{orig.label} ({orig.issue_date.strftime('%d/%m/%Y')})" if orig else "factura original"
        story += [_p(f"Rectifica a la factura {ref}. Motivo: {doc.rectify_reason}", small), Spacer(1, 3 * mm)]
    head = Table(
        [[
            [_p(company.name, ParagraphStyle("b", parent=small, fontName="Helvetica-Bold")),
             _p(f"NIF/CIF: {company.tax_id}" if company.tax_id else "", small),
             _p(company.address, small), _p(company.email, small), _p(company.phone, small)],
            [_p(f"Nº: {doc.label}", right),
             _p(f"Fecha: {doc.issue_date.strftime('%d/%m/%Y')}", right),
             _p(f"Vencimiento: {doc.due_date.strftime('%d/%m/%Y')}" if doc.due_date else "", right)],
        ]],
        colWidths=[100 * mm, 74 * mm],
    )
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [head, Spacer(1, 8 * mm)]

    c = doc.contact
    if c:
        story += [_p("Cliente", ParagraphStyle("h", parent=small, textColor=colors.grey)),
                  _p(c.name, ParagraphStyle("b2", parent=small, fontName="Helvetica-Bold")),
                  _p(f"NIF/CIF: {c.tax_id}" if c.tax_id else "", small), _p(c.address, small)]
    story.append(Spacer(1, 8 * mm))

    rows = [["Descripción", "Cant.", "Precio", "Dto.%", "IVA%", "Importe"]]
    for l in doc.lines:
        rows.append([_p(l.description, small), fmt(l.quantity), fmt(l.unit_price),
                     fmt(l.discount), fmt(l.vat_rate), fmt(l.base)])
    t = Table(rows, colWidths=[78 * mm, 16 * mm, 24 * mm, 14 * mm, 14 * mm, 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _color(company.brand_color2, DEFAULT_BRAND_COLOR2)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
    ]))
    story += [t, Spacer(1, 6 * mm)]

    tot = [["Base imponible", fmt(doc.subtotal)]]
    for rate, base, quota in doc.vat_breakdown:
        tot.append([f"IVA {fmt(rate)}% s/ {fmt(base)}", fmt(quota)])
    if doc.irpf_rate:
        tot.append([f"IRPF -{fmt(doc.irpf_rate)}%", "-" + fmt(doc.irpf_total)])
    tot.append(["TOTAL", fmt(doc.total) + " €"])
    tt = Table(tot, colWidths=[110 * mm, 40 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
    ]))
    story.append(tt)

    extra = []
    if doc.doc_type == "invoice" and company.iban:
        extra.append(f"Forma de pago: transferencia a {company.iban}")
    if doc.notes:
        extra.append(doc.notes)
    if extra:
        story += [Spacer(1, 8 * mm), _p("\n".join(extra), small)]

    pdf.build(story)
    return buf.getvalue()
