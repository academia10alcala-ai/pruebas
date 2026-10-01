from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..money import d
from ..web import get_company, parse_date, render

router = APIRouter(prefix="/expenses")


def _suppliers(db: Session):
    return db.scalars(select(models.Contact).where(models.Contact.kind.in_(["supplier", "both"]))
                      .order_by(models.Contact.name)).all()


@router.get("")
def list_expenses(request: Request, q: str = "", category: str = "", year: str = "", paid: str = "",
                  db: Session = Depends(get_db)):
    stmt = select(models.Expense)
    if category:
        stmt = stmt.where(models.Expense.category == category)
    if year.isdigit():
        stmt = stmt.where(models.Expense.date.between(date(int(year), 1, 1), date(int(year), 12, 31)))
    if paid in ("1", "0"):
        stmt = stmt.where(models.Expense.paid == (paid == "1"))
    items = db.scalars(stmt.order_by(models.Expense.date.desc(), models.Expense.id.desc())).all()
    if q:
        ql = q.lower()
        items = [e for e in items if ql in e.concept.lower() or ql in e.reference.lower()
                 or (e.supplier and ql in e.supplier.name.lower())]
    by_cat: dict[str, Decimal] = {}
    for e in items:
        by_cat[e.category] = by_cat.get(e.category, Decimal(0)) + e.total
    return render(request, "expenses_list.html", items=items, q=q, category=category, year=year, paid=paid,
                  total=sum((e.total for e in items), Decimal(0)),
                  vat=sum((e.vat_amount for e in items), Decimal(0)),
                  by_cat=sorted(by_cat.items(), key=lambda kv: -kv[1]))


@router.get("/new")
def new_expense(request: Request, db: Session = Depends(get_db)):
    expense = models.Expense(date=date.today(), vat_rate=get_company(db).default_vat, irpf_rate=Decimal(0))
    return render(request, "expense_form.html", expense=expense, suppliers=_suppliers(db))


@router.get("/{expense_id}")
def edit_expense(expense_id: int, request: Request, db: Session = Depends(get_db)):
    expense = db.get(models.Expense, expense_id)
    if not expense:
        return RedirectResponse("/expenses", status_code=303)
    return render(request, "expense_form.html", expense=expense, suppliers=_suppliers(db))


@router.post("/save")
def save_expense(
    id: int = Form(0), date_: str = Form("", alias="date"), supplier_id: str = Form(""),
    reference: str = Form(""), concept: str = Form(...), category: str = Form("Otros"),
    base: str = Form("0"), vat_rate: str = Form("21"), irpf_rate: str = Form("0"),
    paid: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db),
):
    expense = db.get(models.Expense, id) if id else models.Expense()
    expense.date = parse_date(date_) or date.today()
    expense.supplier_id = int(supplier_id) if supplier_id else None
    expense.reference, expense.concept, expense.notes = reference.strip(), concept.strip(), notes
    expense.category = category if category in models.EXPENSE_CATEGORIES else "Otros"
    expense.base, expense.vat_rate, expense.irpf_rate = d(base), d(vat_rate), d(irpf_rate)
    expense.paid = paid == "on"
    db.add(expense)
    db.commit()
    return RedirectResponse("/expenses", status_code=303)


@router.post("/{expense_id}/toggle-paid")
def toggle_paid(expense_id: int, db: Session = Depends(get_db)):
    expense = db.get(models.Expense, expense_id)
    if expense:
        expense.paid = not expense.paid
        db.commit()
    return RedirectResponse("/expenses", status_code=303)


@router.post("/{expense_id}/delete")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.get(models.Expense, expense_id)
    if expense:
        db.delete(expense)
        db.commit()
    return RedirectResponse("/expenses", status_code=303)
