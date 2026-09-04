"""Catálogos determinísticos do gerador (não dependem de seed).

Especialidades, procedimentos, planos, contratos, regiões, prestadores e diagnósticos.
Referências entre entidades usam *slugs*; o loader converte para ids reais do banco.
Coerência clínica embutida: faixa etária alvo, especialidade correspondente, custo por
complexidade, tipo de atendimento típico.
"""

from __future__ import annotations

# --------------------------------------------------------------------------------------
# Especialidades (slug, nome, grupo)
# --------------------------------------------------------------------------------------
ESPECIALIDADES: list[tuple[str, str, str]] = [
    ("clinica_medica", "Clínica Médica", "clinica"),
    ("pediatria", "Pediatria", "clinica"),
    ("cardiologia", "Cardiologia", "clinica"),
    ("ortopedia", "Ortopedia e Traumatologia", "cirurgica"),
    ("oftalmologia", "Oftalmologia", "cirurgica"),
    ("gineco_obst", "Ginecologia e Obstetrícia", "cirurgica"),
    ("oncologia", "Oncologia Clínica", "clinica"),
    ("pneumologia", "Pneumologia", "clinica"),
    ("gastro", "Gastroenterologia", "clinica"),
    ("neurologia", "Neurologia", "clinica"),
    ("psiquiatria", "Psiquiatria", "clinica"),
    ("dermatologia", "Dermatologia", "clinica"),
    ("urologia", "Urologia", "cirurgica"),
    ("radiologia", "Radiologia e Diagnóstico por Imagem", "diagnostico"),
    ("fisioterapia", "Fisioterapia e Terapias", "terapia"),
]

# --------------------------------------------------------------------------------------
# Procedimentos
# (codigo, descricao, espec_slug, grupo, complexidade, custo_base, tipo_atend, idade_min, idade_max)
# --------------------------------------------------------------------------------------
PROCEDIMENTOS: list[tuple[str, str, str, str, int, float, str, int, int]] = [
    # Consultas (uma por especialidade) -----------------------------------------------
    ("CON-CLM", "Consulta em clínica médica", "clinica_medica", "Consultas", 1, 180, "consulta", 14, 120),
    ("CON-PED", "Consulta pediátrica", "pediatria", "Consultas", 1, 190, "consulta", 0, 13),
    ("CON-CAR", "Consulta cardiológica", "cardiologia", "Consultas", 1, 260, "consulta", 25, 120),
    ("CON-ORT", "Consulta ortopédica", "ortopedia", "Consultas", 1, 240, "consulta", 5, 120),
    ("CON-OFT", "Consulta oftalmológica", "oftalmologia", "Consultas", 1, 230, "consulta", 0, 120),
    ("CON-GIN", "Consulta ginecológica", "gineco_obst", "Consultas", 1, 240, "consulta", 12, 85),
    ("CON-ONC", "Consulta oncológica", "oncologia", "Consultas", 1, 320, "consulta", 18, 120),
    ("CON-PNE", "Consulta pneumológica", "pneumologia", "Consultas", 1, 250, "consulta", 0, 120),
    ("CON-GAS", "Consulta gastroenterológica", "gastro", "Consultas", 1, 250, "consulta", 5, 120),
    ("CON-NEU", "Consulta neurológica", "neurologia", "Consultas", 1, 300, "consulta", 0, 120),
    ("CON-PSI", "Consulta psiquiátrica", "psiquiatria", "Consultas", 1, 300, "consulta", 8, 120),
    ("CON-DER", "Consulta dermatológica", "dermatologia", "Consultas", 1, 220, "consulta", 0, 120),
    ("CON-URO", "Consulta urológica", "urologia", "Consultas", 1, 250, "consulta", 12, 120),
    # Pronto-socorro -----------------------------------------------------------------
    ("PS-CLM", "Atendimento de pronto-socorro clínico", "clinica_medica", "Pronto-socorro", 2, 420, "pronto_socorro", 14, 120),
    ("PS-PED", "Atendimento de pronto-socorro pediátrico", "pediatria", "Pronto-socorro", 2, 380, "pronto_socorro", 0, 13),
    ("PS-ORT", "Atendimento de pronto-socorro ortopédico", "ortopedia", "Pronto-socorro", 2, 520, "pronto_socorro", 5, 120),
    # Exames laboratoriais ---------------------------------------------------------
    ("LAB-HMG", "Hemograma completo", "clinica_medica", "Exames laboratoriais", 1, 22, "exame", 0, 120),
    ("LAB-GLI", "Glicemia de jejum", "clinica_medica", "Exames laboratoriais", 1, 12, "exame", 0, 120),
    ("LAB-LIP", "Perfil lipídico", "cardiologia", "Exames laboratoriais", 1, 45, "exame", 18, 120),
    ("LAB-TSH", "Dosagem de TSH", "clinica_medica", "Exames laboratoriais", 1, 38, "exame", 0, 120),
    ("LAB-PSA", "Antígeno prostático específico (PSA)", "urologia", "Exames laboratoriais", 1, 55, "exame", 40, 120),
    ("LAB-URC", "Urocultura", "clinica_medica", "Exames laboratoriais", 1, 40, "exame", 0, 120),
    ("LAB-BHCG", "Beta-hCG", "gineco_obst", "Exames laboratoriais", 1, 48, "exame", 12, 55),
    ("LAB-VIT", "Dosagem de vitamina D", "clinica_medica", "Exames laboratoriais", 1, 70, "exame", 5, 120),
    # Exames de imagem simples ---------------------------------------------------
    ("IMG-RXT", "Radiografia de tórax", "radiologia", "Exames de imagem", 2, 95, "exame", 0, 120),
    ("IMG-RXO", "Radiografia de membro/óssea", "radiologia", "Exames de imagem", 2, 110, "exame", 0, 120),
    ("IMG-USG", "Ultrassonografia abdominal", "radiologia", "Exames de imagem", 2, 180, "exame", 0, 120),
    ("IMG-USO", "Ultrassonografia obstétrica", "gineco_obst", "Exames de imagem", 2, 210, "exame", 12, 50),
    ("IMG-ECO", "Ecocardiograma transtorácico", "cardiologia", "Exames de imagem", 3, 340, "exame", 5, 120),
    ("IMG-MMG", "Mamografia bilateral", "radiologia", "Exames de imagem", 2, 160, "exame", 35, 80),
    # Exames de imagem complexos ----------------------------------------------
    ("IMG-TC", "Tomografia computadorizada", "radiologia", "Exames de imagem", 4, 620, "exame", 0, 120),
    ("IMG-RM", "Ressonância magnética", "radiologia", "Exames de imagem", 4, 1150, "exame", 0, 120),
    ("IMG-RMJ", "Ressonância magnética de articulação", "ortopedia", "Exames de imagem", 4, 1250, "exame", 8, 120),
    ("IMG-CIN", "Cintilografia", "radiologia", "Exames de imagem", 4, 980, "exame", 10, 120),
    # Endoscopia / diagnóstico invasivo --------------------------------------
    ("END-EDA", "Endoscopia digestiva alta", "gastro", "Procedimentos ambulatoriais", 3, 640, "exame", 12, 120),
    ("END-COL", "Colonoscopia", "gastro", "Procedimentos ambulatoriais", 3, 980, "exame", 30, 120),
    ("CAR-HOL", "Holter 24h", "cardiologia", "Procedimentos ambulatoriais", 2, 260, "exame", 15, 120),
    ("CAR-TE", "Teste ergométrico", "cardiologia", "Procedimentos ambulatoriais", 2, 300, "exame", 20, 100),
    ("NEU-EEG", "Eletroencefalograma", "neurologia", "Procedimentos ambulatoriais", 2, 280, "exame", 0, 120),
    ("OFT-MAP", "Mapeamento de retina", "oftalmologia", "Procedimentos ambulatoriais", 2, 190, "exame", 0, 120),
    ("OFT-OCT", "Tomografia de coerência óptica (OCT)", "oftalmologia", "Procedimentos ambulatoriais", 3, 320, "exame", 20, 120),
    ("DER-BIO", "Biópsia de pele", "dermatologia", "Procedimentos ambulatoriais", 2, 240, "exame", 5, 120),
    ("URO-URF", "Urofluxometria", "urologia", "Procedimentos ambulatoriais", 2, 180, "exame", 18, 120),
    # Cirurgias oftalmológicas --------------------------------------------
    ("CIR-CAT", "Facectomia com implante de LIO (catarata)", "oftalmologia", "Cirurgias oftalmológicas", 3, 4200, "cirurgia", 45, 120),
    ("CIR-PTG", "Exérese de pterígio", "oftalmologia", "Cirurgias oftalmológicas", 2, 1800, "cirurgia", 25, 100),
    ("CIR-GLA", "Trabeculectomia (glaucoma)", "oftalmologia", "Cirurgias oftalmológicas", 4, 5200, "cirurgia", 40, 120),
    ("CIR-VIT", "Vitrectomia", "oftalmologia", "Cirurgias oftalmológicas", 5, 9800, "cirurgia", 30, 120),
    # Cirurgias ortopédicas + OPME --------------------------------------
    ("CIR-ARTJ", "Artroscopia de joelho", "ortopedia", "Cirurgias ortopédicas", 3, 6800, "cirurgia", 15, 80),
    ("CIR-ARTQ", "Artroplastia total de quadril", "ortopedia", "Cirurgias ortopédicas", 5, 24000, "cirurgia", 45, 95),
    ("CIR-ARTJT", "Artroplastia total de joelho", "ortopedia", "Cirurgias ortopédicas", 5, 22000, "cirurgia", 45, 95),
    ("CIR-FRAT", "Osteossíntese de fratura", "ortopedia", "Cirurgias ortopédicas", 4, 12000, "cirurgia", 5, 100),
    ("OPME-QUA", "OPME - prótese de quadril", "ortopedia", "OPME", 5, 15000, "opme", 45, 95),
    ("OPME-JOE", "OPME - prótese de joelho", "ortopedia", "OPME", 5, 14000, "opme", 45, 95),
    ("OPME-COL", "OPME - material de artrodese de coluna", "ortopedia", "OPME", 5, 18000, "opme", 25, 90),
    # Cirurgias gerais / urologia --------------------------------------
    ("CIR-COL", "Colecistectomia videolaparoscópica", "gastro", "Internações cirúrgicas", 4, 9500, "cirurgia", 18, 90),
    ("CIR-HER", "Herniorrafia inguinal", "gastro", "Internações cirúrgicas", 3, 5200, "cirurgia", 5, 90),
    ("CIR-RTU", "Ressecção transuretral de próstata (RTU)", "urologia", "Internações cirúrgicas", 4, 8800, "cirurgia", 50, 95),
    ("CIR-NEF", "Nefrolitotripsia", "urologia", "Internações cirúrgicas", 4, 7600, "cirurgia", 20, 90),
    # Obstetrícia ----------------------------------------------------
    ("OBS-PN", "Parto normal", "gineco_obst", "Obstetrícia", 3, 3400, "internacao", 14, 49),
    ("OBS-PC", "Parto cesáreo", "gineco_obst", "Obstetrícia", 3, 5100, "cirurgia", 14, 49),
    ("OBS-CUR", "Curetagem pós-aborto", "gineco_obst", "Obstetrícia", 2, 2200, "cirurgia", 14, 49),
    ("GIN-HIS", "Histerectomia", "gineco_obst", "Internações cirúrgicas", 4, 9200, "cirurgia", 35, 80),
    # Internações clínicas -----------------------------------------
    ("INT-PNM", "Internação por pneumonia", "pneumologia", "Internações clínicas", 4, 7800, "internacao", 0, 120),
    ("INT-DPOC", "Internação por exacerbação de DPOC", "pneumologia", "Internações clínicas", 4, 9200, "internacao", 45, 120),
    ("INT-ICC", "Internação por insuficiência cardíaca", "cardiologia", "Internações clínicas", 4, 11000, "internacao", 45, 120),
    ("INT-AVC", "Internação por AVC", "neurologia", "Internações clínicas", 5, 16500, "internacao", 40, 120),
    ("INT-IAM", "Internação por infarto agudo do miocárdio", "cardiologia", "Internações clínicas", 5, 21000, "internacao", 40, 120),
    ("INT-GEA", "Internação por gastroenterite", "pediatria", "Internações clínicas", 3, 4200, "internacao", 0, 13),
    ("INT-ITU", "Internação por infecção urinária/pielonefrite", "clinica_medica", "Internações clínicas", 3, 5200, "internacao", 0, 120),
    ("INT-SEP", "Internação por sepse", "clinica_medica", "Internações clínicas", 5, 28000, "internacao", 0, 120),
    # Quimioterapia / alto custo --------------------------------
    ("ONC-QT1", "Sessão de quimioterapia - esquema padrão", "oncologia", "Quimioterapia e alto custo", 4, 4200, "terapia", 18, 120),
    ("ONC-QT2", "Sessão de quimioterapia - alto custo (alvo/imuno)", "oncologia", "Quimioterapia e alto custo", 5, 16500, "terapia", 18, 120),
    ("ONC-RXT", "Sessão de radioterapia", "oncologia", "Quimioterapia e alto custo", 4, 1900, "terapia", 18, 120),
    ("NEF-HD", "Sessão de hemodiálise", "clinica_medica", "Quimioterapia e alto custo", 4, 430, "terapia", 12, 120),
    ("IMB-INF", "Infusão de imunobiológico", "clinica_medica", "Quimioterapia e alto custo", 5, 6800, "terapia", 12, 120),
    # Terapias --------------------------------------------------
    ("FIS-SES", "Sessão de fisioterapia", "fisioterapia", "Terapias", 1, 95, "terapia", 0, 120),
    ("FIS-RPG", "Sessão de fisioterapia - RPG", "fisioterapia", "Terapias", 1, 130, "terapia", 12, 100),
    ("PSI-PSICO", "Sessão de psicoterapia", "psiquiatria", "Terapias", 1, 200, "terapia", 6, 120),
    ("FON-SES", "Sessão de fonoaudiologia", "fisioterapia", "Terapias", 1, 120, "terapia", 0, 90),
    ("TO-SES", "Sessão de terapia ocupacional", "fisioterapia", "Terapias", 1, 120, "terapia", 0, 90),
    # Ambulatoriais diversos --------------------------------
    ("DER-CRIO", "Crioterapia de lesões de pele", "dermatologia", "Procedimentos ambulatoriais", 1, 160, "consulta", 5, 120),
    ("OFT-LAS", "Fotocoagulação a laser de retina", "oftalmologia", "Procedimentos ambulatoriais", 3, 900, "cirurgia", 30, 120),
    ("CAR-CAT", "Cateterismo cardíaco diagnóstico", "cardiologia", "Procedimentos ambulatoriais", 4, 3200, "internacao", 35, 120),
    ("CAR-ANG", "Angioplastia coronariana com stent", "cardiologia", "Internações cirúrgicas", 5, 19000, "internacao", 40, 120),
    ("URO-VAS", "Vasectomia", "urologia", "Procedimentos ambulatoriais", 2, 1200, "cirurgia", 25, 60),
    ("GAS-POL", "Polipectomia endoscópica", "gastro", "Procedimentos ambulatoriais", 3, 1400, "exame", 30, 100),
]

# --------------------------------------------------------------------------------------
# Planos (codigo, nome, segmentacao, ticket_medio_base)
# --------------------------------------------------------------------------------------
# (codigo, nome, segmentacao, ticket_medio_base, tem_coparticipacao, percentual_coparticipacao)
# Coparticipação incide sobre valor_pago de consulta/exame/terapia/pronto-socorro (não
# sobre internação/cirurgia/OPME — ver generator.py). Planos empresariais e de
# apartamento tipicamente não cobram; individuais/PME de entrada, sim.
PLANOS: list[tuple[str, str, str, float, bool, float]] = [
    ("AMB-E-PF", "Ambulatorial Essencial PF", "ambulatorial", 210, True, 0.30),
    ("AMB-E-PME", "Ambulatorial Essencial PME", "ambulatorial", 235, True, 0.25),
    ("HOSP-E-PF", "Hospitalar Enfermaria PF", "hospitalar", 320, True, 0.20),
    ("HOSP-E-PME", "Hospitalar Enfermaria PME", "hospitalar", 355, True, 0.15),
    ("HOSP-E-EMP", "Hospitalar Enfermaria Empresarial", "hospitalar", 300, False, 0.0),
    ("COMP-E-PF", "Completo Enfermaria PF", "completo", 430, True, 0.15),
    ("COMP-E-PME", "Completo Enfermaria PME", "completo", 465, True, 0.10),
    ("COMP-E-EMP", "Completo Enfermaria Empresarial", "completo", 410, False, 0.0),
    ("COMP-A-PF", "Completo Apartamento PF", "completo", 620, False, 0.0),
    ("COMP-A-PME", "Completo Apartamento PME", "completo", 660, False, 0.0),
    ("COMP-A-EMP", "Completo Apartamento Empresarial", "completo", 585, False, 0.0),
    ("PREM-A-EMP", "Premium Apartamento Empresarial", "completo", 780, False, 0.0),
]

# Contratos (codigo_plano, nome_contrato, tipo)
CONTRATOS: list[tuple[str, str, str]] = [
    ("AMB-E-PF", "Adesão Individual Essencial", "PF"),
    ("AMB-E-PME", "Coletivo por Adesão - Conselhos", "PME"),
    ("HOSP-E-PF", "Individual Enfermaria", "PF"),
    ("HOSP-E-PME", "PME Comércio & Serviços", "PME"),
    ("HOSP-E-EMP", "Empresarial Indústria Metalúrgica", "Empresarial"),
    ("COMP-E-PF", "Individual Completo Enfermaria", "PF"),
    ("COMP-E-PME", "PME Tecnologia", "PME"),
    ("COMP-E-EMP", "Empresarial Varejo Nacional", "Empresarial"),
    ("COMP-A-PF", "Individual Completo Apartamento", "PF"),
    ("COMP-A-PME", "PME Escritórios de Advocacia", "PME"),
    ("COMP-A-EMP", "Empresarial Serviços Financeiros", "Empresarial"),
    ("PREM-A-EMP", "Empresarial Premium - Executivos", "Empresarial"),
]

# --------------------------------------------------------------------------------------
# Regiões (cidade, uf, macrorregiao) e pesos de distribuição da carteira
# --------------------------------------------------------------------------------------
REGIOES: list[tuple[str, str, str, float]] = [
    ("São Paulo", "SP", "Sudeste", 0.24),
    ("Campinas", "SP", "Sudeste", 0.09),
    ("Rio de Janeiro", "RJ", "Sudeste", 0.14),
    ("Belo Horizonte", "MG", "Sudeste", 0.10),
    ("Curitiba", "PR", "Sul", 0.08),
    ("Porto Alegre", "RS", "Sul", 0.07),
    ("Florianópolis", "SC", "Sul", 0.04),
    ("Salvador", "BA", "Nordeste", 0.07),
    ("Recife", "PE", "Nordeste", 0.06),
    ("Fortaleza", "CE", "Nordeste", 0.05),
    ("Brasília", "DF", "Centro-Oeste", 0.04),
    ("Goiânia", "GO", "Centro-Oeste", 0.02),
]

# --------------------------------------------------------------------------------------
# Diagnósticos (cid fictício, descrição, espec_slug|None)
# --------------------------------------------------------------------------------------
DIAGNOSTICOS: list[tuple[str, str, str | None]] = [
    ("W2-E11", "Diabetes mellitus tipo 2", "clinica_medica"),
    ("W2-I10", "Hipertensão essencial", "cardiologia"),
    ("W2-I50", "Insuficiência cardíaca", "cardiologia"),
    ("W2-I21", "Infarto agudo do miocárdio", "cardiologia"),
    ("W2-I63", "Acidente vascular cerebral isquêmico", "neurologia"),
    ("W2-J45", "Asma", "pneumologia"),
    ("W2-J44", "DPOC", "pneumologia"),
    ("W2-J18", "Pneumonia", "pneumologia"),
    ("W2-J06", "Infecção respiratória aguda", "clinica_medica"),
    ("W2-H25", "Catarata senil", "oftalmologia"),
    ("W2-H40", "Glaucoma", "oftalmologia"),
    ("W2-H33", "Descolamento de retina", "oftalmologia"),
    ("W2-M17", "Gonartrose (artrose de joelho)", "ortopedia"),
    ("W2-M16", "Coxartrose (artrose de quadril)", "ortopedia"),
    ("W2-S72", "Fratura de fêmur", "ortopedia"),
    ("W2-M54", "Dor lombar", "ortopedia"),
    ("W2-K80", "Colelitíase", "gastro"),
    ("W2-K40", "Hérnia inguinal", "gastro"),
    ("W2-K21", "Doença do refluxo gastroesofágico", "gastro"),
    ("W2-N20", "Cálculo urinário", "urologia"),
    ("W2-N40", "Hiperplasia prostática benigna", "urologia"),
    ("W2-N39", "Infecção do trato urinário", "clinica_medica"),
    ("W2-C50", "Neoplasia maligna de mama", "oncologia"),
    ("W2-C18", "Neoplasia maligna de cólon", "oncologia"),
    ("W2-C61", "Neoplasia maligna de próstata", "oncologia"),
    ("W2-C34", "Neoplasia maligna de pulmão", "oncologia"),
    ("W2-N18", "Doença renal crônica", "clinica_medica"),
    ("W2-F41", "Transtorno de ansiedade", "psiquiatria"),
    ("W2-F32", "Episódio depressivo", "psiquiatria"),
    ("W2-F84", "Transtorno do espectro autista", "psiquiatria"),
    ("W2-O80", "Parto único espontâneo", "gineco_obst"),
    ("W2-O82", "Parto único por cesariana", "gineco_obst"),
    ("W2-Z34", "Supervisão de gravidez normal", "gineco_obst"),
    ("W2-L40", "Psoríase", "dermatologia"),
    ("W2-L70", "Acne", "dermatologia"),
    ("W2-A09", "Gastroenterite infecciosa", "pediatria"),
    ("W2-R51", "Cefaleia", "neurologia"),
    ("W2-G40", "Epilepsia", "neurologia"),
    ("W2-M79", "Fibromialgia / dor musculoesquelética", "fisioterapia"),
    ("W2-Z00", "Exame médico geral / check-up", None),
]

# Tipos de prestador e quantos gerar de cada
PRESTADOR_TIPOS: list[tuple[str, int]] = [
    ("hospital", 22),
    ("clinica", 46),
    ("laboratorio", 20),
    ("pronto_atendimento", 14),
    ("consultorio", 24),
]

# Palavras para compor nomes fictícios de prestadores (sem qualquer referência real).
_HOSP_NOMES = [
    "São Rafael", "Santa Helena", "Bom Pastor", "Vida Nova", "Aurora", "Monte Azul",
    "São Bento", "Nossa Senhora da Paz", "Central", "Real", "Bandeirantes", "Ipê",
    "Santa Cruz", "São Camilo", "Portal", "Luz", "Primavera", "Horizonte", "Jardins",
    "Cristal", "Guararapes", "Alvorada",
]
_CLIN_NOMES = [
    "Visão", "CardioCare", "OrtoMovimento", "Respirar", "NeuroVida", "Derma Estética",
    "Gastro Saúde", "UroCentro", "MulherViva", "Endoclínica", "Reabilitar", "Clinilab",
    "ProCorpo", "Imagem Diagnóstica", "Bem Estar", "SaúdePlena", "VitaClin", "Instituto do Olho",
    "Centro Ortopédico", "Núcleo Cardio", "Espaço Terapêutico", "da Coluna",
    "Oftalmocenter", "PneumoLab", "OncoVida", "Sorrir", "MedPrev", "CliniCor",
    "Instituto Neuro", "Reviver", "MoveBem", "ClinFisio", "Pediatria Feliz", "Materno",
    "Diagnósticos SP", "Laboratório Central", "OrtoClínica", "Renal", "InfusãoCenter",
    "Dermato", "CentroMed", "Integrada", "SaúdeUrbana", "VidaPlena",
    "Aliança", "Progresso",
]

# --------------------------------------------------------------------------------------
# Perfil de utilização por grupo de procedimento — apoio à classificação de hipóteses na
# análise de coortes (v1.1, Etapa A). Grupos ausentes caem em "variavel" por padrão.
# --------------------------------------------------------------------------------------
GRUPO_PERFIL_UTILIZACAO: dict[str, str] = {
    "Consultas": "recorrente",
    "Exames laboratoriais": "recorrente",
    "Terapias": "recorrente",
    "Quimioterapia e alto custo": "recorrente",
    "Pronto-socorro": "variavel",
    "Exames de imagem": "variavel",
    "Procedimentos ambulatoriais": "variavel",
    "Cirurgias oftalmológicas": "pontual",
    "Cirurgias ortopédicas": "pontual",
    "OPME": "pontual",
    "Internações cirúrgicas": "pontual",
    "Internações clínicas": "pontual",
    "Obstetrícia": "pontual",
}

__all__ = [
    "ESPECIALIDADES",
    "PROCEDIMENTOS",
    "PLANOS",
    "CONTRATOS",
    "REGIOES",
    "DIAGNOSTICOS",
    "GRUPO_PERFIL_UTILIZACAO",
    "PRESTADOR_TIPOS",
    "_HOSP_NOMES",
    "_CLIN_NOMES",
]
