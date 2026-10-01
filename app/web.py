import os
import secrets
from datetime import date

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models
from .money import fmt

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
templates.env.filters["money"] = fmt
templates.env.globals.update(
    STAGES=models.STAGES,
    EXPENSE_CATEGORIES=models.EXPENSE_CATEGORIES,
    today=date.today,
)

_basic = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(_basic)):
    """Si APP_USER y APP_PASSWORD estan definidos, exige autenticacion basica."""
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


def render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)
