from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

ZERO = Decimal("0.00")


def d(value, default="0") -> Decimal:
    """Convierte texto/numero a Decimal aceptando coma decimal."""
    if value is None or value == "":
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        return Decimal(default)


def r2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt(value) -> str:
    """1234.5 -> '1.234,50' (formato espanol)."""
    s = f"{r2(d(value)):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
