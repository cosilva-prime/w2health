# O que pedir ao cliente — requisitos de dados (Fase 2)

Documento para a conversa com a área de TI/dados da operadora. Linguagem de negócio;
o detalhe técnico campo a campo está em [DATA_CONTRACT.md](DATA_CONTRACT.md) e no contrato
operacional ([MAPPING_FRAMEWORK.md](MAPPING_FRAMEWORK.md) §6).

> O W2Health **não** pede nem precisa de nome, CPF, número de carteirinha, endereço,
> telefone, CID individual ou texto clínico. Identificadores de beneficiário devem chegar
> **pseudonimizados** (um código estável que só a operadora consegue reverter).

## 1. Entrega

| Item | Esperado |
|---|---|
| Formato | CSV (um arquivo por entidade), UTF-8, com cabeçalho. Delimitador, separador decimal e formato de data são **do cliente** — declarados no mapping |
| Nome dos arquivos | combinado no discovery (ex.: `beneficiarios.csv`, `eventos.csv`) |
| Janela inicial | **mínimo 13 competências**, ideal 24 (comparações ano a ano e tendência) |
| Atualização | mensal, após o fechamento da competência; reenvio de competências corrigidas é suportado |
| Tamanho | até 50 MB por arquivo e 20 arquivos por envio nesta fase |
| Canal | upload pela equipe Works2Data no Admin (nesta fase); integração direta (banco/API) ainda não existe |

## 2. Entidades

| Entidade | Para quê | Obrigatória? |
|---|---|---|
| Especialidades | agrupamento de procedimentos e pares de prestadores | sim |
| Planos | receita e sinistralidade por plano | sim |
| Contratos | inteligência de contratos | sim |
| Prestadores (com cidade/UF e especialidade principal) | inteligência de prestadores | sim |
| Procedimentos (com especialidade) | composição da despesa | sim |
| Beneficiários (código pseudonimizado, nascimento, sexo, plano, contrato, cidade/UF, adesão, saída) | carteira, faixas etárias, coortes | sim |
| Eventos assistenciais (um registro por item de conta: id estável, beneficiário, prestador, procedimento, data, tipo de atendimento, valores apresentado/glosado/pago/coparticipação) | toda a análise de despesa | sim |
| Receita por competência × plano (contraprestação e quantidade de beneficiários) | **sinistralidade** | sem ela, sinistralidade, visão executiva e insights ficam indisponíveis |

## 3. O que cada módulo exige

Regra do produto: **disponível = contratado no plano E dados prontos**
([CAPABILITY_READINESS.md](CAPABILITY_READINESS.md)).

| Módulo | Precisa de |
|---|---|
| Visão executiva · Sinistralidade · Insights | eventos + receita |
| Composição financeira | eventos + receita (glosa e coparticipação por evento melhoram) |
| Contratos | eventos + beneficiários vinculados a contratos |
| Prestadores | eventos + prestadores |
| Beneficiários | eventos + beneficiários |
| Explicações avançadas | eventos + beneficiários (datas de saída e perfil de procedimento melhoram) |
| Alertas | eventos |

## 4. Qualidade mínima

Com a configuração padrão (limite de rejeição 0), a carga é **bloqueada** (nada publicado) quando há: arquivo obrigatório ausente; coluna
esperada ausente; valor que não converte para o tipo (data, número); código de plano,
contrato, prestador, procedimento ou beneficiário que não existe; UF inválida; valor
negativo; glosa maior que o apresentado; competência inválida; saída antes da adesão.
Se o limite de rejeição for acordado acima de 0 (decisão registrada no onboarding), as
linhas com esses problemas são descartadas individualmente e a carga sai como `PARTIAL`.
O relatório de Data Quality aponta **linha e motivo** — sem expor conteúdo clínico.

## 5. Perguntas que o cliente precisa responder

Ver [SOURCE_DISCOVERY_TEMPLATE.md](SOURCE_DISCOVERY_TEMPLATE.md).
