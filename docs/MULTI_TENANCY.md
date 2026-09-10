# Multi-tenancy — W2Health (v1.2)

## 1. Objetivo

O W2Health será um SaaS com várias operadoras na mesma plataforma. Este documento define
**como distinguir clientes** e **como isolar seus dados**, desde já — sem refatoração
destrutiva do MVP.

## 2. Conceito

Todo dado que pertence a um cliente carrega `tenant_id` (slug, ex.: `operadora-alfa`).
Metadados de rastreabilidade que acompanham o dado desde a ingestão:
`tenant_id`, `source_system`, `source_record_id`, `ingestion_id`, `ingestion_timestamp`,
`source_updated_at`, `reference_date`, `raw_payload_hash`.

**Chave de negócio composta.** A identidade de um beneficiário é `(tenant_id, codigo)` —
nunca `codigo` sozinho, e **nunca CPF/CNS**. Teste de arquitetura obrigatório
(`backend/tests/test_multitenancy.py`):

> `operadora-alfa + BEN-000001` coexiste com `operadora-beta + BEN-000001` e com a massa
> `w2h-demo` — três linhas, uma chave por tenant, zero colisão.

## 3. Estratégias avaliadas

| | Estratégia | SaaS | Segurança | Custo | Manutenção | Escala | LGPD | Onboarding | Desenvolvimento |
|---|---|---|---|---|---|---|---|---|---|
| **A** | `tenant_id` em todas as tabelas (schema/DB compartilhados) | ✅ | média (depende de filtro/RLS) | **baixo** | **baixa** (1 migração, 1 código) | boa até dezenas de clientes | ok com RLS + cifragem + auditoria | **rápido** | **simples** |
| **B** | schema por cliente (mesmo DB) | ✅ | boa (isolamento lógico) | baixo-médio | média (N schemas, migração N×) | boa | boa | médio | médio |
| **C** | banco por cliente | ✅ | **alta** | alto | **alta** (N bancos, backup N×) | limitada por operação | **alta** | lento | complexo |
| **D** | bucket/prefixo por cliente no data lake | (complementa) | boa no lake | baixo | baixa | ótima | boa | rápido | simples |
| **E** | combinação | — | — | — | — | — | — | — | — |

## 4. Recomendação para o estágio atual

**Combinação: A (aplicação) + D (data lake), com RLS no PostgreSQL como reforço de
serving na Fase 2; B e C como escalonamento.**

- **Aplicação / serving:** `tenant_id` em todas as tabelas (**feito na v1.2**), chave de
  negócio composta, camada analítica e código compartilhados. É o padrão de mercado para
  SaaS B2B no início — um cliente agora, onboarding barato, uma base de código.
- **Data lake:** prefixo `/<tenant_id>/{raw,silver,gold}/...` — isolamento físico simples,
  permissões por prefixo, custo de storage por tenant transparente.
- **Fase 2 (antes do 1º cliente real):** **Row-Level Security** no PostgreSQL —
  `CREATE POLICY ... USING (tenant_id = current_setting('app.tenant'))` — para que uma
  query sem `WHERE tenant_id` **não** consiga vazar outro tenant. Hoje as queries do
  repositório **não filtram** por tenant (dívida explícita — o produto opera single-tenant).
- **Escalonamento:** cliente grande, regulado ou que exija isolamento físico → mover
  aquele tenant para **schema próprio (B)** ou **banco próprio (C)**, sem mudar o modelo
  canônico. A decisão é por cliente, não global.

## 5. O que a v1.2 entregou

| Item | Estado |
|---|---|
| `tenant_id` (via `TenantMixin`) em 24 de 26 tabelas | ✅ (exceto `competencias` = calendário global, `tenants` = o cadastro) |
| Tabela `tenants` (cadastro de clientes) | ✅ |
| Chaves de negócio → `(tenant_id, natural)` | ✅ (`beneficiarios`, `planos`, `especialidades`, `procedimentos`, `diagnosticos`, `receitas`, `cenarios_gabarito`, `uq_agg*`) |
| PK de `agg_sinistralidade_competencia` → `(tenant_id, competencia)` | ✅ |
| Seed carimba `tenant_id` (parametrizável via `SeedConfig.tenant_id`) | ✅ |
| `app/core/tenant.py` — ponto único de resolução (hoje: constante `w2h-demo`) | ✅ |
| Job de agregação tenant-scoped | ✅ |
| Filtro `WHERE tenant_id` nas queries de leitura da API | ❌ **Fase 2** (RLS + middleware) |
| RLS no PostgreSQL | ❌ **Fase 2** |
| Autenticação / resolução de tenant por request | ❌ **Fase 2** (pré-requisito real) |

## 6. LGPD / dados sensíveis (documentado, não implementado)

Dados de saúde são sensíveis (LGPD art. 11). Antes de qualquer cliente real:

- **Isolamento por tenant** em todas as camadas (A + D + RLS).
- **Menor privilégio** — credenciais por serviço, sem superusuário na aplicação.
- **Cifragem em trânsito** (TLS) e **em repouso** (disco do lake e do banco).
- **Auditoria** de acesso a dado sensível; **logs sem PII/PHI** (nunca CPF, CNS, nome,
  CID em log).
- **Pseudonimização** já na ingestão: `codigo` do beneficiário entra hasheado/mascarado;
  CPF/CNS, se vierem, ficam só em RAW cifrado e **nunca** viram chave técnica nem sobem
  para Silver.
- **Retenção e eliminação** por tenant (expurgo por prefixo no lake + `DELETE ... WHERE
  tenant_id` no serving).
- **Backup** por tenant restaurável isoladamente.
- **Telas** não exibem CPF/CNS sem necessidade; identificação por código anonimizado
  (já é assim no MVP).
- **Controle por usuário/perfil** — Fase 2, junto com autenticação.

## 7. Regra a partir da v1.2

Toda **nova** estrutura persistida nasce com `tenant_id` e chave de negócio composta.
Nenhuma tabela nova sem tenant (validado por `test_multitenancy.py`).
