# Etapa 1 — Fundações (A1–A4)

Data: 2026-09-02 · Status: **concluída e validada ponta a ponta via Docker Compose**

Escopo desta etapa (aprovado): estrutura do repositório, Docker Compose, PostgreSQL,
backend FastAPI + `/health` + configuração + CORS, frontend Next.js + TypeScript + Tailwind,
shell (sidebar, header, banner, breadcrumbs), `apiClient` e integração frontend → backend
via `/health`.

**Fora do escopo (não implementado, conforme instrução):** modelo de dados, migrations de
entidades de negócio, geração de dados sintéticos, motor analítico, dashboards, regras de
sinistralidade, insights.

---

## O que foi implementado

### Repositório
- Repositório git novo e independente em `projetos/w2health/` (`git init`, branch `main`).
- `.gitignore`, `.gitattributes` (normalização de fim de linha), `.env.example`.
- `Makefile` (alvos `up`, `down`, `logs`, `ps`, `build`, `test`, `clean`) e, para Windows
  sem `make`, `scripts/up.ps1` · `scripts/down.ps1` · `scripts/test-backend.ps1`.
- `README.md` na raiz + `backend/README.md`.

### Docker Compose (`docker-compose.yml`)
- Três serviços: **postgres** (`postgres:16-alpine`, healthcheck `pg_isready`, volume
  `pgdata`), **backend** (build de `./backend`, depende do postgres saudável), **frontend**
  (build de `./frontend`, depende do backend).
- Portas do host parametrizáveis via `.env`; defaults escolhidos para **não colidir** com
  serviços já ativos nesta máquina:
  - backend **8010** → contêiner 8000 (Docker Desktop ocupa a 8000 no host)
  - postgres **5433** → contêiner 5432 (há um PostgreSQL local na 5432)
  - frontend **3000**
- `DATABASE_URL` já é injetada no backend, **reservada para a Etapa 2** (nenhuma conexão é
  aberta ainda).
- `NEXT_PUBLIC_API_BASE_URL` é passada como **build arg** ao frontend (o Next inlina
  variáveis `NEXT_PUBLIC_*` em tempo de build).

### Backend (`backend/`)
- **FastAPI** com `create_app()` factory — [app/main.py](../backend/app/main.py).
- **Configuração** via env / `.env` com `pydantic-settings` —
  [app/core/config.py](../backend/app/core/config.py): `PROJECT_NAME`, `ENVIRONMENT`,
  `API_V1_PREFIX`, `CORS_ORIGINS`, `DATABASE_URL`.
  `cors_origins` é `list[str]` — a variável de ambiente **deve ser um array JSON**
  (`CORS_ORIGINS=["http://localhost:3000"]`), pois o pydantic-settings decodifica
  coleções como JSON.
- **CORS** habilitado para as origens configuradas (default `http://localhost:3000`).
- **Endpoints**:
  - `GET /api/health` → `{status, service, version, environment, timestamp}` —
    [app/api/v1/routes/health.py](../backend/app/api/v1/routes/health.py)
  - `GET /` → metadados (aponta para `/docs` e `/api/health`)
  - `GET /docs` (Swagger) e `GET /openapi.json` nativos do FastAPI
- **Logging** simples em stdout — [app/core/logging.py](../backend/app/core/logging.py).
- Dependências: `uv` + `pyproject.toml` + `uv.lock` no desenvolvimento; `requirements.txt`
  (exportado do lock) instalado com `pip` na imagem Docker — remove a dependência de
  `ghcr.io` (que está bloqueado neste ambiente).
- **Testes** (`pytest`, 9 casos) — [backend/tests/](../backend/tests/):
  `test_health.py` (health 200 + payload, `/`, `/openapi.json` contém `/api/health`,
  CORS em requisição simples, CORS preflight) e `test_config.py` (`cors_origins` default,
  lista explícita, decodificação de array JSON via env, defaults).

### Frontend (`frontend/`)
- **Next.js 14.2.35** (App Router) + **TypeScript** + **Tailwind CSS**.
  (14.2.35 é a versão corrigida da linha 14.2.x — a 14.2.15 tinha CVE.)
- **Shell** — [src/components/shell/](../frontend/src/components/shell/):
  - `AppShell` compõe banner + sidebar + header + `<main>`.
  - `DemoBanner` — faixa fixa **“Ambiente demonstrativo — dados sintéticos”**.
  - `Sidebar` — navegação: Visão Executiva · Sinistralidade · Prestadores · Beneficiários ·
    Insights (item ativo destacado).
  - `Header` — título da seção + `Breadcrumbs` + placeholder inerte para os filtros globais
    (Etapa 6).
  - `Breadcrumbs` — derivados do pathname, com rótulos legíveis.
- **Páginas**: `/` (Visão Executiva, com o cartão de status) e placeholders para
  `/sinistralidade`, `/prestadores`, `/beneficiarios`, `/insights` (só para validar
  navegação e breadcrumbs).
- **`apiClient`** — [src/lib/apiClient.ts](../frontend/src/lib/apiClient.ts): wrapper de
  `fetch` com `API_BASE_URL` (de `NEXT_PUBLIC_API_BASE_URL`), `ApiError`, e `getHealth()`.
- **Integração frontend → backend**: `HealthStatus`
  ([src/components/HealthStatus.tsx](../frontend/src/components/HealthStatus.tsx)) é um
  client component que chama `GET /api/health` na montagem e renderiza online/offline com
  os campos retornados e botão “Recarregar”.

---

## Validação executada

| Verificação | Resultado |
|---|---|
| `uv run pytest` (backend) | ✅ **8 passed** |
| `uv run ruff check .` (backend) | ✅ sem erros |
| Backend sob `uvicorn` — `GET /api/health` | ✅ `200` · `{"status":"ok",...}` |
| Backend — `GET /` e `GET /openapi.json` | ✅ `200`, `/api/health` presente no schema |
| CORS — `GET /api/health` com `Origin: http://localhost:3000` | ✅ `access-control-allow-origin` ecoado |
| CORS — preflight `OPTIONS` | ✅ `200` com headers de CORS |
| `npm run typecheck` (`tsc --noEmit`) | ✅ sem erros |
| `npm run lint` (`next lint`) | ✅ sem warnings/erros |
| `npm run build` (`next build`) | ✅ build OK — 6 rotas, saída `standalone` |
| `docker compose build` | ✅ imagens `w2health-backend` e `w2health-frontend` construídas |
| `docker compose up -d` | ✅ `postgres` healthy · `backend` healthy · `frontend` up |
| `GET http://localhost:8010/api/health` (via Compose) | ✅ `200` · `{"status":"ok","environment":"docker",...}` |
| `GET http://localhost:8010/` e CORS com `Origin: http://localhost:3000` | ✅ `200` · header de CORS ecoado |
| `GET http://localhost:3000/` (frontend via Compose) | ✅ `200` · HTML com banner, sidebar e cartão de status |
| API base URL embutida no bundle do frontend | ✅ `http://localhost:8010/api` |
| `docker compose run --rm --no-deps backend pytest` | ✅ **9 passed** (dentro do contêiner) |

---

## Correções aplicadas durante a subida do Compose

1. **`SettingsError: error parsing value for field "cors_origins"`** — o backend encerrava
   com exit 1. Causa: `cors_origins` é uma coleção (`list[str]`) e o `pydantic-settings`
   decodifica variáveis de ambiente de coleções com `json.loads()`; o valor
   `CORS_ORIGINS=http://localhost:3000` não é JSON válido. Correção: passar a variável como
   **array JSON**. Arquivos alterados:
   - `backend/app/core/config.py` — `cors_origins: list[str]`, com nota sobre o formato.
   - `backend/app/main.py` — usa `settings.cors_origins` direto.
   - `docker-compose.yml` — `CORS_ORIGINS: '${CORS_ORIGINS:-["http://localhost:3000"]}'`.
   - `.env.example` — `CORS_ORIGINS=["http://localhost:3000"]`.
   - `backend/tests/test_config.py` — cobre default, lista explícita e env JSON.
2. **`container_name` fixo causava conflito** ao recriar containers de execuções anteriores.
   Removidos os `container_name:` do `docker-compose.yml` (o Compose passa a nomear como
   `w2health-<serviço>-1` e recria sem conflito).
3. **Frontend só escutava no IP do contêiner.** O Docker injeta `HOSTNAME=<container id>`
   e o servidor standalone do Next passa a escutar só nesse IP (loopback recusava conexão).
   Correção: `ENV HOSTNAME=0.0.0.0` no estágio `runner` do `frontend/Dockerfile`.
4. **Healthcheck do frontend com `localhost`** resolvia para `::1` (IPv6) dentro do
   contêiner, mas o Next escuta em IPv4 → marcava `unhealthy`. Correção: healthcheck usa
   `http://127.0.0.1:3000/` no `docker-compose.yml`. Também foi adicionado healthcheck ao
   serviço `frontend` (antes só `postgres` e `backend` tinham).

## Bloqueio de rede durante a execução (resolvido)

Durante a etapa a máquina ficou temporariamente sem conectividade externa (DNS/HTTP
falhando para Docker Hub, `ghcr.io`, npm, `google.com`). Impactos e resoluções:

- `Dockerfile` do backend deixou de usar `COPY --from=ghcr.io/astral-sh/uv` (host
  bloqueado) e passou a instalar `requirements.txt` (exportado do `uv.lock`) com `pip` —
  só depende de PyPI + Docker Hub. **Mantido** como solução definitiva do MVP.
- O `npm install` precisou de retry. Sem impacto no resultado.
- Assim que a rede voltou, `docker compose build` + `up` rodaram e o stack foi validado
  (ver tabela acima).

---

## Comandos do ambiente

| Ação | Comando |
|---|---|
| Subir tudo (build + start) | `docker compose up -d --build` |
| Parar (mantém o banco) | `docker compose down` |
| Parar e apagar o banco | `docker compose down -v` |
| Status | `docker compose ps` |
| Logs | `docker compose logs -f` |
| Testes do backend (em contêiner) | `docker compose run --rm --no-deps backend pytest` |
| Windows (PowerShell) | `./scripts/up.ps1` · `./scripts/down.ps1` · `./scripts/test-backend.ps1` |

URLs (com as portas default): frontend http://localhost:3000 · backend
http://localhost:8010/api/health · Swagger http://localhost:8010/docs.
