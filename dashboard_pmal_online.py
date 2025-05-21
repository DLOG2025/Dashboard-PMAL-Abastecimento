import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path
from datetime import datetime

# ==============================================================
# CONFIGURAÇÃO GERAL
# ==============================================================
st.set_page_config(page_title="Dashboard PMAL – Frota & Combustível", page_icon="🚔", layout="wide")

# --------------------------------------------------------------
# FUNÇÕES AUXILIARES
# --------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_base_files() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carrega as três planilhas‑base geradas na etapa de ETL.
    Retorna (frota_enriquecida, abastecimentos, custos_padroes_locados)."""
    frota = pd.read_excel("Frota_Master_Enriched.xlsx")
    abast = pd.read_excel("Abastecimentos_Consolidados.xlsx")
    padroes = pd.read_excel("PADRÕES_LOCADOS.xlsx")
    return frota, abast, padroes

@st.cache_data(show_spinner=False)
def preparar_dados():
    frota, abast, pad = load_base_files()

    # ------------ CUSTO MENSAL DE LOCAÇÃO -------------
    pad["PADRAO_EXTRAI"] = pad["PADRÃO"].str.extract(r'"?([A-Z]-?\d+)"?')[0]
    pad["CUSTO_MENSAL"] = (
        pad["CUSTO MENSAL"].astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    custo_dict = pad.set_index("PADRAO_EXTRAI")["CUSTO_MENSAL"].to_dict()

    # Corrige extração (Series) e aplica custo
    padrao_series = frota["PADRAO"].astype(str).str.extract(r'"?([A-Z]-?\d+)"?')[0]
    frota["CUSTO_PADRAO_MENSAL"] = padrao_series.map(custo_dict)
    frota.loc[frota["Frota"] != "LOCADA", "CUSTO_PADRAO_MENSAL"] = 0.0

    # ------------ CUSTO DE COMBUSTÍVEL -------------
    combustivel_por_placa = (
        abast.groupby("PLACA")["VALOR_TOTAL"].sum().rename("CUSTO_COMBUSTIVEL_TOTAL")
    )
    frota = frota.merge(combustivel_por_placa, on="PLACA", how="left")
    frota["CUSTO_COMBUSTIVEL_TOTAL"] = frota["CUSTO_COMBUSTIVEL_TOTAL"].fillna(0.0)

    # ------------ CUSTO TOTAL -------------
    frota["CUSTO_TOTAL"] = frota["CUSTO_PADRAO_MENSAL"].fillna(0) + frota["CUSTO_COMBUSTIVEL_TOTAL"]

    # ------------ IDADE -------------
    current_year = datetime.now().year
    frota["IDADE_FROTA"] = (
        pd.to_numeric(frota["ANO_FABRICACAO"], errors="coerce")
        .apply(lambda y: current_year - y if pd.notna(y) else None)
    )

    return frota, abast

# --------------------------------------------------------------
# ELEMENTOS VISUAIS
# --------------------------------------------------------------

def card_metrics(label, value, help_text=""):
    st.metric(label, value, help=help_text)

# ==============================================================
# MAIN
# ==============================================================

def main():
    st.title("🚔 Dashboard Gerencial da Frota PMAL")
    st.caption("Visão integrada de veículos, custos e abastecimentos – dados consolidados de abril/2025.")

    frota, abast = preparar_dados()

    # ---------------- Sidebar -----------------
    st.sidebar.header("🔍 Filtros")
    opm_unicas = sorted(frota["OPM"].dropna().unique())
    filtro_opm = st.sidebar.multiselect("OPM / Unidade", opm_unicas, default=opm_unicas)
    tipos_frota = ["LOCADA", "PRÓPRIA/JUSTIÇA"]
    filtro_frota = st.sidebar.multiselect("Tipo de Frota", tipos_frota, default=tipos_frota)
    filtro_caract = st.sidebar.multiselect("Caracterização", ["CARACTERIZADO", "DESCARACTERIZADO"], default=["CARACTERIZADO", "DESCARACTERIZADO"])

    frota_f = frota[
        frota["OPM"].isin(filtro_opm)
        & frota["Frota"].isin(filtro_frota)
        & frota["CARACTERIZACAO"].isin(filtro_caract)
    ]

    # ---------------- Métricas -----------------
    col1, col2, col3, col4 = st.columns(4)
    card_metrics("Viaturas Gerais", f"{len(frota_f):,}")
    card_metrics("Idade Média (anos)", f"{frota_f['IDADE_FROTA'].mean():.1f}" if frota_f["IDADE_FROTA"].notna().any() else "–")
    card_metrics("Custo Total R$", f"{frota_f['CUSTO_TOTAL'].sum():,.2f}")
    litros_total = abast[abast["PLACA"].isin(frota_f["PLACA"])] ["TOTAL_LITROS"].sum()
    card_metrics("Total de Litros", f"{litros_total:,.2f} L")

    st.divider()

    # ---------------- Gráficos Mix -----------------
    colA, colB = st.columns(2)
    mix_caract = frota_f["CARACTERIZACAO"].value_counts()
    colA.plotly_chart(px.pie(names=mix_caract.index, values=mix_caract.values, title="Caracterizados × Descaracterizados"), use_container_width=True)

    mix_tipo = frota_f["Frota"].value_counts()
    colB.plotly_chart(px.pie(names=mix_tipo.index, values=mix_tipo.values, title="Locados × Próprios/Justiça"), use_container_width=True)

    # ---------------- Custo por OPM -----------------
    st.subheader("💰 Custo total (locação + combustível) por OPM")
    custo_opm = frota_f.groupby("OPM")["CUSTO_TOTAL"].sum().sort_values(ascending=True)
    st.plotly_chart(px.bar(custo_opm, orientation="h", labels={"value": "R$", "index": "OPM"}), use_container_width=True)

    # ---------------- Idade da Frota -----------------
    if frota_f["IDADE_FROTA"].notna().any():
        st.subheader("📈 Distribuição da Idade da Frota (anos)")
        st.plotly_chart(px.histogram(frota_f, x="IDADE_FROTA", nbins=15, labels={"IDADE_FROTA": "Idade (anos)"}), use_container_width=True)

    # ---------------- Tabela Detalhada -----------------
    st.subheader("📋 Detalhamento – Viaturas (custos, idade, caracterização)")
    ranking_consumo = (
        abast.groupby("PLACA")["VALOR_TOTAL"].sum().rank(method="dense", ascending=False).astype(int)
    )
    df_show = frota_f.copy()
    df_show["Ranking_Consumo"] = df_show["PLACA"].map(ranking_consumo)
    df_show = df_show.sort_values("CUSTO_TOTAL", ascending=False)

    cols_exibir = [
        "Ranking_Consumo","PLACA","OPM","Frota","CARACTERIZACAO","PADRAO","MARCA","MODELO","ANO_FABRICACAO","IDADE_FROTA","CUSTO_PADRAO_MENSAL","CUSTO_COMBUSTIVEL_TOTAL","CUSTO_TOTAL"
    ]
    st.dataframe(df_show[cols_exibir], use_container_width=True)

# --------------------------------------------------
if __name__ == "__main__":
    main()
