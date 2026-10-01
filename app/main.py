import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models
from .db import Base, engine, SessionLocal
from .routers import contacts, crm, dashboard, documents, expenses, settings
from .web import get_company, require_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        get_company(db)
    yield


app = FastAPI(title="Gestión", lifespan=lifespan, dependencies=[Depends(require_auth)])
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

for module in (dashboard, contacts, documents, expenses, crm, settings):
    app.include_router(module.router)
