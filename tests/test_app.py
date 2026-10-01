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
    assert client.get("/healthz").status_code == 200  # el healthcheck de Docker no lleva credenciales
    assert client.get("/manifest.webmanifest").status_code == 401


def _png_bytes(color=(200, 30, 30)):
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (120, 40), color).save(buf, "PNG")
    return buf.getvalue()


def _issue(client, contact_id, **kw):
    doc_id = make_invoice(client, contact_id, **kw)
    client.post(f"/documents/{doc_id}/issue")
    return doc_id


def test_rectifying_invoice_flow(client):
    cid = make_contact(client)
    orig = _issue(client, cid)  # 2 x 100 + 21% = 242
    r = client.post(f"/documents/{orig}/rectify", data={"reason": "Error en cantidad"})
    rect_id = int(r.headers["location"].split("/")[2].split("?")[0])
    with SessionLocal() as db:
        rect = db.get(models.Document, rect_id)
        assert rect.is_rectifying and rect.status == "draft" and rect.series == "R"
        assert rect.total == Decimal("-242.00") and rect.original.id == orig
        assert rect.label == "Rectificativa (borrador)"
    client.post(f"/documents/{rect_id}/issue")
    with SessionLocal() as db:
        assert db.get(models.Document, rect_id).label == f"R-{date.today().year}-0001"
    # la numeracion de la serie F no se ve afectada y el panel netea la factura
    from app.routers.dashboard import summarize
    with SessionLocal() as db:
        s = summarize(db, date.today().year)
    assert s["income"] == Decimal("0.00") and s["vat_out"] == Decimal("0.00")
    assert client.get(f"/documents/{orig}").status_code == 200
    assert client.get(f"/documents/{rect_id}/pdf").content.startswith(b"%PDF")


def test_cannot_rectify_draft_or_a_rectification(client):
    cid = make_contact(client)
    draft = make_invoice(client, cid)
    client.post(f"/documents/{draft}/rectify", data={"reason": "x"})
    with SessionLocal() as db:
        assert db.query(models.Document).filter(models.Document.rectifies_id.isnot(None)).count() == 0
    orig = _issue(client, cid)
    r = client.post(f"/documents/{orig}/rectify", data={"reason": "x"})
    rect_id = int(r.headers["location"].split("/")[2].split("?")[0])
    client.post(f"/documents/{rect_id}/issue")
    client.post(f"/documents/{rect_id}/rectify", data={"reason": "otra"})
    with SessionLocal() as db:
        assert db.query(models.Document).filter(models.Document.rectifies_id.isnot(None)).count() == 1


def test_branding_logo_and_colors(client):
    base = {"name": "Mi Marca", "brand_color": "#e11d48", "brand_color2": "#0f172a"}
    r = client.post("/settings", data=base, files={"logo": ("logo.png", _png_bytes(), "image/png")})
    assert r.headers["location"] == "/settings?saved=1"
    assert client.get("/logo").headers["content-type"] == "image/png"
    page = client.get("/").text
    assert "--accent:#e11d48" in page and "/logo?v=" in page
    assert client.get("/manifest.webmanifest").json()["theme_color"] == "#0f172a"
    cid = make_contact(client)
    doc = _issue(client, cid)
    assert client.get(f"/documents/{doc}/pdf").content.startswith(b"%PDF")
    # un fichero que no es imagen se rechaza y el logo anterior se conserva
    bad = client.post("/settings", data=base, files={"logo": ("x.png", b"no soy una imagen", "image/png")})
    assert "error=logo" in bad.headers["location"] and client.get("/logo").status_code == 200
    # color invalido -> se usa el valor por defecto
    client.post("/settings", data={**base, "brand_color": "rojo"})
    assert "--accent:#2b4975" in client.get("/").text
    client.post("/settings", data={**base, "remove_logo": "on"})
    assert client.get("/logo").status_code == 404


def test_old_database_gets_new_columns(tmp_path):
    import sqlalchemy as sa
    import app.db as dbmod
    old = sa.create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as c:
        c.execute(sa.text("CREATE TABLE company (id INTEGER PRIMARY KEY, name VARCHAR(200))"))
        c.execute(sa.text("INSERT INTO company (id, name) VALUES (1, 'Vieja SL')"))
    original = dbmod.engine
    dbmod.engine = old
    try:
        dbmod.ensure_columns()
        cols = {c["name"] for c in sa.inspect(old).get_columns("company")}
        with old.connect() as c:
            row = c.execute(sa.text("SELECT rectify_series, brand_color FROM company")).one()
    finally:
        dbmod.engine = original
    assert {"logo", "brand_color", "rectify_series"} <= cols
    assert tuple(row) == ("R", "#2b4975")  # las filas existentes reciben el valor por defecto
