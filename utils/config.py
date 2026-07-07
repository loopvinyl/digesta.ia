# =============================================================================
# CONFIGURAÇÕES GLOBAIS – DIGESTA.IA
# Metodologias: UNFCCC A6.4-AMT-003 (2025), TOOL14, ACM0022
# IPCC AR5 (GWP-100)
# =============================================================================

# GWP (AR5) – IPCC AR5
GWP_CH4 = 28.0
GWP_N2O = 265.0

# TOOL04 / A6.4-AMT-003 – Baseline (aterro) – Application B (clima úmido)
PHI_APPLICATION_B = 0.85
OX_SOIL_COVER = 0.383          # aterro com cobertura de solo (Tabela 2 da A6.4-AMT-003)
F_METHANE_FRACTION = 0.5
MCF_DEFAULT_BULK = 0.8

# TOOL14 – Emissões do biodigestor (CSTR com pré-processamento)
F_EC_DEFAULT = 1.54             # MWh / t CH4 produzido
EF_EL_DEFAULT = 1.3             # t CO2 / MWh
EF_CH4_DEFAULT = 0.028          # fração de CH4 vazado (CSTR)
DENSITY_CH4 = 0.00067           # t CH4 / Nm³

# =============================================================================
# TOOL14 – Fatores de vazamento do digestato (storage_factor) – Tabelas 9 e 10
# =============================================================================
STORAGE_FACTOR_POR_TIPO = {
    'CSTR': 0.20,               # Digestor convencional (CSTR) – líquido
    'UASB': 0.15,               # UASB / Filtro anaeróbico / Leito fluidizado
    'Lagoa coberta': 0.10,      # Lagoa anaeróbica coberta
    'Dois estágios': 0.05,      # Digestor de dois estágios (líquido)
    'Sólido (outros)': 0.35     # Digestato sólido – todas as outras tecnologias
}

# =============================================================================
# INTERVALOS DE OSCILAÇÃO REALISTA PARA O STORAGE_FACTOR (SOBOL / MONTE CARLO)
# Cada intervalo é uma tupla (min, max) representando a faixa de variação
# em torno do valor padrão de cada tipo de digestor.
# =============================================================================
STORAGE_FACTOR_RANGES = {
    'CSTR': (0.10, 0.35),        # Variação de ±75% em torno de 0.20
    'UASB': (0.05, 0.30),        # Variação de ±100% em torno de 0.15
    'Lagoa coberta': (0.00, 0.25) # Variação de ±150% em torno de 0.10, com mínimo 0
}

# Valor padrão (fallback)
STORAGE_FACTOR_DEFAULT = STORAGE_FACTOR_POR_TIPO['CSTR']

# Parâmetros de resíduo (default)
DOC_PADRAO = 0.15               # fração de carbono orgânico degradável (para resíduo alimentar)
K_PADRAO = 0.07                 # taxa de decaimento padrão (fallback)

# =============================================================================
# UNFCCC A6.4-AMT-003 (2025) – Tabela 7: Valores default para DOCf
# =============================================================================
DOCF_POR_TIPO = {
    'alimentos': 0.7,      # altamente decomponível (restos de comida, grama, resíduos de jardim)
    'papel': 0.5,          # moderadamente decomponível (papel, têxteis, fraldas)
    'madeira': 0.1,        # menos decomponível (madeira, produtos de madeira)
    'bulk': 0.5            # resíduo a granel (quando a composição não é conhecida)
}

DOCF_DEFAULT = DOCF_POR_TIPO['alimentos']

# Projeção
ANOS_PROJECAO = 20
DIAS_PROJECAO = ANOS_PROJECAO * 365
