from datetime import date
from decimal import Decimal

from app import models
from app.db import SessionLocal
from app.money import d, fmt


def make_contact(client, name="Cliente SL", kind="client"):
    r = client.post("/contacts/save", data={"name": name, "kind": kind, "tax_id": "B123"})
    assert r.status_code == 303
    with SessionLocal() as db:
        return db.query(models.Contact).filter_by(name=name).one().id


def make_invoice(client, contact_id, lines=None, irpf="0", issue_date=None):
    lines = lines or [("Servicio", "2", "100", "0", "21")]
    data = {"doc_type": "invoice", "contact_id": str(contact_id), "irpf_rate": irpf,
            "issue_date": issue_date or date.today().isoformat(), "due_date": "",
            "description": [l[0] for l in lines], "quantity": [l[1] for l in lines],
            "unit_price": [l[2] for l in lines], "discount": [l[3] for l in lines],
            "vat_rate": [l[4] for l in lines]}
    r = client.post("/documents/save", data=data)
    assert r.status_code == 303
    return int(r.headers["location"].split("/")[-1].split("?")[0])


def test_money_helpers():
    assert d("1,5") == Decimal("1.5")
    assert d("abc") == 0
    assert fmt(Decimal("1234.5")) == "1.234,50"


def test_invoice_totals_with_vat_and_irpf(client):
    cid = make_contact(client)
    doc_id = make_invoice(client, cid, [("A", "2", "100", "0", "21"), ("B", "1", "50", "10", "10")], irpf="15")
    with SessionLocal() as db:
        doc = db.get(models.Document, doc_id)
        assert doc.subtotal == Decimal("245.00")           # 200 + 45
        assert doc.vat_total == Decimal("46.50")           # 42 + 4.50
        assert doc.irpf_total == Decimal("36.75")
        assert doc.total == Decimal("254.75")


def test_issue_assigns_correlative_numbers_and_locks(client):
    cid = make_contact(client)
    a, b = make_invoice(client, cid), make_invoice(client, cid)
    client.post(f"/documents/{a}/issue")
    client.post(f"/documents/{b}/issue")
    with SessionLocal() as db:
        assert [db.get(models.Document, i).number for i in (a, b)] == [1, 2]
        assert db.get(models.Document, a).label == f"F-{date.today().year}-0001"
    # emitida: no se puede editar ni borrar
    client.post("/documents/save", data={"id": str(a), "doc_type": "invoice", "contact_id": str(cid),
                                          "description": "X", "quantity": "1", "unit_price": "999",
                                          "discount": "0", "vat_rate": "21"})
    client.post(f"/documents/{a}/delete")
    with SessionLocal() as db:
        doc = db.get(models.Document, a)
        assert doc is not None and doc.total == Decimal("242.00")


def test_numbering_restarts_each_year(client):
    cid = make_contact(client)
    old = make_invoice(client, cid, issue_date="2024-05-01")
    new = make_invoice(client, cid, issue_date="2025-05-01")
    client.post(f"/documents/{old}/issue")
    client.post(f"/documents/{new}/issue")
    with SessionLocal() as db:
        assert db.get(models.Document, new).number == 1


def test_pay_and_pdf(client):
    cid = make_contact(client)
    doc_id = make_invoice(client, cid)
    client.post(f"/documents/{doc_id}/issue")
    client.post(f"/documents/{doc_id}/pay")
    with SessionLocal() as db:
        assert db.get(models.Document, doc_id).status == "paid"
    r = client.get(f"/documents/{doc_id}/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_cannot_issue_without_contact(client):
    r = client.post("/documents/save", data={"doc_type": "invoice", "description": "x", "quantity": "1",
                                              "unit_price": "10", "discount": "0", "vat_rate": "21"})
    doc_id = int(r.headers["location"].split("/")[-1])
    client.post(f"/documents/{doc_id}/issue")
    with SessionLocal() as db:
        assert db.get(models.Document, doc_id).status == "draft"


def test_quote_to_invoice_flow(client):
    cid = make_contact(client)
    r = client.post("/documents/save", data={"doc_type": "quote", "contact_id": str(cid), "description": "Web",
                                              "quantity": "1", "unit_price": "1000", "discount": "0", "vat_rate": "21"})
    qid = int(r.headers["location"].split("/")[-1])
    client.post(f"/documents/{qid}/issue")
    r = client.post(f"/documents/{qid}/to-invoice")
    inv_id = int(r.headers["location"].split("/")[2].split("?")[0])
    again = client.post(f"/documents/{qid}/to-invoice")  # idempotente
    assert again.headers["location"] == f"/documents/{inv_id}"
    with SessionLocal() as db:
        inv, quote = db.get(models.Document, inv_id), db.get(models.Document, qid)
        assert inv.doc_type == "invoice" and inv.total == Decimal("1210.00")
        assert quote.status == "accepted" and quote.label.startswith("P-")


def test_expense_totals_and_list(client):
    sid = make_contact(client, "Proveedor SA", "supplier")
    client.post("/expenses/save", data={"concept": "Alquiler", "category": "Alquiler", "base": "1000",
                                         "vat_rate": "21", "irpf_rate": "19", "paid": "on",
                                         "supplier_id": str(sid), "date": date.today().isoformat()})
    with SessionLocal() as db:
        e = db.query(models.Expense).one()
        assert e.vat_amount == Decimal("210.00") and e.total == Decimal("1020.00") and e.paid
    assert "Alquiler" in client.get("/expenses").text


def test_dashboard_summary(client):
    cid = make_contact(client)
    inv = make_invoice(client, cid, [("A", "1", "1000", "0", "21")])
    client.post(f"/documents/{inv}/issue")
    make_invoice(client, cid)  # borrador: no cuenta
    client.post("/expenses/save", data={"concept": "Material", "base": "200", "vat_rate": "21", "paid": "on"})
    from app.routers.dashboard import summarize
    with SessionLocal() as db:
        s = summarize(db, date.today().year)
    assert s["income"] == Decimal("1000.00") and s["expenses"] == Decimal("200")
    assert s["vat_out"] == Decimal("210.00") and s["vat_in"] == Decimal("42.00")
    assert s["vat_balance"] == Decimal("168.00")
    assert client.get("/").status_code == 200


def test_crm_pipeline(client):
    cid = make_contact(client)
    client.post("/crm/deals/save", data={"title": "Proyecto web", "contact_id": str(cid), "value": "5000",
                                          "stage": "nuevo"})
    with SessionLocal() as db:
        deal_id = db.query(models.Deal).one().id
    assert client.post(f"/crm/deals/{deal_id}/move", json={"stage": "negociacion"}).status_code == 200
    assert client.post(f"/crm/deals/{deal_id}/move", json={"stage": "inventada"}).status_code == 400
    client.post(f"/crm/deals/{deal_id}/move", json={"stage": "ganado"})
    with SessionLocal() as db:
        deal = db.get(models.Deal, deal_id)
        assert deal.stage == "ganado" and deal.closed_at is not None
    client.post(f"/crm/deals/{deal_id}/activity", data={"text": "Llamada"})
    r = client.post(f"/crm/deals/{deal_id}/quote")
    assert "/documents/" in r.headers["location"]
    with SessionLocal() as db:
        q = db.query(models.Document).filter_by(doc_type="quote").one()
        assert q.total == Decimal("6050.00")
    assert "Proyecto web" in client.get("/crm").text


def test_all_pages_render(client):
    cid = make_contact(client)
    doc = make_invoice(client, cid)
    for url in ["/", "/invoices", "/quotes", "/expenses", "/crm", "/contacts", "/settings",
                "/contacts/new", f"/contacts/{cid}", "/documents/new", "/documents/new?type=quote",
                f"/documents/{doc}", f"/documents/{doc}?edit=1", "/expenses/new", "/crm/deals/new"]:
        r = client.get(url)
        assert r.status_code == 200, url


def test_contact_with_documents_is_not_deleted(client):
    cid = make_contact(client)
    make_invoice(client, cid)
    client.post(f"/contacts/{cid}/delete")
    with SessionLocal() as db:
        assert db.get(models.Contact, cid) is not None


def test_basic_auth_when_configured(client, monkeypatch):
    monkeypatch.setenv("APP_USER", "admin")
    monkeypatch.setenv("APP_PASSWORD", "secreto")
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("admin", "mal")).status_code == 401
    assert client.get("/", auth=("admin", "secreto")).status_code == 200
