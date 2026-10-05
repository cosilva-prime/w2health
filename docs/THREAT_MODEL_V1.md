# Threat Model — W2Health V1 (Fundação SaaS)

> Escopo: API FastAPI, frontend Next.js, PostgreSQL de serving, CLI administrativa.
> Ativos: dados assistenciais e financeiros de operadoras (sensíveis — LGPD art. 11),
> credenciais de usuários, segredos de integração, trilha de auditoria.
> Atores hostis considerados: usuário legítimo de um tenant tentando ver outro tenant;
> usuário de papel baixo tentando escalar; atacante externo com credenciais vazadas ou
> sessão roubada; insider com acesso à aplicação (não ao banco).
> Legenda de status: ✅ mitigado e testado · 🟡 mitigado parcialmente · ⛔ aberto.

| # | Ameaça | Vetor | Mitigação | Teste | Status |
|---|---|---|---|---|---|
| T1 | **IDOR** | trocar `id` na URL (`/prestadores/{id}`, `/contratos/{id}`, regra de alerta, usuário) | toda busca por id filtra `tenant_id`; id alheio = 404 idêntico a inexistente; RLS | `test_tenant_isolation` (beneficiário, contrato, prestador, procedimento, regra), `test_admin::confinado` | ✅ |
| T2 | **Broken access control** | rota sem dependência de autorização | toda rota de dado usa `get_tenant_db` + guard de router; teste varre o OpenAPI e exige 401 sem token | `test_security::test_rotas_de_dados_exigem_autenticacao` | ✅ |
| T3 | **Vazamento cross-tenant** | consulta sem `WHERE tenant_id`; JOIN; agregação | filtro na aplicação (fail-closed) + RLS FORCE; sessão sem tenant → 0 linhas | `test_tenant_isolation` (2 modos), `test_rls` | ✅ |
| T4 | **Escalada de privilégio** | VIEWER escrevendo; TENANT_ADMIN virando SUPER_ADMIN; editar o próprio papel | permissões por papel; SUPER_ADMIN só por CLI; papel atribuível restrito; auto-alteração bloqueada; papel relido do banco a cada requisição | `test_rbac`, `test_admin` | ✅ |
| T5 | **JWT misuse** | `alg=none`, chave errada, token expirado, `tid` forjado, challenge usado como access | `algorithms=["HS256"]`, `iss/aud/exp/typ` obrigatórios; `tid` precisa bater com a sessão persistida | `test_auth` (alg none, outra chave, expirado, challenge), `test_tenant_isolation::token_com_tenant_divergente` | ✅ |
| T6 | **Abuso de refresh token** | roubo do cookie, replay | cookie httpOnly/SameSite=Strict/Path restrito; rotação a cada uso; reuso revoga a sessão e é auditado; validade absoluta | `test_auth::refresh_rotaciona_e_reuso_revoga` | ✅ |
| T7 | **Força bruta** | tentativas de senha/código MFA | bloqueio por conta + limite por IP; falhas de MFA contam | `test_auth::bloqueio`, `::limite_por_ip` | 🟡 limite por IP é em memória (por processo) |
| T8 | **Vazamento de credenciais** | senha em claro, segredo MFA, credencial de integração | argon2id; Fernet para segredos; segredos write-only; senha temporária exibida uma vez | `test_auth::argon2id`, `test_admin::segredos`, `test_mfa` | ✅ |
| T9 | **Logs/auditoria sensíveis** | senha/token/código gravados em log ou `details` | `audit.sanitize`; e-mail tentado gravado como hash; nenhuma rota loga corpo | `test_security::redige`, `test_admin::nunca_contem_senha`, `test_mfa` (caplog) | ✅ |
| T10 | **Mass assignment** | enviar `tenant_id`, `id`, `platform_role` no corpo | schemas Pydantic explícitos; `config_repo` descarta `tenant_id`; guard ORM | `test_tenant_isolation::tenant_id_no_corpo` | ✅ |
| T11 | **Injection** | SQL via filtros/dimensões | SQL parametrizado; identificadores só de dicionários fixos (dimensões, catálogos); sem SQL dinâmico com entrada | revisão + testes de API existentes | ✅ |
| T12 | **Seleção direta de tenant insegura** | `?tenant_id=`, `X-Tenant-ID`, cookie | tenant vem só da sessão; troca exige vínculo (ou SUPER_ADMIN + MFA, auditado) | `test_tenant_isolation::tenant_id_enviado_pelo_cliente_e_ignorado`, `::troca_para_tenant_sem_vinculo` | ✅ |
| T13 | **Vazamento por exportação** | download/CSV de outro tenant | não há rota de exportação na V1; qualquer futura exportação deve usar `get_tenant_db` (coberta por T2/T3) | — | ✅ (inexistente) |
| T14 | **Vazamento por cache** | CDN/proxy guardando resposta de tenant; cache do SWR após troca de tenant | `Cache-Control: no-store`; frontend limpa todo o cache SWR em logout/troca | `test_security::no_store` | ✅ |
| T15 | **Vazamento em job de background** | seed/agregação misturando tenants | seed/agregação/limpeza tenant-scoped e com `bind_tenant`; CLI exige `--tenant` | `test_tenant_isolation` (2 tenants semeados lado a lado) | 🟡 não há fila/worker ainda; regra documentada para jobs futuros |
| T16 | **Bypass de feature** | chamar rota direta ou rota composta que embute o módulo | `require_feature` no backend + `feature_filters.sanitize` em explicação/drill/coortes/insights/alertas/visão executiva | `test_features` | ✅ |
| T17 | **Enumeração** | e-mails, tenants, ids | respostas idênticas no login; branding público devolve padrão para tenant inexistente; 404 genérico | `test_auth::mesma_resposta`, `test_admin::nao_enumera` | 🟡 `/public/branding/{tenant}/logo` responde 404×200 para tenants com logo |
| T18 | **Stored XSS via branding** | nome/cores/logo maliciosos | texto sem `<>`/controle, hex estrito, imagem por assinatura (sem SVG), `nosniff` + CSP no asset; React escapa texto | `test_admin::branding_validado` | ✅ |
| T19 | **CSRF** | site terceiro dispara ação com cookie | ações usam Bearer (não cookie); cookie de refresh SameSite=Strict e restrito a `/api/auth` | revisão | ✅ |
| T20 | **Sessão administrativa comprometida** | SUPER_ADMIN com senha vazada | MFA obrigatório para SUPER_ADMIN; promoção só via CLI; toda ação auditada | `test_mfa::super_admin_e_obrigado` | 🟡 sem alerta automático de anomalia |
| T21 | **Conta compartilhada entre tenants tomada por admin de um tenant** | TENANT_ADMIN de A reseta senha de conta que também acessa B | reset por tenant só para contas exclusivas | `test_admin::nao_reseta_conta_compartilhada` | ✅ |
| T22 | **Superusuário na aplicação** | API rodando como dono/superuser anula RLS | papel `w2health_app` NOSUPERUSER/NOBYPASSRLS; compose separa URLs | `test_rls::papel_de_runtime` | ✅ (ambiente compose) |
| T23 | **Configuração insegura em produção** | sem chave JWT, cookie sem Secure, docs abertos | API não sobe em produção/staging sem segredos e `COOKIE_SECURE`; docs desligados | `test_security::producao_exige_segredos` | ✅ |

## Riscos residuais (aceitos nesta fase, com dono no roadmap)

1. Rate limit em memória (T7) — trocar por Redis antes de múltiplas réplicas.
2. Sem códigos de recuperação de MFA — recuperação = reset administrativo auditado.
3. Sem registro de leitura de dado individual de beneficiário (auditoria de acesso a PHI).
4. Sem TLS/WAF/infra de produção definidos (fora do escopo desta fase).
5. Enumeração residual de tenants com logo (T17).
6. Control plane sem RLS (decisão consciente — §5.2 de [SECURITY_AND_TENANT_ISOLATION.md](SECURITY_AND_TENANT_ISOLATION.md)).
