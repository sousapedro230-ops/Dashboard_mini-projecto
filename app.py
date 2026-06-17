import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


CSV_PATH = "df_final.csv"


PLAYER = "Player"
NATION = "Nation"
AGE = "Age"
LEAGUE = "league_name"
MINUTES = "Min"
MIN90 = "Min/90"
MARKET_VALUE = "Valor_de_Mercado"
PERFORMANCE = "Performance_Score"
UNDERVALUED = "sub_valorizacao"
CLUSTER = "Cluster"
PCA_1 = "pca_1"
PCA_2 = "pca_2"

RADAR_METRICS = ["Gls/90", "Ast/90", "Sh/90", "Fls/90", "TklW/90"]


CANONICAL_COLUMNS = {
    "player": PLAYER,
    "jogador": PLAYER,
    "nation": NATION,
    "nacionalidade": NATION,
    "age": AGE,
    "idade": AGE,
    "league_name": LEAGUE,
    "league": LEAGUE,
    "liga": LEAGUE,
    "comp": LEAGUE,
    "min": MINUTES,
    "minutes": MINUTES,
    "min_90": MIN90,
    "valor_de_mercado": MARKET_VALUE,
    "market_value": MARKET_VALUE,
    "performance_score": PERFORMANCE,
    "sub_valorizacao": UNDERVALUED,
    "subvalorizacao": UNDERVALUED,
    "undervalued_score": UNDERVALUED,
    "cluster": CLUSTER,
    "pca_1": PCA_1,
    "pca_2": PCA_2,
    "gls_90": "Gls/90",
    "ast_90": "Ast/90",
    "sh_90": "Sh/90",
    "fls_90": "Fls/90",
    "tklw_90": "TklW/90",
}


st.set_page_config(
    page_title="Dashboard - Jogadores Subvalorizados",
    page_icon="⚽",
    layout="wide",
    
)


def slugify(value: str) -> str:
    text = str(value).strip()
    try:
        text = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text


def normalize_columns(data: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in data.columns:
        canonical = CANONICAL_COLUMNS.get(slugify(column))
        if canonical:
            rename_map[column] = canonical

    data = data.rename(columns=rename_map)
    return data.loc[:, ~data.columns.duplicated(keep="last")]


@st.cache_data(show_spinner=False)
def load_data_from_path(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def load_uploaded_data(uploaded_file) -> pd.DataFrame:
    return pd.read_csv(uploaded_file)


def prepare_data(data: pd.DataFrame) -> pd.DataFrame:
    data = normalize_columns(data.copy())

    numeric_columns = [
        AGE,
        MINUTES,
        MIN90,
        MARKET_VALUE,
        PERFORMANCE,
        UNDERVALUED,
        CLUSTER,
        PCA_1,
        PCA_2,
        *RADAR_METRICS,
    ]

    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    if CLUSTER in data.columns:
        data[CLUSTER] = data[CLUSTER].astype("Int64")

    return data


def required_columns_missing(data: pd.DataFrame) -> list[str]:
    required = [PLAYER, NATION, LEAGUE, MARKET_VALUE, PERFORMANCE, UNDERVALUED, CLUSTER]
    return [column for column in required if column not in data.columns]


def format_eur(value: float) -> str:
    if pd.isna(value):
        return "-"
    if abs(value) >= 1_000_000:
        return f"€{value / 1_000_000:,.1f}M"
    return f"€{value / 1_000:,.0f}K"


def format_number(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{value:,.2f}"


def filter_data(data: pd.DataFrame) -> pd.DataFrame:
    sidebar = st.sidebar
    sidebar.header("Filtros")

    remove_negative = sidebar.toggle("Remover subvalorização negativa", value=True)

    if remove_negative:
        data = data[data[UNDERVALUED] >= 0].copy()

    if MARKET_VALUE in data.columns and data[MARKET_VALUE].notna().any():
        max_available = float(data[MARKET_VALUE].max())
        default_market = min(max_available, 50_000_000.0)
        max_market = sidebar.slider(
            "Valor de mercado máximo (€M)",
            min_value=0.0,
            max_value=max(1.0, round(max_available / 1_000_000, 1)),
            value=round(default_market / 1_000_000, 1),
            step=0.5,
        )
        data = data[data[MARKET_VALUE] <= max_market * 1_000_000].copy()

    if AGE in data.columns and data[AGE].notna().any():
        min_age = int(np.floor(data[AGE].min()))
        max_age_available = int(np.ceil(data[AGE].max()))
        max_age = sidebar.slider(
            "Idade máxima",
            min_value=min_age,
            max_value=max_age_available,
            value=min(26, max_age_available),
        )
        data = data[data[AGE] <= max_age].copy()

    if MINUTES in data.columns and data[MINUTES].notna().any():
        min_minutes = sidebar.slider(
            "Minutos totais mínimos",
            min_value=0,
            max_value=int(np.ceil(data[MINUTES].max())),
            value=0,
            step=50,
        )
        data = data[data[MINUTES] >= min_minutes].copy()

    leagues = sorted(data[LEAGUE].dropna().astype(str).unique())
    selected_leagues = sidebar.multiselect("Liga", options=leagues)
    if selected_leagues:
        data = data[data[LEAGUE].astype(str).isin(selected_leagues)].copy()

    nations = sorted(data[NATION].dropna().astype(str).unique())
    selected_nations = sidebar.multiselect("Nacionalidade", options=nations)
    if selected_nations:
        data = data[data[NATION].astype(str).isin(selected_nations)].copy()

    clusters = sorted(data[CLUSTER].dropna().astype(int).unique())
    selected_clusters = sidebar.multiselect("Cluster", options=clusters)
    if selected_clusters:
        data = data[data[CLUSTER].astype("Int64").isin(selected_clusters)].copy()

    sidebar.divider()
    top_n = sidebar.slider("Top N por cluster", min_value=5, max_value=20, value=10)

    return data, top_n


def get_top_by_cluster(data: pd.DataFrame, top_n: int) -> pd.DataFrame:
    return (
        data.dropna(subset=[CLUSTER, UNDERVALUED, MARKET_VALUE, PERFORMANCE])
        .sort_values(UNDERVALUED, ascending=False)
        .groupby(CLUSTER, group_keys=False)
        .head(top_n)
        .copy()
    )


def opportunity_scatter(data: pd.DataFrame) -> go.Figure:
    plot_data = data.dropna(subset=[MARKET_VALUE, PERFORMANCE, UNDERVALUED, CLUSTER]).copy()
    plot_data["Valor de mercado"] = plot_data[MARKET_VALUE].clip(lower=1)

    fig = px.scatter(
        plot_data,
        x="Valor de mercado",
        y=PERFORMANCE,
        color=CLUSTER,
        size=UNDERVALUED,
        hover_name=PLAYER,
        hover_data={
            NATION: True,
            LEAGUE: True,
            AGE: ":.0f" if AGE in plot_data else False,
            MARKET_VALUE: ":,.0f",
            UNDERVALUED: ":,.2f",
            PERFORMANCE: ":.3f",
            "Valor de mercado": False,
        },
        log_x=True,
        template="plotly_white",
        title="Mapa de oportunidade: Performance Score vs Valor de Mercado",
        labels={
            "Valor de mercado": "Valor de mercado (€)",
            PERFORMANCE: "Performance Score",
            CLUSTER: "Cluster",
            UNDERVALUED: "Subvalorização",
        },
    )

    if not plot_data.empty:
        fig.add_hline(
            y=plot_data[PERFORMANCE].median(),
            line_dash="dash",
            line_color="#6B7280",
            annotation_text="Mediana performance",
        )
        fig.add_vline(
            x=plot_data[MARKET_VALUE].median(),
            line_dash="dash",
            line_color="#6B7280",
            annotation_text="Mediana valor",
        )

    fig.update_traces(marker=dict(opacity=0.72, line=dict(width=0.6, color="white")))
    fig.update_layout(height=560, legend_title_text="Cluster")
    return fig


def top_players_bar(top_data: pd.DataFrame) -> go.Figure:
    plot_data = top_data.copy()
    plot_data["label"] = "C" + plot_data[CLUSTER].astype(str) + " | " + plot_data[PLAYER].astype(str)
    plot_data["market_m"] = plot_data[MARKET_VALUE] / 1_000_000
    plot_data = plot_data.sort_values([CLUSTER, UNDERVALUED], ascending=[True, True])

    fig = px.bar(
        plot_data,
        x=UNDERVALUED,
        y="label",
        color=CLUSTER,
        orientation="h",
        text=plot_data["market_m"].map(lambda value: f"{value:.1f}M€"),
        hover_data={
            PLAYER: True,
            NATION: True,
            LEAGUE: True,
            AGE: ":.0f" if AGE in plot_data else False,
            MARKET_VALUE: ":,.0f",
            PERFORMANCE: ":.3f",
            UNDERVALUED: ":,.2f",
            "label": False,
            "market_m": False,
        },
        template="plotly_white",
        title="Top jogadores subvalorizados por cluster",
        labels={
            UNDERVALUED: "Subvalorização",
            "label": "Jogador",
            CLUSTER: "Cluster",
        },
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=max(520, len(plot_data) * 24), yaxis_title="")
    return fig


def cluster_summary_chart(data: pd.DataFrame) -> go.Figure:
    summary = (
        data.groupby(CLUSTER, dropna=True)
        .agg(
            jogadores=(PLAYER, "count"),
            sub_media=(UNDERVALUED, "mean"),
            valor_medio=(MARKET_VALUE, "mean"),
            performance_media=(PERFORMANCE, "mean"),
        )
        .reset_index()
    )
    summary["valor_medio_m"] = summary["valor_medio"] / 1_000_000

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=summary[CLUSTER].astype(str),
            y=summary["sub_media"],
            name="Subvalorização média",
            marker_color="#2563EB",
            text=summary["sub_media"].map(lambda value: f"{value:,.0f}"),
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=summary[CLUSTER].astype(str),
            y=summary["valor_medio_m"],
            name="Valor médio (€M)",
            mode="lines+markers+text",
            yaxis="y2",
            marker_color="#F97316",
            text=summary["jogadores"].map(lambda value: f"n={value}"),
            textposition="top center",
        )
    )

    fig.update_layout(
        title="Resumo executivo por cluster",
        xaxis_title="Cluster",
        yaxis_title="Subvalorização média",
        yaxis2=dict(title="Valor médio (€M)", overlaying="y", side="right"),
        template="plotly_white",
        height=470,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def pca_scatter(data: pd.DataFrame) -> go.Figure:
    plot_data = data.dropna(subset=[PCA_1, PCA_2, CLUSTER]).copy()
    fig = px.scatter(
        plot_data,
        x=PCA_1,
        y=PCA_2,
        color=CLUSTER,
        size=UNDERVALUED,
        hover_name=PLAYER,
        hover_data={
            NATION: True,
            LEAGUE: True,
            MARKET_VALUE: ":,.0f",
            PERFORMANCE: ":.3f",
            UNDERVALUED: ":,.2f",
        },
        template="plotly_white",
        title="Separação dos clusters no espaço PCA",
        labels={PCA_1: "PCA 1", PCA_2: "PCA 2", CLUSTER: "Cluster"},
    )
    fig.update_traces(marker=dict(opacity=0.75, line=dict(width=0.5, color="white")))
    fig.update_layout(height=560)
    return fig


def normalize_for_radar(data: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    normalized = data[metrics].copy()
    for metric in metrics:
        minimum = normalized[metric].min()
        maximum = normalized[metric].max()
        if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
            normalized[metric] = 50
        else:
            normalized[metric] = ((normalized[metric] - minimum) / (maximum - minimum)) * 100
    return normalized


def radar_chart(data: pd.DataFrame, cluster, top_n: int) -> go.Figure:
    available_metrics = [metric for metric in RADAR_METRICS if metric in data.columns]
    cluster_data = (
        data[data[CLUSTER] == cluster]
        .dropna(subset=[UNDERVALUED, *available_metrics])
        .sort_values(UNDERVALUED, ascending=False)
        .head(top_n)
        .copy()
    )

    normalized = normalize_for_radar(cluster_data, available_metrics)
    theta = available_metrics + [available_metrics[0]]

    fig = go.Figure()
    for row_index, row in cluster_data.reset_index(drop=True).iterrows():
        values = normalized.iloc[row_index][available_metrics].tolist()
        real_values = row[available_metrics].tolist()

        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=theta,
                fill="toself",
                name=row[PLAYER],
                opacity=0.45,
                customdata=real_values + [real_values[0]],
                hovertemplate=(
                    f"<b>{row[PLAYER]}</b><br>"
                    "Métrica: %{theta}<br>"
                    "Valor real: %{customdata:.2f}<br>"
                    "Valor normalizado: %{r:.1f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=f"Radar operacional - Top {top_n} do Cluster {cluster}",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        template="plotly_white",
        height=650,
        showlegend=True,
    )
    return fig


def league_summary(data: pd.DataFrame) -> go.Figure:
    summary = (
        data.groupby(LEAGUE)
        .agg(
            jogadores=(PLAYER, "count"),
            sub_media=(UNDERVALUED, "mean"),
            valor_mediano=(MARKET_VALUE, "median"),
        )
        .query("jogadores >= 2")
        .sort_values("sub_media", ascending=False)
        .head(12)
        .reset_index()
    )

    summary["valor_mediano_m"] = summary["valor_mediano"] / 1_000_000

    fig = px.bar(
        summary.sort_values("sub_media", ascending=True),
        x="sub_media",
        y=LEAGUE,
        orientation="h",
        color="valor_mediano_m",
        text="jogadores",
        color_continuous_scale="Blues",
        template="plotly_white",
        title="Ligas com maior média de oportunidades",
        labels={
            "sub_media": "Subvalorização média",
            LEAGUE: "Liga",
            "valor_mediano_m": "Valor mediano (€M)",
            "jogadores": "Jogadores",
        },
    )
    fig.update_traces(texttemplate="n=%{text}", textposition="outside")
    fig.update_layout(height=500)
    return fig


def show_kpis(data: pd.DataFrame) -> None:
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Jogadores filtrados", f"{len(data):,}")
    col2.metric("Clusters ativos", f"{data[CLUSTER].nunique():,}")
    col3.metric("Valor médio", format_eur(data[MARKET_VALUE].mean()))
    col4.metric("Performance média", format_number(data[PERFORMANCE].mean()))
    col5.metric("Melhor subvalorização", format_number(data[UNDERVALUED].max()))


def show_candidate_table(data: pd.DataFrame) -> None:
    columns = [
        PLAYER,
        NATION,
        LEAGUE,
        AGE,
        CLUSTER,
        MARKET_VALUE,
        PERFORMANCE,
        UNDERVALUED,
        *[metric for metric in RADAR_METRICS if metric in data.columns],
    ]
    table = data[columns].sort_values(UNDERVALUED, ascending=False).copy()
    table[MARKET_VALUE] = table[MARKET_VALUE].map(format_eur)
    table[PERFORMANCE] = table[PERFORMANCE].map(lambda value: f"{value:.3f}" if pd.notna(value) else "-")
    table[UNDERVALUED] = table[UNDERVALUED].map(lambda value: f"{value:,.2f}" if pd.notna(value) else "-")
    st.dataframe(table, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("Dashboard de Jogadores Subvalorizados")
    st.caption(
        "Análise orientada à decisão: encontrar jogadores com bom Performance Score, "
        "baixo valor de mercado e oportunidade clara dentro do respetivo cluster."
    )

uploaded_file = st.sidebar.file_uploader(
    "CSV alternativo",
    type=["csv"]
)

try:
    if uploaded_file is not None:
        raw_data = load_uploaded_data(uploaded_file)
    else:
        raw_data = load_data_from_path(CSV_PATH)

except FileNotFoundError:
    st.error(f"Não encontrei o CSV: {CSV_PATH}")
    st.stop()

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

data = prepare_data(raw_data)
missing = required_columns_missing(data)
if missing:
        st.error("Faltam colunas necessárias no CSV: " + ", ".join(missing))
        st.write("Colunas encontradas:", list(data.columns))
        st.stop()

filtered_data, top_n = filter_data(data)

if filtered_data.empty:
        st.warning("Não existem jogadores depois de aplicar estes filtros.")
        st.stop()

show_kpis(filtered_data)

executive_tab, operational_tab, decision_tab = st.tabs(
        ["Visão executiva", "Análise operacional", "Lista de decisão"]
    )

top_by_cluster = get_top_by_cluster(filtered_data, top_n)

with executive_tab:
        left, right = st.columns([1.4, 1])
        with left:
            st.plotly_chart(opportunity_scatter(filtered_data), use_container_width=True)
        with right:
            st.plotly_chart(cluster_summary_chart(filtered_data), use_container_width=True)

        st.plotly_chart(top_players_bar(top_by_cluster), use_container_width=True)

        if filtered_data[LEAGUE].nunique() > 1:
            st.plotly_chart(league_summary(filtered_data), use_container_width=True)

with operational_tab:
        pca_available = {PCA_1, PCA_2}.issubset(filtered_data.columns)
        if pca_available and filtered_data[[PCA_1, PCA_2]].notna().any().all():
            st.plotly_chart(pca_scatter(filtered_data), use_container_width=True)

        available_metrics = [metric for metric in RADAR_METRICS if metric in filtered_data.columns]
        if available_metrics:
            cluster_options = sorted(filtered_data[CLUSTER].dropna().astype(int).unique())
            selected_cluster = st.selectbox("Cluster para radar operacional", options=cluster_options)
            st.plotly_chart(radar_chart(filtered_data, selected_cluster, top_n), use_container_width=True)
        else:
            st.info("Não encontrei métricas operacionais suficientes para o radar.")

with decision_tab:
        st.subheader("Ranking de jogadores para análise")
        st.caption(
            "Ordenado por subvalorização. Usa esta lista para shortlists, scouting e validação manual."
        )
        show_candidate_table(filtered_data)


if __name__ == "__main__":
    main()

