from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, Text, Date, DateTime, Integer, Boolean, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .money import ZERO, d, r2


class Money(TypeDecorator):
    """Decimal exacto guardado como texto (SQLite no tiene decimales nativos)."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(d(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


STAGES = [
    ("nuevo", "Nuevo"),
    ("contactado", "Contactado"),
    ("propuesta", "Propuesta"),
    ("negociacion", "Negociación"),
    ("ganado", "Ganado"),
    ("perdido", "Perdido"),
]
STAGE_KEYS = [k for k, _ in STAGES]

EXPENSE_CATEGORIES = [
    "Alquiler", "Suministros", "Material de oficina", "Software y suscripciones",
    "Servicios profesionales", "Marketing", "Viajes y dietas", "Transporte",
    "Sueldos y seguros sociales", "Impuestos y tasas", "Otros",
]

INVOICE_STATUSES = {"draft": "Borrador", "issued": "Emitida", "paid": "Cobrada"}
QUOTE_STATUSES = {"draft": "Borrador", "sent": "Enviado", "accepted": "Aceptado", "rejected": "Rechazado"}


class Company(Base):
    """Datos de la empresa emisora (una sola fila)."""
    __tablename__ = "company"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="Mi Empresa S.L.")
    tax_id: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    iban: Mapped[str] = mapped_column(String(50), default="")
    invoice_series: Mapped[str] = mapped_column(String(10), default="F")
    quote_series: Mapped[str] = mapped_column(String(10), default="P")
    default_vat: Mapped[Decimal] = mapped_column(Money, default=Decimal("21"))
    payment_days: Mapped[int] = mapped_column(Integer, default=30)


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10), default="client")  # client | supplier | both
    tax_id: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    deals: Mapped[list["Deal"]] = relationship(back_populates="contact")


class Document(Base):
    """Factura o presupuesto (doc_type: invoice | quote)."""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(10), default="invoice")
    status: Mapped[str] = mapped_column(String(10), default="draft")
    series: Mapped[str] = mapped_column(String(10), default="")
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # se asigna al emitir
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date, default=date.today)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    irpf_rate: Mapped[Decimal] = mapped_column(Money, default=ZERO)
    notes: Mapped[str] = mapped_column(Text, default="")
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_quote_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    contact: Mapped[Contact | None] = relationship()
    lines: Mapped[list["Line"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Line.position"
    )

    @property
    def label(self) -> str:
        if self.number is None:
            return "Borrador" if self.doc_type == "invoice" else "Presupuesto (borrador)"
        return f"{self.series}-{self.issue_date.year}-{self.number:04d}"

    @property
    def statuses(self) -> dict:
        return INVOICE_STATUSES if self.doc_type == "invoice" else QUOTE_STATUSES

    @property
    def status_label(self) -> str:
        return self.statuses.get(self.status, self.status)

    @property
    def subtotal(self) -> Decimal:
        return sum((l.base for l in self.lines), ZERO)

    @property
    def vat_breakdown(self) -> list[tuple[Decimal, Decimal, Decimal]]:
        """[(tipo_iva, base, cuota)] ordenado por tipo."""
        groups: dict[Decimal, Decimal] = {}
        for l in self.lines:
            groups[l.vat_rate] = groups.get(l.vat_rate, ZERO) + l.base
        return [(rate, base, r2(base * rate / 100)) for rate, base in sorted(groups.items())]

    @property
    def vat_total(self) -> Decimal:
        return sum((q for _, _, q in self.vat_breakdown), ZERO)

    @property
    def irpf_total(self) -> Decimal:
        return r2(self.subtotal * self.irpf_rate / 100)

    @property
    def total(self) -> Decimal:
        return r2(self.subtotal + self.vat_total - self.irpf_total)

    @property
    def overdue(self) -> bool:
        return (
            self.doc_type == "invoice" and self.status == "issued"
            and self.due_date is not None and self.due_date < date.today()
        )


class Line(Base):
    __tablename__ = "lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Money, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Money, default=ZERO)
    discount: Mapped[Decimal] = mapped_column(Money, default=ZERO)  # %
    vat_rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("21"))

    document: Mapped[Document] = relationship(back_populates="lines")

    @property
    def base(self) -> Decimal:
        return r2(self.quantity * self.unit_price * (Decimal(100) - self.discount) / 100)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    reference: Mapped[str] = mapped_column(String(100), default="")  # n.º factura del proveedor
    concept: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(60), default="Otros")
    base: Mapped[Decimal] = mapped_column(Money, default=ZERO)
    vat_rate: Mapped[Decimal] = mapped_column(Money, default=Decimal("21"))
    irpf_rate: Mapped[Decimal] = mapped_column(Money, default=ZERO)
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    supplier: Mapped[Contact | None] = relationship()

    @property
    def vat_amount(self) -> Decimal:
        return r2(self.base * self.vat_rate / 100)

    @property
    def irpf_amount(self) -> Decimal:
        return r2(self.base * self.irpf_rate / 100)

    @property
    def total(self) -> Decimal:
        return r2(self.base + self.vat_amount - self.irpf_amount)


class Deal(Base):
    """Oportunidad del embudo de ventas."""
    __tablename__ = "deals"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    value: Mapped[Decimal] = mapped_column(Money, default=ZERO)
    stage: Mapped[str] = mapped_column(String(20), default="nuevo")
    expected_close: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    contact: Mapped[Contact | None] = relationship(back_populates="deals")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan", order_by="Activity.created_at.desc()"
    )


class Activity(Base):
    """Notas / seguimiento de una oportunidad."""
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    deal: Mapped[Deal] = relationship(back_populates="activities")
