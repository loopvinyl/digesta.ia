import numpy as np
import pandas as pd
from utils.config import *

# =============================================================================
# BASELINE (UNFCCC A6.4-AMT-003, 2025) – Emissões do aterro
# =============================================================================

def calcular_baseline_aterro(
    massa_kg,
    captura_metano=0.0,
    k=K_PADRAO,
    doc=DOC_PADRAO,
    docf=DOCF_DEFAULT,
    mcf=1.0,
    anos=ANOS_PROJECAO,
    gwp_ch4=GWP_CH4
):
    """
    Retorna o total de CO2e (t) emitido ao longo de ANOS_PROJECAO.
    Agora usando DOCf fixo (Tabela 7 da A6.4-AMT-003) e gwp_ch4 opcional.
    """
    if massa_kg <= 0:
        return 0.0
    phi = PHI_APPLICATION_B
    ox = OX_SOIL_COVER
    f = F_METHANE_FRACTION
    ch4_pot_por_kg = (doc * docf * mcf * f * (16/12) * (1 - ox) * phi) * (1 - captura_metano)
    dias = anos * 365
    entrada = np.zeros(dias)
    dias_entrada = 365
    if dias_entrada > dias:
        dias_entrada = dias
    entrada[:dias_entrada] = massa_kg / dias_entrada
    t = np.arange(1, dias+1, dtype=float)
    kernel = np.exp(-k * (t-1)/365) - np.exp(-k * t/365)
    kernel = np.maximum(kernel, 0)
    ch4_diario_kg = np.convolve(entrada, kernel, mode='full')[:dias] * ch4_pot_por_kg
    co2eq_t = (ch4_diario_kg * gwp_ch4) / 1000.0
    return co2eq_t.sum()

def calcular_baseline_aterro_series(
    massa_kg,
    captura_metano=0.0,
    k=K_PADRAO,
    doc=DOC_PADRAO,
    docf=DOCF_DEFAULT,
    mcf=1.0,
    anos=ANOS_PROJECAO,
    gwp_ch4=GWP_CH4
):
    """
    Retorna array diário de CO2e (t) para o baseline (aterro).
    Agora usando DOCf fixo (Tabela 7 da A6.4-AMT-003) e gwp_ch4 opcional.
    """
    if massa_kg <= 0:
        return np.zeros(anos * 365)
    phi = PHI_APPLICATION_B
    ox = OX_SOIL_COVER
    f = F_METHANE_FRACTION
    ch4_pot_por_kg = (doc * docf * mcf * f * (16/12) * (1 - ox) * phi) * (1 - captura_metano)
    dias = anos * 365
    entrada = np.zeros(dias)
    dias_entrada = 365
    if dias_entrada > dias:
        dias_entrada = dias
    entrada[:dias_entrada] = massa_kg / dias_entrada
    t = np.arange(1, dias+1, dtype=float)
    kernel = np.exp(-k * (t-1)/365) - np.exp(-k * t/365)
    kernel = np.maximum(kernel, 0)
    ch4_diario_kg = np.convolve(entrada, kernel, mode='full')[:dias] * ch4_pot_por_kg
    co2eq_diario_t = (ch4_diario_kg * gwp_ch4) / 1000.0
    return co2eq_diario_t

# =============================================================================
# ESTIMATIVA DE METANO PRODUZIDO
# =============================================================================

def estimar_metano_produzido(massa_ano_kg, eficiencia_motor=0.40, pci_biogas_mj_m3=21.5, f_ch4=0.6):
    """
    Estima a quantidade de CH4 (t) produzida a partir da digestão anaeróbica.
    Aproximação: 1 kg de resíduo alimentar gera ~0,1 Nm³ de CH4.
    """
    ch4_nm3 = massa_ano_kg * 0.10   # 0,1 Nm³/kg
    ch4_t = ch4_nm3 * DENSITY_CH4
    return ch4_t

# =============================================================================
# EMISSÕES DO BIODIGESTOR (TOOL14) – COM STORAGE_FACTOR DINÂMICO
# =============================================================================

def calcular_emissoes_biodigestor(q_ch4_t, tipo='CSTR', storage_factor=None):
    """
    Retorna: PE_EC, PE_CH4, PE_flare, LE_storage (t CO2e)
    - storage_factor: fração do CH4 produzido que vaza do digestato.
      Se None, usa o valor padrão baseado no tipo de digestor (TOOL14).
    """
    # Definir fatores padrão baseados no tipo de digestor (TOOL14)
    if tipo == 'CSTR':
        f_ec = F_EC_DEFAULT
        ef_ch4 = EF_CH4_DEFAULT
        default_storage = STORAGE_FACTOR_POR_TIPO.get('CSTR', 0.20)
    elif tipo == 'UASB':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('UASB', 0.15)
    elif tipo == 'Lagoa coberta':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('Lagoa coberta', 0.10)
    else:
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = 0.20

    if storage_factor is None:
        storage_factor = default_storage
    storage_factor = max(0.0, min(0.5, storage_factor))

    PE_EC = q_ch4_t * f_ec * EF_EL_DEFAULT
    PE_CH4 = q_ch4_t * ef_ch4 * GWP_CH4
    PE_flare = 0.0
    LE_storage = q_ch4_t * storage_factor * GWP_CH4

    return PE_EC, PE_CH4, PE_flare, LE_storage

def calcular_emissoes_biodigestor_series(q_ch4_t, tipo='CSTR', storage_factor=None, anos=ANOS_PROJECAO):
    """
    Retorna dicionário com séries diárias de PE_EC, PE_CH4, LE_storage (t CO2e/dia).
    As emissões são distribuídas uniformemente ao longo dos dias.
    """
    dias = anos * 365

    if tipo == 'CSTR':
        f_ec = F_EC_DEFAULT
        ef_ch4 = EF_CH4_DEFAULT
        default_storage = STORAGE_FACTOR_POR_TIPO.get('CSTR', 0.20)
    elif tipo == 'UASB':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('UASB', 0.15)
    elif tipo == 'Lagoa coberta':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('Lagoa coberta', 0.10)
    else:
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = 0.20

    if storage_factor is None:
        storage_factor = default_storage
    storage_factor = max(0.0, min(0.5, storage_factor))

    PE_EC_dia = (q_ch4_t * f_ec * EF_EL_DEFAULT) / dias
    PE_CH4_dia = (q_ch4_t * ef_ch4 * GWP_CH4) / dias
    LE_storage_dia = (q_ch4_t * storage_factor * GWP_CH4) / dias

    return {
        'PE_EC': np.full(dias, PE_EC_dia),
        'PE_CH4': np.full(dias, PE_CH4_dia),
        'LE_storage': np.full(dias, LE_storage_dia),
        'PE_total': np.full(dias, PE_EC_dia + PE_CH4_dia),
        'LE_total': np.full(dias, LE_storage_dia)
    }

# =============================================================================
# REDUÇÃO LÍQUIDA (ACM0022) – VERSÕES COM PARÂMETROS EXPLÍCITOS
# =============================================================================

def calcular_reducoes_com_parametros(
    massa_ano_kg: float,
    k: float,
    doc: float,
    docf: float = DOCF_DEFAULT,
    captura_metano: float = 0.0,
    storage_factor: float = None,
    eficiencia_motor: float = 0.40,
    umidade: float = 0.85,
    mcf: float = 1.0,
    tipo_digestor: str = 'CSTR',
    gwp_ch4: float = GWP_CH4,
    gwp_n2o: float = GWP_N2O
) -> dict:
    """
    Calcula reduções com todos os parâmetros explicitamente.
    Agora sem modificar variáveis globais – passamos gwp_ch4 diretamente.
    """
    # Baseline usando o gwp_ch4 fornecido
    baseline = calcular_baseline_aterro(
        massa_ano_kg,
        captura_metano,
        k,
        doc,
        docf,
        mcf,
        gwp_ch4=gwp_ch4
    )

    q_ch4 = estimar_metano_produzido(massa_ano_kg)

    # Determinar fatores padrão (repetido aqui para garantir que não dependa de globais)
    if tipo_digestor == 'CSTR':
        f_ec = F_EC_DEFAULT
        ef_ch4 = EF_CH4_DEFAULT
        default_storage = STORAGE_FACTOR_POR_TIPO.get('CSTR', 0.20)
    elif tipo_digestor == 'UASB':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('UASB', 0.15)
    elif tipo_digestor == 'Lagoa coberta':
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = STORAGE_FACTOR_POR_TIPO.get('Lagoa coberta', 0.10)
    else:
        f_ec = 0.0
        ef_ch4 = 0.05
        default_storage = 0.20

    if storage_factor is None:
        storage_factor = default_storage
    storage_factor = max(0.0, min(0.5, storage_factor))

    PE_EC = q_ch4 * f_ec * EF_EL_DEFAULT
    PE_CH4 = q_ch4 * ef_ch4 * gwp_ch4
    PE_flare = 0.0
    LE_storage = q_ch4 * storage_factor * gwp_ch4

    PE = PE_EC + PE_CH4
    LE = LE_storage
    ER = baseline - PE - LE

    return {
        'baseline': baseline,
        'PE_EC': PE_EC,
        'PE_CH4': PE_CH4,
        'PE_total': PE,
        'LE_storage': LE_storage,
        'LE_total': LE,
        'ER': ER,
        'q_ch4': q_ch4
    }

# =============================================================================
# CÁLCULO DE DOC E K PONDERADOS (COM BASE NA CARACTERIZAÇÃO DO SNIS)
# =============================================================================

def calcular_doc_k_ponderado(df_municipio):
    """
    Calcula DOC e k ponderados com base na caracterização dos resíduos (SNIS).
    O DOCf é fixo (Tabela 7 da A6.4-AMT-003) e depende da predominância de alimentos.
    """
    colunas_caract = {
        'Alimentos_Verdes': 'GTR1501',
        'Vidros': 'GTR1502',
        'Metais': 'GTR1503',
        'Plasticos': 'GTR1504',
        'Papeis': 'GTR1505',
        'Têxteis': 'GTR1506',
        'Outros': 'GTR1507'
    }
    colunas_presentes = [col for col in colunas_caract.values() if col in df_municipio.columns]
    if not colunas_presentes:
        return DOC_PADRAO, K_PADRAO, DOCF_DEFAULT

    df_caract = df_municipio[colunas_presentes].copy()
    for col in df_caract.columns:
        df_caract[col] = pd.to_numeric(df_caract[col], errors='coerce').fillna(0)

    pct = {}
    for nome, col in colunas_caract.items():
        if col in df_caract.columns:
            val = df_caract[col].mean()
            pct[nome] = val if val > 0 else 0
        else:
            pct[nome] = 0

    if sum(pct.values()) == 0:
        return DOC_PADRAO, K_PADRAO, DOCF_DEFAULT

    doc_pond = (pct['Alimentos_Verdes'] * 0.7 +
                pct['Papeis'] * 0.5 +
                pct['Têxteis'] * 0.24 +
                pct['Outros'] * 0.1) / 100.0

    k_pond = (pct['Alimentos_Verdes'] * 0.17 +
              pct['Papeis'] * 0.07 +
              pct['Têxteis'] * 0.07 +
              pct['Outros'] * 0.035) / 100.0

    doc_pond = max(doc_pond, DOC_PADRAO) if doc_pond > 0 else DOC_PADRAO
    k_pond = max(k_pond, K_PADRAO) if k_pond > 0 else K_PADRAO

    # DOCf fixo: se predominam alimentos, usar 0.7; senão, usar 0.5 (bulk)
    if pct['Alimentos_Verdes'] > 50:
        docf = 0.7
    else:
        docf = 0.5

    return doc_pond, k_pond, docf
