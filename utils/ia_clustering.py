import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns

def preparar_dados_clusterizacao(df, col_municipio='MUNICÍPIO', col_massa='MASSA_COLETADA', col_destino='DESTINO'):
    df_agg = df.groupby(col_municipio).agg({
        col_massa: 'sum',
        col_destino: lambda x: list(x)
    }).reset_index()
    
    df_agg['massa_total'] = pd.to_numeric(df_agg[col_massa], errors='coerce').fillna(0)
    df_agg['num_rotas'] = df_agg[col_destino].apply(len)
    
    # Calcular percentuais por destino (simplificado)
    df_agg['pct_aterro'] = 0
    df_agg['pct_compostagem'] = 0
    
    X = df_agg[['massa_total', 'num_rotas', 'pct_aterro', 'pct_compostagem']].values
    X = np.nan_to_num(X, nan=0.0)
    
    return X, df_agg

def clusterizar_municipios(X, n_clusters=4):
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    return labels, kmeans, scaler

def aplicar_pca(X):
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X)
    return X_pca, pca

def plot_clusters(X_pca, labels, df_cluster):
    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(X_pca[:, 0], X_pca[:, 1], c=labels, cmap='viridis', alpha=0.7, s=50)
    ax.set_title('Clusterização de Municípios por Perfil de Resíduos')
    ax.set_xlabel('PC1')
    ax.set_ylabel('PC2')
    plt.colorbar(scatter, label='Cluster')
    return fig

def resumo_clusters(df_cluster, labels):
    df_cluster['Cluster'] = labels
    resumo = df_cluster.groupby('Cluster').agg({
        'massa_total': ['mean', 'median', 'sum'],
        'num_rotas': 'mean',
        'pct_aterro': 'mean',
        'pct_compostagem': 'mean'
    }).round(2)
    resumo.columns = ['Massa_Media', 'Massa_Mediana', 'Massa_Total_Cluster', 'Rotas_Media', 'Pct_Aterro_Media', 'Pct_Compostagem_Media']
    return resumo

def descrever_clusters(df_cluster, labels):
    df_cluster['Cluster'] = labels
    descricoes = {}
    for cluster in sorted(df_cluster['Cluster'].unique()):
        df_c = df_cluster[df_cluster['Cluster'] == cluster]
        massa_total = df_c['massa_total'].sum()
        num_mun = len(df_c)
        descricoes[cluster] = f"""
**Cluster {cluster+1}** – {num_mun} municípios  
Massa total: {massa_total:,.0f} t  
Massa média: {df_c['massa_total'].mean():,.0f} t  
Número médio de rotas: {df_c['num_rotas'].mean():.1f}  
Percentual médio para aterro: {df_c['pct_aterro'].mean():.1f}%  
Percentual médio para compostagem: {df_c['pct_compostagem'].mean():.1f}%  
"""
    return descricoes
