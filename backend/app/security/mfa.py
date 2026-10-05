"""MFA por TOTP (RFC 6238) — pyotp + QR Code SVG (segno, sem dependência de imagem).

* Segredo de 160 bits (base32), cifrado em repouso; exibido UMA vez ao usuário no setup.
* Janela de ±1 passo (30 s) para tolerar relógio; **anti-replay**: um time-step já aceito
  não é aceito de novo (`mfa_last_used_step`).
* Nada deste módulo loga segredo ou código.
"""

from __future__ import annotations

import time

import pyotp
import segno

ISSUER = "W2Health"
_STEP = 30


def new_secret() -> str:
    return pyotp.random_base32(length=32)


def provisioning_uri(secret: str, account: str, issuer: str = ISSUER) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=issuer)


def qr_svg_data_uri(uri: str) -> str:
    return segno.make(uri, error="m").svg_data_uri(scale=5, border=2)


def verify(secret: str, code: str, last_used_step: int | None, *, now: float | None = None) -> int | None:
    """Valida `code`. Retorna o time-step aceito (para gravar) ou None se inválido/reusado."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    agora = time.time() if now is None else now
    passo_atual = int(agora // _STEP)
    for delta in (0, -1, 1):
        passo = passo_atual + delta
        if last_used_step is not None and passo <= last_used_step:
            continue
        if pyotp.utils.strings_equal(totp.at(passo * _STEP), code):
            return passo
    return None
