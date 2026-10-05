# Template de discovery de fonte — W2Health

Preencher **com o cliente**, uma cópia por fonte. Nenhuma resposta deve ser presumida: o
que não for respondido vira pendência registrada no onboarding. Não registrar aqui
credenciais, connection strings nem dados de beneficiários.

## 1. Identificação

| Pergunta | Resposta |
|---|---|
| Tenant (código W2Health) | |
| Nome da fonte (rótulo) | |
| Sistema de origem (rótulo livre — não precisa ser o nome comercial) | |
| Responsável técnico do cliente (nome/cargo) | |
| Responsável Works2Data | |
| Data do discovery | |

## 2. Forma de entrega

| Pergunta | Resposta |
|---|---|
| Tipo: arquivo / banco / API | (nesta fase só **arquivo** é executável) |
| Formato (CSV? outro?) e encoding | |
| Delimitador · separador decimal · formato de data | |
| Um arquivo por entidade? Nomes? | |
| Frequência e dia de envio | |
| Janela histórica disponível (desde quando?) | |
| Volume aproximado (beneficiários, eventos/mês) | |
| Competência fechada pode ser reenviada? Com que frequência há correção retroativa? | |

## 3. Por entidade (repetir)

| Pergunta | Resposta |
|---|---|
| Entidade W2Health | especialidade / plano / contrato / prestador / procedimento / beneficiário / receita / evento |
| Arquivo / tabela de origem | |
| Chave única na origem (estável entre envios?) | |
| Colunas e significado (anexar dicionário do cliente) | |
| Valores codificados (ex.: tipo de guia 1, 2, 3…) e seu significado | |
| Campos que podem vir vazios e o que significa vazio | |
| Registros excluídos na origem: somem do arquivo ou vêm marcados? | |

## 4. Regras de negócio a confirmar

| Pergunta | Resposta |
|---|---|
| Competência do evento = mês do atendimento, da apresentação ou do pagamento? | |
| `valor_pago` vem pronto ou é apresentado − glosado? | |
| Coparticipação vem por evento? | |
| Receita é por plano × competência? Inclui quais componentes? | |
| Identificador de beneficiário já é pseudonimizado? Estável no tempo? | |
| Existe evento sem beneficiário/prestador identificado? Como tratar? | |

## 5. Segurança e LGPD

| Pergunta | Resposta |
|---|---|
| Base legal / contrato de operador de dados assinado? | |
| Campos sensíveis que **não** devem ser enviados foram removidos? | |
| Canal de envio aprovado pela segurança do cliente | |
| Retenção acordada e procedimento de eliminação | |

## 6. Resultado

| | |
|---|---|
| Mapping criado (`data_platform/mappings/<id>_v<n>.yaml`) | |
| Decisões tomadas (com data e quem decidiu) | |
| Pendências | |
| Próximo passo | |
