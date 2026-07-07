import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import joblib
import os

def normalizar_texto(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto).lower()
    texto = re.sub(r'[^a-záéíóúãõç ]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def classificar_destino_regra(texto):
    if pd.isna(texto):
        return "Indefinido"
    t = normalizar_texto(texto)
    if "aterro" in t:
        return "Aterro"
    elif "transbordo" in t:
        return "Transbordo"
    elif "compostagem" in t or "compost" in t:
        return "Compostagem"
    elif "triagem" in t or "galpão" in t:
        return "Triagem"
    elif "reciclagem" in t:
        return "Reciclagem"
    else:
        return "Outros"

class ClassificadorDestinoIA:
    def __init__(self):
        self.pipeline = None
        self.classes_ = None

    def carregar_ou_treinar(self, df, col_texto):
        modelo_path = "modelos/classificador_destino.pkl"
        if os.path.exists(modelo_path):
            self.pipeline = joblib.load(modelo_path)
            self.classes_ = self.pipeline.classes_
            return
        self.treinar_com_dados_snis(df, col_texto)

    def treinar_com_dados_snis(self, df, col_texto):
        df_temp = df.dropna(subset=[col_texto]).copy()
        df_temp['texto_norm'] = df_temp[col_texto].apply(normalizar_texto)
        df_temp['classe'] = df_temp[col_texto].apply(classificar_destino_regra)
        
        X = df_temp['texto_norm']
        y = df_temp['classe']
        
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1,2))),
            ('clf', LogisticRegression(max_iter=1000, random_state=42))
        ])
        self.pipeline.fit(X, y)
        self.classes_ = self.pipeline.classes_
        
        os.makedirs("modelos", exist_ok=True)
        joblib.dump(self.pipeline, "modelos/classificador_destino.pkl")

    def prever(self, texto, threshold=0.3):
        if pd.isna(texto) or self.pipeline is None:
            return "Indefinido"
        texto_norm = normalizar_texto(texto)
        probs = self.pipeline.predict_proba([texto_norm])[0]
        max_prob = max(probs)
        if max_prob < threshold:
            return classificar_destino_regra(texto)
        return self.pipeline.predict([texto_norm])[0]
