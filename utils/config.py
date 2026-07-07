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
F_WW_CH4_DEFAULT = 0.20         # CH4 residual do digestato armazenado
DENSITY_CH4 = 0.00067           # t CH4 / Nm³

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

# Valor default para resíduo alimentar (caso da USP)
DOCF_DEFAULT = DOCF_POR_TIPO['alimentos']

# Projeção
ANOS_PROJECAO = 20
DIAS_PROJECAO = ANOS_PROJECAO * 365
