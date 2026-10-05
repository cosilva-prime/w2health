"""Segurança da Fundação SaaS V1: senhas, tokens, criptografia, MFA, RBAC e dependências.

Fluxo de autorização de toda requisição autenticada (ver `deps.py`):

    JWT → User → Tenant Membership → TenantContext → RBAC → Feature Guard → Repository → Banco
"""
