from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..web import brand, get_company

router = APIRouter()


@router.get("/logo")
def logo(db: Session = Depends(get_db)):
    company = get_company(db)
    if not company.logo:
        return Response(status_code=404)
    return Response(company.logo, media_type=company.logo_mime or "image/png",
                    headers={"Cache-Control": "private, max-age=300"})


@router.get("/manifest.webmanifest")
def manifest(db: Session = Depends(get_db)):
    """Permite instalar la app en el movil/tablet/PC (\"Anadir a pantalla de inicio\")."""
    company = get_company(db)
    b = brand(company)
    data = {
        "name": company.name, "short_name": company.name[:12], "start_url": "/", "scope": "/",
        "display": "standalone", "lang": "es", "background_color": "#ffffff", "theme_color": b["color2"],
    }
    if company.logo and company.logo_mime == "image/png":
        data["icons"] = [{"src": "/logo", "sizes": "512x512", "type": "image/png", "purpose": "any"}]
    return JSONResponse(data, media_type="application/manifest+json")
