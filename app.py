import streamlit as st
import pandas as pd

# --------------------------------------------------
# Configuração da página
# --------------------------------------------------
st.set_page_config(
    page_title="Players Dashboard", # O título que mostra na tab do browser
    layout="wide" # A opção "centered" coloca a página numa coluna central
)

st.title("📊 Players Dashboard")
st.markdown("Dashboard de Jogadores")

# --------------------------------------------------
# Carregamento dos dados
# --------------------------------------------------
# Esta linha é extremamente importante. 
# Ao ler o ficheiro a primeira vez, a app guarda os dados em memória (cache)
# Assim, sempre que houver interações com o dashboard (ex: mudar um filtro), não é necessário ler o ficheiro csv novamente
@st.cache_data 
def load_data():
    file_name = "players_data-2025_2026.csv"
    df = pd.read_csv(["players_data-2025_2026.csv"])
    return df


# --------------------------------------------------
# Definir um Sidebar com filtros
# --------------------------------------------------
st.sidebar.header("Filtros")

# Filtro de Nações
sorted_nations = sorted(df["Nation"].unique())
nations = st.sidebar.multiselect(
    "Nation",
    options=sorted_nations,
    default=sorted_nations
)

# Filtro de Posições
sorted_positions = sorted(df["Pos"].unique())
positions = st.sidebar.multiselect(
    "Pos",
    options=sorted_positions,
    default=sorted_positions
)

# Filtro de Idade
Ages = sorted(df["Age"].dt.year.unique())
Age_range = st.sidebar.slider(
    "Age",
    min_value=int(min(Ages)),
    max_value=int(max(Ages)),
    value=(int(min(Ages)), int(max(Ages)))
)

# Aplicar filtros
filtered_df = df[
    (df["Nation"].isin(nations)) &
    (df["Pos"].isin(positions)) &
    (df["Age"].dt.year.between(Age_range[0], Age_range[1]))
]

# --------------------------------------------------
# Parte superior com KPIs
# --------------------------------------------------
total_golos = filtered_df["Gls"].sum()
total_Assistências = filtered_df["Ast"].sum()
num_minutos = filtered_df["Min"].nunique()

# Vamos dividir a área em 3 colunas para mostrar os KPIs lado a lado
col1, col2, col3 = st.columns(3)
col1.metric("⚽ Golos Totais", f"{total_golos:,.0f}")
col2.metric("📈 Assistências Totais", f"{total_Assistências:,.0f}")
col3.metric("⏱️ Nº de Minutos", f"{num_minutos:,.0f}")

st.divider()

# ------------------------------------------------------------------
# Gráfico 1 - Golos por idade (cada categoria é uma série)
# ------------------------------------------------------------------
st.subheader("📅 Golos por idade")

# Agrupar a soma de Sales em cada mês por Category
golos_por_idade = (
    filtered_df
    .groupby(
        [pd.Grouper(key="Age", freq="YE"), "Category"]
    )["Gls"]
    .sum()
    .reset_index()
)

# Criar uma pivot table
golos_pivot = golos_por_idade.pivot(
    index="Age",
    columns="Category",
    values="Gls"
)

st.line_chart(golos_pivot)

# --------------------------------------------------
# Gráfico 2 - Golos por Região
# --------------------------------------------------
st.subheader("🌍 Golos por Região")

# Agrupar a soma de Golos por Region
golos_by_region = (
    filtered_df
    .groupby("Region")["Gls"]
    .sum()
)

st.bar_chart(golos_by_region)

st.divider()

# --------------------------------------------------
# Table - Top jogadores
# --------------------------------------------------
st.subheader("🏆 Top 10 jogadores por Golos")

# Agrupar a soma de Golos por Player Name, ordenar e mostrar os top 10
top_players = (
    filtered_df
    .groupby("Player Name")["Gls"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

st.dataframe(top_players)

# --------------------------------------------------
# Rodapé
# --------------------------------------------------
st.caption("Dados: Keegle")
