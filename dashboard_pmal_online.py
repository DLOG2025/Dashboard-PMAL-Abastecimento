import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ==============================================================
# CONFIGURAÇÃO GERAL
# ==============================================================
st.set_page_config(
    page_title="Dashboard PMAL - Combustível",
    page_icon="🚒",
    layout="wide"
)

# ==============================================================
# FUNÇÕES AUXILIARES
# ==============================================================

def padroniza_placa(placa):
    return str(placa).upper().replace('-', '').replace(' ', '')

def tipo_combustivel(row):
    combustiveis = {
        'Gasolina': row.get('Gasolina (Lts)', 0),
        'Álcool': row.get('Álcool (Lts)', 0),
        'Diesel': row.get('Diesel (Lts)', 0),
        'Diesel S10': row.get('Diesel S10 (Lts)', 0)
    }
    return max(combustiveis, key=combustiveis.get)

def valor_total(row):
    total = 0.0
    for col in ['Gasolina (R$)', 'Álcool (R$)', 'Diesel (R$)', 'Diesel S10 (R$)']:
        if col in row and not pd.isna(row[col]):
            v = str(row[col]).replace('R$', '').replace(' ', '').replace(',', '.').replace('-', '0')
            try:
                total += float(v)
            except:
                pass
    return total

@st.cache_data(show_spinner=False)
def carregar_dados(arq_abast, arq_proprios, arq_locados):
    # Processa abastecimentos
    records = []
    for arquivo in arq_abast:
        df = pd.read_excel(arquivo, skiprows=4)
        df.rename(columns={df.columns[0]: 'PLACA'}, inplace=True)
        df = df[df['PLACA'].astype(str).str.upper().str.strip() != 'TOTAL']
        df['UNIDADE'] = arquivo.name.split(' ABR')[0].replace('º','').strip()
        df['ARQUIVO']  = arquivo.name
        df['PLACA']    = df['PLACA'].apply(padroniza_placa)
        for col in ['Gasolina (Lts)', 'Álcool (Lts)', 'Diesel (Lts)', 'Diesel S10 (Lts)']:
            if col not in df.columns:
                df[col] = 0
        for col in ['Gasolina (R$)', 'Álcool (R$)', 'Diesel (R$)', 'Diesel S10 (R$)']:
            if col not in df.columns:
                df[col] = 0
        df['TOTAL_LITROS']        = df[['Gasolina (Lts)', 'Álcool (Lts)', 'Diesel (Lts)', 'Diesel S10 (Lts)']].sum(axis=1)
        df['VALOR_TOTAL']         = df.apply(valor_total, axis=1)
        df['COMBUSTÍVEL']         = df.apply(tipo_combustivel, axis=1)
        records.append(df)
    if records:
        df_abastecimento = pd.concat(records, ignore_index=True)
    else:
        df_abastecimento = pd.DataFrame(columns=['PLACA','UNIDADE','ARQUIVO','Gasolina (Lts)','Álcool (Lts)','Diesel (Lts)','Diesel S10 (Lts)','Gasolina (R$)','Álcool (R$)','Diesel (R$)','Diesel S10 (R$)','TOTAL_LITROS','VALOR_TOTAL','COMBUSTÍVEL'])

    # Processa frota
    df_proprios, df_locados = None, None
    if arq_proprios:
        df_proprios = pd.read_excel(arq_proprios)
        df_proprios.rename(columns={df_proprios.columns[0]:'PLACA'}, inplace=True)
        df_proprios['PLACA'] = df_proprios['PLACA'].apply(padroniza_placa)
        df_proprios['FROTA'] = 'PRÓPRIO'
    if arq_locados:
        df_locados = pd.read_excel(arq_locados)
        df_locados.rename(columns={df_locados.columns[0]:'PLACA'}, inplace=True)
        df_locados['PLACA'] = df_locados['PLACA'].apply(padroniza_placa)
        df_locados['FROTA'] = 'LOCADO'
    if df_proprios is not None and df_locados is not None:
        df_frota = pd.concat([df_proprios, df_locados], ignore_index=True)
    elif df_proprios is not None:
        df_frota = df_proprios.copy()
    elif df_locados is not None:
        df_frota = df_locados.copy()
    else:
        df_frota = pd.DataFrame(columns=['PLACA','FROTA'])
    frota_map = dict(zip(df_frota['PLACA'], df_frota['FROTA']))
    df_abastecimento['FROTA'] = df_abastecimento['PLACA'].map(frota_map).fillna('NÃO ENCONTRADO')

    # Identifica placas em múltiplas OMs
    placas_mult = df_abastecimento.groupby('PLACA')['UNIDADE'].nunique()
    placas_mult = placas_mult[placas_mult > 1].index.tolist()
    df_mult_om = df_abastecimento[df_abastecimento['PLACA'].isin(placas_mult)].sort_values('PLACA')

    return df_abastecimento, df_mult_om

# Formata valores em reais

def formatar_reais(valor):
    try:
        return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
    except:
        return valor

# ==============================================================
# FUNÇÃO PRINCIPAL
# ==============================================================
def main():
    st.title("🚒 Dashboard Final de Abastecimento - PMAL")
    st.caption("Faça upload dos arquivos Excel para análise online!")

    st.sidebar.header("🔽 Upload dos Arquivos")
    abast_files = st.sidebar.file_uploader(
        "1️⃣ Abastecimentos (.xlsx)", type="xlsx", accept_multiple_files=True
    )
    frota_proprios = st.sidebar.file_uploader(
        "2️⃣ Frota Própria/Justiça (.xlsx) [opcional]", type="xlsx"
    )
    frota_locados = st.sidebar.file_uploader(
        "3️⃣ Frota Locada (.xlsx) [opcional]", type="xlsx"
    )

    if not abast_files:
        st.warning("Faça upload de pelo menos um arquivo de abastecimento para continuar.")
        st.stop()

    df, df_mult = carregar_dados(abast_files, frota_proprios, frota_locados)

    # --------------------- FILTROS ---------------------
    unidades    = st.sidebar.multiselect("Unidades:", df['UNIDADE'].unique(), default=df['UNIDADE'].unique())
    combustiveis= st.sidebar.multiselect("Combustíveis:", df['COMBUSTÍVEL'].unique(), default=df['COMBUSTÍVEL'].unique())
    frotas      = st.sidebar.multiselect("Frotas:", df['FROTA'].unique(), default=df['FROTA'].unique())

    df_fil = df[
        df['UNIDADE'].isin(unidades) &
        df['COMBUSTÍVEL'].isin(combustiveis) &
        df['FROTA'].isin(frotas)
    ]

    # -------------------- MÉTRICAS --------------------
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Registros",   len(df_fil))
    col2.metric("Viaturas Únicas",      df_fil['PLACA'].nunique())
    col3.metric("Total de Litros",      f"{df_fil['TOTAL_LITROS'].sum():,.2f} L")
    col4.metric("Total Gasto (R$)",     "R$ " + formatar_reais(df_fil['VALOR_TOTAL'].sum()))
    perc = df_fil['FROTA'].value_counts(normalize=True).get('NÃO ENCONTRADO',0)*100
    col5.metric("% Não Encontrados", f"{perc:.1f}%")

    # -------------------- GRÁFICOS --------------------
    st.subheader("📊 Consumo e Gasto por Unidade")
    g1, g2 = st.columns(2)
    cons_un = df_fil.groupby('UNIDADE')['TOTAL_LITROS'].sum().sort_values()
    g1.plotly_chart(px.bar(cons_un, orientation='h', labels={'index':'Unidade','value':'Litros'}), use_container_width=True)
    val_un  = df_fil.groupby('UNIDADE')['VALOR_TOTAL'].sum().sort_values()
    g2.plotly_chart(px.bar(val_un, orientation='h', labels={'index':'Unidade','value':'R$'}), use_container_width=True)

    st.subheader("🏆 Top 20 Viaturas por Consumo")
    top_cons = df_fil.groupby('PLACA')['TOTAL_LITROS'].sum().nlargest(20)
    st.plotly_chart(px.bar(top_cons, labels={'index':'PLACA','value':'Litros'}), use_container_width=True)

    st.subheader("🏆 Top 20 Viaturas por Valor")
    top_val  = df_fil.groupby('PLACA')['VALOR_TOTAL'].sum().nlargest(20)
    st.plotly_chart(px.bar(top_val, labels={'index':'PLACA','value':'R$'}), use_container_width=True)

    st.subheader("⛽ Distribuição de Combustível")
    pie = df_fil['COMBUSTÍVEL'].value_counts()
    st.plotly_chart(px.pie(names=pie.index, values=pie.values), use_container_width=True)

    st.subheader("📋 Detalhamento dos Abastecimentos")
    df_show = df_fil[['PLACA','UNIDADE','COMBUSTÍVEL','TOTAL_LITROS','VALOR_TOTAL','FROTA']].copy()
    df_show['VALOR_TOTAL'] = df_show['VALOR_TOTAL'].apply(formatar_reais)
    st.dataframe(df_show.reset_index(drop=True), use_container_width=True)

    if not df_mult.empty:
        st.warning("🚨 Viaturas em mais de uma OM")
        df_dup = df_mult[['PLACA','UNIDADE','COMBUSTÍVEL','TOTAL_LITROS','VALOR_TOTAL','FROTA']].copy()
        df_dup['VALOR_TOTAL'] = df_dup['VALOR_TOTAL'].apply(formatar_reais)
        st.dataframe(df_dup.reset_index(drop=True).sort_values(['PLACA','UNIDADE']), use_container_width=True)

if __name__ == "__main__":
    main()
