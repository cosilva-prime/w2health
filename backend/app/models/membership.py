"""Carteira e receita: competências, beneficiários, receitas de contraprestação."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.catalog import Contrato, Plano, Regiao


class Competencia(Base):
    __tablename__ = "competencias"

    competencia: Mapped[date] = mapped_column(Date, primary_key=True)  # 1º dia do mês
    ano: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    mes_nome: Mapped[str] = mapped_column(String(20))
    trimestre: Mapped[int] = mapped_column(Integer)
    is_inverno: Mapped[bool] = mapped_column(Boolean, default=False)


class Beneficiario(Base):
    __tablename__ = "beneficiarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # BEN-000001
    sexo: Mapped[str] = mapped_column(String(1))  # M | F
    data_nascimento: Mapped[date] = mapped_column(Date)
    faixa_etaria: Mapped[str] = mapped_column(String(10), index=True)
    id_regiao: Mapped[int] = mapped_column(ForeignKey("regioes.id"), index=True)
    id_plano: Mapped[int] = mapped_column(ForeignKey("planos.id"), index=True)
    id_contrato: Mapped[int] = mapped_column(ForeignKey("contratos.id"), index=True)
    data_adesao: Mapped[date] = mapped_column(Date)
    data_saida: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="ativo")  # ativo | inativo

    regiao: Mapped[Regiao] = relationship()
    plano: Mapped[Plano] = relationship()
    contrato: Mapped[Contrato] = relationship()


class Receita(Base):
    __tablename__ = "receitas"
    __table_args__ = (UniqueConstraint("competencia", "id_plano", name="uq_receita_comp_plano"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    competencia: Mapped[date] = mapped_column(Date, index=True)
    id_plano: Mapped[int] = mapped_column(ForeignKey("planos.id"), index=True)
    quantidade_beneficiarios: Mapped[int] = mapped_column(Integer)
    receita_contraprestacao: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    plano: Mapped[Plano] = relationship()
