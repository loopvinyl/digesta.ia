# ⚡ Digesta.IA

**Simulador de créditos de carbono para usinas de bioenergia a partir de resíduos orgânicos, com IA para identificar municípios prioritários.**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://digesta-ia.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 🌱 Visão Geral

O **Digesta.IA** é uma ferramenta de apoio à gestão pública e ao planejamento de projetos de bioenergia. Ele permite:

- **Simular** as emissões de gases de efeito estufa (GEE) e o potencial de geração de créditos de carbono para uma usina de digestão anaeróbica (como a do IEE/USP).
- **Identificar**, com o auxílio de Inteligência Artificial, os municípios brasileiros com maior potencial de redução de emissões ao implantar uma usina similar.

O aplicativo utiliza dados públicos do **SNIS (Sistema Nacional de Informações sobre Saneamento)** e metodologias oficiais da **UNFCCC** para o cálculo do baseline e das emissões do projeto, garantindo robustez técnica e alinhamento com o mercado de carbono.

---

## 🧪 Metodologias Utilizadas

| Componente | Metodologia | Descrição |
|------------|-------------|-----------|
| **Baseline (aterro)** | **UNFCCC A6.4-AMT-003 (2025)**<br>(antiga TOOL04) | Cálculo das emissões de metano de aterros sanitários usando modelo de primeira ordem (FOD) e parâmetros calibrados para clima úmido (\(\phi = 0,85\), \(OX = 0,383\)). |
| **Emissões do projeto (biodigestor)** | **TOOL14**<br>(Project and leakage emissions from anaerobic digesters) | Contabiliza emissões de CH₄ e CO₂ provenientes do consumo de eletricidade, vazamentos do digestor e armazenamento do digestato. |
| **Integração e redução líquida** | **ACM0022**<br>(Alternative waste treatment processes) | Consolida baseline, emissões do projeto e vazamentos para calcular as reduções líquidas de emissões (\(ER = BE - PE - LE\)). |
| **Fatores de GWP** | **IPCC AR5 (GWP-100)** | GWP_CH₄ = 28, GWP_N₂O = 265 (conforme decisão da CMA/UNFCCC). |

---

## 🧠 Inteligência Artificial Aplicada

- **Classificação de destinos (PLN)**: utilizamos um modelo de **Regressão Logística com TF-IDF** para padronizar as descrições textuais do SNIS (ex: “Aterro Sanitário Caieiras” → “Aterro com captura de biogás”).
- **Clusterização de municípios (K-Means)**: agrupa municípios por perfil de geração e destinação de resíduos, auxiliando na identificação de padrões e prioridades.
- **Ranking inteligente**: ordena municípios pelo **potencial de redução de emissões (ER)**, considerando a massa de orgânicos, o destino atual e a captura de metano real.

---

## 📊 Funcionalidades

### 🧪 Aba 1 – Simulador da Usina IEE
- Entrada de dados: quantidade de resíduos (kg/dia ou ton/ano), tipo de biodigestor, captura de metano no aterro, destino do digestato.
- Cálculo instantâneo de:
  - Baseline (aterro)
  - Emissões do projeto (PE)
  - Vazamentos (LE)
  - Redução líquida (ER)
  - Receita potencial anual (em R$)
- Gráfico comparativo de emissões.

### 🤖 Aba 2 – Potencial por Localidade (IA)
- Processamento de **todos os municípios brasileiros** que possuem coleta de resíduos orgânicos (dados SNIS 2023/2024).
- Classificação automática de destinos via IA.
- Cálculo do potencial de ER e receita para cada município.
- **Ranking nacional** (Top N configurável).
- **Gráficos interativos** (Top 10 municípios, potencial por estado).
- **Download dos resultados** em CSV.

---

## 📂 Dados Utilizados

Os dados de resíduos sólidos urbanos são obtidos do **SNIS** (Sistema Nacional de Informações sobre Saneamento), por meio dos arquivos Excel disponibilizados publicamente:

- `rsuBrasil_2023.xlsx`
- `rsuBrasil_2024.xlsx`

Esses arquivos são carregados diretamente do repositório (pasta `data/`) e contêm informações sobre rotas de coleta, massas coletadas e destinação final.

---

## 🚀 Como Executar Localmente

### Pré‑requisitos
- Python 3.10 ou superior
- Pip (gerenciador de pacotes)

### Passos

1. **Clone o repositório**
   ```bash
   git clone https://github.com/loopvinyl/digesta.ia.git
   cd digesta.ia
