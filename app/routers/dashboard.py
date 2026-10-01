from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..money import ZERO
from ..web import render

router = APIRouter()
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def summarize(db: Session, year: int, quarter: int = 0) -> dict:
    """Resumen contable del ejercicio (o trimestre). Las facturas cuentan desde que se emiten."""
    def in_range(d: date) -> bool:
        return d.year == year and (not quarter or (d.month - 1) // 3 + 1 == quarter)

    invoices = [x for x in db.scalars(select(models.Document).where(
        models.Document.doc_type == "invoice", models.Document.status.in_(["issued", "paid"]))) if in_range(x.issue_date)]
    expenses = [e for e in db.scalars(select(models.Expense)) if in_range(e.date)]

    income = sum((x.subtotal for x in invoices), ZERO)
    spent = sum((e.base for e in expenses), ZERO)
    vat_out = sum((x.vat_total for x in invoices), ZERO)
    vat_in = sum((e.vat_amount for e in expenses), ZERO)
    return {
        "income": income, "expenses": spent, "profit": income - spent,
        "vat_out": vat_out, "vat_in": vat_in, "vat_balance": vat_out - vat_in,
        "irpf_withheld": sum((x.irpf_total for x in invoices), ZERO),
        "invoices": invoices, "expense_items": expenses,
    }


@router.get("/")
def dashboard(request: Request, year: int = 0, quarter: int = 0, db: Session = Depends(get_db)):
    year = year or date.today().year
    quarter = quarter if quarter in (1, 2, 3, 4) else 0
    s = summarize(db, year, quarter)

    monthly = []
    for m in range(12):
        inc = sum((x.subtotal for x in s["invoices"] if x.issue_date.month == m + 1), ZERO)
        exp = sum((e.base for e in s["expense_items"] if e.date.month == m + 1), ZERO)
        monthly.append({"label": MONTHS[m], "income": inc, "expenses": exp})
    peak = max([max(m["income"], m["expenses"]) for m in monthly] + [Decimal(1)])
    for m in monthly:
        m["income_pct"] = int(m["income"] / peak * 100)
        m["expenses_pct"] = int(m["expenses"] / peak * 100)

    all_invoices = db.scalars(select(models.Document).where(
        models.Document.doc_type == "invoice", models.Document.status == "issued")).all()
    overdue = [x for x in all_invoices if x.overdue]
    deals = db.scalars(select(models.Deal).where(models.Deal.stage.notin_(["ganado", "perdido"]))).all()
    unpaid_exp = db.scalars(select(models.Expense).where(models.Expense.paid.is_(False))).all()

    return render(
        request, "dashboard.html", s=s, year=year, quarter=quarter, monthly=monthly,
        pending=sum((x.total for x in all_invoices), ZERO), overdue=overdue,
        overdue_total=sum((x.total for x in overdue), ZERO),
        pipeline=sum((x.value for x in deals), ZERO), open_deals=len(deals),
        unpaid_expenses=sum((e.total for e in unpaid_exp), ZERO),
        years=range(date.today().year - 4, date.today().year + 1),
    )
