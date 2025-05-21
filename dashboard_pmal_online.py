import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import re

st.set_page_config(
    page_title="DASHBOARD DLOG - ABASTECIMENTO",
    page_icon="🚒",
    layout="wide"
)

# Configuração do seu repositório GitHub
GITHUB_USER = "DLOG2025"
GITHUB_REPO = "Dashboard-PMAL-Abastecimento"
GITHUB_PATH = ""  # Raiz do repositório

def get_abastecimento_files():
    lista_links = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_PATH}?page={page}&per_page=100"
        resp = requests.get(url)
        arquivos = resp.json()
        if not isinstance(arquivos, list) or not arquivos:
            break
        count = 0
        for arq in arquivos:
            if (
                isinstance(arq, dict)
                and arq['name'].endswith('.xlsx')
                and arq['name'].startswith('Relatório Combustível OPM')
            ):
                lista_links.append(arq['download_url'])
                count += 1
        if len(arquivos) < 100:
            break
        page += 1
    if not lista_links:
        st.error("Nenhum relatório de abastecimento foi encontrado no repositório!")
    return lista_links

def get_download_url(filename):
    return f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/raw/main/{filename}"

LINK_LOCADOS = get_download_url('LOCADOS.xlsx')
LINK_PROPRIOS = get_download_url('PROPRIOS_JUSTIÇA.xlsx')
LINK_CIDADES_OPM = get_download_url('CIDADES_POR_OPM.xlsx')

def baixar_excel(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return pd.read_excel(io.BytesIO(resp.content))

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

def limpar_nome_opm(nome):
    if pd.isna(nome):
        return ""
    return re.sub(r'[º°/]', '', str(nome)).strip().upper()

def carregar_dados():
    RELATORIOS_ABAST = get_abastecimento_files()
    dados = []
    for url in RELATORIOS_ABAST:
        df = baixar_excel(url)
        df.rename(columns={df.columns[0]: 'PLACA'}, inplace=True)
        df = df[df['PLACA'].astype(str).str.upper().str.strip() != 'TOTAL']
        nome_arquivo = url.split('/')[-1].replace('.xlsx','')
        unidade = nome_arquivo.replace('Relatório Combustível OPM - ', '').replace('º','').strip()
        df['UNIDADE'] = unidade
        df['ARQUIVO'] = nome_arquivo
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
    if not dados:
        st.error("Nenhum arquivo de abastecimento foi carregado! Verifique o repositório.")
        st.stop()
    df_abastecimento = pd.concat(dados, ignore_index=True)

    df_proprios = baixar_excel(LINK_PROPRIOS)
    df_proprios.rename(columns={df_proprios.columns[0]: 'PLACA'}, inplace=True)
    df_proprios['PLACA'] = df_proprios['PLACA'].apply(padroniza_placa)
    df_proprios['FROTA'] = 'PRÓPRIO'

    df_locados = baixar_excel(LINK_LOCADOS)
    df_locados.rename(columns={df_locados.columns[0]: 'PLACA'}, inplace=True)
    df_locados['PLACA'] = df_locados['PLACA'].apply(padroniza_placa)
    df_locados['FROTA'] = 'LOCADO'

    df_frota = pd.concat([df_proprios, df_locados], ignore_index=True)
    frota_dict = dict(zip(df_frota['PLACA'], df_frota['FROTA']))
    df_abastecimento['FROTA'] = df_abastecimento['PLACA'].map(frota_dict)
    df_abastecimento['FROTA'] = df_abastecimento['FROTA'].fillna('NÃO ENCONTRADO')

    placas_multiplas_om = df_abastecimento.groupby('PLACA')['UNIDADE'].nunique()
    placas_multiplas_om = placas_multiplas_om[placas_multiplas_om > 1].index.tolist()
    df_multiplas_om = df_abastecimento[df_abastecimento['PLACA'].isin(placas_multiplas_om)].sort_values('PLACA')

    df_cidades_opm = baixar_excel(LINK_CIDADES_OPM)
    df_cidades_opm.columns = [col.strip().upper() for col in df_cidades_opm.columns]
    df_cidades_opm['OPM_LIMPA'] = df_cidades_opm['OPM'].apply(limpar_nome_opm)
    return df_abastecimento, df_multiplas_om, df_cidades_opm

def formatar_reais(valor):
    try:
        return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
    except:
        return valor

def main():
    st.title("🚒 DASHBOARD DLOG - ABASTECIMENTO")
    st.caption("100% ONLINE - Dados oficiais já carregados do GitHub")

    with st.spinner("Carregando dados diretamente do GitHub..."):
        df, df_multiplas_om, df_cidades_opm = carregar_dados()
    st.success("Dados carregados automaticamente!")

    st.sidebar.header("🔍 Filtros Avançados")
    unidades = st.sidebar.multiselect("Unidade:", df['UNIDADE'].unique(), default=list(df['UNIDADE'].unique()))
    combustiveis = st.sidebar.multiselect("Tipo de Combustível:", df['COMBUSTÍVEL'].unique(), default=list(df['COMBUSTÍVEL'].unique()))
    frotas = st.sidebar.multiselect("Frota:", df['FROTA'].unique(), default=list(df['FROTA'].unique()))

    df_filtrado = df[
        df['UNIDADE'].isin(unidades) &
        df['COMBUSTÍVEL'].isin(combustiveis) &
        df['FROTA'].isin(frotas)
    ]

    if df_cidades_opm is not None:
        st.subheader("🚗 Distribuição de Viaturas por OPM (Interior)")
        df['UNIDADE_LIMPA'] = df['UNIDADE'].apply(limpar_nome_opm)
        opms_interior = df_cidades_opm['OPM_LIMPA'].unique()
        df_interior = df[df['UNIDADE_LIMPA'].isin(opms_interior)]
        viaturas_por_opm = df_interior.groupby('UNIDADE_LIMPA')['PLACA'].nunique().reset_index(name='VIATURAS')
        resumo_opm = df_cidades_opm.merge(viaturas_por_opm, left_on='OPM_LIMPA', right_on='UNIDADE_LIMPA', how='left')
        resumo_opm['VIATURAS'] = resumo_opm['VIATURAS'].fillna(0).astype(int)
        resumo_opm['VIAT_POR_CIDADE'] = (resumo_opm['VIATURAS'] / resumo_opm['QTD_CIDADES']).round(2)
        resumo_opm = resumo_opm.sort_values('VIAT_POR_CIDADE')
        colX, colY = st.columns([2, 1])
        colX.plotly_chart(
            px.bar(
                resumo_opm, 
                x='OPM', y='VIAT_POR_CIDADE',
                title='Ranking de Viaturas por Cidade Atendida (Interior)',
                labels={'VIAT_POR_CIDADE': 'Viaturas/Cidade', 'OPM': 'OPM do Interior'},
                text='VIAT_POR_CIDADE'
            ).update_traces(texttemplate='%{text:.2f}', textposition='outside'),
            use_container_width=True
        )
        colY.dataframe(
            resumo_opm[['OPM', 'QTD_CIDADES', 'VIATURAS', 'VIAT_POR_CIDADE']],
            use_container_width=True
        )
        st.info("🔎 **Menor valor de Viaturas por Cidade indica OPM potencialmente mais desfavorecida**.")

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
        st.warning("🚨 Viaturas abastecidas em mais de uma OPM/planilha:")
        df_multiplas_om_show = df_multiplas_om[['PLACA', 'UNIDADE', 'COMBUSTÍVEL', 'TOTAL_LITROS', 'VALOR_TOTAL', 'FROTA']].copy()
        df_multiplas_om_show['VALOR_TOTAL'] = df_multiplas_om_show['VALOR_TOTAL'].apply(formatar_reais)
        st.dataframe(df_multiplas_om_show.sort_values(['PLACA', 'UNIDADE']), use_container_width=True)

if __name__ == "__main__":
    main()
