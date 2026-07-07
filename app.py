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
if 'df_potencial' not in st.session_state:
    st.session_state.df_potencial = None

# =============================================================================
# TÍTULO
# =============================================================================
st.title("⚡ Digesta.IA - Simulador de Créditos de Carbono")
st.caption("Usina de Bioenergia e Biofertilizantes do IEE/USP | Metodologia: ACM0022 + TOOL14 + TOOL04 (UNFCCC)")

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

            fig, ax = plt.subplots(figsize=(8, 4))
            ax.bar(["Baseline", "Projeto", "Vazamento"], [resultados['baseline'], resultados['PE_total'], resultados['LE_total']],
                   color=['red', 'orange', 'blue'])
            ax.set_ylabel("tCO₂e")
            ax.set_title("Comparação de emissões")
            st.pyplot(fig)

# =============================================================================
# ABA 2 – IA (POTENCIAL POR LOCALIDADE) – CÓDIGO COMPLETO
# =============================================================================
with tab_ia:
    st.header("🧠 Análise de Potencial por Localidade (IA)")
    st.markdown("""
    A IA processa os dados do **SNIS** para identificar municípios com maior potencial de emissões evitadas
    ao implantar uma usina de bioenergia similar à do IEE/USP (digestão anaeróbica).
    """)

    # =========================================================
    # CARREGAR DADOS DO SNIS
    # =========================================================
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

    # =========================================================
    # PARÂMETROS DA SIMULAÇÃO
    # =========================================================
    col1, col2 = st.columns(2)
    with col1:
        ano_selecionado = st.selectbox("Selecione o ano de referência:", ["2023", "2024"], index=1)
        st.session_state.ano_ia = ano_selecionado
        tipo_digestor_ia = "CSTR"
        digestato_armazenado_ia = True

    with col2:
        ordenar_por = st.selectbox(
            "Ordenar por:",
            ["Potencial de redução (tCO₂e/ano)", "Massa orgânica (t/ano)", "Receita potencial (R$/ano)"],
            index=0
        )
        top_n = st.slider("Mostrar os top N municípios:", 5, 50, 20, 5)

    # =========================================================
    # INICIALIZAR CLASSIFICADOR IA
    # =========================================================
    with st.spinner("🤖 Inicializando o modelo de IA..."):
        from utils.ia_classificacao import ClassificadorDestinoIA, classificar_destino_regra
        classificador_ia = ClassificadorDestinoIA()

    if st.button("🔍 Analisar Potencial Nacional", type="primary"):
        with st.spinner("🔄 Processando dados de todos os municípios... Isso pode levar alguns segundos."):

            df = load_data(ano_selecionado)
            if df is None:
                st.error("Não foi possível carregar os dados do SNIS.")
                st.stop()

            # Preparar colunas
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

            # Filtrar orgânicos
            mask_organica = df["TIPO_COLETA"].astype(str).str.contains(
                "indiferenciada|orgânico|poda|galhada|verde", case=False, na=False, regex=True
            )
            df_org = df[mask_organica].copy()

            if df_org.empty:
                st.warning("Nenhum dado de coleta orgânica encontrado para este ano.")
                st.stop()

            # Treinar IA
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

            from utils.calculos_emissao import calcular_reducoes, calcular_doc_k_ponderado

            resultados_municipios = []
            total_municipios = len(df_org["MUNICIPIO"].unique())
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, municipio in enumerate(df_org["MUNICIPIO"].unique()):
                status_text.text(f"Processando {idx+1}/{total_municipios}: {municipio}")
                progress_bar.progress((idx+1)/total_municipios)

                df_mun = df_org[df_org["MUNICIPIO"] == municipio]
                massa_total = df_mun["MASSA"].sum()
                if massa_total <= 0:
                    continue

                doc, k = calcular_doc_k_ponderado(df_mun)

                for _, row in df_mun.iterrows():
                    massa_rota = row["MASSA"]
                    if massa_rota <= 0:
                        continue
                    mcf = row["MCF"]
                    captura = row["CAPTURA"]

                    try:
                        resultado = calcular_reducoes(
                            massa_ano_kg=massa_rota * 1000,
                            captura_metano_baseline=captura,
                            doc=doc,
                            k=k,
                            mcf=mcf,
                            tipo_digestor=tipo_digestor_ia,
                            digestato_armazenado=digestato_armazenado_ia
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

            st.subheader("📊 Top 10 – Potencial de Redução de Emissões")
            fig, ax = plt.subplots(figsize=(10, 6))
            top10 = df_agg.head(10)
            cores = plt.cm.Greens(np.linspace(0.4, 0.9, 10))
            ax.barh(top10["Município"] + " - " + top10["UF"], top10["ER"], color=cores)
            ax.set_xlabel("Redução Líquida (tCO₂e/ano)")
            ax.set_title("Municípios com maior potencial de redução (usina de bioenergia)")
            ax.grid(True, linestyle="--", alpha=0.3)
            for i, (idx, row) in enumerate(top10.iterrows()):
                ax.text(row["ER"] + 1, i, formatar_br(row["ER"], auto_precision=False, casas_override=0), va="center", fontsize=9)
            st.pyplot(fig)

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
            """)

            st.session_state.df_potencial = df_agg
