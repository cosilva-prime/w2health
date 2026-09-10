"""Limiares numéricos compartilhados entre o seed (agregação) e o motor analítico.

São parâmetros de PRODUTO, não regra de negócio validada — documentados em
`docs/DISCOVERY_GESTAO_SAUDE.md` e `docs/V1.2.md`. Um cliente real calibraria estes
valores para a escala da sua carteira.
"""

#: Despesa líquida mensal (R$) a partir da qual um beneficiário conta como "alto custo"
#: no mês — usado em `agg_contrato_competencia.n_beneficiarios_alto_custo` e no indicador
#: de alerta `beneficiario / novo_caso_alto_custo`.
ALTO_CUSTO_MES = 15_000.0
