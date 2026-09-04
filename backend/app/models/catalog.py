"""Catálogos: regiões, planos, contratos, especialidades, procedimentos, prestadores."""

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Regiao(Base):
    __tablename__ = "regioes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2))
    macrorregiao: Mapped[str] = mapped_column(String(20))


class Plano(Base):
    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    segmentacao: Mapped[str] = mapped_column(String(30))  # ambulatorial | hospitalar | completo
    ticket_medio_base: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Coparticipação (v1.1, Etapa B): se o plano cobra, e o percentual sobre valor_pago
    # aplicado a atendimentos tipicamente sujeitos a copay (consulta/exame/terapia/PS).
    tem_coparticipacao: Mapped[bool] = mapped_column(Boolean, default=False)
    percentual_coparticipacao: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)


class Contrato(Base):
    __tablename__ = "contratos"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_plano: Mapped[int] = mapped_column(ForeignKey("planos.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(20))  # PF | PME | Empresarial

    plano: Mapped[Plano] = relationship()


class Especialidade(Base):
    __tablename__ = "especialidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    grupo: Mapped[str] = mapped_column(String(30))  # clinica | cirurgica | diagnostico | terapia


class Procedimento(Base):
    __tablename__ = "procedimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    descricao: Mapped[str] = mapped_column(String(120))
    id_especialidade: Mapped[int] = mapped_column(ForeignKey("especialidades.id"), index=True)
    grupo_procedimento: Mapped[str] = mapped_column(String(60))
    complexidade: Mapped[int] = mapped_column(Integer)  # 1..5
    custo_base: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tipo_atendimento_tipico: Mapped[str] = mapped_column(String(20))
    idade_min: Mapped[int] = mapped_column(Integer, default=0)
    idade_max: Mapped[int] = mapped_column(Integer, default=120)
    # pontual | recorrente | variavel — apoio à classificação de hipóteses na análise de
    # coortes (Etapa A da v1.1). Nunca usado sozinho para afirmar causalidade.
    perfil_utilizacao: Mapped[str] = mapped_column(String(12), default="variavel")

    especialidade: Mapped[Especialidade] = relationship()


class Prestador(Base):
    __tablename__ = "prestadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_ficticio: Mapped[str] = mapped_column(String(100))
    # hospital | clinica | laboratorio | pronto_atendimento | consultorio
    tipo_prestador: Mapped[str] = mapped_column(String(30))
    id_regiao: Mapped[int] = mapped_column(ForeignKey("regioes.id"), index=True)
    id_especialidade_principal: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), index=True
    )
    nivel_preco: Mapped[float] = mapped_column(Numeric(5, 3), default=1.0)  # multiplicador interno

    regiao: Mapped[Regiao] = relationship()
    especialidade_principal: Mapped[Especialidade] = relationship()


class Diagnostico(Base):
    __tablename__ = "diagnosticos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cid: Mapped[str] = mapped_column(String(10), unique=True)
    descricao: Mapped[str] = mapped_column(String(120))
    id_especialidade: Mapped[int | None] = mapped_column(
        ForeignKey("especialidades.id"), nullable=True, index=True
    )
