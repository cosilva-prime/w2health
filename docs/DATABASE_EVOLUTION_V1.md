# Evolução do Banco — Fundação SaaS V1

> Revisões: `b2d3f4a5c6e7` (v1.2) → **`c7a1e2b3d4f5`** → **`e8b9c0d1f2a3`** (head).
> Ambas aditivas, com `downgrade` testado (ida e volta no banco com a massa da v1.2).
> `alembic check` sem drift após a evolução.

## 1. Estratégia (sem migration destrutiva)

O banco da v1.2 já tinha `tenant_id String(40) NOT NULL` + índice nas 24 tabelas de dados,
todas preenchidas com `w2h-demo`, e nenhuma linha com `tenant_id` nulo. Por isso a
estratégia pedida (tenant demo → backfill → coluna → índices → constraints → NOT NULL) já
estava cumprida para a coluna em si; esta fase completou o restante:

| Passo | Como |
|---|---|
| 1. Tenant demonstrativo | `tenants.w2h-demo` existente: status `ativo → ACTIVE`, nome → "Operadora Vida Plena", `is_synthetic = true` |
| 2. Backfill | plano ENTERPRISE para `w2h-demo` (mantém todas as funcionalidades) |
| 3. Coluna `tenant_id` | já existia; migration remove qualquer `DEFAULT` remanescente (fail-closed) |
| 4. Verificação | a migration **aborta** se houver `tenant_id` sem cadastro em `tenants` |
| 5. Índices | `(tenant_id, competencia)` e `(tenant_id, id_beneficiario)` na fato; `(tenant_id, id_beneficiario)` em `agg_beneficiario_competencia` |
| 6. Constraints | CHECK de status e de formato do código do tenant; FK `tenants.plan_id` |
| 7. RLS | revisão separada (`e8b9c0d1f2a3`) para revisão independente |

## 2. Decisões de alto impacto (conservadoras)

1. **`tenant_id` continua sendo o slug** (`w2h-demo`), não UUID. Converter exigiria
   reescrever 24 colunas e ~330 mil linhas, sem ganho de segurança. `tenants.id` é o
   **código imutável**; `tenants.uuid` (gerado) é o identificador público estável.
   Consequência: o código do tenant não pode ser renomeado (CHECK + ausência de rota).
2. **Sem FK `tenant_id → tenants.id` nas 24 tabelas do data plane** nesta fase. Motivo:
   preservar o teste histórico `test_chave_de_negocio_e_composta_sem_colisao` (insere
   tenants fictícios sem cadastro) e evitar lock longo na fato. Mitigação: verificação de
   órfãos na migration + RLS + `before_flush`. Registrado como P1 no roadmap.
3. **Control plane em metadata separada** (`ControlBase`) — mantém o invariante "toda
   tabela do data plane tem `tenant_id`" sem exceções novas.
4. **Renomes em `tenants`** (`nome→name`, `criado_em→created_at`) por `ALTER ... RENAME`
   (sem perda de dado), alinhando ao modelo conceitual da fase.

## 3. Revisão `c7a1e2b3d4f5` — control plane

| Tabela | Papel |
|---|---|
| `tenants` (alterada) | + `uuid`, `legal_name`, `plan_id`, `is_synthetic`, `updated_at`; status `ACTIVE/SUSPENDED/INACTIVE` |
| `users` | identidade, hash argon2id, papel de plataforma, MFA cifrado, bloqueio, `token_version` |
| `user_tenants` | vínculo usuário × tenant com papel e status (PK composta) |
| `auth_sessions` | sessões de login (validade absoluta, revogação) |
| `refresh_tokens` | hash SHA-256 dos refresh tokens, rotação (`used_at`) |
| `plans`, `features`, `plan_features` | catálogo comercial (seed do catálogo na própria migration) |
| `tenant_features` | override por tenant com motivo |
| `tenant_branding`, `tenant_branding_assets` | white-label limitado (CHECK de hex; imagens validadas) |
| `tenant_settings` | configuração funcional (catálogo fechado no código) |
| `tenant_secrets` | credenciais cifradas (Fernet) |
| `audit_logs` | trilha de auditoria |

## 4. Revisão `e8b9c0d1f2a3` — RLS e papel de runtime

- Cria/ajusta o papel `APP_DB_ROLE` (padrão `w2health_app`) com senha `APP_DB_PASSWORD`
  (sem senha → `NOLOGIN`). Papéis são do cluster: o downgrade revoga grants, não remove o papel.
- Grants mínimos (ver [SECURITY_AND_TENANT_ISOLATION.md](SECURITY_AND_TENANT_ISOLATION.md) §5.2).
- `ENABLE` + `FORCE ROW LEVEL SECURITY` e política `tenant_isolation` nas 24 tabelas.
- **Regra para migrations futuras**: toda tabela nova do data plane precisa de grant e
  política — `tests/test_rls.py::test_lista_de_tabelas_da_migration_bate_com_metadata`
  falha se a lista divergir da metadata.

## 5. Como aplicar a partir do estado anterior

```bash
# backup antes (recomendado)
docker compose exec -T postgres pg_dump -U w2health -d w2health -Fc > backup.dump
# APP_DB_PASSWORD precisa estar no .env (cria o papel de runtime com login)
docker compose up -d --build          # o backend roda `alembic upgrade head` no start
docker compose exec backend python -m app.saas.cli bootstrap-demo
```

Validado nesta fase sobre o banco local real da v1.2 (328.778 eventos preservados;
`downgrade b2d3f4a5c6e7` + `upgrade head` sem perda).

## 6. Mudanças no seed

- `wipe_dados(session, tenant_id)` passou a apagar **só o tenant semeado** (antes apagava
  todos). `competencias` é inserida só se faltar (calendário global compartilhado).
- O seed amarra o tenant à sessão, marca o tenant como sintético e roda `ANALYZE` após a
  carga em massa (com vários tenants, planos ruins deixavam a agregação ~20× mais lenta).
- Novo parâmetro `--tenant/--tenant-name` (2º tenant sintético: `make seed-tenant-b`).
