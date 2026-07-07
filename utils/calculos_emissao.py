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
    anos=ANOS_PROJECAO
):
    """
    Retorna o total de CO2e (t) emitido ao longo de ANOS_PROJECAO.
    Agora usando DOCf fixo (Tabela 7 da A6.4-AMT-003).
    A temperatura não entra mais no cálculo do DOCf.
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
    co2eq_t = (ch4_diario_kg * GWP_CH4) / 1000.0
    return co2eq_t.sum()

def calcular_baseline_aterro_series(
    massa_kg,
    captura_metano=0.0,
    k=K_PADRAO,
    doc=DOC_PADRAO,
    docf=DOCF_DEFAULT,
    mcf=1.0,
    anos=ANOS_PROJECAO
):
    """
    Retorna array diário de CO2e (t) para o baseline (aterro).
    Agora usando DOCf fixo (Tabela 7 da A6.4-AMT-003).
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
    co2eq_diario_t = (ch4_diario_kg * GWP_CH4) / 1000.0
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
# EMISSÕES DO BIODIGESTOR (TOOL14)
# =============================================================================

def calcular_emissoes_biodigestor(q_ch4_t, tipo='CSTR', digestato_armazenado_anaerobicamente=True):
    """
    Retorna: PE_EC, PE_CH4, PE_flare, LE_storage (t CO2e)
    """
    if tipo == 'CSTR':
        f_ec = F_EC_DEFAULT
        ef_ch4 = EF_CH4_DEFAULT
        f_storage = F_WW_CH4_DEFAULT
    else:
        f_ec = 0.0
        ef_ch4 = 0.05
        f_storage = 0.10

    PE_EC = q_ch4_t * f_ec * EF_EL_DEFAULT
    PE_CH4 = q_ch4_t * ef_ch4 * GWP_CH4
    PE_flare = 0.0

    if digestato_armazenado_anaerobicamente:
        LE_storage = q_ch4_t * f_storage * GWP_CH4
    else:
        LE_storage = 0.0

    return PE_EC, PE_CH4, PE_flare, LE_storage

def calcular_emissoes_biodigestor_series(q_ch4_t, tipo='CSTR', digestato_armazenado=True, anos=ANOS_PROJECAO):
    """
    Retorna dicionário com séries diárias de PE_EC, PE_CH4, LE_storage (t CO2e/dia).
    As emissões são distribuídas uniformemente ao longo dos dias.
    """
    dias = anos * 365
    if tipo == 'CSTR':
        f_ec = F_EC_DEFAULT
        ef_ch4 = EF_CH4_DEFAULT
        f_storage = F_WW_CH4_DEFAULT
    else:
        f_ec = 0.0
        ef_ch4 = 0.05
        f_storage = 0.10

    PE_EC_dia = (q_ch4_t * f_ec * EF_EL_DEFAULT) / dias
    PE_CH4_dia = (q_ch4_t * ef_ch4 * GWP_CH4) / dias
    if digestato_armazenado:
        LE_storage_dia = (q_ch4_t * f_storage * GWP_CH4) / dias
    else:
        LE_storage_dia = 0.0

    return {
        'PE_EC': np.full(dias, PE_EC_dia),
        'PE_CH4': np.full(dias, PE_CH4_dia),
        'LE_storage': np.full(dias, LE_storage_dia),
        'PE_total': np.full(dias, PE_EC_dia + PE_CH4_dia),
        'LE_total': np.full(dias, LE_storage_dia)
    }

# =============================================================================
# REDUÇÃO LÍQUIDA (ACM0022) – VERSÕES COM GWP CUSTOMIZADO E PARÂMETROS EXPLÍCITOS
# =============================================================================

def calcular_reducoes_com_gwp(massa_ano_kg, captura_metano_baseline=0.0,
                              doc=DOC_PADRAO, k=K_PADRAO, mcf=1.0,
                              tipo_digestor='CSTR', digestato_armazenado=True,
                              gwp_ch4=GWP_CH4, gwp_n2o=GWP_N2O,
                              docf=DOCF_DEFAULT):
    """
    Versão da função calcular_reducoes que aceita GWP personalizado e docf.
    Retorna o dicionário com baseline, PE, LE, ER usando os GWP fornecidos.
    """
    # Baseline usa o GWP_CH4 fornecido (mas a função calcular_baseline_aterro usa GWP_CH4 global)
    from utils.config import GWP_CH4 as GWP_CH4_DEFAULT, GWP_N2O as GWP_N2O_DEFAULT
    # Guardar valores originais
    orig_gwp_ch4 = GWP_CH4_DEFAULT
    orig_gwp_n2o = GWP_N2O_DEFAULT
    # Temporariamente substituir
    import utils.config
    utils.config.GWP_CH4 = gwp_ch4
    utils.config.GWP_N2O = gwp_n2o

    # Reimportar funções para usar os novos GWP
    from utils.calculos_emissao import calcular_baseline_aterro, estimar_metano_produzido, calcular_emissoes_biodigestor

    baseline = calcular_baseline_aterro(massa_ano_kg, captura_metano_baseline, k, doc, docf, mcf)
    q_ch4 = estimar_metano_produzido(massa_ano_kg)
    PE_EC, PE_CH4, PE_flare, LE_storage = calcular_emissoes_biodigestor(q_ch4, tipo_digestor, digestato_armazenado)
    PE = PE_EC + PE_CH4
    LE = LE_storage
    ER = baseline - PE - LE

    # Restaurar valores originais
    utils.config.GWP_CH4 = orig_gwp_ch4
    utils.config.GWP_N2O = orig_gwp_n2o

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

def calcular_reducoes_com_parametros(
    massa_ano_kg: float,
    k: float,
    doc: float,
    docf: float = DOCF_DEFAULT,
    captura_metano: float = 0.0,
    eficiencia_motor: float = 0.40,
    umidade: float = 0.85,
    mcf: float = 1.0,
    tipo_digestor: str = 'CSTR',
    digestato_armazenado: bool = True,
    gwp_ch4: float = GWP_CH4,
    gwp_n2o: float = GWP_N2O
) -> dict:
    """
    Versão da função calcular_reducoes com todos os parâmetros explicitamente.
    Usa docf fixo (A6.4-AMT-003) e permite GWP customizado.
    """
    from utils.config import GWP_CH4 as GWP_CH4_DEFAULT, GWP_N2O as GWP_N2O_DEFAULT
    orig_gwp_ch4 = GWP_CH4_DEFAULT
    orig_gwp_n2o = GWP_N2O_DEFAULT
    import utils.config
    utils.config.GWP_CH4 = gwp_ch4
    utils.config.GWP_N2O = gwp_n2o

    baseline = calcular_baseline_aterro(massa_ano_kg, captura_metano, k, doc, docf, mcf)
    q_ch4 = estimar_metano_produzido(massa_ano_kg)
    PE_EC, PE_CH4, PE_flare, LE_storage = calcular_emissoes_biodigestor(q_ch4, tipo_digestor, digestato_armazenado)
    PE = PE_EC + PE_CH4
    LE = LE_storage
    ER = baseline - PE - LE

    utils.config.GWP_CH4 = orig_gwp_ch4
    utils.config.GWP_N2O = orig_gwp_n2o

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
    O DOCf agora é fixo (Tabela 7 da A6.4-AMT-003).
    A temperatura NÃO influencia mais o DOCf.
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
