# Roadmap V1 — W2Health

> Situação após a Fundação SaaS V1. Itens de DISCOVERY **não** são movidos para
> implementação sem decisão explícita.

## P0 — bloqueia cliente real

| Item | Por quê |
|---|---|
| Infra de produção: TLS ponta a ponta, `COOKIE_SECURE=true`, banco gerenciado com cifragem em repouso, segredos em cofre (KMS/Key Vault), domínio próprio | dado de saúde (LGPD art. 11) |
| Backup cifrado com restauração **por tenant** testada; política de retenção/eliminação por tenant | LGPD e contrato |
| Auditoria de **leitura** de dado individual de beneficiário (quem viu qual código, quando) | rastreabilidade de acesso a PHI |
| Rate limit compartilhado (Redis) antes de mais de uma réplica da API | o limitador atual é por processo |
| Papel de banco separado para pipelines (nem runtime nem dono), com `bind_tenant` obrigatório | ingestão real |
| Primeiro conector real via Data Platform (mapping → Silver → Gold) — sem acoplar a API ao sistema de origem | dado real |
| Pentest externo + revisão de dependências (SCA) | validação independente |
| Processo de onboarding (DPA, termo de uso, encarregado/DPO, procedimento de incidente) | LGPD |

## P1 — V1 comercial

| Item |
|---|
| Códigos de recuperação de MFA (hoje: reset administrativo auditado) |
| Convite de usuário por e-mail com link de uso único (hoje: senha temporária exibida uma vez) |
| SSO (OIDC/SAML) por tenant |
| Listar e encerrar sessões ativas na conta; alerta de novo dispositivo |
| FK `tenant_id → tenants.id` no data plane (após revisar teste histórico e janela de lock) |
| Capability Readiness automatizada por tenant (`tenant_capabilities`) ligada às features |
| Tela de Data Quality por tenant (feature `data_quality`) quando houver resultados reais |
| Exportações (CSV/PDF) com auditoria e marca d'água de tenant |
| Telemetria/observabilidade (logs estruturados, métricas por tenant, alertas de segurança) |
| Revisão da cor do delta de sinistralidade no card executivo (hoje alta aparece em verde — herdado do MVP) |
| `?id_contrato=` documentado na v1.2 para a lista de beneficiários: a rota lê `contrato_id` (alinhar doc/rota) |
| Faixa etária por competência (herdado do MVP) |

## P2 — pós-V1

| Item |
|---|
| Schema/banco dedicado para clientes que exijam isolamento físico (estratégias B/C de MULTI_TENANCY) |
| Billing/medição de uso por tenant |
| Preferências por usuário (dashboards salvos, filtros favoritos) |
| Internacionalização da interface |
| Tema escuro |

## DISCOVERY — ainda não implementar

Reajuste contratual (motor de simulação) · receita por contrato e sinistralidade
contratual · receita atribuída por beneficiário / "sinistralidade individual" · previsão,
ML e projeções · LLM/chatbot de narrativa · conectores específicos MV/Tasy/Benner/TISS ·
Data Lake físico, Kafka, Kubernetes, microserviços, Data Mesh · funcionalidades clínicas.
Referências: [DISCOVERY_GESTAO_SAUDE.md](DISCOVERY_GESTAO_SAUDE.md),
[EVOLUCAO_FEEDBACK_ESPECIALISTA.md](EVOLUCAO_FEEDBACK_ESPECIALISTA.md).
