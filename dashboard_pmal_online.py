import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(
    page_title="Dashboard PMAL - Combustível",
    page_icon="🚒",
    layout="wide"
)

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
    return (
        float(str(row.get('Gasolina (R$)', '0')).replace('R$', '').replace(' ', '').replace(',', '.').replace('-', '0') or 0) +
        float(str(row.get('Álcool (R$)', '0')).replace('R$', '').replace(' ', '').replace(',', '.').replace('-', '0') or 0) +
        float(str(row.get('Diesel (R$)', '0')).replace('R$', '').replace(' ', '').replace(',', '.').replace('-', '0') or 0) +
        float(str(row.get('Diesel S10 (R$)', '0')).replace('R$', '').replace(' ', '').replace(',', '.').replace('-', '0') or 0)
    )

def carregar_dados():
    # Lista todos os arquivos da pasta atual
    arquivos = [f for f in os.listdir() if f.upper().endswith("ABR.XLSX") and not f.startswith("~$")]
    dados = []
    for arquivo in arquivos:
        df = pd.read_excel(arquivo, skiprows=4)
        df.rename(columns={df.columns[0]: 'PLACA'}, inplace=True)
        df = df[df['PLACA'].astype(str).str.upper().str.strip() != 'TOTAL']
        df['UNIDADE'] = arquivo.split(' ABR')[0].replace('º', '').strip()
        df['ARQUIVO'] = arquivo
        df['PLACA'] = df['PLACA'].apply(padroniza_placa)
        for col in ['Gasolina (Lts)', 'Álcool (Lts)', 'Diesel (Lts)', 'Diesel S10 (Lts)']:
            if col not in df.columns:
                df[col] = 0
        for col in ['Gasolina (R$)', 'Álcool (R$)', 'Diesel (R$)', 'Diesel S10 (R$)']:
            if col not in df.columns:
                df[col] = 0
        df['TOTAL_LITROS'] = df[['Gasolina (Lts)', 'Álcool (Lts)', 'Diesel (Lts)', 'Diesel S10 (Lts)']].sum(axis=1)
        df['VALOR_TOTAL'] = df.apply(valor_total, axis=1)
        df['COMBUSTÍVEL'] = df.apply(tipo_combustivel, axis=1)
        dados.append(df)
    df_abastecimento = pd.concat(dados, ignore_index=True)

    # Frota PRÓPRIOS
    df_proprios = pd.read_excel("PROPRIOS_JUSTIÇA.xlsx")
    df_proprios.rename(columns={df_proprios.columns[0]: 'PLACA'}, inplace=True)
    df_proprios['PLACA'] = df_proprios['PLACA'].apply(padroniza_placa)
    df_proprios['FROTA'] = 'PRÓPRIO'

    # Frota LOCADOS
    df_locados = pd.read_excel("LOCADOS.xlsx")
    df_locados.rename(columns={df_locados.columns[0]: 'PLACA'}, inplace=True)
    df_locados['PLACA'] = df_locados['PLACA'].apply(padroniza_placa)
    df_locados['FROTA'] = 'LOCADO'

    # Monta base única de frota
    df_frota = pd.concat([df_proprios, df_locados], ignore_index=True)
    frota_dict = dict(zip(df_frota['PLACA'], df_frota['FROTA']))
    df_abastecimento['FROTA'] = df_abastecimento['PLACA'].map(frota_dict)
    df_abastecimento['FROTA'] = df_abastecimento['FROTA'].fillna('NÃO ENCONTRADO')

    # Placas em mais de uma OM/arquivo
    placas_multiplas_om = df_abastecimento.groupby('PLACA')['UNIDADE'].nunique()
    placas_multiplas_om = placas_multiplas_om[placas_multiplas_om > 1].index.tolist()
    df_multiplas_om = df_abastecimento[df_abastecimento['PLACA'].isin(placas_multiplas_om)].sort_values('PLACA')

    return df_abastecimento, df_multiplas_om

def formatar_reais(valor):
    try:
        return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
    except:
        return valor

def main():
    st.title("🚒 Dashboard Final de Abastecimento - PMAL")
    st.caption("Todos os dados carregados automaticamente do repositório!")

    df, df_multiplas_om = carregar_dados()

    st.sidebar.header("🔍 Filtros Avançados")
    unidades = st.sidebar.multiselect("Unidade:", df['UNIDADE'].unique(), default=list(df['UNIDADE'].unique()))
    combustiveis = st.sidebar.multiselect("Tipo de Combustível:", df['COMBUSTÍVEL'].unique(), default=list(df['COMBUSTÍVEL'].unique()))
    frotas = st.sidebar.multiselect("Frota:", df['FROTA'].unique(), default=list(df['FROTA'].unique()))

    df_filtrado = df[
        df['UNIDADE'].isin(unidades) &
        df['COMBUSTÍVEL'].isin(combustiveis) &
        df['FROTA'].isin(frotas)
    ]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Registros", len(df_filtrado))
    col2.metric("Viaturas Únicas", df_filtrado['PLACA'].nunique())
    col3.metric("Total de Litros", f"{df_filtrado['TOTAL_LITROS'].sum():,.2f} L")
    col4.metric("Total Gasto (R$)", "R$ " + formatar_reais(df_filtrado['VALOR_TOTAL'].sum()))
    perc_nao_encontrado = (df_filtrado['FROTA'].value_counts(normalize=True).get('NÃO ENCONTRADO', 0)) * 100
    col5.metric("% Não Encontrados", f"{perc_nao_encontrado:.1f}%")

    st.subheader("📊 Consumo e Gasto por Unidade")
    colA, colB = st.columns(2)
    consumo_por_unidade = df_filtrado.groupby('UNIDADE')['TOTAL_LITROS'].sum().sort_values(ascending=True)
    colA.plotly_chart(
        px.bar(
            consumo_por_unidade, 
            orientation='h', 
            labels={'value': 'Litros', 'index': 'Unidade'}, 
            title='Litros por Unidade'
        ), 
        use_container_width=True
    )

    valor_por_unidade = df_filtrado.groupby('UNIDADE')['VALOR_TOTAL'].sum().sort_values(ascending=True)
    colB.plotly_chart(
        px.bar(
            valor_por_unidade, 
            orientation='h', 
            labels={'value': 'R$', 'index': 'Unidade'}, 
            title='Valor Gasto por Unidade'
        ), 
        use_container_width=True
    )

    st.subheader("🏆 Top 20 Viaturas por Consumo e por Valor Gasto")
    top_litros = df_filtrado.groupby('PLACA')['TOTAL_LITROS'].sum().sort_values(ascending=False).head(20)
    st.plotly_chart(
        px.bar(
            top_litros, 
            labels={'value': 'Litros', 'index': 'PLACA'}, 
            title='Top 20 Viaturas em Litros'
        ), 
        use_container_width=True
    )

    top_valor = df_filtrado.groupby('PLACA')['VALOR_TOTAL'].sum().sort_values(ascending=False).head(20)
    st.plotly_chart(
        px.bar(
            top_valor, 
            labels={'value': 'R$', 'index': 'PLACA'}, 
            title='Top 20 Viaturas em Valor'
        ), 
        use_container_width=True
    )

    st.subheader("⛽ Distribuição de Combustível")
    combustiveis_graf = df_filtrado['COMBUSTÍVEL'].value_counts()
    st.plotly_chart(
        px.pie(
            names=combustiveis_graf.index, 
            values=combustiveis_graf.values, 
            title="Proporção por Combustível"
        ), 
        use_container_width=True
    )

    st.subheader("📋 Detalhamento dos Abastecimentos")
    df_show = df_filtrado[['PLACA', 'UNIDADE', 'COMBUSTÍVEL', 'TOTAL_LITROS', 'VALOR_TOTAL', 'FROTA']].copy()
    df_show['VALOR_TOTAL'] = df_show['VALOR_TOTAL'].apply(formatar_reais)
    st.dataframe(df_show, use_container_width=True)

    if not df_multiplas_om.empty:
        st.warning("🚨 Viaturas abastecidas em mais de uma OM/planilha:")
        df_multiplas_om_show = df_multiplas_om[['PLACA', 'UNIDADE', 'COMBUSTÍVEL', 'TOTAL_LITROS', 'VALOR_TOTAL', 'FROTA']].copy()
        df_multiplas_om_show['VALOR_TOTAL'] = df_multiplas_om_show['VALOR_TOTAL'].apply(formatar_reais)
        st.dataframe(df_multiplas_om_show.sort_values(['PLACA', 'UNIDADE']), use_container_width=True)

if __name__ == "__main__":
    main()
