"""Ponto de entrada da aplicação FastAPI do W2Health Intelligence.

Fundação SaaS V1: autenticação, contexto de tenant, RBAC, features, auditoria e
administração. Camadas transversais registradas aqui:

* middleware de requisição — `X-Request-ID`, IP/User-Agent para auditoria, headers de
  segurança e `Cache-Control: no-store` (respostas com dado de tenant nunca vão para cache
  compartilhado);
* tratadores de erro — corpo padronizado `{"detail", "code"}`; exceção não tratada vira
  500 genérico com `request_id` (sem stack trace, sem estrutura interna);
* validação de configuração — em produção/staging a API não sobe sem segredos.
"""

import logging
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, set_log_context
from app.core.tenant import TenantContextMissing
from app.saas.audit import RequestMeta, set_request_meta
from app.security.errors import ApiError

settings = get_settings()
log = logging.getLogger("app")

_REQ_ID = re.compile(r"^[A-Za-z0-9._-]{8,40}$")
_CODE_BY_STATUS = {400: "invalid_request", 401: "not_authenticated", 403: "forbidden",
                   404: "not_found", 405: "invalid_request", 409: "conflict",
                   422: "invalid_request", 429: "rate_limited", 503: "service_unavailable"}

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> Any:
    """Startup: logging + validação de configuração de segurança."""
    configure_logging()
    problemas = settings.validate_for_runtime()
    if problemas and settings.is_production_like:
        raise RuntimeError("Configuração de segurança inválida: " + "; ".join(problemas))
    for p in problemas:
        log.warning("configuração (desenvolvimento): %s", p)
    yield


def _client_ip(request: Request) -> str | None:
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def _body(detail: Any, code: str, request: Request, **extra: Any) -> dict:
    out = {"detail": detail, "code": code, **extra}
    rid = getattr(request.state, "request_id", None)
    if rid:
        out["request_id"] = rid
    return out


def create_app() -> FastAPI:
    """Factory da aplicação — facilita instâncias isoladas nos testes."""
    app = FastAPI(
        title=settings.project_name,
        description=(
            "Decision Intelligence Platform for Healthcare — API REST. "
            "Toda rota de dados exige autenticação e contexto de tenant."
        ),
        version=settings.version,
        lifespan=lifespan,
        # documentação interativa só fora de produção (reduz superfície exposta)
        docs_url=None if settings.is_production_like else "/docs",
        redoc_url=None if settings.is_production_like else "/redoc",
        openapi_url=None if settings.is_production_like else "/openapi.json",
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or ""
        rid = rid if _REQ_ID.match(rid) else uuid.uuid4().hex
        request.state.request_id = rid
        set_log_context(request_id=rid, correlation_id=rid)
        set_request_meta(RequestMeta(ip=_client_ip(request),
                                     user_agent=request.headers.get("user-agent"),
                                     request_id=rid))
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path.startswith(settings.api_v1_prefix):
            # assets públicos de branding definem o próprio cache
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.detail, exc.code, request, **exc.extra),
                            status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODE_BY_STATUS.get(exc.status_code, "error")
        return JSONResponse(_body(exc.detail, code, request), status_code=exc.status_code,
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        erros = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body(erros, "invalid_request", request), status_code=422)

    @app.exception_handler(TenantContextMissing)
    async def _sem_tenant(request: Request, exc: TenantContextMissing) -> JSONResponse:
        log.error("acesso a dado sem tenant no contexto: %s %s", request.method, request.url.path)
        return JSONResponse(_body("Erro interno.", "internal_error", request), status_code=500)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("erro não tratado em %s %s", request.method, request.url.path)
        return JSONResponse(_body("Erro interno.", "internal_error", request), status_code=500)

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Infraestrutura"], summary="Metadados da API")
    def root() -> dict[str, str]:
        return {
            "service": settings.project_name,
            "version": settings.version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
