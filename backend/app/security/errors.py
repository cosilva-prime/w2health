"""Erros HTTP padronizados com `code` estável — o frontend decide o estado de UX pelo código.

Corpo: `{"detail": "<mensagem segura>", "code": "<código>"}`. Mensagens nunca revelam
estrutura interna, existência de conta, ids de outro tenant ou stack trace.

| code                    | HTTP | estado de UX                        |
|-------------------------|------|-------------------------------------|
| not_authenticated       | 401  | redireciona ao login                |
| session_expired         | 401  | "Sessão expirada" + login           |
| invalid_credentials     | 401  | erro no formulário de login         |
| forbidden               | 403  | "Acesso não permitido"              |
| feature_unavailable     | 403  | "Recurso não disponível no plano"   |
| capability_not_ready    | 403  | "Contratado, mas dados ainda não disponíveis" |
| tenant_suspended        | 403  | "Ambiente suspenso"                 |
| tenant_required         | 403  | seletor de ambiente (SUPER_ADMIN)   |
| no_tenant_access        | 403  | "Sem acesso a nenhum ambiente"      |
| mfa_setup_required      | 403  | fluxo de configuração de MFA        |
| rate_limited            | 429  | "Muitas tentativas"                 |
| not_found               | 404  | "Não encontrado"                    |
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

_DEFAULT_MSG = {
    "not_authenticated": "Autenticação necessária.",
    "session_expired": "Sua sessão expirou. Entre novamente.",
    "invalid_credentials": "Credenciais inválidas ou acesso temporariamente bloqueado.",
    "forbidden": "Você não tem permissão para esta ação.",
    "feature_unavailable": "Este recurso não está disponível no plano contratado.",
    "capability_not_ready": "Recurso contratado, mas os dados necessários ainda não estão disponíveis.",
    "tenant_suspended": "Este ambiente está suspenso. Procure o administrador.",
    "tenant_required": "Selecione um ambiente (tenant) para continuar.",
    "no_tenant_access": "Sua conta não tem acesso a nenhum ambiente ativo.",
    "mfa_setup_required": "Este ambiente exige autenticação em dois fatores.",
    "rate_limited": "Muitas tentativas. Aguarde um instante e tente novamente.",
    "not_found": "Recurso não encontrado.",
    "conflict": "Conflito com o estado atual.",
    "invalid_request": "Requisição inválida.",
    "service_unavailable": "Serviço temporariamente indisponível.",
}

_STATUS = {
    "not_authenticated": 401, "session_expired": 401, "invalid_credentials": 401,
    "forbidden": 403, "feature_unavailable": 403, "capability_not_ready": 403, "tenant_suspended": 403,
    "tenant_required": 403, "no_tenant_access": 403, "mfa_setup_required": 403,
    "rate_limited": 429, "not_found": 404, "conflict": 409, "invalid_request": 422,
    "service_unavailable": 503,
}


class ApiError(HTTPException):
    def __init__(self, code: str, detail: str | None = None, *, extra: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> None:
        status = _STATUS.get(code, 400)
        if status == 401 and headers is None:
            headers = {"WWW-Authenticate": "Bearer"}
        super().__init__(status_code=status, detail=detail or _DEFAULT_MSG.get(code, code),
                         headers=headers)
        self.code = code
        self.extra = extra or {}
