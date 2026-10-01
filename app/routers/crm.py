from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..money import d
from ..web import get_company, parse_date, render

router = APIRouter(prefix="/crm")


def _contacts(db: Session):
    return db.scalars(select(models.Contact).order_by(models.Contact.name)).all()


def _set_stage(deal: models.Deal, stage: str):
    deal.stage = stage
    deal.closed_at = datetime.utcnow() if stage in ("ganado", "perdido") else None


@router.get("")
def board(request: Request, db: Session = Depends(get_db)):
    deals = db.scalars(select(models.Deal).order_by(models.Deal.created_at)).all()
    columns = []
    for key, label in models.STAGES:
        items = [x for x in deals if x.stage == key]
        columns.append({"key": key, "label": label, "deals": items,
                        "total": sum((x.value for x in items), Decimal(0))})
    open_deals = [x for x in deals if x.stage not in ("ganado", "perdido")]
    won = [x for x in deals if x.stage == "ganado"]
    lost = [x for x in deals if x.stage == "perdido"]
    closed = len(won) + len(lost)
    return render(request, "crm_board.html", columns=columns,
                  open_value=sum((x.value for x in open_deals), Decimal(0)),
                  won_value=sum((x.value for x in won), Decimal(0)),
                  win_rate=round(100 * len(won) / closed) if closed else None)


@router.get("/deals/new")
def new_deal(request: Request, stage: str = "nuevo", contact_id: int = 0, db: Session = Depends(get_db)):
    deal = models.Deal(stage=stage if stage in models.STAGE_KEYS else "nuevo", contact_id=contact_id or None)
    return render(request, "deal_form.html", deal=deal, contacts=_contacts(db))


@router.get("/deals/{deal_id}")
def edit_deal(deal_id: int, request: Request, db: Session = Depends(get_db)):
    deal = db.get(models.Deal, deal_id)
    if not deal:
        return RedirectResponse("/crm", status_code=303)
    return render(request, "deal_form.html", deal=deal, contacts=_contacts(db))


@router.post("/deals/save")
def save_deal(
    id: int = Form(0), title: str = Form(...), contact_id: str = Form(""), value: str = Form("0"),
    stage: str = Form("nuevo"), expected_close: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_db),
):
    deal = db.get(models.Deal, id) if id else models.Deal()
    deal.title, deal.notes = title.strip(), notes
    deal.contact_id = int(contact_id) if contact_id else None
    deal.value, deal.expected_close = d(value), parse_date(expected_close)
    _set_stage(deal, stage if stage in models.STAGE_KEYS else "nuevo")
    db.add(deal)
    db.commit()
    return RedirectResponse("/crm", status_code=303)


@router.post("/deals/{deal_id}/move")
async def move_deal(deal_id: int, request: Request, db: Session = Depends(get_db)):
    """Llamado por el arrastrar y soltar del tablero."""
    payload = await request.json()
    deal, stage = db.get(models.Deal, deal_id), payload.get("stage")
    if not deal or stage not in models.STAGE_KEYS:
        return JSONResponse({"ok": False}, status_code=400)
    _set_stage(deal, stage)
    db.commit()
    return {"ok": True}


@router.post("/deals/{deal_id}/activity")
def add_activity(deal_id: int, text: str = Form(...), db: Session = Depends(get_db)):
    if db.get(models.Deal, deal_id) and text.strip():
        db.add(models.Activity(deal_id=deal_id, text=text.strip()))
        db.commit()
    return RedirectResponse(f"/crm/deals/{deal_id}", status_code=303)


@router.post("/deals/{deal_id}/quote")
def deal_to_quote(deal_id: int, db: Session = Depends(get_db)):
    """Crea un presupuesto borrador a partir de la oportunidad."""
    deal = db.get(models.Deal, deal_id)
    if not deal:
        return RedirectResponse("/crm", status_code=303)
    company = get_company(db)
    quote = models.Document(
        doc_type="quote", series=company.quote_series, contact_id=deal.contact_id, issue_date=date.today(),
        lines=[models.Line(description=deal.title, quantity=Decimal(1), unit_price=deal.value,
                           vat_rate=company.default_vat)],
    )
    db.add(quote)
    if deal.stage in ("nuevo", "contactado"):
        _set_stage(deal, "propuesta")
    db.add(models.Activity(deal_id=deal.id, text="Presupuesto creado desde la oportunidad."))
    db.commit()
    return RedirectResponse(f"/documents/{quote.id}?edit=1", status_code=303)


@router.post("/deals/{deal_id}/delete")
def delete_deal(deal_id: int, db: Session = Depends(get_db)):
    deal = db.get(models.Deal, deal_id)
    if deal:
        db.delete(deal)
        db.commit()
    return RedirectResponse("/crm", status_code=303)
