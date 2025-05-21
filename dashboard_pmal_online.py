import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import zipfile
import tempfile
import os
import re
import requests

st.set_page_config(
    page_title="DASHBOARD DLOG - ABASTECIMENTO",
    page_icon="🚒",
    layout="wide"
)

# LINK CORRETO DO ZIP HOSPEDADO NO GITHUB
URL_ZIP = 'https://github.com/DLOG2025/Dashboard-PMAL-Abastecimento/raw/main/Dashboard-PMAL-Abastecimento-main.zip'

def baixar_e_extrair_zip(url_zip):
    # Faz download do zip para um arquivo temporário
    resp = requests.get(url_zip)
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_zip.write(resp.content)
    temp_zip.close()

    # Extrai o conteúdo do zip para uma pasta temporária
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(temp_zip.name, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    return temp_dir

def encontrar_arquivo_por_nome(pasta, trecho_nome):
    for raiz, dirs, arquivos in os.walk(pasta):
        for arq in arquivos:
            if trecho_nome.lower() in arq.lower() and arq.lower().endswith('.xlsx'):
                return os.path.join(raiz, arq)
    return None

def encontrar_todos_arquivos_por_trecho(pasta, trecho_nome):
    lista = []
    for raiz, dirs, arquivos in os.walk(pasta):
        for arq in arquivos:
            if trecho_nome.lower() in arq.lower() and arq.lower().endswith('.xlsx'):
                lista.append(os.path.join(raiz, arq))
    return lista

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

def carregar_dados(pasta):
    # Encontra todos os arquivos de abastecimento na pasta (padrão: 'ABASTEC' no nome)
    abast_files = encontrar_todos_arquivos_por_trecho(pasta, 'ABASTEC')
    dados = []
    for arquivo in abast_files:
        df = pd.read_excel(arquivo, skiprows=4)
        df.rename(columns={df.columns[0]: 'PLACA'}, inplace=True)
        df = df[df['PLACA'].astype(str).str.upper().str.strip() != 'TOTAL']
        df['UNIDADE'] = os.path.basename(arquivo).split(' ABR')[0].replace('º', '').strip()
        df['ARQUIVO'] = os.path.basename(arquivo)
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

    # Carregar e tratar arquivos de frota
    arquivo_proprios = encontrar_arquivo_por_nome(pasta, 'PROPRIOS')
    arquivo_locados = encontrar_arquivo_por_nome(pasta, 'LOCADOS')

    df_proprios, df_locados = None, None
    if arquivo_proprios:
        df_proprios = pd.read_excel(arquivo_proprios)
        df_proprios.rename(columns={df_proprios.columns[0]: 'PLACA'}, inplace=True)
        df_proprios['PLACA'] = df_proprios['PLACA'].apply(padroniza_placa)
        df_proprios['FROTA'] = 'PRÓPRIO'
    if arquivo_locados:
        df_locados = pd.read_excel(arquivo_locados)
        df_locados.rename(columns={df_locados.columns[0]: 'PLACA'}, inplace=True)
        df_locados['PLACA'] = df_locados['PLACA'].apply(padroniza_placa)
        df_locados['FROTA'] = 'LOCADO'

    if df_proprios is not None and df_locados is not None:
        df_frota = pd.concat([df_proprios, df_locados], ignore_index=True)
    elif df_proprios is not None:
        df_frota = df_proprios.copy()
    elif df_locados is not None:
        df_frota = df_locados.copy()
    else:
        df_frota = pd.DataFrame(columns=['PLACA', 'FROTA'])

    frota_dict = dict(zip(df_frota['PLACA'], df_frota['FROTA']))
    df_abastecimento['FROTA'] = df_abastecimento['PLACA'].map(frota_dict)
    df_abastecimento['FROTA'] = df_abastecimento['FROTA'].fillna('NÃO ENCONTRADO')

    # Placas em mais de uma OM/arquivo
    placas_multiplas_om = df_abastecimento.groupby('PLACA')['UNIDADE'].nunique()
    placas_multiplas_om = placas_multiplas_om[placas_multiplas_om > 1].index.tolist()
    df_multiplas_om = df_abastecimento[df_abastecimento['PLACA'].isin(placas_multiplas_om)].sort_values('PLACA')

    # Arquivo cidades por OPM (interior)
    arquivo_cidades = encontrar_arquivo_por_nome(pasta, 'CIDADES_POR_OPM')
    if arquivo_cidades:
        df_cidades_opm = pd.read_excel(arquivo_cidades)
        df_cidades_opm.columns = [col.strip().upper() for col in df_cidades_opm.columns]
        if not 'OPM' in df_cidades_opm.columns or not 'QTD_CIDADES' in df_cidades_opm.columns:
            df_cidades_opm = None
        else:
            df_cidades_opm['OPM_LIMPA'] = df_cidades_opm['OPM'].apply(lambda nome: re.sub(r'[º°/]', '', str(nome)).strip().upper())
    else:
        df_cidades_opm = None

    return df_abastecimento, df_multiplas_om, df_cidades_opm

def formatar_reais(valor):
    try:
        return f"{valor:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.')
    except:
        return valor

def limpar_nome_opm(nome):
    if pd.isna(nome):
        return ""
    return re.sub(r'[º°/]', '', str(nome)).strip().upper()

def main():
    st.title("🚒 DASHBOARD DLOG - ABASTECIMENTO")
    st.caption("100% ONLINE - Dados oficiais já carregados")

    with st.spinner("Carregando dados oficiais, aguarde..."):
        temp_dir = baixar_e_extrair_zip(URL_ZIP)
        df, df_multiplas_om, df_cidades_opm = carregar_dados(temp_dir)

    st.success("Dados carregados automaticamente!")

    # Filtros avançados
    st.sidebar.header("🔍 Filtros Avançados")
    unidades = st.sidebar.multiselect("Unidade:", df['UNIDADE'].unique(), default=list(df['UNIDADE'].unique()))
    combustiveis = st.sidebar.multiselect("Tipo de Combustível:", df['COMBUSTÍVEL'].unique(), default=list(df['COMBUSTÍVEL'].unique()))
    frotas = st.sidebar.multiselect("Frota:", df['FROTA'].unique(), default=list(df['FROTA'].unique()))

    df_filtrado = df[
        df['UNIDADE'].isin(unidades) &
        df['COMBUSTÍVEL'].isin(combustiveis) &
        df['FROTA'].isin(frotas)
    ]

    # Painel de Equidade por Cidades/OPM (Interior)
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

    # Métricas principais
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Registros", len(df_filtrado))
    col2.metric("Viaturas Únicas", df_filtrado['PLACA'].nunique())
    col3.metric("Total de Litros", f"{df_filtrado['TOTAL_LITROS'].sum():,.2f} L")
    col4.metric("Total Gasto (R$)", "R$ " + formatar_reais(df_filtrado['VALOR_TOTAL'].sum()))
    perc_nao_encontrado = (df_filtrado['FROTA'].value_counts(normalize=True).get('NÃO ENCONTRADO', 0)) * 100
    col5.metric("% Não Encontrados", f"{perc_nao_encontrado:.1f}%")

    # Gráficos
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
