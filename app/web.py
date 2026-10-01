import os
import re
import secrets
from datetime import date

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models
from .db import SessionLocal
from .money import fmt

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
templates.env.filters["money"] = fmt
templates.env.globals.update(
    STAGES=models.STAGES,
    EXPENSE_CATEGORIES=models.EXPENSE_CATEGORIES,
    today=date.today,
)

_basic = HTTPBasic(auto_error=False)


def require_auth(request: Request, credentials: HTTPBasicCredentials | None = Depends(_basic)):
    """Si APP_USER y APP_PASSWORD estan definidos, exige autenticacion basica (salvo /healthz)."""
    if request.url.path == "/healthz":
        return
    user, password = os.environ.get("APP_USER"), os.environ.get("APP_PASSWORD")
    if not user or not password:
        return
    ok = (
        credentials is not None
        and secrets.compare_digest(credentials.username, user)
        and secrets.compare_digest(credentials.password, password)
    )
    if not ok:
        raise HTTPException(401, "Autenticación requerida", headers={"WWW-Authenticate": "Basic"})


def get_company(db: Session) -> models.Company:
    company = db.get(models.Company, 1)
    if company is None:
        company = models.Company(id=1)
        db.add(company)
        db.commit()
    return company


def parse_date(value: str | None):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def valid_color(value: str | None, fallback: str) -> str:
    return value if value and HEX.match(value) else fallback


def brand(company: models.Company) -> dict:
    """Colores y logo de la marca; calcula si el texto sobre el color principal debe ser claro u oscuro."""
    color = valid_color(company.brand_color, "#2563eb")
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return {
        "name": company.name, "color": color, "color2": valid_color(company.brand_color2, "#1f2937"),
        "on_color": "#111827" if luminance > 0.6 else "#ffffff",
        "logo_version": len(company.logo) if company.logo else 0,
    }


def render(request: Request, name: str, **ctx):
    with SessionLocal() as db:
        ctx["brand"] = brand(get_company(db))
    return templates.TemplateResponse(request, name, ctx)
