# W2Health — Fundação SaaS V1

> Transforma o W2Health de aplicação analítica demonstrativa em base SaaS segura e
> administrável, **sem alterar o motor de Healthcare Decision Intelligence**.
> Baseline: [V1_SAAS_BASELINE.md](V1_SAAS_BASELINE.md). Segurança:
> [SECURITY_AND_TENANT_ISOLATION.md](SECURITY_AND_TENANT_ISOLATION.md) ·
> [THREAT_MODEL_V1.md](THREAT_MODEL_V1.md). Acesso: [RBAC_MATRIX.md](RBAC_MATRIX.md) ·
> [FEATURE_CATALOG.md](FEATURE_CATALOG.md). Banco: [DATABASE_EVOLUTION_V1.md](DATABASE_EVOLUTION_V1.md).
> Próximos passos: [V1_ROADMAP.md](V1_ROADMAP.md).

## 1. Princípios aplicados

| Princípio | Como ficou no código |
|---|---|
| O produto não conhece sistemas de origem | inalterado: motor lê só o modelo canônico/serving; teste source-agnostic preservado |
| O produto conhece TENANTS | `TenantContext` em toda requisição; filtro + RLS; seed/jobs tenant-scoped |
| O produto conhece FEATURES, não planos | `has_feature` único; planos são só a origem padrão; teste proíbe `plan ==`/`role ==` |

## 2. Arquitetura

```
frontend (Next.js) ── Bearer (memória) + cookie httpOnly de refresh ──▶ FastAPI
                                                                          │
   /api/public  ─ branding de login (sem auth)                            │
   /api/auth    ─ login, MFA, refresh, logout, switch-tenant, /me         │
   /api/admin   ─ plataforma Works2Data (SUPER_ADMIN)                     │
   /api/tenant  ─ administração do próprio tenant (TENANT_ADMIN)          │
   /api/executive, /api/analytics/*, /api/config/* ─ módulos analíticos   │
                                                                          ▼
     app/security  (tokens, senhas, MFA, RBAC, deps)  app/saas (features, branding,
     settings, segredos, auditoria, usuários, tenants)  app/analytics (motor — intacto)
                                                                          │
                     app/repositories (fail-closed por tenant) ──────────▶ PostgreSQL
                                                     papel w2health_app + RLS (data plane)
```

**Data plane** (`Base`, 24 tabelas + calendário) × **control plane** (`ControlBase`,
14 tabelas). Ver [DATABASE_EVOLUTION_V1.md](DATABASE_EVOLUTION_V1.md).

## 3. O que foi entregue

| # | Item | Status |
|---|---|---|
| 1 | Multi-tenancy real (contexto por requisição, filtro em 100% das consultas) | ✅ |
| 2 | Autenticação (argon2id, JWT curto, refresh rotativo, logout, revogação) | ✅ |
| 3 | RBAC por permissões (4 papéis) | ✅ |
| 4 | MFA TOTP completo (setup, QR, confirmação, desafio, obrigatoriedade, reset auditado) | ✅ |
| 5 | Planos | ✅ (matriz demonstrativa configurável) |
| 6 | Features/capabilities + kill switch global | ✅ |
| 7 | Entitlements por tenant (overrides com motivo) | ✅ |
| 8 | Branding por tenant (limitado e validado) | ✅ |
| 9 | Configurações por tenant (catálogo fechado) + cofre de segredos | ✅ |
| 10 | Auditoria (append-only para a aplicação) | ✅ |
| 11 | Área administrativa Works2Data (`/admin`) | ✅ |
| 12 | Área administrativa do tenant (`/gestao`) | ✅ |
| 13 | Segurança e isolamento (aplicação + RLS + testes) | ✅ |
| 14 | Identidade visual estrutural (design system mínimo, tema por tenant) | ✅ |
| 15 | Transparência de indicadores | ✅ (KPIs principais) |
| 16 | Testes de segurança/isolamento | ✅ 112 novos |

## 4. Fluxos principais

**Login**: e-mail+senha → (troca obrigatória de senha) → (código MFA | configuração de
MFA obrigatória) → sessão no tenant escolhido (vínculo ativo; SUPER_ADMIN sem tenant fica
em modo plataforma). Detalhe em SECURITY §3–4.

**Troca de tenant**: seletor "Ambiente" no topo → `POST /auth/switch-tenant` (valida
vínculo; SUPER_ADMIN audita `platform.tenant_access`) → novo access token → cache do
frontend limpo.

**Administração Works2Data** (`/admin`): Tenants (lista, criação, visão completa com
identificação, plano, status, features com override, usuários, branding, configurações,
segredos write-only e auditoria recente), Planos (matriz), Features (kill switch),
Usuários (status, reset de senha/MFA), Branding, Configurações, Auditoria.

**Administração do tenant** (`/gestao`): ambiente (plano e recursos, somente leitura),
usuários, identidade visual (se `custom_branding`), configurações, auditoria; regras de
alerta continuam em `/configuracao/insights`.

## 5. Módulos analíticos — o que mudou (e o que NÃO mudou)

| Módulo | Feature | Mudança |
|---|---|---|
| Visão Executiva | `executive_overview` | fatores de atenção filtrados por features; transparência nos KPIs |
| Sinistralidade (+ procedimentos) | `loss_ratio_intelligence` (+ `financial_composition`, `advanced_explanations`) | drill/explicação saneados; transparência |
| Contratos | `contract_intelligence` | alertas e beneficiários do detalhe saneados |
| Prestadores | `provider_intelligence` | gating |
| Beneficiários | `beneficiary_intelligence` | gating |
| Insights & Alertas | `insights`, `alerts` | filtro de deep-links; escrita de regras exige `alert_rules:write` e é auditada |

**Nenhuma fórmula, limiar, cenário sintético ou classificação foi alterado.**
FATO / HIPÓTESE / A INVESTIGAR e a confiança explícita permanecem exatamente como na
v1.1 (`app/analytics/cohorts.py` intocado; `CausasPanel` intocado). Os 125 testes do
motor/API anteriores continuam verdes.

## 6. Transparência

`GET /api/meta/transparencia` devolve definição, fórmula e composição de cada KPI (as
fórmulas efetivamente implementadas) e a **procedência real**: última carga
(`seed_manifest` ou `ingestion_runs`), janela, camada e natureza do dado (sintético ou do
cliente). O componente `KpiInfo` (ⓘ) mostra isso junto da competência e dos filtros
aplicados; o que não existe aparece como "Não disponível".

## 7. Estados de UX padronizados

`Loading` · `Empty` · `Error` · `Forbidden` · `FeatureUnavailable` · `TenantSuspended` ·
`SessionExpired` (+ seleção de ambiente para SUPER_ADMIN). O backend devolve `code`
estável em todo erro; `DataState`/`ApiErrorState` escolhem o estado. Nenhuma mensagem
expõe stack trace ou estrutura interna.

## 8. Compatibilidade com a Data Platform

Nada da arquitetura Raw → Silver → Gold → Serving foi redesenhado. A fundação é
compatível: o serving continua sendo as `agg_*` por tenant; `source_connections.config`
passa a referenciar segredos do cofre (`tenant_secrets`); pipelines futuros devem amarrar o
tenant (`bind_tenant`) e rodar com papel de pipeline próprio (ver roadmap).

## 9. Como rodar

```bash
./scripts/gen-secrets.ps1                 # .env com segredos aleatórios (não versionado)
docker compose up -d --build              # migrations no start do backend
make seed                                 # Operadora Vida Plena (sintética)
make seed-tenant-b                        # 2º tenant sintético (opcional)
make bootstrap                            # planos/features + usuários demo (senhas exibidas uma vez)
# http://localhost:3000/login
```

Usuários demo: `superadmin@works2data.example` (MFA obrigatório no 1º login),
`admin@vidaplena.example`, `gestor@vidaplena.example`, `leitor@vidaplena.example`,
`admin@horizonte.example`. Senhas: geradas no bootstrap (ou `DEMO_USER_PASSWORD` em dev).
