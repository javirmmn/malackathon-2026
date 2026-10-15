"""Plantilla de dashboard. Copiar a kits/<kit>/app.py y adaptar el día del reto.

    streamlit run common/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # para `import common` con streamlit run

import pandas as pd
import plotly.express as px
import streamlit as st

import common.charts  # noqa: F401  (activa la plantilla de gráficos)
from common import DATA_DIR
from common.dataio import normalize_columns, quick_profile, read_any

st.set_page_config(page_title="Malackathon 2026", page_icon="📊", layout="wide")


@st.cache_data
def load_file(path_or_buffer, name: str):
    if hasattr(path_or_buffer, "read"):  # fichero subido
        tmp = DATA_DIR / f"_upload_{name}"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(path_or_buffer.getvalue())
        path_or_buffer = tmp
    return normalize_columns(read_any(path_or_buffer))


# ---------------- Barra lateral: origen de datos ----------------
st.sidebar.title("Datos")
source = st.sidebar.radio("Origen", ["Fichero de data/", "Subir fichero"])

df = None
if source == "Fichero de data/":
    files = sorted(
        p for p in DATA_DIR.glob("*")
        if p.suffix.lower() in {".csv", ".xlsx", ".xls", ".json", ".parquet"}
        and not p.name.startswith("_upload_")
    )
    if files:
        choice = st.sidebar.selectbox("Fichero", files, format_func=lambda p: p.name)
        df = load_file(choice, choice.name)
    else:
        st.sidebar.info("No hay ficheros en data/.")
else:
    up = st.sidebar.file_uploader("CSV / Excel / JSON / Parquet")
    if up:
        df = load_file(up, up.name)

# ---------------- Contenido ----------------
st.title("Malackathon 2026 · Dashboard")

if df is None:
    st.info("Elige un origen de datos en la barra lateral.")
    st.stop()

# Filtros por columnas categóricas (pocas categorías y que se repitan, no identificadores)
cat_cols = [
    c for c in df.columns
    if not pd.api.types.is_numeric_dtype(df[c])
    and not pd.api.types.is_datetime64_any_dtype(df[c])
    and 1 < df[c].nunique() <= min(30, len(df) - 1)
]
filtered = df
with st.sidebar.expander("Filtros", expanded=bool(cat_cols)):
    for col in cat_cols[:5]:
        values = sorted(df[col].dropna().unique().tolist())
        sel = st.multiselect(col, values, default=values)
        filtered = filtered[filtered[col].isin(sel)]

num_cols = filtered.select_dtypes("number").columns.tolist()

k1, k2, k3 = st.columns(3)
k1.metric("Filas", f"{len(filtered):,}".replace(",", "."))
k2.metric("Columnas", len(filtered.columns))
k3.metric("Numéricas", len(num_cols))

tab_datos, tab_graf, tab_perfil = st.tabs(["Datos", "Gráficos", "Perfil"])

with tab_datos:
    st.dataframe(filtered, width="stretch", hide_index=True)
    st.download_button(
        "Descargar CSV",
        filtered.to_csv(index=False).encode("utf-8-sig"),
        "datos_filtrados.csv",
        "text/csv",
    )

with tab_graf:
    c1, c2 = st.columns(2)
    if num_cols:
        col = c1.selectbox("Histograma de", num_cols)
        c1.plotly_chart(px.histogram(filtered, x=col, title=f"Distribución de {col}"), width="stretch")
    if cat_cols:
        cat = c2.selectbox("Recuento por", cat_cols)
        counts = filtered[cat].value_counts().reset_index()
        c2.plotly_chart(px.bar(counts, x=cat, y="count", title=f"Filas por {cat}"), width="stretch")
    if len(num_cols) >= 2:
        x, y = st.columns(2)
        cx = x.selectbox("Eje X", num_cols, index=0)
        cy = y.selectbox("Eje Y", num_cols, index=1)
        st.plotly_chart(
            px.scatter(filtered, x=cx, y=cy, color=cat_cols[0] if cat_cols else None),
            width="stretch",
        )

with tab_perfil:
    st.dataframe(quick_profile(filtered), width="stretch")
