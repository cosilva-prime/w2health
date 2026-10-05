"""Branding por tenant — white-label LIMITADO e seguro.

O que um tenant pode personalizar:
  * nome do produto exibido (texto puro, ≤ 60);
  * cor primária e de destaque (hex `#rrggbb`; a primária precisa de contraste ≥ 4.5:1
    com texto branco — WCAG AA — porque é fundo da navegação);
  * título e mensagem da tela de login (texto puro);
  * logo e favicon (PNG/JPEG/WebP, ≤ 256 KB, tipo validado pela ASSINATURA dos bytes,
    nunca pela extensão/Content-Type informado; SVG recusado por poder conter script).

Nada de CSS, HTML ou JavaScript arbitrário. O frontend aplica os valores como variáveis CSS
dentro de um ThemeProvider controlado.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Tenant, TenantBranding, TenantBrandingAsset

#: Identidade padrão W2Health · Works2Data (navy/gold — tailwind.config.ts).
DEFAULT_BRANDING = {
    "product_name": "W2Health Intelligence",
    "primary_color": "#0b1b32",
    "accent_color": "#d3a63e",
    "login_title": "W2Health Intelligence",
    "login_message": "Decision Intelligence Platform for Healthcare",
}

MAX_ASSET_BYTES = 256 * 1024
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")

TEXT_LIMITS = {"product_name": 60, "login_title": 80, "login_message": 300}


class BrandingError(ValueError):
    pass


def _luminancia(hex_color: str) -> float:
    def canal(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste_com_branco(hex_color: str) -> float:
    return 1.05 / (_luminancia(hex_color) + 0.05)


def normalize_color(value: str | None, *, campo: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _HEX.match(value):
        raise BrandingError(f"{campo}: use o formato hexadecimal #rrggbb")
    v = value.lower()
    if campo == "primary_color" and contraste_com_branco(v) < 4.5:
        raise BrandingError("primary_color: contraste insuficiente com texto branco (mín. 4.5:1)")
    return v


def normalize_text(value: str | None, *, campo: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BrandingError(f"{campo}: texto inválido")
    v = value.strip()
    if not v:
        return None
    if len(v) > TEXT_LIMITS[campo]:
        raise BrandingError(f"{campo}: máximo de {TEXT_LIMITS[campo]} caracteres")
    if _CONTROL.search(v):
        raise BrandingError(f"{campo}: caracteres não permitidos")
    return v


def sniff_image(data: bytes) -> str:
    """Content-type pela assinatura dos bytes. Levanta se não for PNG/JPEG/WebP."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise BrandingError("imagem deve ser PNG, JPEG ou WebP")


def effective(session: Session, tenant: Tenant | None) -> dict[str, Any]:
    """Branding efetivo (padrão W2Health + overrides do tenant)."""
    out: dict[str, Any] = {**DEFAULT_BRANDING, "logo_url": None, "favicon_url": None,
                           "customized": False}
    if tenant is None:
        return out
    b = session.get(TenantBranding, tenant.id)
    if b is not None:
        for campo in ("product_name", "primary_color", "accent_color", "login_title", "login_message"):
            v = getattr(b, campo)
            if v:
                out[campo] = v
                out["customized"] = True
    for kind in ("logo", "favicon"):
        a = session.get(TenantBrandingAsset, (tenant.id, kind))
        if a is not None:
            out[f"{kind}_url"] = f"/public/branding/{tenant.id}/{kind}?v={a.sha256[:12]}"
            out["customized"] = True
    return out


def raw(session: Session, tenant_id: str) -> dict[str, Any]:
    b = session.get(TenantBranding, tenant_id)
    campos = ("product_name", "primary_color", "accent_color", "login_title", "login_message")
    return {c: (getattr(b, c) if b else None) for c in campos}


def update(session: Session, tenant_id: str, dados: dict[str, Any], *, user_id=None) -> dict[str, Any]:
    """Aplica somente os campos informados (validados). Retorna o estado bruto novo."""
    b = session.get(TenantBranding, tenant_id)
    if b is None:
        b = TenantBranding(tenant_id=tenant_id)
        session.add(b)
    for campo, valor in dados.items():
        if campo in ("primary_color", "accent_color"):
            setattr(b, campo, normalize_color(valor, campo=campo))
        elif campo in TEXT_LIMITS:
            setattr(b, campo, normalize_text(valor, campo=campo))
        else:
            raise BrandingError(f"campo não permitido: {campo}")
    b.updated_by = user_id
    session.flush()
    return raw(session, tenant_id)


def set_asset(session: Session, tenant_id: str, kind: str, data: bytes, *, user_id=None) -> dict:
    if kind not in ("logo", "favicon"):
        raise BrandingError("tipo de imagem inválido")
    if not data or len(data) > MAX_ASSET_BYTES:
        raise BrandingError("imagem vazia ou maior que 256 KB")
    ctype = sniff_image(data)
    digest = hashlib.sha256(data).hexdigest()
    a = session.get(TenantBrandingAsset, (tenant_id, kind))
    if a is None:
        a = TenantBrandingAsset(tenant_id=tenant_id, kind=kind)
        session.add(a)
    a.content_type, a.data, a.sha256, a.size, a.updated_by = ctype, data, digest, len(data), user_id
    session.flush()
    return {"kind": kind, "content_type": ctype, "size": len(data), "sha256": digest}


def delete_asset(session: Session, tenant_id: str, kind: str) -> bool:
    a = session.get(TenantBrandingAsset, (tenant_id, kind))
    if a is None:
        return False
    session.delete(a)
    session.flush()
    return True
