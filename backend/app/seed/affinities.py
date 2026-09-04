"""Afinidades demográficas: propensão de uso por idade/sexo e pesos de procedimento.

Tudo aqui é heurística demonstrativa — plausível clinicamente, sem representar qualquer
população real.
"""

from __future__ import annotations

import numpy as np

# Pirâmide etária da carteira (idade_min, idade_max, peso relativo).
AGE_PYRAMID: list[tuple[int, int, float]] = [
    (0, 4, 0.06),
    (5, 12, 0.10),
    (13, 19, 0.10),
    (20, 29, 0.17),
    (30, 39, 0.18),
    (40, 49, 0.15),
    (50, 59, 0.11),
    (60, 69, 0.08),
    (70, 79, 0.04),
    (80, 92, 0.01),
]

# Taxa anual base de eventos por idade (curva em "U": alta nos extremos).
def taxa_anual_base(idade: np.ndarray) -> np.ndarray:
    idade = idade.astype(float)
    base = (
        6.5
        + 12.0 * np.exp(-idade / 3.0)           # bebês/crianças pequenas
        + 0.10 * np.clip(idade - 35, 0, None)   # crescimento na meia-idade
        + 0.0040 * np.clip(idade - 45, 0, None) ** 2  # aceleração nos idosos
    )
    return base


# Propensão relativa por especialidade em função da idade. Cada entrada é uma função
# vetorizada idade -> peso (>= 0).
def _peso_pediatria(a):
    return np.where(a < 13, 3.5, np.where(a < 16, 0.4, 0.02))


def _peso_gineco(a, sexo):
    base = np.where((a >= 12) & (a < 52), 1.4, np.where(a < 70, 0.5, 0.15))
    return base * np.where(sexo == "F", 1.0, 0.02)


def _peso_obstetricia(a, sexo):
    base = np.where((a >= 16) & (a < 43), 1.0, 0.0)
    return base * np.where(sexo == "F", 1.0, 0.0)


def _peso_oftalmo(a):
    return 0.5 + 0.9 * (a >= 45) + 1.6 * (a >= 60) + 1.0 * (a >= 70)


def _peso_cardio(a):
    return 0.2 + 0.05 * np.clip(a - 30, 0, None) + 0.9 * (a >= 55)


def _peso_ortopedia(a):
    return 0.5 + 0.35 * (a >= 15) + 0.9 * (a >= 45) + 1.1 * (a >= 65)


def _peso_onco(a):
    return 0.05 + 0.9 * (a >= 45) + 1.2 * (a >= 60)


def _peso_pneumo(a):
    return np.where(a < 6, 1.4, 0.5) + 0.9 * (a >= 55)


def _peso_neuro(a):
    return 0.4 + 0.5 * (a >= 40) + 0.9 * (a >= 65)


def _peso_psi(a):
    return np.where((a >= 12) & (a < 60), 1.1, 0.5)


def _peso_derma(a):
    return np.where(a < 30, 1.2, 0.8)


def _peso_uro(a, sexo):
    base = 0.2 + 0.5 * (a >= 40) + 0.9 * (a >= 60)
    return base * np.where(sexo == "M", 1.6, 0.5)


def _peso_gastro(a):
    return 0.4 + 0.5 * (a >= 35) + 0.5 * (a >= 55)


def _peso_clinica(a):
    return 1.0 + 0.02 * np.clip(a - 20, 0, None)


def _peso_radiologia(a):
    return 0.6 + 0.02 * np.clip(a - 25, 0, None)


def _peso_fisio(a):
    return 0.4 + 0.5 * (a >= 25) + 0.6 * (a >= 55)


def pesos_especialidade(idade: np.ndarray, sexo: np.ndarray) -> dict[str, np.ndarray]:
    """Matriz de propensão especialidade -> vetor de pesos (por beneficiário)."""
    return {
        "clinica_medica": _peso_clinica(idade),
        "pediatria": _peso_pediatria(idade),
        "cardiologia": _peso_cardio(idade),
        "ortopedia": _peso_ortopedia(idade),
        "oftalmologia": _peso_oftalmo(idade),
        "gineco_obst": _peso_gineco(idade, sexo),
        "oncologia": _peso_onco(idade),
        "pneumologia": _peso_pneumo(idade),
        "gastro": _peso_gastro(idade),
        "neurologia": _peso_neuro(idade),
        "psiquiatria": _peso_psi(idade),
        "dermatologia": _peso_derma(idade),
        "urologia": _peso_uro(idade, sexo),
        "radiologia": _peso_radiologia(idade),
        "fisioterapia": _peso_fisio(idade),
    }


# Peso relativo de cada procedimento DENTRO da sua especialidade (frequência típica).
# Procedimentos não citados recebem peso 1.0. Consultas dominam; cirurgias são raras.
PESO_PROCEDIMENTO: dict[str, float] = {
    # consultas
    "CON-CLM": 26, "CON-PED": 24, "CON-CAR": 12, "CON-ORT": 12, "CON-OFT": 12,
    "CON-GIN": 12, "CON-ONC": 5, "CON-PNE": 9, "CON-GAS": 9, "CON-NEU": 8,
    "CON-PSI": 7, "CON-DER": 12, "CON-URO": 9,
    # pronto-socorro
    "PS-CLM": 7, "PS-PED": 9, "PS-ORT": 4,
    # laboratório / imagem simples (frequentes)
    "LAB-HMG": 12, "LAB-GLI": 10, "LAB-LIP": 7, "LAB-TSH": 6, "LAB-PSA": 4,
    "LAB-URC": 4, "LAB-BHCG": 3, "LAB-VIT": 5,
    "IMG-RXT": 6, "IMG-RXO": 5, "IMG-USG": 6, "IMG-USO": 4, "IMG-ECO": 4, "IMG-MMG": 4,
    # imagem complexa (menos frequente)
    "IMG-TC": 2.2, "IMG-RM": 1.8, "IMG-RMJ": 1.6, "IMG-CIN": 0.6,
    # ambulatoriais
    "END-EDA": 1.6, "END-COL": 1.2, "CAR-HOL": 1.4, "CAR-TE": 1.4, "NEU-EEG": 1.0,
    "OFT-MAP": 3.0, "OFT-OCT": 1.6, "DER-BIO": 1.2, "URO-URF": 1.0, "DER-CRIO": 2.0,
    "GAS-POL": 0.5, "URO-VAS": 0.4, "OFT-LAS": 0.5, "CAR-CAT": 0.5,
    # cirurgias / internações (raras)
    "CIR-CAT": 0.9, "CIR-PTG": 0.25, "CIR-GLA": 0.18, "CIR-VIT": 0.10,
    "CIR-ARTJ": 0.28, "CIR-ARTQ": 0.10, "CIR-ARTJT": 0.10, "CIR-FRAT": 0.18,
    "OPME-QUA": 0.09, "OPME-JOE": 0.09, "OPME-COL": 0.06,
    "CIR-COL": 0.22, "CIR-HER": 0.18, "CIR-RTU": 0.10, "CIR-NEF": 0.10,
    "GIN-HIS": 0.10, "OBS-PN": 0.55, "OBS-PC": 0.55, "OBS-CUR": 0.10,
    "INT-PNM": 0.30, "INT-DPOC": 0.16, "INT-ICC": 0.16, "INT-AVC": 0.10,
    "INT-IAM": 0.09, "INT-GEA": 0.30, "INT-ITU": 0.16, "INT-SEP": 0.05,
    "CAR-ANG": 0.10,
    # alto custo / terapias
    "ONC-QT1": 1.4, "ONC-QT2": 0.5, "ONC-RXT": 1.0, "NEF-HD": 0.8, "IMB-INF": 0.4,
    "FIS-SES": 30, "FIS-RPG": 6, "PSI-PSICO": 14, "FON-SES": 6, "TO-SES": 5,
}

# Tipos de atendimento e leve variação em torno do "típico" do procedimento.
SEXO_PESOS = {"M": 0.49, "F": 0.51}
