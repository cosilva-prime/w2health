# Segurança e Isolamento de Tenants — W2Health V1

> Documento de referência da Fundação SaaS V1. Substitui as seções "Fase 2" de
> [MULTI_TENANCY.md](MULTI_TENANCY.md) e a dívida "sem autenticação" de [V1.1.md](V1.1.md) /
> [V1.2.md](V1.2.md). Ameaças e mitigações em [THREAT_MODEL_V1.md](THREAT_MODEL_V1.md).

## 1. Princípios

1. **O produto conhece TENANTS**, não clientes. Todo dado de operadora tem `tenant_id`.
2. **Sem tenant válido, sem dado** (fail-closed) — na aplicação **e** no banco.
3. **O tenant efetivo vem do contexto autenticado**, nunca de parâmetro, cabeçalho, cookie
   ou corpo enviado pelo cliente.
4. **O código pergunta capacidades**: permissão (`require_permission`) e feature
   (`require_feature`). Nenhuma regra compara nome de papel ou de plano (teste
   `test_rbac.py::test_nenhuma_rota_compara_nome_de_papel_ou_plano`).
5. **O frontend não é autoridade**: esconde menu e mostra estados; o backend revalida tudo.

## 2. Cadeia de autorização de cada requisição

```
Authorization: Bearer <JWT>
   │  app/security/deps.py::get_principal
   ▼  assinatura HS256 (alg fixo), iss/aud/exp; relê do banco: usuário ACTIVE,
User   token_version igual, sessão não revogada/expirada, tid do token == tenant da sessão
   │  get_tenant_context
   ▼  tenant ACTIVE + vínculo ACTIVE (ou SUPER_ADMIN em acesso explícito e auditado)
TenantContext (tenant_id, papel, permissões, features efetivas)
   │  require_permission(...) → 403 forbidden (auditado como access.denied)
   ▼  require_feature(...)    → 403 feature_unavailable
Rota  ── get_tenant_db: sessão amarrada ao tenant (bind_tenant)
   │
   ▼  repositório: WHERE tenant_id = :t  (tenant_of(session) — levanta se ausente)
PostgreSQL ── RLS: tenant_id = current_setting('app.tenant_id', true)
```

Papel e permissões **não** são autoridade dentro do token: são relidos a cada requisição.
Mudar papel, desativar usuário, suspender tenant ou trocar senha tem efeito imediato.

## 3. Autenticação

| Item | Implementação |
|---|---|
| Senhas | argon2id (`argon2-cffi`), salt aleatório, rehash transparente; política: ≥ 12 caracteres, não previsível, não contém o identificador do e-mail |
| Enumeração de contas | mesma resposta/mesmo custo para e-mail inexistente (`DUMMY_HASH`); auditoria grava só hash curto do e-mail tentado |
| Força bruta | bloqueio por conta (5 falhas → 15 min, configurável) + limite por IP (20/min nas rotas `/auth/*`) |
| Access token | JWT HS256, 15 min, `sub/sid/tid/ver/typ/iss/aud/iat/exp/jti`; mantido **em memória** no frontend |
| Refresh token | opaco (256 bits), só o SHA-256 é persistido; cookie `httpOnly`, `SameSite=Strict`, `Path=/api/auth`, `Secure` obrigatório fora de dev; **rotação a cada uso** e **detecção de reuso** (reapresentar token consumido revoga a sessão inteira e audita `auth.refresh_reuse_detected`) |
| Sessão | validade absoluta de 12 h (refresh não estende); logout revoga sessão |
| Revogação global | `users.token_version` — incrementado em troca/reset de senha, reset de MFA e desativação |
| Etapas intermediárias | *challenge tokens* (5 min, `typ` = `mfa` / `password_change` / `mfa_setup`) não acessam dados |
| Usuário inativo | 403 genérico no login; tokens existentes caem na próxima requisição |
| Tenant suspenso | login → `tenant_suspended`; tokens existentes → 403 `tenant_suspended`; refresh revoga a sessão |

## 4. MFA (TOTP, RFC 6238)

- Setup: segredo de 160 bits gerado no servidor, **cifrado** (Fernet) em
  `users.mfa_pending_secret_enc`; QR Code SVG + chave manual exibidos **uma vez**.
- Confirmação com o primeiro código → `mfa_secret_enc`; `mfa_enabled = true`.
- Login com MFA: senha → challenge `mfa` → código. Janela ±30 s; **anti-replay**
  (`mfa_last_used_step`); falhas contam para o bloqueio da conta.
- **Obrigatório** para SUPER_ADMIN (`SUPER_ADMIN_REQUIRE_MFA=true`) e por tenant
  (`security.require_mfa`) — o usuário é levado à configuração no próximo login e não pode
  desabilitar enquanto for obrigatório.
- Desabilitar exige senha + código. Reset administrativo (plataforma, ou TENANT_ADMIN só
  para contas exclusivas do próprio tenant) exige motivo, é auditado e revoga sessões.
- Segredo nunca aparece em log, auditoria ou resposta (exceto o setup) — testado em
  `test_mfa.py`.
- Risco residual: sem códigos de recuperação nesta fase (recuperação = reset
  administrativo auditado). Ver [V1_ROADMAP.md](V1_ROADMAP.md).

## 5. Isolamento em três camadas

### 5.1 Aplicação (1ª camada)
- `app/db/tenant_scope.py`: `bind_tenant(session, tenant)` guarda o tenant em
  `session.info`; `tenant_of(session)` levanta `TenantContextMissing` se ausente.
- **Todas as 41 funções** de `analytics_repo.py`, `config_repo.py`, catálogos e
  transparência filtram `tenant_id = :t`. Buscas por id/código também filtram — id de
  outro tenant é indistinguível de inexistente (404, sem vazamento por erro).
- Guard de escrita do ORM (`before_flush`): objeto novo recebe o tenant do contexto; objeto
  com tenant diferente do contexto → erro. `tenant_id` nunca vem do payload.
- Uma sessão nunca troca de tenant.

### 5.2 Banco — Row-Level Security (2ª camada)
- Migration `e8b9c0d1f2a3`: `ENABLE` + `FORCE ROW LEVEL SECURITY` nas **24** tabelas do
  data plane (27 após a Fase 2), política `tenant_isolation` (`USING` + `WITH CHECK`).
- O tenant chega ao banco por `set_config('app.tenant_id', <tenant>, true)` executado no
  início de **cada transação** (listener `after_begin`). `true` = local à transação → não
  vaza entre requisições que reutilizam a conexão do pool (testado).
- A API conecta como **`w2health_app`**: NOSUPERUSER, NOBYPASSRLS, sem DDL; SELECT no data
  plane (escrita só em `regras_alerta`); CRUD no control plane; **`audit_logs` só
  SELECT/INSERT** (trilha imutável para a aplicação).
- Migrations/seed/CLI usam o papel dono (`DATABASE_ADMIN_URL`) e **não** são expostos por HTTP.
  O seed também amarra o tenant (funciona com `FORCE RLS` e dono não-superusuário).
- Control plane (usuários, vínculos, planos…) **não** tem RLS: o próprio login precisa ler
  vínculos de vários tenants. Proteção: dependências de RBAC + serviços confinados
  (`app/saas/users.py`).

### 5.3 Testes (3ª camada)
- `test_tenant_isolation.py` — Tenant A × Tenant B com `BEN-000001` e mesmos códigos de
  contrato/prestador/procedimento; cada caso roda **com RLS** e **somente com a aplicação**
  (papel dono, que ignora RLS) — 37 execuções.
- `test_rls.py` — SQL cru no papel de runtime: sem tenant → 0 linhas; JOIN sem filtro
  isolado; escrita cruzada rejeitada; UPDATE/DELETE cruzado afeta 0 linhas; runtime não
  escreve em fatos/agregados; auditoria append-only; lista de tabelas da migration = metadata.

## 6. SUPER_ADMIN e acesso de plataforma

- Papel de plataforma (`users.platform_role`), fora de `user_tenants`. Concedido **só pela
  CLI** com acesso ao banco (`python -m app.saas.cli create-superadmin`).
- Sem tenant selecionado, administra a plataforma mas **não vê dados** (`tenant_required`).
- Entrar em um tenant é um fluxo explícito (`POST /auth/switch-tenant`) e gera
  `platform.tenant_access` na auditoria. Exige MFA ativo.

## 7. Features (entitlements)

Resolução única em `app/saas/features.py` (global → override → plano). O backend bloqueia
rotas por router/rota **e** saneia respostas compostas (`app/saas/feature_filters.py`):
explicação, drill, coortes, insights, alertas e visão executiva omitem blocos de
beneficiário/prestador/contrato não contratados e declaram `restricoes_plano`.
Detalhe em [FEATURE_CATALOG.md](FEATURE_CATALOG.md).

## 8. Segredos e configurações

| Tipo | Onde | Proteção |
|---|---|---|
| Configuração funcional | `tenant_settings` (JSON) | catálogo fechado + validação + quem pode editar (`tenant_admin` × `platform`) |
| Credenciais de integração | `tenant_secrets` | Fernet (MultiFernet, rotação de chave); **write-only** na API; `reveal()` só para uso interno de conectores |
| Segredo MFA | `users.mfa_secret_enc` | Fernet |
| Chaves da aplicação | `JWT_SECRET_KEY`, `DATA_ENCRYPTION_KEY`, `APP_DB_PASSWORD` | variáveis de ambiente (`.env` gitignored); obrigatórias em produção/staging (a API não sobe sem elas) |

`source_connections.configuration` aceita só chaves conhecidas e não sensíveis por tipo;
credenciais entram apenas como `secret_reference` (`tenant:<chave>` no cofre do tenant;
`env:<NOME>` só em DEV; `vault:` reservado ao gerenciador de nuvem) — a referência nem é
exibida pela API (só `has_secret`). Abstração: `app/core/secrets.py`.

## 9. Auditoria

`audit_logs`: ator (id, e-mail, papel), tenant, ação, entidade/id, resultado
(`success`/`failure`/`denied`), IP, User-Agent, `request_id`, `details` saneado
(`app/saas/audit.sanitize` — chaves com cara de senha/token/segredo/código viram
`[REDACTED]`, textos truncados). Mutações administrativas gravam na **mesma transação**;
falhas de autenticação e negações gravam em transação independente.

Eventos: `auth.login`, `auth.login_failed`, `auth.login_blocked`, `auth.account_locked`,
`auth.mfa_failed`, `auth.logout`, `auth.tenant_switch`, `auth.refresh_reuse_detected`,
`access.denied`, `platform.tenant_access`, `mfa.setup_started`, `mfa.enabled`,
`mfa.disabled`, `mfa.admin_reset`, `user.*`, `tenant.*`, `plan.*`, `feature.updated`,
`tenant.feature_override`, `settings.updated`, `branding.*`, `secret.*`, `alert_rule.*`,
`platform.superadmin_created`.

## 10. Transporte, respostas e logs

- Headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy`, `Permissions-Policy`,
  `X-Request-ID`; **`Cache-Control: no-store`** em toda resposta de `/api`.
- CORS: origens explícitas, credenciais só para essas origens, métodos/cabeçalhos listados.
- Erros: corpo `{detail, code, request_id}`; exceção não tratada → 500 genérico (sem stack
  trace). Swagger/OpenAPI desligados em produção/staging.
- Logs: nunca senha, token, segredo, código MFA ou conteúdo clínico. Identificação de
  beneficiário é sempre o código pseudonimizado.
- Branding: só hex validado (primária com contraste ≥ 4,5:1), textos sem `<>`/controle,
  imagens PNG/JPEG/WebP validadas por assinatura (SVG recusado), servidas com `nosniff` e
  CSP `default-src 'none'`. Nenhum CSS/HTML/JS do cliente.

## 11. LGPD e dados sensíveis

- Dados de saúde (art. 11): isolamento em 3 camadas, menor privilégio, trilha de auditoria,
  códigos pseudonimizados, sem CPF/CNS no produto.
- Ainda **não** implementado (bloqueia cliente real — ver roadmap P0): TLS ponta a ponta no
  deploy, cifragem em repouso do volume, política de retenção/eliminação por tenant
  automatizada, backup restaurável por tenant.
- Acesso a dado **individual** de beneficiário é auditado desde a Fase 2
  (`data.beneficiary.*`: quem, qual beneficiário — id técnico —, quando; sem conteúdo clínico).

## 12. Backups

**Não existe backup de produção.** Existe um teste local de backup/restore (banco + RAW,
contagens por tenant, RLS preservada) — [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md).
Para produção: backup gerenciado com cifragem, retenção definida em contrato e restauração
**por tenant** automatizada e testada antes do primeiro cliente — P0.

## 13. Como verificar

```bash
cd backend && uv run pytest tests/test_tenant_isolation.py tests/test_rls.py tests/test_auth.py \
    tests/test_mfa.py tests/test_rbac.py tests/test_features.py tests/test_admin.py tests/test_security.py
```

## 14. Fase 2 — Data Platform

| Controle | Implementação | Teste |
|---|---|---|
| Pipeline com tenant explícito | `PipelineContext`; tenant inexistente/suspenso → erro; não existe "todos os tenants" | `test_pipeline_sem_tenant_falha` |
| Papel de pipeline sem privilégio | `w2health_pipeline`: NOSUPERUSER, NOBYPASSRLS, sem DDL, sem acesso a usuários/sessões/segredos; sem `DATABASE_PIPELINE_URL` o pipeline não roda (sem fallback para o dono) | `test_papel_de_pipeline_sem_privilegio_e_sob_rls` |
| RLS nas novas tabelas | `raw_objects`, `reconciliation_results`, `capability_readiness` (total: 27 tabelas com ENABLE+FORCE) | `test_rls.py` (lista da migration = metadata) |
| Fonte de outro tenant | id de fonte de A usado no caminho de B → recusado ("fonte inexistente", invisível por RLS); ingestões e RAW de B invisíveis no contexto de A | `test_fonte_de_outro_tenant_nao_e_utilizavel` |
| Upload controlado | só SUPER_ADMIN; nome/extensão/tamanho/quantidade/encoding/estrutura validados; binário e path traversal recusados; conteúdo nunca executado | `test_validacao_de_arquivo_recusa_entradas_inseguras`, `test_csv_malformado_e_recusado_sem_executar` |
| RAW | prefixo por tenant, chave validada, imutável, fora de pasta servida | `test_raw_storage_e_imutavel_e_por_tenant`, `test_raw_key_recusa_path_traversal` |
| Segredos de fonte | nunca em `configuration`; nunca exibidos | `test_admin_integracoes_nao_exibe_segredo` |
| Auditoria sem conteúdo clínico | carga, fonte, onboarding e leitura individual auditados só com metadados | `test_carga_e_auditada`, `test_acesso_individual_e_auditado_sem_conteudo_clinico` |
| MFA recovery codes | 10 códigos, argon2id, uso único, regeneração invalida os anteriores, auditado sem o código, reset administrativo apaga | `test_phase2_security.py` |
| Rate limit compartilhado | `auth_rate_limits` no banco (chave = SHA-256 do identificador/IP, nunca em claro) | `test_rate_limit_compartilhado_no_banco` |
| Logs estruturados | JSON com `request_id`, tenant, pipeline/ingestão; chaves sensíveis `[REDACTED]` | `test_log_estruturado_com_correlacao_e_sem_segredo` |
| Dependências | `scripts/security-check.ps1`; achados e decisões em [DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md) | — |

Novos eventos de auditoria: `pipeline.ingestion_completed|failed|duplicate`,
`integration.source_created|source_status|source_validated|readiness_refreshed|onboarding_decision`,
`data.beneficiary.*`, `mfa.recovery_code_used`, `mfa.recovery_codes_generated`.
