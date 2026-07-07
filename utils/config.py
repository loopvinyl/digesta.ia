# =============================================================================
# CONFIGURAÇÕES GLOBAIS – DIGESTA.IA
# Metodologias: UNFCCC A6.4-AMT-003 (TOOL04), TOOL14, ACM0022
# IPCC AR5 (GWP-100)
# =============================================================================

# GWP (AR5)
GWP_CH4 = 28.0
GWP_N2O = 265.0

# TOOL04 – Baseline (aterro) – Application B (clima úmido)
PHI_APPLICATION_B = 0.85
OX_SOIL_COVER = 0.383          # aterro com cobertura de solo
F_METHANE_FRACTION = 0.5
MCF_DEFAULT_BULK = 0.8

# TOOL14 – Emissões do biodigestor (CSTR com pré-processamento)
F_EC_DEFAULT = 1.54             # MWh / t CH4 produzido
EF_EL_DEFAULT = 1.3             # t CO2 / MWh
EF_CH4_DEFAULT = 0.028          # fração de CH4 vazado (CSTR)
F_WW_CH4_DEFAULT = 0.20         # CH4 residual do digestato armazenado
DENSITY_CH4 = 0.00067           # t CH4 / Nm³

# Parâmetros de resíduo (default)
DOC_PADRAO = 0.15
K_PADRAO = 0.07
T_ORGANICO = 25.0

# Projeção
ANOS_PROJECAO = 20
DIAS_PROJECAO = ANOS_PROJECAO * 365
