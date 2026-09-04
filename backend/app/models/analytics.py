"""Camada analítica: agregações mensais materializadas + gabarito de cenários.

Estas tabelas são (re)construídas pelo job de agregação após o seed. O motor analítico
lê predominantemente daqui — a fato bruta só é varrida em telas de 1 beneficiário.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Dimensões suportadas pela decomposição (valor da coluna `dimensao`).
DIMENSOES = (
    "grupo_despesa",
    "tipo_atendimento",
    "especialidade",
    "procedimento",
    "prestador",
    "regiao",
    "faixa_etaria",
    "sexo",
    "plano",
    "contrato",
)


class AggSinistralidadeCompetencia(Base):
    __tablename__ = "agg_sinistralidade_competencia"

    # Composição financeira (v1.1, Etapa B — ver docs/DATA_MODEL.md):
    #   despesa_bruta    = Σ valor_apresentado
    #   glosas           = Σ valor_glosado
    #   coparticipacao   = Σ valor_coparticipacao
    #   despesa_liquida  = despesa_bruta - glosas - coparticipacao  (base oficial do MVP p/ KPI)
    #   sinistralidade_bruta / _liquida = despesa_{bruta,liquida} / receita * 100
    # Não existem colunas "despesa"/"sinistralidade" isoladas — usar sempre a variante
    # bruta ou líquida explicitamente, para nunca apresentar um número ambíguo.
    competencia: Mapped[date] = mapped_column(Date, primary_key=True)
    receita: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    despesa_bruta: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    glosas: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    coparticipacao: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    despesa_liquida: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    sinistralidade_bruta: Mapped[float] = mapped_column(Float, default=0.0)  # %
    sinistralidade_liquida: Mapped[float] = mapped_column(Float, default=0.0)  # %
    beneficiarios_ativos: Mapped[int] = mapped_column(Integer, default=0)
    exposicao_beneficiario_mes: Mapped[int] = mapped_column(Integer, default=0)
    eventos: Mapped[int] = mapped_column(Integer, default=0)
    custo_pmpm: Mapped[float] = mapped_column(Float, default=0.0)
    receita_media_beneficiario: Mapped[float] = mapped_column(Float, default=0.0)


class AggCompetenciaDimensao(Base):
    __tablename__ = "agg_competencia_dimensao"
    __table_args__ = (
        UniqueConstraint(
            "competencia", "dimensao", "chave", name="uq_aggdim_comp_dim_chave"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    dimensao: Mapped[str] = mapped_column(String(20), index=True)
    chave: Mapped[str] = mapped_column(String(60))
    rotulo: Mapped[str] = mapped_column(String(160))

    despesa: Mapped[float] = mapped_column(Float, default=0.0)
    eventos: Mapped[int] = mapped_column(Integer, default=0)
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    beneficiarios: Mapped[int] = mapped_column(Integer, default=0)
    custo_medio: Mapped[float] = mapped_column(Float, default=0.0)
    freq_por_mil: Mapped[float] = mapped_column(Float, default=0.0)


class AggPrestadorCompetencia(Base):
    __tablename__ = "agg_prestador_competencia"
    __table_args__ = (
        UniqueConstraint("competencia", "id_prestador", name="uq_aggprest_comp_prest"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    id_prestador: Mapped[int] = mapped_column(ForeignKey("prestadores.id"), index=True)

    despesa: Mapped[float] = mapped_column(Float, default=0.0)
    eventos: Mapped[int] = mapped_column(Integer, default=0)
    beneficiarios: Mapped[int] = mapped_column(Integer, default=0)
    custo_medio: Mapped[float] = mapped_column(Float, default=0.0)
    participacao: Mapped[float] = mapped_column(Float, default=0.0)  # fração da despesa do mês
    procedimento_top_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    procedimento_top_share: Mapped[float] = mapped_column(Float, default=0.0)


class AggBeneficiarioCompetencia(Base):
    __tablename__ = "agg_beneficiario_competencia"
    __table_args__ = (
        UniqueConstraint("competencia", "id_beneficiario", name="uq_aggben_comp_ben"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    id_beneficiario: Mapped[int] = mapped_column(ForeignKey("beneficiarios.id"), index=True)
    despesa: Mapped[float] = mapped_column(Float, default=0.0)
    eventos: Mapped[int] = mapped_column(Integer, default=0)


class CenarioGabarito(Base):
    """Verdade-fundamental dos cenários plantados pelo gerador (consumido pelos testes)."""

    __tablename__ = "cenarios_gabarito"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    competencia_alvo: Mapped[date | None] = mapped_column(Date, nullable=True)
    dimensao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chave_alvo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rotulo_alvo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    efeito_esperado: Mapped[str | None] = mapped_column(String(20), nullable=True)
    descricao: Mapped[str] = mapped_column(String(600), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)


class SeedManifest(Base):
    __tablename__ = "seed_manifest"

    id: Mapped[int] = mapped_column(primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    beneficiarios: Mapped[int] = mapped_column(Integer)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    escala_eventos: Mapped[float] = mapped_column(Float, default=1.0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contagens: Mapped[dict] = mapped_column(JSON, default=dict)
