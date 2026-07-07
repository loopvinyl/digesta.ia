import numpy as np
import pandas as pd
from utils.config import *

# =============================================================================
# BASELINE (TOOL04) – Emissões do aterro
# =============================================================================

def calcular_baseline_aterro(massa_kg, captura_metano=0.0, temp=T_ORGANICO, doc=DOC_PADRAO, k=K_PADRAO, mcf=1.0):
    """
    Retorna o total de CO2e (t) emitido ao longo de ANOS_PROJECAO.
    captura_metano: fração do metano capturado no aterro (0 a 1)
    """
    if massa_kg <= 0:
        return 0.0
    phi = PHI_APPLICATION_B
    ox = OX_SOIL_COVER
    f = F_METHANE_FRACTION
    docf = 0.0147 * temp + 0.28
    ch4_pot_por_kg = (doc * docf * mcf * f * (16/12) * (1 - ox) * phi) * (1 - captura_metano)

    dias = ANOS_PROJECAO * 365
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

# =============================================================================
# REDUÇÃO LÍQUIDA (ACM0022)
# =============================================================================

def calcular_reducoes(massa_ano_kg, captura_metano_baseline=0.0, doc=DOC_PADRAO, k=K_PADRAO, mcf=1.0,
                      tipo_digestor='CSTR', digestato_armazenado=True):
    """
    Retorna dicionário com baseline, emissões projeto, vazamentos e ER.
    """
    baseline = calcular_baseline_aterro(massa_ano_kg, captura_metano_baseline, doc=doc, k=k, mcf=mcf)
    q_ch4 = estimar_metano_produzido(massa_ano_kg)
    PE_EC, PE_CH4, PE_flare, LE_storage = calcular_emissoes_biodigestor(q_ch4, tipo_digestor, digestato_armazenado)
    PE = PE_EC + PE_CH4 + PE_flare
    LE = LE_storage
    ER = baseline - PE - LE
    return {
        'baseline': baseline,
        'PE_EC': PE_EC,
        'PE_CH4': PE_CH4,
        'PE_flare': PE_flare,
        'LE_storage': LE_storage,
        'PE_total': PE,
        'LE_total': LE,
        'ER': ER,
        'q_ch4': q_ch4
    }

# =============================================================================
# CÁLCULO DE DOC E K PONDERADOS (COM BASE NA CARACTERIZAÇÃO DO SNIS)
# =============================================================================

def calcular_doc_k_ponderado(df_municipio):
    """
    Calcula DOC e k ponderados com base na caracterização dos resíduos.
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
        return DOC_PADRAO, K_PADRAO

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
        return DOC_PADRAO, K_PADRAO

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
    return doc_pond, k_pond
