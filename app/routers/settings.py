from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..money import d
from ..web import get_company, render

router = APIRouter(prefix="/settings")


@router.get("")
def show(request: Request, saved: str = "", db: Session = Depends(get_db)):
    return render(request, "settings.html", company=get_company(db), saved=bool(saved))


@router.post("")
def save(
    name: str = Form(...), tax_id: str = Form(""), address: str = Form(""), email: str = Form(""),
    phone: str = Form(""), iban: str = Form(""), invoice_series: str = Form("F"),
    quote_series: str = Form("P"), default_vat: str = Form("21"), payment_days: int = Form(30),
    db: Session = Depends(get_db),
):
    c = get_company(db)
    c.name, c.tax_id, c.address, c.email, c.phone, c.iban = name, tax_id, address, email, phone, iban
    c.invoice_series, c.quote_series = invoice_series.strip() or "F", quote_series.strip() or "P"
    c.default_vat, c.payment_days = d(default_vat, "21"), max(payment_days, 0)
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)
