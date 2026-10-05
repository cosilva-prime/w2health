# W2Health — Baseline antes da Fundação SaaS V1

> **Data:** 2026-10-05 · **Branch:** `v1.2` (commit `6fb37f8`) · **Revisão Alembic:** `b2d3f4a5c6e7`
>
> Fotografia do estado do produto **antes** de qualquer alteração da fase "Fundação SaaS V1".
> Serve de referência para medir o impacto da evolução e garantir que nada do motor
> analítico foi perdido. Documentos de evolução: [V1_SAAS_FOUNDATION.md](V1_SAAS_FOUNDATION.md),
> [DATABASE_EVOLUTION_V1.md](DATABASE_EVOLUTION_V1.md).

## 1. Baseline executado

| Item | Resultado |
|---|---|
| Suíte de testes backend (`pytest`) | **125 testes, 125 verdes, 0 pulados** (~56 s) |
| Contagem por arquivo | formulas 29 · api 20 · scenarios 20 · alerts 14 · cohorts 11 · composicao_dimensao 6 · contratos 6 · data_quality 5 · health 5 · multitenancy 5 · config 4 |
| Observação | `docs/V1.2.md` cita "120"; a contagem real coletada pelo pytest é **125** |
| Typecheck frontend (`tsc --noEmit`) | ✅ sem erros |
| Banco local (volume `w2health_pgdata`) | revisão `b2d3f4a5c6e7`, 1 tenant (`w2h-demo`), 328.778 eventos |
| Backup antes da evolução | `pg_dump -Fc` do banco local (fora do repositório) |
| Papéis do PostgreSQL | apenas `w2health` — **superusuário com BYPASSRLS**, usado pela aplicação |

## 2. O que já existe

### Backend (FastAPI · SQLAlchemy 2.0 síncrono · Alembic · PostgreSQL 16)
- **Monolito modular**: `api → analytics (motor) → repositories (SQL text()) → Postgres`.
- **Motor analítico** (`app/analytics/`): sinistralidade bruta/líquida, evolução, MoM/YoY/12m,
  decomposição numerador×denominador, contribuição por 10 dimensões, bridge Bennet/Laspeyres,
  composição financeira (bruta/glosa/coparticipação/líquida, 4 efeitos), concentração
  (top-k, Gini, Pareto), z-score de prestadores vs pares, sazonalidade, coortes com
  **FATO / HIPÓTESE / A_INVESTIGAR**, motor de insights, alertas configuráveis (catálogo fechado),
  Contract Intelligence, descritores de beneficiário (C5).
- **34 endpoints** (todos GET, exceto CRUD de `regras_alerta`).
- **Camada analítica materializada**: 5 tabelas `agg_*` reconstruídas por `app/seed/aggregate.py`
  (tenant-scoped).
- **Massa sintética**: gerador NumPy determinístico, 19 cenários com gabarito, operadora fictícia
  "Vida Plena".

### Multi-tenancy (parcial, v1.2)
- `tenant_id String(40)` (slug) via `TenantMixin` em **24 tabelas de dados**; `competencias` é
  calendário global; `tenants` é o cadastro.
- Chaves de negócio compostas `(tenant_id, natural)` — `BEN-000001` pode existir em 2 tenants.
- `app/core/tenant.py`: `ContextVar` com default `w2h-demo` — **não usado por nenhuma consulta**.
- Tabelas de controle da Data Platform (`source_connections`, `ingestion_runs`, …) — vazias.

### Frontend (Next.js 14 App Router · TypeScript · Tailwind · SWR · Recharts)
- 11 páginas: Visão Executiva, Sinistralidade, Contratos (+detalhe), Prestadores (+detalhe),
  Beneficiários (+detalhe), Insights, Configuração de alertas.
- Shell: Sidebar navy/gold Works2Data, Header com filtros globais (competência/comparação na URL),
  Breadcrumbs, banner permanente "Ambiente demonstrativo — dados sintéticos".
- Componentes base em `components/ui.tsx` (Card, Stat, Badge, DataState, EfeitoBadge, LinkButton).

### Data Platform (conceitual)
- `data_platform/`: 13 contratos canônicos YAML, mappings, SQL silver→gold→serving de referência,
  regras de qualidade executáveis. Nenhum pipeline roda.

## 3. O que está parcial

| Tema | Estado |
|---|---|
| `tenant_id` nas tabelas | ✅ coluna NOT NULL + índice · ❌ nenhuma query filtra |
| Tenant por request | ❌ constante `w2h-demo` |
| Cadastro `tenants` | colunas `id, nome, status ('ativo'), criado_em` — sem plano, sem `updated_at` |
| Seed multi-tenant | parametrizável por `SeedConfig.tenant_id`, **mas `wipe_dados` apaga TODOS os tenants** |
| `source_connections.config` | JSON "sem segredos em claro" — só convenção, sem cofre |
| Estados de UX | loading/erro/vazio existem; sem forbidden/feature/sessão/tenant suspenso |

## 4. O que está ausente

Autenticação · usuários · sessões/refresh · MFA · RBAC · planos · features/entitlements ·
branding por tenant · configurações por tenant · cofre de segredos · auditoria · área
administrativa · RLS · papel de banco sem privilégio · headers de segurança · tratamento
genérico de erro 500 · rate limit · testes de isolamento entre tenants.

## 5. Riscos encontrados (antes da evolução)

| # | Risco | Severidade |
|---|---|---|
| R1 | **Nenhuma consulta filtra por tenant** (~45 SQLs em `analytics_repo.py`, `insights.py`, `config_repo.py`, catálogos). Com 2 tenants, todas as telas misturariam dados. | P0 |
| R2 | `beneficiario_por_codigo` usa `scalar_one_or_none()` sem tenant → com `BEN-000001` em 2 tenants, **erro 500** (e, sem o erro, retornaria o beneficiário de outro tenant). Mesmo padrão em `_chave_pneumologia`. | P0 |
| R3 | Detalhes por id (`/prestadores/{id}`, `/contratos/{id}`, `/beneficiarios/{id}`, regras) sem verificação de dono → **IDOR** assim que houver 2 tenants. | P0 |
| R4 | Endpoints de escrita (`/config/regras-alerta`) **sem autenticação**. | P0 |
| R5 | Aplicação conecta como **superusuário** (`w2health`, BYPASSRLS) → RLS seria inócuo. | P0 |
| R6 | `TenantMixin` declara `server_default='w2h-demo'` (o banco já não tem o default — drift). Se reaplicado, INSERT sem tenant cairia silenciosamente no tenant demo. | P1 |
| R7 | `wipe_dados` do seed apaga todos os tenants. | P1 (dev) |
| R8 | Endpoints compostos (explain/insights/visão executiva) embutem dados de beneficiário e prestador — gating por feature precisa sanear a resposta, não só bloquear rotas. | P1 |
| R9 | Exceções não tratadas devolvem 500 padrão do Starlette; sem request id; sem `Cache-Control: no-store`. | P1 |
| R10 | `/analytics/gabarito` expõe o gabarito dos cenários sintéticos (QA) para qualquer chamador. | P2 |

## 6. Impacto esperado da evolução

- **Backend**: nova camada `app/security/` (auth, tokens, RBAC, contexto de tenant),
  `app/saas/` (planos, features, branding, settings, segredos, auditoria) e rotas `auth`,
  `admin`, `tenant`. Rotas analíticas passam a depender de `TenantContext` + permissão + feature.
- **Repositórios**: todas as consultas recebem filtro explícito de `tenant_id` lido do contexto
  da sessão — fail-closed se ausente. **Nenhuma fórmula muda.**
- **Banco**: migrations aditivas (control plane + RLS + papel `w2health_app`); dados existentes
  preservados (tenant demo continua sendo `w2h-demo`).
- **Testes**: fixtures adaptadas para autenticar (asserções antigas intactas) + suítes novas.
- **Frontend**: login, contexto de sessão, gating de navegação, áreas `/admin` e `/gestao`,
  tema por tenant, estados de UX padronizados, componente de transparência.

## 7. Decisões conservadoras tomadas a partir do baseline

1. **`tenant_id` continua sendo o slug** (`w2h-demo`) nas 24 tabelas de dados. Trocar para UUID
   exigiria reescrever 24 colunas, ~330 mil linhas e todo o seed sem ganho de segurança. O
   cadastro `tenants` ganha um `uuid` (identificador público estável) e o slug passa a ser o
   `code` imutável. Ver [DATABASE_EVOLUTION_V1.md](DATABASE_EVOLUTION_V1.md).
2. **Control plane separado do data plane**: tabelas globais (tenants, usuários, planos,
   features, auditoria…) usam uma metadata própria (`ControlBase`). O invariante "toda tabela
   de dados tem `tenant_id`" (teste `test_multitenancy.py`) continua válido sem exceções novas.
3. **Defesa em profundidade**: filtro explícito na aplicação **e** RLS no PostgreSQL com um
   papel sem privilégio (`w2health_app`); seed/migrations continuam com o papel dono.
