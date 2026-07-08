import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import seaborn as sns
from scipy import stats
from joblib import Parallel, delayed
import warnings
from matplotlib.ticker import FuncFormatter
from SALib.sample.sobol import sample
from SALib.analyze.sobol import analyze

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option('display.max_columns', None)
plt.rcParams['figure.dpi'] = 150
plt.rcParams['font.size'] = 10
sns.set_style("whitegrid")

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(page_title="Digesta.IA - Bioenergia IEE USP", layout="wide")

# =============================================================================
# IMPORTAÇÕES DOS MÓDULOS INTERNOS
# =============================================================================
from utils.formatacao import *
from utils.calculos_emissao import (
    calcular_baseline_aterro_series,
    calcular_emissoes_biodigestor_series,
    calcular_reducoes_com_parametros,
    estimar_metano_produzido,
    calcular_doc_k_ponderado
)
from utils.config import (
    GWP_CH4, GWP_N2O,
    DOC_PADRAO, K_PADRAO,
    DOCF_DEFAULT,
    STORAGE_FACTOR_POR_TIPO,
    STORAGE_FACTOR_RANGES,
    PHI_APPLICATION_B, OX_SOIL_COVER,
    F_METHANE_FRACTION,
    ANOS_PROJECAO
)
from utils.ia_classificacao import ClassificadorDestinoIA

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
if 'df_potencial' not in st.session_state:
    st.session_state.df_potencial = None

# =============================================================================
# FUNÇÃO CORRIGIDA PARA CÁLCULO DO PE (EMBUTIDA NO APP)
# =============================================================================
def calcular_pe_corrigido(massa_ano_kg, ch4_gerado, eficiencia_motor, umidade, gwp_ch4, storage_factor):
    """
    Calcula as emissões do projeto (PE) de forma correta:
    - Slip do motor (3% do CH4)
    - Geração de energia elétrica (kWh)
    - Deslocamento da rede elétrica (fator 0.0461 kg CO2/kWh)
    - Consumo interno da usina (5% da energia gerada)
    """
    # 1. Slip (escape de metano)
    slip_percentual = 0.03  # 3% (padrão para motores modernos)
    pe_ch4_slip = ch4_gerado * slip_percentual  # kg CH4

    # 2. Energia gerada (kWh)
    pci_ch4 = 13.9  # kWh/kg CH4
    energia_kwh = ch4_gerado * pci_ch4 * eficiencia_motor * umidade

    # 3. Emissões evitadas pela energia (deslocamento da rede)
    fator_emissao_rede = 0.0000461  # tCO2/kWh (0.0461 kg/kWh)
    energia_evitada_tco2 = energia_kwh * fator_emissao_rede

    # 4. Consumo interno da usina (5% da energia gerada)
    consumo_interno_kwh = energia_kwh * 0.05
    pe_operacional_tco2 = consumo_interno_kwh * fator_emissao_rede

    # 5. PE total (tCO2e)
    pe_total = (pe_ch4_slip * gwp_ch4) + pe_operacional_tco2 - energia_evitada_tco2

    return pe_total, energia_kwh, energia_evitada_tco2

# =============================================================================
# TÍTULO
# =============================================================================
st.title("⚡ Digesta.IA - Simulador de Créditos de Carbono")
st.caption("Usina de Bioenergia e Biofertilizantes do IEE/USP | Metodologia: UNFCCC A6.4-AMT-003 (2025) + TOOL14 + ACM0022 | IPCC AR5")

# =============================================================================
# ABAS
# =============================================================================
tab_simulador, tab_ia = st.tabs(["🧪 Simulador da Usina IEE", "🤖 Potencial por Localidade (IA)"])

# =============================================================================
# ABA 1 – SIMULADOR DA USINA IEE (VERSÃO AVANÇADA) - CORRIGIDO
# =============================================================================
with tab_simulador:
    st.header("⚙️ Simulador Avançado – Usina IEE USP")
    st.markdown("""
    Esta ferramenta projeta as emissões de gases de efeito estufa e o potencial de créditos de carbono
    para uma usina de **digestão anaeróbica** (biodigestor) que processa resíduos orgânicos.

    **Inclui análise de sensibilidade global (Sobol) e incerteza (Monte Carlo)** com os seguintes parâmetros:
    - Taxa de decaimento do aterro (k)
    - Carbono orgânico degradável (DOC)
    - Fração de carbono que se decompõe (DOCf) – fixa por tipo de resíduo (Tabela 7 da A6.4-AMT-003)
    - Captura de metano no aterro
    - **Fator de vazamento do digestato** (storage_factor) – oscila em torno do valor padrão do tipo de digestor (TOOL14)
    """)

    # =============================================================
    # PARÂMETROS DE ENTRADA (COM SLIDERS DE EFICIÊNCIA E UMIDADE)
    # =============================================================
    col1, col2 = st.columns(2)
    with col1:
        unidade = st.radio("Unidade de entrada:", ["kg/dia", "ton/ano"])
        if unidade == "kg/dia":
            residuos_kg_dia = st.slider("Resíduos (kg/dia)", 10, 5000, 100, step=10)
            massa_ano_kg = residuos_kg_dia * 365
        else:
            residuos_ton_ano = st.number_input("Resíduos (ton/ano)", min_value=1.0, max_value=100000.0, value=460.0, step=1.0)
            massa_ano_kg = residuos_ton_ano * 1000
        captura_metano_fixo = st.slider("Captura de metano no aterro (%)", 0, 100, 65, 1) / 100
        st.caption("ℹ️ Para aterros com usina de biogás (ex: Caieiras), use ~65%.")

    with col2:
        tipo_digestor = st.selectbox(
            "Tipo de biodigestor",
            ["CSTR", "UASB", "Lagoa coberta"],
            index=0,
            help="O tipo define o fator de vazamento padrão do digestato (TOOL14) e o intervalo de oscilação para as análises."
        )
        storage_default = STORAGE_FACTOR_POR_TIPO.get(tipo_digestor, 0.20)
        storage_min, storage_max = STORAGE_FACTOR_RANGES.get(tipo_digestor, (0.0, 0.35))
        
        st.info(f"**Fator de vazamento padrão (TOOL14) para {tipo_digestor}: {storage_default*100:.0f}%**")
        st.caption(f"**Intervalo de oscilação (Sobol/MC):** {storage_min*100:.0f}% a {storage_max*100:.0f}%")

        storage_factor_manual = st.slider(
            "Fator de vazamento do digestato (%) – ajuste manual (para o cálculo determinístico)",
            min_value=0,
            max_value=50,
            value=int(storage_default*100),
            step=1,
            help="Valor fixo usado no cálculo determinístico. A análise Sobol/MC usará o intervalo dinâmico acima."
        ) / 100.0

        anos_simulacao = st.slider("Anos de simulação", 5, 50, 20, 5)

    # NOVOS SLIDERS PARA ENERGIA
    col3, col4 = st.columns(2)
    with col3:
        eficiencia_motor = st.slider(
            "Eficiência do motor (%) para geração de eletricidade",
            min_value=20,
            max_value=50,
            value=40,
            step=1,
            help="Eficiência de conversão do biogás em eletricidade. Motores modernos operam entre 35% e 45%."
        ) / 100.0
        st.caption(f"⚡ Eficiência selecionada: {eficiencia_motor*100:.0f}%")

    with col4:
        umidade = st.slider(
            "Umidade do resíduo (%)",
            min_value=70,
            max_value=90,
            value=80,
            step=1,
            help="Teor de umidade do resíduo orgânico. Afeta a produção de biogás."
        ) / 100.0
        st.caption(f"💧 Umidade selecionada: {umidade*100:.0f}%")

    # Escolha do tipo de resíduo para DOCf
    tipo_residuo = st.selectbox(
        "Tipo de resíduo (para DOCf – Tabela 7 da A6.4-AMT-003):",
        ["Alimentos (altamente decomponível)", "Papel (moderadamente decomponível)", "Madeira (pouco decomponível)", "Bulk (não especificado)"],
        index=0
    )
    mapa_docf = {
        "Alimentos (altamente decomponível)": 0.7,
        "Papel (moderadamente decomponível)": 0.5,
        "Madeira (pouco decomponível)": 0.1,
        "Bulk (não especificado)": 0.5
    }
    docf_selecionado = mapa_docf[tipo_residuo]

    # =============================================================
    # PARÂMETROS PARA ANÁLISE DE SENSIBILIDADE (SOBOL)
    # =============================================================
    st.subheader("📊 Parâmetros para Análise de Sensibilidade (Sobol)")
    st.info(f"""
    Os parâmetros abaixo serão variados nas análises Sobol e Monte Carlo.
    - **Taxa de decaimento (k)**: 0,06 a 0,40 ano⁻¹
    - **Carbono orgânico degradável (DOC)**: 0,10 a 0,25
    - **Captura de metano**: 0% a 90%
    - **Fator de vazamento do digestato**: **{storage_min*100:.0f}% a {storage_max*100:.0f}%** (intervalo dinâmico para {tipo_digestor})
    """)
    col5, col6 = st.columns(2)
    with col5:
        n_samples = st.slider("Número de amostras Sobol", 32, 256, 64, 16)
    with col6:
        n_simulations = st.slider("Número de simulações Monte Carlo", 50, 1000, 100, 50)

    # =============================================================
    # BOTÃO DE EXECUÇÃO
    # =============================================================
    if st.button("🚀 Executar Simulação Avançada", type="primary"):
        with st.spinner("Executando simulação... Isso pode levar alguns segundos."):

            # =============================================================
            # 1. CÁLCULO DETERMINÍSTICO (COM PE CORRIGIDO)
            # =============================================================
            gwps = {
                "Otimista (GWP-20)": (79.7, 273),
                "Realista (GWP-100)": (27.0, 273),
                "Pessimista (GWP-500)": (7.2, 130)
            }

            doc_fixo = DOC_PADRAO
            k_fixo = K_PADRAO
            mcf = 1.0

            # Estima o metano gerado anualmente
            ch4_gerado = estimar_metano_produzido(massa_ano_kg)  # kg CH4/ano

            resultados_gwp = {}
            for nome_gwp, (gwp_ch4, gwp_n2o) in gwps.items():
                # Baseline (aterro)
                baseline = calcular_baseline_aterro_series(
                    massa_ano_kg, captura_metano_fixo, k_fixo, doc_fixo, docf_selecionado, mcf, anos_simulacao
                ).sum()
                
                # PE corrigido (usando a nova função)
                pe_total, energia_kwh, energia_evitada = calcular_pe_corrigido(
                    massa_ano_kg, ch4_gerado, eficiencia_motor, umidade, gwp_ch4, storage_factor_manual
                ) * anos_simulacao  # multiplica pelos anos (a função retorna valor anual)

                # LE (vazamento do digestato)
                # Usamos a função original para LE
                emissoes_biodigestor = calcular_emissoes_biodigestor_series(
                    ch4_gerado, tipo_digestor, storage_factor_manual, anos_simulacao
                )
                le_total = emissoes_biodigestor['LE_total'].sum()

                # ER (redução líquida)
                er_total = baseline - pe_total - le_total

                resultados_gwp[nome_gwp] = {
                    'baseline': baseline,
                    'PE_total': pe_total,
                    'LE_total': le_total,
                    'ER': er_total,
                    'energia_kwh': energia_kwh * anos_simulacao,
                    'energia_evitada_tco2': energia_evitada * anos_simulacao
                }

            resultados = resultados_gwp["Otimista (GWP-20)"]
            baseline_total = resultados['baseline']
            pe_total = resultados['PE_total']
            le_total = resultados['LE_total']
            er_total = resultados['ER']
            energia_total_kwh = resultados['energia_kwh']
            energia_evitada_total = resultados['energia_evitada_tco2']

            # =============================================================
            # 2. GERAR SÉRIES DIÁRIAS PARA GRÁFICOS
            # =============================================================
            baseline_serie = calcular_baseline_aterro_series(
                massa_ano_kg, captura_metano_fixo, k_fixo, doc_fixo, docf_selecionado, mcf, anos_simulacao
            )
            # Para as séries de PE e LE, usamos a lógica original (mas com nosso PE corrigido apenas para o total)
            # Como a série diária de PE não é trivial, vamos manter a original para o gráfico,
            # mas ajustar o total com nosso valor corrigido.
            emissoes_biodigestor = calcular_emissoes_biodigestor_series(
                ch4_gerado, tipo_digestor, storage_factor_manual, anos_simulacao
            )
            pe_serie_original = emissoes_biodigestor['PE_total']
            le_serie = emissoes_biodigestor['LE_total']
            # Ajustamos a série de PE para ter o mesmo total que o nosso PE corrigido
            fator_ajuste = pe_total / pe_serie_original.sum() if pe_serie_original.sum() != 0 else 0
            pe_serie = pe_serie_original * fator_ajuste
            er_serie = baseline_serie - pe_serie - le_serie

            dias = anos_simulacao * 365
            datas = pd.date_range(start=datetime.now(), periods=dias, freq='D')
            df_diario = pd.DataFrame({
                'Data': datas,
                'Baseline': baseline_serie,
                'Projeto': pe_serie,
                'Vazamento': le_serie,
                'Reducao': er_serie
            })
            df_diario['Year'] = df_diario['Data'].dt.year

            df_anual = df_diario.groupby('Year').agg({
                'Baseline': 'sum',
                'Projeto': 'sum',
                'Vazamento': 'sum',
                'Reducao': 'sum'
            }).reset_index()
            df_anual['Reducao_Acumulada'] = df_anual['Reducao'].cumsum()

            # =============================================================
            # 3. EXIBIÇÃO DE RESULTADOS DETERMINÍSTICOS
            # =============================================================
            st.header("📈 Resultados da Simulação")
            st.info(f"""
            **Parâmetros utilizados:**
            - Resíduos: {formatar_br(residuos_kg_dia)} kg/dia ({formatar_br(massa_ano_kg/1000)} t/ano)
            - Captura de metano no aterro: {formatar_br(captura_metano_fixo*100)}%
            - Tipo de biodigestor: {tipo_digestor}
            - Fator de vazamento do digestato: {formatar_br(storage_factor_manual*100)}%
            - Anos de simulação: {anos_simulacao}
            - k = {formatar_br(k_fixo)} ano⁻¹
            - DOC = {formatar_br(doc_fixo)}
            - DOCf = {formatar_br(docf_selecionado)} → {tipo_residuo}
            - **Eficiência do motor:** {eficiencia_motor*100:.0f}%
            - **Umidade do resíduo:** {umidade*100:.0f}%
            - **Energia gerada (total):** {formatar_br(energia_total_kwh, 0)} kWh
            - **Emissões evitadas pela energia:** {formatar_br(energia_evitada_total, 2)} tCO₂e
            """)

            # Diagnóstico: exibir os componentes
            with st.expander("🔍 Diagnóstico dos componentes do cálculo"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Baseline (tCO₂e)", formatar_br(baseline_total, 2))
                with col_b:
                    st.metric("Projeto PE (tCO₂e)", formatar_br(pe_total, 2))
                with col_c:
                    st.metric("Vazamento LE (tCO₂e)", formatar_br(le_total, 2))
                st.metric("Redução Líquida ER (tCO₂e)", formatar_br(er_total, 2), delta_color="normal")

            st.subheader("📊 Comparação entre Cenários de GWP")
            comp_gwp = []
            for nome, res in resultados_gwp.items():
                comp_gwp.append({
                    "Cenário": nome,
                    "Redução Líquida (tCO₂e)": res['ER'],
                    "Média anual (tCO₂e/ano)": res['ER'] / anos_simulacao,
                    "Energia (kWh)": res['energia_kwh']
                })
            df_comp_gwp = pd.DataFrame(comp_gwp)
            st.dataframe(df_comp_gwp.style.format({
                "Redução Líquida (tCO₂e)": lambda x: formatar_br(x),
                "Média anual (tCO₂e/ano)": lambda x: formatar_br(x),
                "Energia (kWh)": lambda x: formatar_br(x, 0)
            }))

            # Valores financeiros
            preco_carbono = st.session_state.preco_carbono
            moeda = st.session_state.moeda_carbono
            taxa_cambio = st.session_state.taxa_cambio
            valor_eur = er_total * preco_carbono
            valor_brl = er_total * preco_carbono * taxa_cambio

            st.subheader("💰 Valor Financeiro das Emissões Evitadas (Cenário Otimista)")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Preço Carbono (Euro)", f"{moeda} {formatar_br(preco_carbono)}/tCO₂eq")
            with col2:
                st.metric("Receita em Euro", f"{moeda} {formatar_br(valor_eur)}",
                          help=f"{formatar_br(er_total)} tCO₂eq evitadas")
            with col3:
                st.metric("Receita em Reais", f"R$ {formatar_br(valor_brl)}",
                          help=f"{formatar_br(er_total)} tCO₂eq evitadas")

            # Gráfico de barras
            st.subheader("📊 Comparação Anual das Emissões (Cenário Otimista)")
            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(df_anual['Year']))
            width = 0.25
            ax.bar(x - width, df_anual['Baseline'], width, label='Baseline (Aterro)', color='red', edgecolor='black')
            ax.bar(x, df_anual['Projeto'], width, label='Projeto (Biodigestor)', color='orange', edgecolor='black')
            ax.bar(x + width, df_anual['Vazamento'], width, label='Vazamento (Digestato)', color='blue', edgecolor='black')
            for i, (b, p, v) in enumerate(zip(df_anual['Baseline'], df_anual['Projeto'], df_anual['Vazamento'])):
                ax.text(i - width, b + max(b, p, v)*0.01, formatar_br(b), ha='center', fontsize=8)
                ax.text(i, p + max(b, p, v)*0.01, formatar_br(p), ha='center', fontsize=8)
                ax.text(i + width, v + max(b, p, v)*0.01, formatar_br(v), ha='center', fontsize=8)
            ax.set_xlabel('Ano')
            ax.set_ylabel('tCO₂e')
            ax.set_title('Comparação Anual: Baseline vs Projeto vs Vazamento')
            ax.set_xticks(x)
            ax.set_xticklabels(df_anual['Year'])
            ax.legend()
            ax.yaxis.set_major_formatter(FuncFormatter(br_format))
            st.pyplot(fig)
            plt.close(fig)

            # Gráfico de redução acumulada
            st.subheader("📉 Redução de Emissões Acumulada (Cenário Otimista)")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(datas, df_diario['Baseline'].cumsum(), 'r-', label='Baseline (Aterro)', linewidth=2)
            ax.plot(datas, (df_diario['Projeto'] + df_diario['Vazamento']).cumsum(), 'b-', label='Projeto + Vazamento', linewidth=2)
            ax.fill_between(datas,
                            (df_diario['Projeto'] + df_diario['Vazamento']).cumsum(),
                            df_diario['Baseline'].cumsum(),
                            color='skyblue', alpha=0.5, label='Emissões Evitadas')
            ax.set_title(f'Redução de Emissões em {anos_simulacao} Anos (k = {formatar_br(k_fixo)} ano⁻¹)')
            ax.set_xlabel('Data')
            ax.set_ylabel('tCO₂e Acumulado')
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.yaxis.set_major_formatter(FuncFormatter(br_format))
            st.pyplot(fig)
            plt.close(fig)

            # =============================================================
            # 4. ANÁLISE DE SENSIBILIDADE SOBOL (4 PARÂMETROS)
            # =============================================================
            st.subheader("🎯 Análise de Sensibilidade Global (Sobol) - GWP-20")
            st.info(f"**Parâmetros variados:** k, DOC, Captura, Storage_Factor (intervalo: {storage_min*100:.0f}% a {storage_max*100:.0f}%)")

            problem = {
                'num_vars': 4,
                'names': ['k', 'DOC', 'captura', 'storage_factor'],
                'bounds': [
                    [0.06, 0.40],
                    [0.10, 0.25],
                    [0.0, 0.9],
                    [storage_min, storage_max]
                ]
            }
            param_values = sample(problem, n_samples, seed=50)
            gwp20_ch4, gwp20_n2o = gwps["Otimista (GWP-20)"]

            def executar_biodigestor_sobol(params):
                k_sobol, DOC_sobol, captura_sobol, storage_sobol = params
                # Baseline
                baseline_sobol = calcular_baseline_aterro_series(
                    massa_ano_kg, captura_sobol, k_sobol, DOC_sobol, docf_selecionado, mcf, anos_simulacao
                ).sum()
                # PE corrigido
                ch4_gerado_sobol = estimar_metano_produzido(massa_ano_kg)
                pe_sobol, _, _ = calcular_pe_corrigido(
                    massa_ano_kg, ch4_gerado_sobol, eficiencia_motor, umidade, gwp20_ch4, storage_sobol
                ) * anos_simulacao
                # LE
                emissoes_biodigestor_sobol = calcular_emissoes_biodigestor_series(
                    ch4_gerado_sobol, tipo_digestor, storage_sobol, anos_simulacao
                )
                le_sobol = emissoes_biodigestor_sobol['LE_total'].sum()
                er_sobol = baseline_sobol - pe_sobol - le_sobol
                return er_sobol

            with st.spinner("Calculando índices Sobol..."):
                results_sobol = Parallel(n_jobs=1)(
                    delayed(executar_biodigestor_sobol)(p) for p in param_values
                )
                Si = analyze(problem, np.array(results_sobol), print_to_console=False)

            df_sens = pd.DataFrame({
                'Parâmetro': ['Taxa de Decaimento (k)', 'DOC', 'Captura de Metano', 'Fator de Vazamento'],
                'S1': Si['S1'],
                'ST': Si['ST']
            }).sort_values('ST', ascending=False)

            fig, ax = plt.subplots(figsize=(10, 6))
            sns.barplot(x='ST', y='Parâmetro', data=df_sens, palette='viridis', ax=ax)
            ax.set_title('Sensibilidade Global - Redução Líquida (GWP-20)')
            ax.set_xlabel('Índice ST (Sobol Total)')
            ax.set_ylabel('Parâmetro')
            ax.grid(axis='x', linestyle='--', alpha=0.7)
            ax.xaxis.set_major_formatter(FuncFormatter(br_format))
            for i, st_val in enumerate(df_sens['ST']):
                ax.text(st_val, i, f' {formatar_br(st_val)}', va='center', fontweight='bold')
            st.pyplot(fig)
            plt.close(fig)
            st.dataframe(df_sens.style.format({'S1': '{:.4f}', 'ST': '{:.4f}'}))

            # =============================================================
            # 5. MONTE CARLO
            # =============================================================
            st.subheader("🎲 Análise de Incerteza (Monte Carlo) - Comparação entre Cenários de GWP")

            np.random.seed(50)
            k_mc = np.random.uniform(0.06, 0.40, n_simulations)
            DOC_mc = np.random.triangular(0.12, 0.15, 0.18, n_simulations)
            captura_mc = np.random.uniform(0.0, 0.9, n_simulations)
            storage_mc = np.random.uniform(storage_min, storage_max, n_simulations)
            umidade_mc = np.random.uniform(0.75, 0.90, n_simulations)
            eficiencia_mc = np.random.uniform(0.30, 0.50, n_simulations)

            mc_results = {}
            for nome_gwp, (gwp_ch4, gwp_n2o) in gwps.items():
                er_arr = []
                for i in range(n_simulations):
                    # Baseline
                    baseline_mc = calcular_baseline_aterro_series(
                        massa_ano_kg, captura_mc[i], k_mc[i], DOC_mc[i], docf_selecionado, mcf, anos_simulacao
                    ).sum()
                    # PE corrigido
                    ch4_gerado_mc = estimar_metano_produzido(massa_ano_kg)
                    pe_mc, _, _ = calcular_pe_corrigido(
                        massa_ano_kg, ch4_gerado_mc, eficiencia_mc[i], umidade_mc[i], gwp_ch4, storage_mc[i]
                    ) * anos_simulacao
                    # LE
                    emissoes_biodigestor_mc = calcular_emissoes_biodigestor_series(
                        ch4_gerado_mc, tipo_digestor, storage_mc[i], anos_simulacao
                    )
                    le_mc = emissoes_biodigestor_mc['LE_total'].sum()
                    er_mc = baseline_mc - pe_mc - le_mc
                    er_arr.append(er_mc)
                mc_results[nome_gwp] = np.array(er_arr)

            fig, ax = plt.subplots(figsize=(12, 6))
            for nome, arr in mc_results.items():
                sns.kdeplot(arr, label=nome, ax=ax, linewidth=2)
            ax.set_title('Distribuição da Redução Líquida de Emissões (Monte Carlo)')
            ax.set_xlabel('Redução Líquida (tCO₂e)')
            ax.set_ylabel('Densidade')
            ax.legend()
            ax.grid(alpha=0.3)
            ax.xaxis.set_major_formatter(FuncFormatter(br_format))
            st.pyplot(fig)
            plt.close(fig)

            stats_list = []
            for nome, arr in mc_results.items():
                stats_list.append({
                    "Cenário": nome,
                    "Média (tCO₂e)": np.mean(arr),
                    "Mediana (tCO₂e)": np.median(arr),
                    "Desvio Padrão": np.std(arr),
                    "IC 95% Inferior": np.percentile(arr, 2.5),
                    "IC 95% Superior": np.percentile(arr, 97.5)
                })
            df_mc_stats = pd.DataFrame(stats_list)
            st.subheader("📊 Estatísticas do Monte Carlo")
            st.dataframe(df_mc_stats.style.format({
                "Média (tCO₂e)": lambda x: formatar_br(x),
                "Mediana (tCO₂e)": lambda x: formatar_br(x),
                "Desvio Padrão": lambda x: formatar_br(x),
                "IC 95% Inferior": lambda x: formatar_br(x),
                "IC 95% Superior": lambda x: formatar_br(x)
            }))

            # =============================================================
            # 6. TESTES ESTATÍSTICOS
            # =============================================================
            st.subheader("📊 Testes Estatísticos")
            diff = mc_results["Otimista (GWP-20)"] - mc_results["Realista (GWP-100)"]
            shapiro_stat, shapiro_p = stats.shapiro(diff)
            t_stat, t_p = stats.ttest_1samp(diff, 0)
            st.write(f"**Diferença Otimista – Realista:** média = {formatar_br(np.mean(diff))} tCO₂e")
            st.write(f"**Shapiro-Wilk (normalidade):** estatística = {shapiro_stat:.5f}, p = {shapiro_p:.5f}")
            st.write(f"**Teste t (média ≠ 0):** t = {t_stat:.5f}, p = {t_p:.5f}")

            # =============================================================
            # 7. RESULTADOS ANUAIS E DOWNLOAD
            # =============================================================
            st.subheader("📋 Resultados Anuais (Cenário Otimista)")
            df_anual_fmt = df_anual.copy()
            for col in ['Baseline', 'Projeto', 'Vazamento', 'Reducao']:
                df_anual_fmt[col] = df_anual_fmt[col].apply(lambda x: formatar_br(x))
            st.dataframe(df_anual_fmt)

            csv = df_anual.to_csv(index=False)
            st.download_button(
                label="📥 Baixar resultados anuais (CSV)",
                data=csv,
                file_name="resultados_usina_iee.csv",
                mime="text/csv"
            )

    else:
        st.info("💡 Ajuste os parâmetros acima e clique em **Executar Simulação Avançada** para ver os resultados.")


# =============================================================================
# ABA 2 – IA (POTENCIAL POR LOCALIDADE) - CORRIGIDO
# =============================================================================
with tab_ia:
    st.header("🧠 Análise de Potencial por Localidade (IA)")
    st.markdown("""
    A IA processa os dados do **SNIS** para identificar municípios com maior potencial de emissões evitadas
    ao implantar uma usina de bioenergia similar à do IEE/USP (digestão anaeróbica).
    """)

    @st.cache_data
    def load_data(ano):
        url = f"https://raw.githubusercontent.com/loopvinyl/digesta.ia/main/data/rsuBrasil_{ano}.xlsx"
        try:
            df = pd.read_excel(url, sheet_name="Manejo_Coleta_e_Destinação", header=12)
            df = df.dropna(how="all")
            df.columns = [str(col).strip() for col in df.columns]
            return df
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return None

    col1, col2 = st.columns(2)
    with col1:
        ano_selecionado = st.selectbox("Selecione o ano de referência:", ["2023", "2024"], index=1)
        st.session_state.ano_ia = ano_selecionado
        tipo_digestor_ia = "CSTR"
        storage_factor_ia = STORAGE_FACTOR_POR_TIPO['CSTR']

    with col2:
        ordenar_por = st.selectbox(
            "Ordenar por:",
            ["Potencial de redução (tCO₂e/ano)", "Massa orgânica (t/ano)", "Receita potencial (R$/ano)"],
            index=0
        )
        top_n = st.slider("Mostrar os top N municípios:", 5, 50, 20, 5)

    with st.spinner("🤖 Inicializando o modelo de IA..."):
        from utils.ia_classificacao import ClassificadorDestinoIA, classificar_destino_regra
        classificador_ia = ClassificadorDestinoIA()

    if st.button("🔍 Analisar Potencial Nacional", type="primary"):
        with st.spinner("🔄 Processando dados de todos os municípios... Isso pode levar alguns segundos."):

            df = load_data(ano_selecionado)
            if df is None:
                st.error("Não foi possível carregar os dados do SNIS.")
                st.stop()

            col_codigo = df.columns[16] if len(df.columns) > 16 else df.columns[0]
            col_municipio = df.columns[2] if len(df.columns) > 2 else df.columns[0]
            col_tipo_coleta = df.columns[17] if len(df.columns) > 17 else df.columns[0]
            col_massa = df.columns[24] if len(df.columns) > 24 else df.columns[0]
            col_destino = df.columns[28] if len(df.columns) > 28 else df.columns[0]
            col_uf = df.columns[3] if len(df.columns) > 3 else df.columns[0]

            df = df.rename(columns={
                col_municipio: "MUNICIPIO",
                col_tipo_coleta: "TIPO_COLETA",
                col_massa: "MASSA",
                col_destino: "DESTINO",
                col_uf: "UF"
            })
            df["MASSA"] = pd.to_numeric(df["MASSA"], errors="coerce").fillna(0)

            mask_organica = df["TIPO_COLETA"].astype(str).str.contains(
                "indiferenciada|orgânico|poda|galhada|verde", case=False, na=False, regex=True
            )
            df_org = df[mask_organica].copy()

            if df_org.empty:
                st.warning("Nenhum dado de coleta orgânica encontrado para este ano.")
                st.stop()

            if not hasattr(classificador_ia, 'pipeline') or classificador_ia.pipeline is None:
                with st.spinner("Treinando modelo de IA..."):
                    classificador_ia.treinar_com_dados_snis(df, "DESTINO")

            df_org["DESTINO_CLASSIFICADO"] = df_org["DESTINO"].apply(
                lambda x: classificador_ia.prever(x, threshold=0.3) if pd.notna(x) else "Indefinido"
            )

            def obter_parametros_destino(destino):
                if pd.isna(destino) or destino == "Indefinido":
                    return 0.6, 0.0
                d = destino.upper()
                if "ATERRO" in d:
                    if "CAIEIRAS" in d or "GUATAPARÁ" in d or "GUATAPARA" in d:
                        return 1.0, 0.65
                    else:
                        return 0.8, 0.0
                elif "COMPOSTAGEM" in d or "COMPOST" in d:
                    return 0.0, 0.0
                elif "TRANSBORDO" in d:
                    return 0.6, 0.0
                else:
                    return 0.4, 0.0

            df_org["MCF"], df_org["CAPTURA"] = zip(*df_org["DESTINO_CLASSIFICADO"].apply(obter_parametros_destino))

            from utils.calculos_emissao import calcular_reducoes_com_parametros, calcular_doc_k_ponderado

            resultados_municipios = []
            total_municipios = len(df_org["MUNICIPIO"].unique())
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Parâmetros fixos para a IA (usamos os sliders da aba 1, mas com valores padrão)
            eficiencia_ia = 0.40  # 40% (padrão)
            umidade_ia = 0.80     # 80%

            for idx, municipio in enumerate(df_org["MUNICIPIO"].unique()):
                status_text.text(f"Processando {idx+1}/{total_municipios}: {municipio}")
                progress_bar.progress((idx+1)/total_municipios)

                df_mun = df_org[df_org["MUNICIPIO"] == municipio]
                massa_total = df_mun["MASSA"].sum()
                if massa_total <= 0:
                    continue

                doc, k, docf = calcular_doc_k_ponderado(df_mun)

                for _, row in df_mun.iterrows():
                    massa_rota = row["MASSA"]
                    if massa_rota <= 0:
                        continue
                    mcf = row["MCF"]
                    captura = row["CAPTURA"]

                    try:
                        # Usamos a função original do utils, mas passamos os parâmetros
                        # de eficiência e umidade para ela considerar a energia.
                        resultado = calcular_reducoes_com_parametros(
                            massa_ano_kg=massa_rota * 1000,
                            k=k,
                            doc=doc,
                            docf=docf,
                            captura_metano=captura,
                            storage_factor=storage_factor_ia,
                            mcf=mcf,
                            tipo_digestor=tipo_digestor_ia,
                            eficiencia_motor=eficiencia_ia,
                            umidade=umidade_ia,
                            gwp_ch4=27.0,   # GWP-100 padrão
                            gwp_n2o=273
                        )
                    except Exception as e:
                        continue

                    preco = st.session_state.preco_carbono
                    cambio = st.session_state.taxa_cambio
                    receita = resultado['ER'] * preco * cambio

                    resultados_municipios.append({
                        "Município": municipio,
                        "UF": row.get("UF", ""),
                        "Massa_Total_Ano": massa_total,
                        "Massa_Rota_Ano": massa_rota,
                        "Destino": row["DESTINO_CLASSIFICADO"],
                        "Destino_Original": row["DESTINO"][:50] if pd.notna(row["DESTINO"]) else "",
                        "MCF": mcf,
                        "Captura_Metano": captura,
                        "Baseline": resultado['baseline'],
                        "PE_total": resultado['PE_total'],
                        "LE_total": resultado['LE_total'],
                        "ER": resultado['ER'],
                        "Receita_Anual": receita
                    })

            progress_bar.empty()
            status_text.empty()

            if not resultados_municipios:
                st.warning("Nenhum resultado calculado. Verifique os dados.")
                st.stop()

            df_resultados = pd.DataFrame(resultados_municipios)
            df_agg = df_resultados.groupby(["Município", "UF"]).agg({
                "Massa_Total_Ano": "first",
                "Massa_Rota_Ano": "sum",
                "Baseline": "sum",
                "PE_total": "sum",
                "LE_total": "sum",
                "ER": "sum",
                "Receita_Anual": "sum",
                "Destino": lambda x: ", ".join(sorted(set(x))),
                "Destino_Original": lambda x: ", ".join(sorted(set(x)))[:100]
            }).reset_index()

            df_agg["Potencial_por_t"] = df_agg["ER"] / df_agg["Massa_Rota_Ano"] if df_agg["Massa_Rota_Ano"].sum() > 0 else 0
            df_agg["Baseline_por_t"] = df_agg["Baseline"] / df_agg["Massa_Rota_Ano"] if df_agg["Massa_Rota_Ano"].sum() > 0 else 0

            mapa_ordenacao = {
                "Potencial de redução (tCO₂e/ano)": "ER",
                "Massa orgânica (t/ano)": "Massa_Rota_Ano",
                "Receita potencial (R$/ano)": "Receita_Anual"
            }
            col_ordenacao = mapa_ordenacao.get(ordenar_por, "ER")
            df_agg = df_agg.sort_values(col_ordenacao, ascending=False).reset_index(drop=True)

            st.subheader(f"📊 Ranking Nacional – Top {top_n} municípios")
            st.caption(f"Ano: {ano_selecionado} | Critério: {ordenar_por}")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Municípios analisados", len(df_agg))
            col2.metric("Massa orgânica total", f"{formatar_br(df_agg['Massa_Rota_Ano'].sum(), auto_precision=False, casas_override=0)} t")
            col3.metric("Potencial total de ER", f"{formatar_br(df_agg['ER'].sum(), auto_precision=False, casas_override=0)} tCO₂e")
            col4.metric("Receita potencial total", f"R$ {formatar_br(df_agg['Receita_Anual'].sum(), auto_precision=False, casas_override=0)}")

            df_exibicao = df_agg.head(top_n).copy()
            df_exibicao["ER"] = df_exibicao["ER"].apply(lambda x: formatar_br(x, auto_precision=False, casas_override=2))
            df_exibicao["Receita_Anual"] = df_exibicao["Receita_Anual"].apply(lambda x: f"R$ {formatar_br(x, auto_precision=False, casas_override=2)}")
            df_exibicao["Massa_Rota_Ano"] = df_exibicao["Massa_Rota_Ano"].apply(lambda x: formatar_br(x, auto_precision=False, casas_override=0))
            df_exibicao["Baseline"] = df_exibicao["Baseline"].apply(lambda x: formatar_br(x, auto_precision=False, casas_override=2))
            df_exibicao["PE_total"] = df_exibicao["PE_total"].apply(lambda x: formatar_br(x, auto_precision=False, casas_override=2))
            df_exibicao["LE_total"] = df_exibicao["LE_total"].apply(lambda x: formatar_br(x, auto_precision=False, casas_override=2))

            st.dataframe(
                df_exibicao[["Município", "UF", "Massa_Rota_Ano", "Destino", "Baseline", "PE_total", "LE_total", "ER", "Receita_Anual"]],
                use_container_width=True,
                column_config={
                    "Município": "Município",
                    "UF": "UF",
                    "Massa_Rota_Ano": "Massa (t/ano)",
                    "Destino": "Destino (IA)",
                    "Baseline": "Baseline (tCO₂e)",
                    "PE_total": "Projeto (tCO₂e)",
                    "LE_total": "Vazamento (tCO₂e)",
                    "ER": "Redução Líquida (tCO₂e)",
                    "Receita_Anual": "Receita (R$/ano)"
                }
            )

            # =============================================================
            # GRÁFICO TOP 10 – CORRIGIDO (ax.invert_yaxis())
            # =============================================================
            st.subheader("📊 Top 10 – Potencial de Redução de Emissões")
            fig, ax = plt.subplots(figsize=(10, 6))
            top10 = df_agg.head(10)
            cores = plt.cm.Greens(np.linspace(0.4, 0.9, 10))
            ax.barh(top10["Município"] + " - " + top10["UF"], top10["ER"], color=cores)
            
            # === CORREÇÃO VISUAL: Inverte o eixo Y para o maior valor ficar no topo ===
            ax.invert_yaxis()
            # ========================================================================
            
            ax.set_xlabel("Redução Líquida (tCO₂e/ano)")
            ax.set_title("Municípios com maior potencial de redução (usina de bioenergia)")
            ax.grid(True, linestyle="--", alpha=0.3)
            for i, (idx, row) in enumerate(top10.iterrows()):
                ax.text(row["ER"] + 1, i, formatar_br(row["ER"], auto_precision=False, casas_override=0), va="center", fontsize=9)
            st.pyplot(fig)
            plt.close(fig)

            # =============================================================
            # GRÁFICO POR ESTADO (já está correto)
            # =============================================================
            st.subheader("📊 Potencial por Estado (UF)")
            df_uf = df_agg.groupby("UF").agg({
                "ER": "sum",
                "Massa_Rota_Ano": "sum"
            }).reset_index()
            df_uf = df_uf.sort_values("ER", ascending=False)

            fig2, ax2 = plt.subplots(figsize=(10, 5))
            cores_uf = plt.cm.Blues(np.linspace(0.4, 0.9, len(df_uf)))
            ax2.bar(df_uf["UF"], df_uf["ER"], color=cores_uf)
            ax2.set_xlabel("Estado")
            ax2.set_ylabel("Redução Líquida (tCO₂e/ano)")
            ax2.set_title("Potencial de redução por estado")
            ax2.grid(True, linestyle="--", alpha=0.3)
            for i, (_, row) in enumerate(df_uf.iterrows()):
                ax2.text(i, row["ER"] + max(df_uf["ER"])*0.01, formatar_br(row["ER"], auto_precision=False, casas_override=0), ha="center", fontsize=9)
            st.pyplot(fig2)
            plt.close(fig2)

            st.subheader("📥 Exportar resultados")
            csv = df_agg.to_csv(index=False, encoding="utf-8")
            st.download_button(
                label="📥 Baixar ranking completo (CSV)",
                data=csv,
                file_name=f"ranking_potencial_digestao_anaerobica_{ano_selecionado}.csv",
                mime="text/csv"
            )

            st.info("""
            💡 **Interpretação dos resultados:**  
            - **Baseline**: emissões atuais do aterro (considerando captura de metano real).  
            - **Projeto (PE)**: emissões da usina de bioenergia (consumo elétrico + vazamentos do biodigestor).  
            - **Vazamento (LE)**: emissões do digestato se armazenado anaerobicamente.  
            - **Redução Líquida (ER)**: é o potencial de créditos de carbono.  
            - Municípios com maior **ER** têm maior potencial de gerar receita com créditos de carbono.
            - **Agora o cálculo inclui o benefício da geração de eletricidade** com sliders ajustáveis para eficiência e umidade.
            """)

            st.session_state.df_potencial = df_agg


# =============================================================================
# RODAPÉ
# =============================================================================
st.markdown("---")
st.caption("""
**Digesta.IA** | Ferramenta de apoio à gestão de resíduos sólidos e créditos de carbono  
Dados: SNIS (2023/2024) | Metodologia: UNFCCC A6.4-AMT-003 (2025) + TOOL14 + ACM0022 | IPCC AR5 (GWP-100)
""")
