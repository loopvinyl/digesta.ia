import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# Configuração da página
st.set_page_config(page_title="Digesta.IA - Bioenergia IEE USP", layout="wide")

# Importações dos módulos
from utils.formatacao import *
from utils.calculos_emissao import *
from utils.config import *

# =============================================================================
# INICIALIZAÇÃO DO ESTADO DA SESSÃO
# =============================================================================
if 'preco_carbono' not in st.session_state:
    preco, moeda, _, _, _ = obter_cotacao_carbono()
    st.session_state.preco_carbono = preco
    st.session_state.moeda_carbono = moeda
if 'taxa_cambio' not in st.session_state:
    cambio, moeda_r, _, _ = obter_cotacao_euro_real()
    st.session_state.taxa_cambio = cambio
    st.session_state.moeda_real = moeda_r

# =============================================================================
# TÍTULO
# =============================================================================
st.title("⚡ Digesta.IA - Simulador de Créditos de Carbono")
st.caption("Usina de Bioenergia e Biofertilizantes do IEE/USP | Metodologia: ACM0022 + TOOL14 + TOOL04")

# =============================================================================
# ABA 1 – SIMULADOR
# =============================================================================
tab_simulador, tab_ia = st.tabs(["🧪 Simulador da Usina IEE", "🤖 Potencial por Localidade (IA)"])

with tab_simulador:
    st.header("📊 Simulador de Emissões e Créditos")

    col1, col2 = st.columns(2)
    with col1:
        unidade = st.radio("Unidade de entrada:", ["kg/dia", "ton/ano"])
        if unidade == "kg/dia":
            residuos_kg_dia = st.slider("Resíduos (kg/dia)", 10, 5000, 100, step=10)
            massa_ano_kg = residuos_kg_dia * 365
        else:
            residuos_ton_ano = st.number_input("Resíduos (ton/ano)", min_value=1.0, max_value=100000.0, value=460.0, step=1.0)
            massa_ano_kg = residuos_ton_ano * 1000
        captura_metano = st.slider("Captura de metano no aterro (%)", 0, 100, 65, 1) / 100
    with col2:
        tipo_digestor = st.selectbox("Tipo de biodigestor", ["CSTR", "UASB", "Lagoa coberta"])
        digestato_armazenado = st.checkbox("Digestato armazenado anaerobicamente?", value=True)
        anos_proj = st.slider("Anos de projeção", 5, 30, 20, 1)

    if st.button("🚀 Executar Simulação", type="primary"):
        with st.spinner("Calculando..."):
            # Parâmetros fixos (por enquanto)
            doc = DOC_PADRAO
            k = K_PADRAO
            mcf = 1.0

            resultados = calcular_reducoes(massa_ano_kg, captura_metano, doc, k, mcf, tipo_digestor, digestato_armazenado)

            st.subheader("📈 Resultados")
            colA, colB, colC = st.columns(3)
            colA.metric("Baseline (aterro)", f"{formatar_br(resultados['baseline'], auto_precision=False, casas_override=2)} tCO₂e")
            colB.metric("Emissões do projeto (PE)", f"{formatar_br(resultados['PE_total'], auto_precision=False, casas_override=2)} tCO₂e")
            colC.metric("Vazamentos (LE)", f"{formatar_br(resultados['LE_total'], auto_precision=False, casas_override=2)} tCO₂e")
            st.metric("Redução líquida (ER)", f"{formatar_br(resultados['ER'], auto_precision=False, casas_override=2)} tCO₂e")

            with st.expander("📋 Detalhamento das emissões"):
                st.write(f"**CH4 produzido:** {formatar_br(resultados['q_ch4'], auto_precision=False, casas_override=2)} t")
                st.write(f"**PE_EC (eletricidade):** {formatar_br(resultados['PE_EC'], auto_precision=False, casas_override=2)} tCO₂e")
                st.write(f"**PE_CH4 (vazamento do digester):** {formatar_br(resultados['PE_CH4'], auto_precision=False, casas_override=2)} tCO₂e")
                st.write(f"**LE_storage (digestato):** {formatar_br(resultados['LE_storage'], auto_precision=False, casas_override=2)} tCO₂e")

            preco_carbono = st.session_state.preco_carbono
            cambio = st.session_state.taxa_cambio
            receita = resultados['ER'] * preco_carbono * cambio
            st.metric("💰 Receita potencial anual", f"R$ {formatar_br(receita, auto_precision=False, casas_override=2)}")

            # Gráfico simples (opcional)
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(["Baseline", "Projeto", "Vazamento"], [resultados['baseline'], resultados['PE_total'], resultados['LE_total']],
                   color=['red', 'orange', 'blue'])
            ax.set_ylabel("tCO₂e")
            ax.set_title("Comparação de emissões")
            st.pyplot(fig)

# =============================================================================
# ABA 2 – IA (placeholder)
# =============================================================================
with tab_ia:
    st.header("🧠 Análise de Potencial por Localidade (IA)")
    st.info("🚧 Esta funcionalidade está em desenvolvimento. Em breve, você poderá visualizar um ranking de municípios com maior potencial de emissões evitadas ao implantar uma usina de bioenergia.")
