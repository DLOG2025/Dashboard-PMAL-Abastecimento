import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(
    page_title="Dashboard PMAL - Combustível",
    page_icon="⛽️",
    layout="wide"
)

@st.cache_data(ttl=3600)
def load_data():
    # Lê apenas as colunas essenciais para performance
    ab = pd.read_excel(
        "Abastecimentos_Consolidados.xlsx",
        usecols=["Placa", "Unidade", "TOTAL_LITROS", "VALOR_TOTAL"]
    )
    fr = pd.read_excel(
        "Frota_Master_Enriched.xlsx",
        usecols=["Placa"]
    )

    # Padroniza nomes de colunas
    ab.columns = ab.columns.str.upper()
    fr.columns = fr.columns.str.upper()

    # Renomeia para padrão interno
    ab = ab.rename(columns={
        "PLACA": "Placa",
        "UNIDADE": "OPM",
        "TOTAL_LITROS": "Litros",
        "VALOR_TOTAL": "Custo"
    })
    fr = fr.rename(columns={"PLACA": "Placa"})

    # Padroniza valores de placa
    ab["Placa"] = (
        ab["Placa"].astype(str)
        .str.upper()
        .str.replace(r"[^A-Z0-9]", "", regex=True)
    )
    fr["Placa"] = (
        fr["Placa"].astype(str)
        .str.upper()
        .str.replace(r"[^A-Z0-9]", "", regex=True)
    )

    # Mescla abastecimentos com frota
    df = ab.merge(fr, on="Placa", how="left")
    return df

# Função principal

def main():
    st.title("📊 Dashboard Online – Consumo de Combustível PMAL")

    # Carrega os dados
    df = load_data()

    # SIDEBAR: filtros de OPM
    st.sidebar.header("Filtros")
    if "OPM" in df.columns:
        opms = sorted(df["OPM"].dropna().unique())
        sel_opm = st.sidebar.multiselect("Selecione OPM(s)", opms, default=opms)
        df = df[df["OPM"].isin(sel_opm)]

    # Abas do dashboard
    tab1, tab2, tab3, tab4 = st.tabs([
        "✅ KPIs",
        "📈 Consumo por Arquivo",
        "🥧 Distribuição de Combustível",
        "🚨 Anomalias"
    ])

    with tab1:
        st.subheader("KPIs Principais")
        total_l = df["Litros"].sum()
        total_c = df["Custo"].sum()
        media_v = df.groupby("Placa")["Litros"].sum().mean()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Litros (L)", f"{total_l:,.0f}")
        c2.metric("Total Gasto (R$)", f"R$ {total_c:,.2f}")
        c3.metric("Média por Viatura (L)", f"{media_v:,.1f}")

    with tab2:
        st.subheader("Consumo por Arquivo")
        if "ARQUIVO" in df.columns:
            grp = df.groupby("ARQUIVO")["Litros"].sum().reset_index()
            fig = px.bar(grp, x="ARQUIVO", y="Litros", labels={"Litros": "Litros (L)"})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Coluna 'ARQUIVO' não encontrada.")

    with tab3:
        st.subheader("Distribuição por Combustível Dominante")
        if "COMBUSTIVEL_DOMINANTE" in df.columns:
            dist = df.groupby("COMBUSTIVEL_DOMINANTE")["Litros"].sum().reset_index()
            fig = px.pie(dist, names="COMBUSTIVEL_DOMINANTE", values="Litros", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Coluna 'COMBUSTIVEL_DOMINANTE' não encontrada.")

    with tab4:
        st.subheader("Detecção de Anomalias (Z-score)")
        df["Z"] = (df["Litros"] - df["Litros"].mean()) / df["Litros"].std()
        anomal = df[df["Z"].abs() > 2]
        st.metric("Total Registros", len(df), delta=f"{len(anomal)} anomalias")
        st.dataframe(anomal[["Placa", "Litros", "Custo"]], use_container_width=True)

    # Efeito visual: balões
    if st.sidebar.button("🎉 Balões"):
        st.balloons()

    st.markdown("---")
    st.markdown("_Dashboard sem mapeamento e rápido de carregar (usecols)._")

if __name__ == "__main__":
    main()
