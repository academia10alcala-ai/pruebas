from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..money import d
from ..pdf import render_document_pdf
from ..web import get_company, parse_date, render

router = APIRouter()
LIST_URL = {"invoice": "/invoices", "quote": "/quotes"}


def _editable(doc: models.Document) -> bool:
    if doc.doc_type == "invoice":
        return doc.status == "draft"
    return doc.status in ("draft", "sent")


def _clients(db: Session):
    return db.scalars(select(models.Contact).where(models.Contact.kind.in_(["client", "both"]))
                      .order_by(models.Contact.name)).all()


def _list(request: Request, db: Session, doc_type: str, status: str, q: str, year: str):
    stmt = select(models.Document).where(models.Document.doc_type == doc_type)
    if status:
        stmt = stmt.where(models.Document.status == status)
    if year.isdigit():
        stmt = stmt.where(models.Document.issue_date.between(date(int(year), 1, 1), date(int(year), 12, 31)))
    docs = db.scalars(stmt.order_by(models.Document.issue_date.desc(), models.Document.id.desc())).all()
    if q:
        ql = q.lower()
        docs = [x for x in docs if ql in x.label.lower() or (x.contact and ql in x.contact.name.lower())]
    pending = sum((x.total for x in docs if x.doc_type == "invoice" and x.status == "issued"), Decimal(0))
    return render(request, "documents_list.html", docs=docs, doc_type=doc_type, status=status, q=q,
                  year=year, pending=pending, total=sum((x.total for x in docs), Decimal(0)))


@router.get("/invoices")
def list_invoices(request: Request, status: str = "", q: str = "", year: str = "", db: Session = Depends(get_db)):
    return _list(request, db, "invoice", status, q, year)


@router.get("/quotes")
def list_quotes(request: Request, status: str = "", q: str = "", year: str = "", db: Session = Depends(get_db)):
    return _list(request, db, "quote", status, q, year)


@router.get("/documents/new")
def new_document(request: Request, type: str = "invoice", contact_id: int = 0, db: Session = Depends(get_db)):
    company = get_company(db)
    doc_type = type if type in LIST_URL else "invoice"
    doc = models.Document(
        doc_type=doc_type, issue_date=date.today(), irpf_rate=Decimal(0),
        due_date=date.today() + timedelta(days=company.payment_days) if doc_type == "invoice" else None,
        contact_id=contact_id or None, lines=[models.Line(description="", vat_rate=company.default_vat)],
    )
    return render(request, "document_form.html", doc=doc, clients=_clients(db), editable=True)


@router.get("/documents/{doc_id}")
def view_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        return RedirectResponse("/invoices", status_code=303)
    if _editable(doc) and request.query_params.get("edit"):
        return render(request, "document_form.html", doc=doc, clients=_clients(db), editable=True)
    source = db.get(models.Document, doc.source_quote_id) if doc.source_quote_id else None
    converted = db.scalar(select(models.Document).where(models.Document.source_quote_id == doc.id))
    return render(request, "document_view.html", doc=doc, editable=_editable(doc), source=source,
                  converted=converted, company=get_company(db))


@router.post("/documents/save")
async def save_document(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    doc_id = int(form.get("id") or 0)
    doc = db.get(models.Document, doc_id) if doc_id else models.Document(doc_type=form.get("doc_type", "invoice"))
    if doc_id and (doc is None or not _editable(doc)):
        return RedirectResponse(f"/documents/{doc_id}", status_code=303)
    company = get_company(db)

    doc.contact_id = int(form["contact_id"]) if form.get("contact_id") else None
    doc.issue_date = parse_date(form.get("issue_date")) or date.today()
    doc.due_date = parse_date(form.get("due_date"))
    doc.irpf_rate = d(form.get("irpf_rate"))
    doc.notes = form.get("notes", "")
    doc.series = doc.series or (company.invoice_series if doc.doc_type == "invoice" else company.quote_series)

    doc.lines.clear()
    rows = zip(form.getlist("description"), form.getlist("quantity"), form.getlist("unit_price"),
               form.getlist("discount"), form.getlist("vat_rate"))
    for pos, (desc, qty, price, disc, vat) in enumerate(rows):
        if not desc.strip() and not d(price):
            continue
        doc.lines.append(models.Line(position=pos, description=desc.strip(), quantity=d(qty, "1"),
                                     unit_price=d(price), discount=min(d(disc), Decimal(100)),
                                     vat_rate=d(vat, str(company.default_vat))))
    db.add(doc)
    db.commit()
    return RedirectResponse(f"/documents/{doc.id}", status_code=303)


def _next_number(db: Session, doc: models.Document) -> int:
    year = doc.issue_date.year
    current = db.scalar(
        select(func.max(models.Document.number)).where(
            models.Document.doc_type == doc.doc_type, models.Document.series == doc.series,
            models.Document.issue_date.between(date(year, 1, 1), date(year, 12, 31)),
        )
    )
    return (current or 0) + 1


@router.post("/documents/{doc_id}/issue")
def issue_document(doc_id: int, db: Session = Depends(get_db)):
    """Emite la factura (o envia el presupuesto): asigna numero correlativo y la bloquea."""
    doc = db.get(models.Document, doc_id)
    if doc and doc.status == "draft" and doc.contact_id and doc.lines:
        doc.number = _next_number(db, doc)
        doc.status = "issued" if doc.doc_type == "invoice" else "sent"
        db.commit()
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/pay")
def pay_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if doc and doc.doc_type == "invoice" and doc.status == "issued":
        doc.status, doc.paid_date = "paid", date.today()
        db.commit()
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/unpay")
def unpay_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if doc and doc.doc_type == "invoice" and doc.status == "paid":
        doc.status, doc.paid_date = "issued", None
        db.commit()
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/quote-status/{status}")
def quote_status(doc_id: int, status: str, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if doc and doc.doc_type == "quote" and doc.number is not None and status in ("sent", "accepted", "rejected"):
        doc.status = status
        db.commit()
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.post("/documents/{doc_id}/to-invoice")
def quote_to_invoice(doc_id: int, db: Session = Depends(get_db)):
    quote = db.get(models.Document, doc_id)
    if not quote or quote.doc_type != "quote":
        return RedirectResponse("/quotes", status_code=303)
    existing = db.scalar(select(models.Document).where(models.Document.source_quote_id == quote.id))
    if existing:
        return RedirectResponse(f"/documents/{existing.id}", status_code=303)
    company = get_company(db)
    invoice = models.Document(
        doc_type="invoice", series=company.invoice_series, contact_id=quote.contact_id,
        issue_date=date.today(), due_date=date.today() + timedelta(days=company.payment_days),
        irpf_rate=quote.irpf_rate, notes=quote.notes, source_quote_id=quote.id,
        lines=[models.Line(position=l.position, description=l.description, quantity=l.quantity,
                           unit_price=l.unit_price, discount=l.discount, vat_rate=l.vat_rate)
               for l in quote.lines],
    )
    quote.status = "accepted"
    db.add(invoice)
    db.commit()
    return RedirectResponse(f"/documents/{invoice.id}?edit=1", status_code=303)


@router.post("/documents/{doc_id}/delete")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Las facturas emitidas no se borran (numeracion correlativa); solo borradores y presupuestos."""
    doc = db.get(models.Document, doc_id)
    if not doc:
        return RedirectResponse("/invoices", status_code=303)
    back = LIST_URL[doc.doc_type]
    if doc.doc_type == "quote" or doc.status == "draft":
        for inv in db.scalars(select(models.Document).where(models.Document.source_quote_id == doc.id)):
            inv.source_quote_id = None
        db.delete(doc)
        db.commit()
        return RedirectResponse(back, status_code=303)
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


@router.get("/documents/{doc_id}/pdf")
def document_pdf(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        return RedirectResponse("/invoices", status_code=303)
    data = render_document_pdf(doc, get_company(db))
    filename = (doc.label if doc.number else f"borrador-{doc.id}").replace(" ", "_") + ".pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
