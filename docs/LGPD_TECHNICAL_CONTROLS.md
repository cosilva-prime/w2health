# Controles técnicos para a LGPD — W2Health

> Requisitos e controles **técnicos**. Não é parecer jurídico nem contrato. Bases legais,
> papéis (controlador/operador), prazos e cláusulas são definidos pelo jurídico/DPO.
> Legenda: ✅ implementado · 🟡 parcial / depende de infraestrutura · ⛔ não implementado.

| Controle | Como o W2Health atende | Estado |
|---|---|---|
| **Minimização** | o produto não pede nem armazena nome, CPF, carteirinha, endereço, telefone, CID individual ou texto clínico; contrato de dados lista só o necessário por módulo ([CLIENT_DATA_REQUIREMENTS.md](CLIENT_DATA_REQUIREMENTS.md)) | ✅ |
| **Pseudonimização** | beneficiário identificado por código estável fornecido já pseudonimizado pelo cliente; a reversão fica com a operadora | ✅ (responsabilidade compartilhada: o envio pseudonimizado é do cliente) |
| **Segregação por cliente** | `tenant_id` em todo dado, filtro na aplicação + RLS FORCE no PostgreSQL + papéis sem BYPASSRLS; RAW com prefixo por tenant; worker reconstrói contexto por job | ✅ testado |
| **Cifragem em trânsito** | TLS no proxy/LB, HSTS, cookies `Secure`; tráfego interno em rede privada | 🟡 depende do deployment (referência pronta) |
| **Cifragem em repouso** | segredos de MFA e de integração cifrados na aplicação (Fernet); disco do banco e bucket cifrados pela infraestrutura | 🟡 aplicação ✅ / infraestrutura a configurar |
| **Controle de acesso** | autenticação com MFA (obrigatório para a equipe de plataforma), RBAC por tenant, features por plano, readiness, rate limit, bloqueio de conta | ✅ |
| **Registro de acesso** | auditoria append-only de login, MFA, administração, cargas, filas, segredos e **leitura de dado individual de beneficiário** — sem conteúdo clínico | ✅ |
| **Retenção** | prazo por tenant definido em contrato; tecnicamente: dados por competência, RAW por prefixo, backups com retenção do provedor | ⛔ política automatizada não implementada (P1) |
| **Eliminação / anonimização ao fim do contrato** | possível por tenant: `DELETE ... WHERE tenant_id` + `delete_prefix` do RAW + expiração dos backups | 🟡 procedimento manual documentado; sem rotina automatizada |
| **Implicações de backup** | backups contêm dados de todos os tenants; eliminação de um tenant só se completa quando os backups que o contêm expiram — prazo a constar em contrato | 🟡 documentado |
| **Portabilidade / cópia ao cliente** | export lógico por tenant (`app.ops.tenant_backup export`) com manifesto e sha256 | 🟡 ferramenta operacional, não autoatendimento |
| **Resposta a incidentes** | [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — avaliação por tenant a partir de logs/auditoria | ✅ procedimento |
| **Logs sem dado pessoal desnecessário** | logs JSON sem payload de linha, sem segredo (chaves sensíveis redigidas), sem query string; e-mail tentado no login registrado como hash | ✅ testado |
| **Suboperadores** | nuvem (computação, banco, storage), provedor de e-mail (futuro), ferramentas de observabilidade — listar no contrato antes do primeiro cliente | ⛔ decisão de deployment pendente |
| **Residência de dados** | provider-neutral; região/país do processamento e dos backups é decisão de deployment a registrar com cada cliente | ⛔ decisão pendente |
| **Ambientes não produtivos** | dados sintéticos; dado real de cliente nunca em desenvolvimento/teste | ✅ regra; 🟡 depende de disciplina operacional |
