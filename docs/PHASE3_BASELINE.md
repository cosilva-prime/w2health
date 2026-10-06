# Fase 3 — Baseline (Production Readiness / Hardening)

> Levantado em 2026-10-06, antes de qualquer alteração de código da Fase 3.
> Branch de trabalho: `fase3-production-readiness`, criada a partir de `eaacab9`
> (último commit da Fase 2 em `v1-saas-foundation`).

## 1. Estado do repositório

| Item | Encontrado |
|---|---|
| Último commit | `eaacab9` — documentação da Data Platform operacional |
| Working tree | limpo (só `docs.zip`, arquivo do usuário, não versionado) |
| Migrations | head `a7d8e9f0b1c2` (backfill da fonte sintética), `alembic check` sem drift |
| Ambiente local | Docker Compose: `postgres`, `backend`, `frontend` saudáveis |

## 2. Testes

| Suíte | Resultado real |
|---|---|
| Backend (`pytest`, suíte inteira) | **306 passed**, 0 failed, 254,9 s |
| Frontend | sem testes unitários; `tsc --noEmit` e `next lint` limpos; build OK |
| E2E de navegador (fora do repositório, Playwright) | Fase 2: 17/17; recovery codes: 6/6 |
| Lint backend (`ruff check app tests`) | 17 achados herdados (anteriores à Fase 2) |

## 3. Dependências e vulnerabilidades (antes)

| Camada | Ferramenta | Resultado |
|---|---|---|
| Backend | `pip-audit` (requirements travado) | **23 achados em 3 pacotes**: starlette 0.46.2 (7 advisories — multipart, `request.form()`, Range, Host/path), cryptography 46.0.7 (4), pytest 8.4.2 (1) |
| Frontend — produção | `npm audit --omit=dev` | **next 14.2.35 crítico** (RCE no otimizador de imagem/Windows, SSRF, DoS, cache poisoning…) + postcss interno |
| Frontend — total | `npm audit` | 14 achados (1 crítico, 11 altos, 2 moderados) |

Leitura dos advisories do Next (faixas exatas de cada um): **todos** são corrigidos em
`15.5.24` ou anterior na linha 15 — a sugestão `next@16.3.8` do `npm audit` vem da faixa
agregada do pacote, não de um advisory que exija o 16.

## 4. Arquitetura relevante para a Fase 3 (antes)

| Tema | Estado |
|---|---|
| Execução de carga | **síncrona dentro da requisição HTTP** (`run_in_threadpool`) |
| Fila/worker | inexistente |
| RAW | `RawStorage` com uma implementação (filesystem local); sem adapter de object storage |
| Segredos | `app/core/secrets.py`: referências `tenant:` (cofre Fernet no banco), `env:` (só DEV), `vault:` (não implementado); segredos da aplicação só por variável de ambiente |
| Configuração | `validate_for_runtime` exige JWT, chave de criptografia e `COOKIE_SECURE` em production/staging; não valida CORS, hosts, URLs de banco, storage, MFA obrigatório |
| Proxy | `TRUST_PROXY_HEADERS` lê o 1º `X-Forwarded-For` de qualquer origem quando ligado |
| Containers | imagem única do backend, **root**, inclui pytest/ruff, roda migrations no start; frontend roda como root |
| Health | `GET /api/health` (API + banco) |
| Métricas | inexistentes |
| Logs | JSON com contexto; sem `service`, `environment`, `user_id`, `job_id`, duração por requisição |
| Rate limit | compartilhado no banco, só nas rotas de autenticação (por IP) |
| Upload | limites de tamanho/quantidade; sem limite de colunas/linha, sem checagem de MIME |
| Headers | API com headers básicos; frontend sem CSP/HSTS |
| Backup | teste local de dump/restore; sem procedimento de restauração por tenant |
| CI | inexistente |

## 5. P0 herdados da Fase 2 (ponto de partida)

1. Dependências vulneráveis (Next, Starlette, cryptography).
2. Carga síncrona na requisição; sem fila/worker.
3. RAW só em filesystem local.
4. Infra de produção (TLS, proxy, segredos em cofre) não definida.
5. Imagem de runtime com dependências de desenvolvimento.
6. Backup de produção e restauração por tenant inexistentes.
7. Pentest externo não realizado.
