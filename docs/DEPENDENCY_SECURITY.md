# Segurança de dependências — W2Health

Verificação de vulnerabilidades conhecidas **sem upgrade automático**. Upgrades major
(ou que exigem mudar a faixa de versão declarada) são decididos e testados à parte.

```powershell
./scripts/security-check.ps1     # ou: make security-check
```

- Backend: `uvx pip-audit -r backend/requirements.txt` (lock exportado do `uv.lock`).
- Frontend: `npm audit --omit=dev` (produção) e `npm audit` (inclui build/lint).
- Sai com código 1 se houver achado. **Nunca** rodar `npm audit fix --force`.

## Resultado da verificação de 2026-10-05

### Backend (pip-audit)

| Pacote | Versão | Advisories | Correção em | Exposição no W2Health | Decisão |
|---|---|---|---|---|---|
| **starlette** (via FastAPI 0.115) | 0.46.2 | CVE-2025-54121 (multipart com arquivo grande bloqueia o event loop), CVE-2026-54283 (`request.form()` sem limite efetivo de campos/partes), CVE-2025-62727 (header Range quadrático), CVE-2026-48710 / CVE-2026-54282 (Host/path na reconstrução de URL), CVE-2026-48817, CVE-2026-48818 (StaticFiles no Windows) | 0.47.2 … 1.3.1 | **Alta** para o upload multipart do Admin (Fase 2) e uploads de branding — só SUPER_ADMIN/admin autenticado, mas é parsing antes do handler. Range e StaticFiles: não usamos `FileResponse`/`StaticFiles` (assets de branding saem como `Response` em memória) | **P0 antes de produção**: subir FastAPI para uma linha compatível com starlette ≥ 1.3.1 (mudança de faixa → testar a suíte inteira). Mitigação até lá: limite de corpo no proxy reverso (ex.: 60 MB), upload só autenticado/SUPER_ADMIN, API não exposta sem proxy |
| **cryptography** | 46.0.7 | CVE-2026-69247 (PKCS7 decrypt), CVE-2026-69248 / CVE-2026-69249 (validação de cadeia X.509), GHSA-537c-gmf6-5ccf (OpenSSL embutido nos wheels) | 48.0.1 / 49 / 50 | **Baixa–média**: usamos Fernet (cofre de segredos/MFA), não PKCS7 nem validação de cadeia X.509. O OpenSSL embutido é a exposição real | Atualizar para ≥ 50 junto com o upgrade acima (faixa declarada hoje `<47`) |
| **pytest** | 8.4.2 | CVE-2025-71176 (diretório `/tmp/pytest-of-*` previsível) | 9.0.3 | Ferramenta de teste: está na imagem (o `requirements.txt` exportado inclui o grupo dev e `make test` roda a suíte no contêiner), mas nunca é executada pelo serviço; a falha exige usuário local no mesmo host | Atualizar no próximo ciclo de dev (major 9) |

### Frontend (npm audit)

| Pacote | Versão | Severidade | Advisories (resumo) | Correção em | Exposição | Decisão |
|---|---|---|---|---|---|---|
| **next** | 14.2.35 (última da linha 14) | crítica | cache poisoning de RSC, DoS/SSRF em Server Actions, SSRF em rewrites, RCE no otimizador de imagem (AVIF) e em servidores Windows, divulgação de endpoints de Server Functions, bypass de middleware com i18n | **16.x (major)** | O app não usa Server Actions, `next/image`, rewrites, i18n nem middleware; roda em contêiner Linux (`output: standalone`); toda autorização é revalidada pela API. Ainda assim, crítico em produção | **P0 antes de produção**: migrar Next 14 → 15/16 (App Router já em uso; revisar breaking changes), sem `--force` |
| **postcss** (dependência do next) | ≤ 8.5.22 | alta | XSS no stringify, leitura de `.map` arbitrário | vem com o next corrigido | build-time; CSS é nosso | resolvido com o upgrade do Next |

`npm audit` total (com devDependencies): 11 achados (10 altos, 1 crítico) — os demais são
ferramentas de build/lint.

## Política

1. Rodar `security-check` a cada release e antes de qualquer cliente real.
2. Patch/minor dentro da faixa declarada: pode atualizar após a suíte verde.
3. Major ou mudança de faixa: issue própria, leitura de changelog, suíte completa + E2E.
4. Achado sem correção aplicável: registrar aqui exposição, mitigação e prazo.
5. Lock files versionados (`uv.lock`, `requirements.txt`, `package-lock.json`).
   Pendência: a imagem do backend instala também o grupo dev (pytest, ruff, httpx) — separar
   imagem de teste e de runtime antes de produção.

## Mudança feita nesta fase

`pyyaml` passou a ser dependência **direta** do backend (o mapping framework usa YAML);
antes vinha só transitivamente pelo uvicorn. Mesma versão (6.0.3) — nada foi atualizado.
