from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..money import d
from ..web import get_company, render, valid_color

router = APIRouter(prefix="/settings")


@router.get("")
def show(request: Request, saved: str = "", error: str = "", db: Session = Depends(get_db)):
    return render(request, "settings.html", company=get_company(db), saved=bool(saved), error=error)


@router.post("")
async def save(
    name: str = Form(...), tax_id: str = Form(""), address: str = Form(""), email: str = Form(""),
    phone: str = Form(""), iban: str = Form(""), invoice_series: str = Form("F"),
    quote_series: str = Form("P"), rectify_series: str = Form("R"),
    brand_color: str = Form("#2563eb"), brand_color2: str = Form("#1f2937"),
    logo: UploadFile | None = File(None), remove_logo: str = Form(""), default_vat: str = Form("21"), payment_days: int = Form(30),
    db: Session = Depends(get_db),
):
    c = get_company(db)
    c.name, c.tax_id, c.address, c.email, c.phone, c.iban = name, tax_id, address, email, phone, iban
    c.invoice_series, c.quote_series = invoice_series.strip() or "F", quote_series.strip() or "P"
    c.rectify_series = rectify_series.strip() or "R"
    c.brand_color = valid_color(brand_color, "#2563eb")
    c.brand_color2 = valid_color(brand_color2, "#1f2937")
    if remove_logo:
        c.logo, c.logo_mime = None, ""
    elif logo is not None and logo.filename:
        data = await logo.read()
        mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg" if data[:3] == b"\xff\xd8\xff" else ""
        if not mime or len(data) > 2_000_000:
            return RedirectResponse("/settings?error=logo", status_code=303)
        c.logo, c.logo_mime = data, mime
    c.default_vat, c.payment_days = d(default_vat, "21"), max(payment_days, 0)
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)
