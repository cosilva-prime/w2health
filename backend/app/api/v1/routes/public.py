"""Rotas PÚBLICAS (sem autenticação) — somente o necessário para a tela de login.

* `GET /public/branding?tenant=<code>` — identidade da tela de login. Código desconhecido,
  inativo ou suspenso devolve o branding PADRÃO W2Health (mesma resposta), para não
  permitir enumeração de clientes.
* `GET /public/branding/{tenant}/{kind}` — logo/favicon já validados no upload, servidos
  com o content-type detectado e `nosniff`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Tenant, TenantBrandingAsset
from app.saas import branding
from app.security.errors import ApiError

router = APIRouter(prefix="/public", tags=["Público"])


@router.get("/branding", summary="Branding da tela de login (sem dados sensíveis)")
def login_branding(tenant: str | None = Query(None, max_length=40), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, tenant) if tenant else None
    if t is not None and t.status != "ACTIVE":
        t = None
    b = branding.effective(db, t)
    return {k: b[k] for k in ("product_name", "primary_color", "accent_color", "login_title",
                              "login_message", "logo_url", "favicon_url")}


@router.get("/branding/{tenant_id}/{kind}", summary="Logo/favicon do tenant")
def branding_asset(tenant_id: str, kind: str, db: Session = Depends(get_db)) -> Response:
    if kind not in ("logo", "favicon"):
        raise ApiError("not_found")
    t = db.get(Tenant, tenant_id)
    a = db.get(TenantBrandingAsset, (tenant_id, kind)) if t is not None and t.status == "ACTIVE" else None
    if a is None:
        raise ApiError("not_found")
    return Response(content=a.data, media_type=a.content_type, headers={
        "Cache-Control": "public, max-age=3600",
        "Content-Security-Policy": "default-src 'none'",
        "Content-Disposition": "inline",
    })
