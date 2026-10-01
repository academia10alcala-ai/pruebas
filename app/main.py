import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models
from .db import Base, engine, SessionLocal, ensure_columns
from .routers import brand, contacts, crm, dashboard, documents, expenses, settings
from .web import get_company, require_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_columns()
    with SessionLocal() as db:
        get_company(db)
    yield


app = FastAPI(title="Gestión", lifespan=lifespan, dependencies=[Depends(require_auth)])
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


for module in (brand, dashboard, contacts, documents, expenses, crm, settings):
    app.include_router(module.router)
