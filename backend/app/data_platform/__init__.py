"""DATA PLATFORM do W2Health (Fase 2) — separação lógica da Application Platform.

Responsabilidades deste pacote (ver docs/PHASE2_DATA_PLATFORM.md):

    connections → ingestion → RAW → mapping → canônico/Silver → data quality →
    Gold → Serving → reconciliação → lineage → capability readiness → onboarding

Regras:
* **Toda execução tem tenant explícito** (`PipelineContext`). Não existe "processar todos".
* **A origem termina no mapping.** Depois dele só existem nomes do modelo canônico
  (`data_platform/contracts/*.yaml`). O motor analítico (`app/analytics`) não importa nada
  deste pacote e não sabe se o dado veio do gerador sintético ou de um arquivo externo.
* Escritas usam o papel de banco **w2health_pipeline** (sem superusuário, sujeito a RLS);
  nunca o papel dono.
* Monolito modular: é um pacote do mesmo backend, não um serviço separado.
"""
