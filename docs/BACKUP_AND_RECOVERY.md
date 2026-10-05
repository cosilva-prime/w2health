# Backup e recuperação — W2Health

> **Não existe backup de produção.** Não há ambiente de produção. O que existe é um
> **teste local de backup/restore** que prova que o banco (com RLS) e o RAW podem ser
> copiados e restaurados sem perda — e define o que a produção vai precisar.

## 1. O que precisa de backup

| Ativo | Onde (DEV/Compose) | Por quê |
|---|---|---|
| PostgreSQL (`w2health`) | volume `pgdata` | control plane (tenants, usuários, planos, auditoria, segredos cifrados) + data plane (Silver, Gold, metadados de ingestão) |
| RAW | volume `rawdata` (`/var/lib/w2health/raw`) | **única cópia do dado original** recebido do cliente |
| Mappings | `data_platform/mappings/` (Git) | versionados no repositório |
| `DATA_ENCRYPTION_KEY` | `.env` (DEV) / cofre (produção) | sem ela, segredos de tenant e MFA no backup são ilegíveis — guardar **separado** do backup |

## 2. Teste local de backup/restore

```powershell
./scripts/backup-restore-check.ps1     # ou: make backup-check
```

1. `pg_dump -Fc` do banco principal (somente leitura);
2. restore num banco **temporário** `w2health_restore_check` — nunca no principal;
3. compara contagens por tabela **e por tenant** (data plane, metadados de ingestão,
   auditoria) e tabelas globais (tenants, usuários, vínculos, planos, features, versão do
   Alembic);
4. confere que as tabelas com RLS (ENABLE + FORCE) continuam protegidas no restaurado;
5. empacota o volume RAW (`tar.gz`) e confere a quantidade de arquivos;
6. remove o banco temporário. Artefatos em `var/backups/` (gitignored — contêm dados).

### Execuções (2026-10-05, ambiente local Docker Compose)

| Item | 1ª execução (antes da carga via Docker) | 2ª execução (após carga do tenant `homolog-csv`) |
|---|---|---|
| dump (formato custom) | 17,6 MB | 17,8 MB |
| restore no banco temporário | 30 s | 18,8 s |
| contagens tabela × tenant comparadas | 37 linhas — **iguais** | 51 linhas — **iguais** |
| tabelas com RLS (ENABLE+FORCE) no restaurado | 27 | 27 |
| RAW: arquivos no volume × no pacote | 0 × 0 (cargas anteriores rodaram fora do contêiner) | **8 × 8** |
| resultado | PASS | **PASS** |

## 3. Restauração por tenant

O dump é do banco inteiro. Restaurar **um** tenant sem afetar os outros não é um
`pg_restore` direto: o procedimento é restaurar num banco temporário e copiar só as linhas
do tenant (todas as tabelas do data plane têm `tenant_id`) com o papel dono, numa
transação, depois de apagar as linhas atuais do tenant. **Não está automatizado** — é
pendência P0 para produção ([V1_ROADMAP.md](V1_ROADMAP.md)).

## 4. Requisitos para produção (não implementados)

- banco gerenciado com backup automático, PITR e cifragem em repouso;
- retenção definida em contrato (ex.: diária 35 dias + mensal 12 meses) e eliminação por
  tenant ao fim do contrato (LGPD);
- RAW em object storage com versionamento, cifragem (KMS) e replicação;
- teste de restauração **periódico** (este script como base), com RTO/RPO medidos;
- chave de criptografia em cofre, com rotação e backup próprio;
- acesso aos backups restrito e auditado.
