from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..web import render

router = APIRouter(prefix="/contacts")


@router.get("")
def list_contacts(request: Request, q: str = "", kind: str = "", db: Session = Depends(get_db)):
    stmt = select(models.Contact).order_by(models.Contact.name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(models.Contact.name.ilike(like), models.Contact.tax_id.ilike(like),
                              models.Contact.email.ilike(like)))
    if kind in ("client", "supplier"):
        stmt = stmt.where(models.Contact.kind.in_([kind, "both"]))
    return render(request, "contacts_list.html", contacts=db.scalars(stmt).all(), q=q, kind=kind)


@router.get("/new")
def new_contact(request: Request, kind: str = "client"):
    return render(request, "contact_form.html", contact=models.Contact(kind=kind))


@router.get("/{contact_id}")
def edit_contact(contact_id: int, request: Request, db: Session = Depends(get_db)):
    contact = db.get(models.Contact, contact_id)
    if not contact:
        return RedirectResponse("/contacts", status_code=303)
    docs = db.scalars(select(models.Document).where(models.Document.contact_id == contact_id)
                      .order_by(models.Document.issue_date.desc())).all()
    expenses = db.scalars(select(models.Expense).where(models.Expense.supplier_id == contact_id)
                          .order_by(models.Expense.date.desc())).all()
    return render(request, "contact_form.html", contact=contact, docs=docs, expenses=expenses)


@router.post("/save")
def save_contact(
    id: int = Form(0), name: str = Form(...), kind: str = Form("client"), tax_id: str = Form(""),
    email: str = Form(""), phone: str = Form(""), address: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_db),
):
    contact = db.get(models.Contact, id) if id else models.Contact()
    if kind not in ("client", "supplier", "both"):
        kind = "client"
    contact.name, contact.kind, contact.tax_id = name.strip(), kind, tax_id.strip()
    contact.email, contact.phone, contact.address, contact.notes = email.strip(), phone.strip(), address, notes
    db.add(contact)
    db.commit()
    return RedirectResponse("/contacts", status_code=303)


@router.post("/{contact_id}/delete")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.get(models.Contact, contact_id)
    in_use = db.scalar(select(models.Document.id).where(models.Document.contact_id == contact_id).limit(1)) \
        or db.scalar(select(models.Expense.id).where(models.Expense.supplier_id == contact_id).limit(1))
    if contact and not in_use:
        for deal in contact.deals:
            deal.contact_id = None
        db.delete(contact)
        db.commit()
    return RedirectResponse("/contacts", status_code=303)
