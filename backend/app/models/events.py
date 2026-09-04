"""Eventos assistenciais — grão de 1 linha por atendimento/procedimento."""

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Tipos de atendimento admitidos (validação em código; armazenado como texto).
TIPOS_ATENDIMENTO = (
    "consulta",
    "exame",
    "terapia",
    "pronto_socorro",
    "internacao",
    "cirurgia",
    "opme",
)


class EventoAssistencial(Base):
    __tablename__ = "eventos_assistenciais"
    __table_args__ = (
        Index("ix_evento_comp_espec", "competencia", "id_especialidade"),
        Index("ix_evento_comp_prest", "competencia", "id_prestador"),
        Index("ix_evento_comp_proc", "competencia", "id_procedimento"),
        Index("ix_evento_comp_tipo", "competencia", "tipo_atendimento"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_beneficiario: Mapped[int] = mapped_column(ForeignKey("beneficiarios.id"), index=True)
    id_prestador: Mapped[int] = mapped_column(ForeignKey("prestadores.id"), index=True)
    id_procedimento: Mapped[int] = mapped_column(ForeignKey("procedimentos.id"), index=True)
    id_especialidade: Mapped[int] = mapped_column(ForeignKey("especialidades.id"), index=True)
    id_diagnostico: Mapped[int | None] = mapped_column(
        ForeignKey("diagnosticos.id"), nullable=True
    )
    id_regiao: Mapped[int] = mapped_column(ForeignKey("regioes.id"), index=True)

    data_evento: Mapped[date] = mapped_column(Date)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    tipo_atendimento: Mapped[str] = mapped_column(String(20))
    quantidade: Mapped[int] = mapped_column(Integer, default=1)

    # Semântica financeira (v1.1, Etapa B — ver docs/DATA_MODEL.md):
    #   valor_apresentado    = despesa BRUTA apresentada pelo prestador
    #   valor_glosado        = parcela glosada pela operadora (não paga ao prestador)
    #   valor_pago           = valor_apresentado - valor_glosado (pago ao prestador)
    #   valor_coparticipacao = parcela de valor_pago cobrada do beneficiário
    #   despesa líquida da operadora (calculada, não persistida por evento) =
    #       valor_pago - valor_coparticipacao
    #       = valor_apresentado - valor_glosado - valor_coparticipacao
    valor_apresentado: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valor_glosado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valor_coparticipacao: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Rótulo do cenário sintético que injetou/alterou a linha (apenas QA/testes).
    cenario_tag: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
