# Backup e recuperação — W2Health

> **Não existe backup de produção** porque não existe ambiente de produção. O que existe:
> (1) procedimento operacional formal para quando houver; (2) teste local de backup/restore
> do banco inteiro + RAW; (3) ferramenta testada de **restauração lógica por tenant**.
> Valores de RPO/RTO abaixo são **hipóteses técnicas iniciais**, não SLA comercial.

## 1. O que precisa de backup

| Ativo | Onde | Por quê | Como (produção) |
|---|---|---|---|
| PostgreSQL | banco gerenciado | control plane (tenants, usuários, planos, auditoria, segredos cifrados, fila) + data plane (Silver, Gold, metadados de ingestão) | snapshot diário + WAL contínuo (PITR) do provedor, cifrado |
| RAW (object storage) | bucket `w2health-raw`, prefixo `tenant/<id>/` | **única cópia do dado original** do cliente | versionamento + replicação para outra zona/região (ou backup do bucket) |
| Configuração | variáveis/segredos do deployment, mappings (Git), imagens versionadas | reconstruir o ambiente | Git + registro de imagens + gerenciador de segredos |
| `DATA_ENCRYPTION_KEY` | gerenciador de segredos | sem ela, MFA e segredos de tenant no backup são ilegíveis | backup próprio, **separado** dos dados |

## 2. Procedimento operacional (proposta)

| Item | Proposta inicial (hipótese, a validar com cliente/contrato e custo) |
|---|---|
| Banco — backup completo | snapshot diário automático |
| Banco — incremental | WAL contínuo / PITR habilitado |
| Retenção | diários 35 dias + mensais 12 meses (alinhar à política de eliminação de cada contrato) |
| RAW | versionamento do bucket + replicação; retenção das versões antigas: 35 dias |
| Criptografia | em repouso (KMS do provedor) e em trânsito; acesso aos backups por papel restrito e auditado |
| **RPO** (perda máxima) | ≤ 15 min para o banco (PITR); RAW: zero após confirmação do upload (objeto gravado antes do job) |
| **RTO** (tempo para voltar) | ≤ 4 h para DR completo; ≤ 1 h para restauração lógica de um tenant |
| Teste de restauração | mensal (restore num ambiente isolado + `backup-restore-check` adaptado) e a cada mudança relevante de esquema |
| Validação após restore | `alembic current`, contagens por tenant, RLS ativo, `/health/ready`, amostra de indicadores, reconciliação |

## 3. Disaster recovery × restauração de UM tenant

| | DR completo | Restauração lógica de um tenant |
|---|---|---|
| Quando | perda do banco/região, corrupção geral | erro operacional ou carga indevida que afetou só um cliente |
| Ferramenta | snapshot/PITR do provedor (ou `pg_restore` do dump) | `python -m app.ops.tenant_backup` |
| Efeito | banco inteiro volta a um ponto no tempo (todos os tenants) | só as linhas do tenant voltam ao estado do arquivo; demais tenants intocados |
| Limitação | — | ids preservados: restaurar em **outro** banco que já use os mesmos ids falha (fazer no mesmo ambiente ou num banco vazio do mesmo esquema); segredos exigem a mesma `DATA_ENCRYPTION_KEY` |

O PostgreSQL não restaura "um tenant" a partir de um snapshot físico. Procedimento para
voltar um tenant a um ponto anterior **sem** um export daquele momento: restaurar o snapshot
num banco temporário → `tenant_backup export` dali → `tenant_backup import` no banco de produção.

### Ferramenta de restauração por tenant

```bash
python -m app.ops.tenant_backup export --tenant <id> --out tenant.tar.gz      # + RAW do prefixo
python -m app.ops.tenant_backup verify --file tenant.tar.gz                    # manifesto e sha256
python -m app.ops.tenant_backup import --file tenant.tar.gz --tenant <id> --confirmar <id>
```

Garantias (testadas em `tests/test_tenant_backup.py`): manifesto com revisão Alembic e sha256
por tabela/objeto; arquivo adulterado, de outro tenant, com linha de outro tenant ou de outro
esquema é recusado; import em **uma transação** (apaga o estado atual do tenant e carrega o do
arquivo — falhou, nada muda); `audit_logs` nunca é apagado (só entram linhas que faltam);
sessões do tenant são revogadas; sequências ajustadas; assinatura (contagens + somas) do
tenant idêntica à do export e outro tenant inalterado.

## 4. Testes executados

| Data | Teste | Resultado |
|---|---|---|
| 2026-10-05 | `backup-restore-check` (banco inteiro + RAW), 2 execuções | PASS (37 e 51 contagens iguais; RAW 8/8) |
| 2026-10-06 | `backup-restore-check` após a Fase 3 (inclui fila) | **PASS** — dump 20,3 MB, restore 53 s, 74 contagens tabela×tenant iguais, 27 tabelas com RLS, RAW 56/56 |
| 2026-10-06 | `tenant_backup` — testes automatizados (4) | PASS — restauração idêntica após "incidente" simulado; recusas de arquivo adulterado/tenant/esquema |
| 2026-10-06 | `tenant_backup` no deployment de referência (RAW em S3) | PASS — export 38 tabelas + 8 objetos, verify, import |

## 5. Pendências (dependem da escolha de infraestrutura)
Backup automático de produção, PITR, replicação do bucket, cofre da chave de criptografia,
rotina mensal de teste de restauração com RTO/RPO medidos — itens do
[PRODUCTION_RELEASE_CHECKLIST.md](PRODUCTION_RELEASE_CHECKLIST.md) marcados FAIL até existirem.
