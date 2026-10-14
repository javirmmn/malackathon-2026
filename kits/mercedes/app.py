"""Dashboard de segmentos. Antes: python -m kits.mercedes.run --data <fichero>

    streamlit run kits/mercedes/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # para `import common` / `kits` con streamlit run

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

import common.charts  # noqa: F401
from common import OUT_DIR
from kits.mercedes import pipeline as pl

OUT = OUT_DIR / "mercedes"
st.set_page_config(page_title="Segmentos de clientes", page_icon="⭐", layout="wide")

if not (OUT / "modelo.joblib").exists():
    st.error("No hay resultados. Ejecuta antes:  python -m kits.mercedes.run --data data/<fichero>")
    st.stop()


@st.cache_resource
def load_bundle():
    return joblib.load(OUT / "modelo.joblib")


@st.cache_data
def load_tables():
    seg = pd.read_csv(OUT / "clientes_segmentados.csv")
    rasgos = pd.read_csv(OUT / "perfiles_rasgos.csv", index_col=0)
    tam = pd.read_csv(OUT / "perfiles_tamanos.csv", index_col=0)
    medias = pd.read_csv(OUT / "perfiles_medias.csv", index_col=0)
    modelos = pd.read_csv(OUT / "modelos.csv")
    return seg, rasgos, tam, medias, modelos


def load_personas(names: dict[int, str]) -> dict[int, dict]:
    """personas.yaml (rellenado a mano) manda sobre los nombres automáticos."""
    p = OUT / "personas.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {s: {"nombre": (data or {}).get(s, {}).get("nombre") or names[s],
                "descripcion": (data or {}).get(s, {}).get("descripcion", ""),
                "acciones": [a for a in (data or {}).get(s, {}).get("acciones", []) if a]} for s in names}


b = load_bundle()
seg, rasgos, tam, medias, modelos = load_tables()
personas = load_personas(b["names"])
nombre = {s: p["nombre"] for s, p in personas.items()}
seg["nombre"] = seg["segmento"].map(nombre).fillna("ruido")

st.title("Segmentación de clientes")
st.caption(f"Modelo: {b['chosen']} · {len(nombre)} segmentos · {len(seg):,} clientes".replace(",", "."))

tab_res, tab_seg, tab_sim, tab_mod = st.tabs(["Resumen", "Segmento", "¿A qué segmento pertenece?", "Modelos"])

with tab_res:
    cols = st.columns(len(nombre))
    for col, (s, n) in zip(cols, nombre.items()):
        col.metric(n.split(" · ")[0] if n.startswith("S") else n, f"{tam.loc[s, 'pct']} %", f"{int(tam.loc[s, 'clientes'])} clientes", delta_color="off")
    eje = "umap" if "umap_1" in seg else "pca"
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(px.scatter(seg, x=f"{eje}_1", y=f"{eje}_2", color="nombre", opacity=0.6, height=520,
                               title=f"Clientes en 2D ({eje.upper()})", render_mode="webgl"), width="stretch")
    t = tam.reset_index().assign(nombre=lambda d: d["segmento"].map(nombre))
    c2.plotly_chart(px.pie(t, names="nombre", values="clientes", hole=0.45, height=520, title="Peso de cada segmento"),
                    width="stretch")

with tab_seg:
    s = st.selectbox("Segmento", list(nombre), format_func=lambda x: nombre[x])
    p = personas[s]
    st.subheader(p["nombre"])
    if p["descripcion"]:
        st.write(p["descripcion"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Qué lo distingue**")
        for _, r in rasgos[rasgos["segmento"] == s].iterrows():
            st.markdown(f"- {pl.describe_trait(r)}")
        if p["acciones"]:
            st.markdown("**Acciones de marketing**")
            for a in p["acciones"]:
                st.markdown(f"- {a}")
        else:
            st.info("Rellena nombre, descripción y acciones en out/mercedes/personas.yaml (parte de personas_plantilla.yaml).")
    with c2:
        if not medias.empty:
            norm = (medias - medias.min()) / (medias.max() - medias.min()).replace(0, 1)
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=norm.mean().tolist() + [norm.mean().iloc[0]], theta=list(norm.columns) + [norm.columns[0]],
                                          name="media de segmentos", line=dict(dash="dot", color="#7a8394")))
            fig.add_trace(go.Scatterpolar(r=norm.loc[s].tolist() + [norm.loc[s].iloc[0]], theta=list(norm.columns) + [norm.columns[0]],
                                          fill="toself", name=nombre[s]))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 1])), height=460, title="Perfil (0–1 entre segmentos)")
            st.plotly_chart(fig, width="stretch")
    st.markdown("**Clientes del segmento**")
    st.dataframe(seg[seg["segmento"] == s].drop(columns=[c for c in seg if c.startswith(("pca_", "umap_"))]),
                 width="stretch", hide_index=True)

with tab_sim:
    st.write("Introduce los datos de un cliente y el modelo te dice a qué segmento se parece más (centroide más cercano).")
    vals = {}
    cols = st.columns(3)
    feats = b["num_cols"] + b["cat_cols"]
    for i, c in enumerate(feats):
        with cols[i % 3]:
            if c in b["cat_cols"]:
                opts = b["choices"][c]
                d = b["defaults"][c]
                vals[c] = st.selectbox(c, opts, index=opts.index(d) if d in opts else 0)
            else:
                vals[c] = st.number_input(c, value=float(round(b["defaults"][c], 2)))
    if st.button("Asignar segmento", type="primary"):
        Z = b["preprocessor"].transform(pd.DataFrame([vals])[feats])
        res = int(pl.assign(np.asarray(Z), b["centroids"])[0])
        st.success(f"Segmento: **{nombre[res]}**")
        for a in personas[res]["acciones"]:
            st.markdown(f"- {a}")

with tab_mod:
    st.dataframe(modelos, width="stretch", hide_index=True)
    km = modelos[modelos["metodo"] == "K-Means"]
    c1, c2 = st.columns(2)
    if not km.empty:
        c1.plotly_chart(px.line(km, x="k", y="inercia", markers=True, title="Codo (K-Means)"), width="stretch")
    c2.plotly_chart(px.line(modelos.dropna(subset=["k", "silhouette"]), x="k", y="silhouette", color="metodo", markers=True,
                            title="Silhouette por k"), width="stretch")
    st.caption("Informes completos: out/mercedes/informe.html y out/mercedes/eda.html")
