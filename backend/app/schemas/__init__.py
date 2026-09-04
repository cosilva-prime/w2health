"""Schemas Pydantic — validação de corpos de requisição (endpoints de escrita).

Todo o resto da API responde com `dict` livre (leitura, sem risco de escrita). Os
schemas tipados aparecem aqui porque são os PRIMEIROS endpoints de escrita do produto
(configuração de regras de alerta, v1.1 Etapa C) — write-boundary é onde validação
tipada importa de verdade.
"""
