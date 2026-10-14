"""Dashboard de clasificación de servicios. Antes: python -m kits.nics.run --testbed (o --targets ...)

    streamlit run kits/nics/app.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # para `import common` / `kits` con streamlit run

import pandas as pd
import plotly.express as px
import streamlit as st

import common.charts  # noqa: F401
from common import OUT_DIR
from kits.nics.report import COLOR, ETIQUETA, RASGOS_CLAVE
from kits.nics.run import classify_saved

OUT = OUT_DIR / "nics"
st.set_page_config(page_title="Infiltrados en la red", page_icon="🕵️", layout="wide")

if not (OUT / "evidencias.csv").exists():
    st.error("No hay evidencias. Ejecuta antes:  python -m kits.nics.run --testbed   (o --targets ... --scope ...)")
    st.stop()


@st.cache_data
def load(stamp: float):
    res = pd.DataFrame(json.loads((OUT / "resultados.json").read_text(encoding="utf-8")))
    feats = pd.read_csv(OUT / "rasgos.csv", encoding="utf-8-sig")
    ev = pd.read_csv(OUT / "evidencias.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    return res, feats, ev


st.sidebar.title("Acciones")
if st.sidebar.button("Reclasificar con rules.yaml", help="Aplica las reglas editadas sin volver a escanear"):
    classify_saved(OUT)
    st.sidebar.success("Reclasificado")
res, feats, ev = load((OUT / "resultados.json").stat().st_mtime)
clases = st.sidebar.multiselect("Clases", list(ETIQUETA), default=list(ETIQUETA), format_func=ETIQUETA.get)
umbral = st.sidebar.slider("Confianza mínima", 0.0, 1.0, 0.0, 0.05)

st.title("Infiltrados en la red · ¿quién es la IA impostora?")
c = st.columns(4)
c[0].metric("Servicios", len(res))
for i, k in enumerate(ETIQUETA, 1):
    c[i].metric(ETIQUETA[k], int((res["clase"] == k).sum()))

vista = res[res["clase"].isin(clases) & (res["confianza"] >= umbral)].copy()
vista["clasificación"] = vista["clase"].map(ETIQUETA)
vista["confianza_pct"] = (vista["confianza"] * 100).round()
st.dataframe(vista[["servicio", "url_base", "clasificación", "confianza_pct", "que_lo_delato"]], width="stretch", hide_index=True,
             column_config={"confianza_pct": st.column_config.ProgressColumn("confianza", min_value=0, max_value=100, format="%d%%")})

t1, t2, t3 = st.tabs(["Detalle del servicio", "Mapa de rasgos", "Evidencias en bruto"])

with t1:
    s = st.selectbox("Servicio", vista["servicio"].tolist() or res["servicio"].tolist())
    r = res.set_index("servicio").loc[s]
    st.subheader(f"{s} · {ETIQUETA.get(r['clase'], r['clase'])} ({r['confianza']:.0%})")
    a, b = st.columns([3, 2])
    with a:
        st.markdown("**Evidencias (reglas cumplidas)**")
        for e in sorted(r["evidencias"], key=lambda e: -e["peso"]):
            st.markdown(f"- **{e['regla']}** · +{e['peso']} *{ETIQUETA.get(e['clase'], e['clase'])}* — {e['texto']}")
        f = feats.set_index("servicio").loc[s]
        st.markdown("**Rasgos medidos**")
        st.dataframe(pd.DataFrame({"valor": [str(f[k]) for k in RASGOS_CLAVE if k in f]},
                                  index=[k for k in RASGOS_CLAVE if k in f]), width="stretch")
    with b:
        pts = pd.DataFrame({"clase": [ETIQUETA[k] for k in ETIQUETA], "puntos": [r[f"puntos_{k}"] for k in ETIQUETA],
                            "k": list(ETIQUETA)})
        st.plotly_chart(px.bar(pts, x="clase", y="puntos", color="k", color_discrete_map=COLOR, title="Puntuación por clase",
                               height=300).update_layout(showlegend=False), width="stretch")
        e_s = ev[ev["servicio"] == s]
        st.plotly_chart(px.box(e_s, x="sonda", y="latencia_ms", points="all", title="Latencia por sonda (ms)", height=300),
                        width="stretch")
    st.markdown("**Respuestas**")
    for sonda, g in e_s.groupby("sonda", sort=False):
        with st.expander(f"{sonda} · {g['metodo'].iat[0]} {g['ruta'].iat[0]} · status {sorted(set(g['status'].dropna().astype(int)))} · "
                         f"{g['sha1'].nunique()} respuesta(s) distinta(s)"):
            for _, x in g.head(3).iterrows():
                st.code(str(x["cuerpo"])[:1500] or "(vacío)", language="html")

with t2:
    num = ["consistencia_raiz", "consistencia_inexistente", "latencia_media_ms", "latencia_cv", "inexistente_vs_raiz"]
    m = feats.merge(res[["servicio", "clase"]], on="servicio")
    x = st.selectbox("Eje X", num, index=0)
    y = st.selectbox("Eje Y", num, index=2)
    st.plotly_chart(px.scatter(m, x=x, y=y, color="clase", color_discrete_map=COLOR, hover_name="servicio", height=480,
                               size_max=14).update_traces(marker_size=14), width="stretch")
    st.dataframe(feats, width="stretch", hide_index=True)

with t3:
    st.dataframe(ev.drop(columns=["cuerpo"]), width="stretch", hide_index=True)
    st.caption("Informe completo: out/nics/informe.html · out/nics/informe.md")
