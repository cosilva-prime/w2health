-- SERVING — o que a aplicação W2Health lê.
--
-- Hoje: serving == gold, no MESMO PostgreSQL. As tabelas `agg_*` são materializadas nele.
-- Este arquivo é o CONTRATO de serving: se o serving migrar para outra tecnologia (DW,
-- query engine), estas visões/tabelas precisam existir com o mesmo layout e a API não muda.
--
-- Parâmetro: :tenant_id (na v1.2 as queries da API ainda NÃO filtram por tenant —
-- dívida de Fase 2; ver docs/MULTI_TENANCY.md).

-- 1:1 com gold (cópia ou view). Layout = backend/app/models/analytics.py
CREATE OR REPLACE VIEW serving.agg_sinistralidade_competencia AS
    SELECT * FROM gold.agg_sinistralidade_competencia;

CREATE OR REPLACE VIEW serving.agg_competencia_dimensao AS
    SELECT * FROM gold.agg_competencia_dimensao;

CREATE OR REPLACE VIEW serving.agg_prestador_competencia AS
    SELECT * FROM gold.agg_prestador_competencia;

CREATE OR REPLACE VIEW serving.agg_beneficiario_competencia AS
    SELECT * FROM gold.agg_beneficiario_competencia;

CREATE OR REPLACE VIEW serving.agg_contrato_competencia AS
    SELECT * FROM gold.agg_contrato_competencia;

-- A fato `silver.evento_assistencial` também é exposta ao serving: usada só no detalhe de
-- 1 beneficiário (indexado) e no escopo de contrato (sob demanda). Nunca varrida inteira
-- por request de dashboard.
CREATE OR REPLACE VIEW serving.eventos_assistenciais AS
    SELECT * FROM silver.evento_assistencial;
