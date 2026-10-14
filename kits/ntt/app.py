"""Dashboard del Guardián. Antes: python -m kits.ntt.run --data <fichero>

    streamlit run kits/ntt/app.py
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
from kits.ntt.guardian import Guardian
from kits.ntt.report import highlight

st.set_page_config(page_title="El Guardián", page_icon="🛡️", layout="wide")
carpetas = sorted(p for p in OUT_DIR.glob("ntt*") if (p / "resultados.csv").exists())
if not carpetas:
    st.error("No hay resultados. Ejecuta antes:  python -m kits.ntt.run --data data/<fichero>")
    st.stop()

OUT = st.sidebar.selectbox("Ejecución", carpetas, format_func=lambda p: p.name)
res = pd.read_csv(OUT / "resultados.csv", encoding="utf-8-sig")
metrics = json.loads((OUT / "metricas.json").read_text(encoding="utf-8"))
resp_col = next(c for c in ["respuesta", "response", "answer", "output"] if c in res) if any(
    c in res for c in ["respuesta", "response", "answer", "output"]) else res.columns[0]
fuen_col = next((c for c in ["fuentes", "contexto", "context", "sources"] if c in res), None)

st.title("El Guardián · ¿se lo ha inventado la IA?")
c = st.columns(4)
c[0].metric("Respuestas", len(res))
c[1].metric("Marcadas como alucinación", int(res["prediccion"].sum()))
m = metrics.get("sobre_estos_datos") or {}
c[2].metric("Accuracy", m.get("accuracy", "—"))
c[3].metric("F1", m.get("f1", "—"))

t1, t2, t3 = st.tabs(["Respuestas", "Probar una respuesta", "Métricas"])

with t1:
    solo = st.radio("Mostrar", ["Todas", "Solo alucinaciones", "Solo fieles"], horizontal=True)
    v = res if solo == "Todas" else res[res["prediccion"] == (1 if solo == "Solo alucinaciones" else 0)]
    show = [c for c in ["id", "prob_alucina", "prediccion", resp_col, "motivos"] if c in v]
    st.dataframe(v.sort_values("prob_alucina", ascending=False)[show], width="stretch", hide_index=True,
                 column_config={"prob_alucina": st.column_config.ProgressColumn("prob.", min_value=0, max_value=1, format="%.2f")})
    idx = st.selectbox("Ver detalle de", v.index, format_func=lambda i: f"{res.loc[i, 'id'] if 'id' in res else i} · "
                       f"{str(res.loc[i, resp_col])[:80]}")
    r = res.loc[idx]
    st.markdown(f"**Probabilidad de alucinación: {r['prob_alucina']:.2f}** → {'🚩 alucina' if r['prediccion'] else '✅ fiel'}")
    a, b = st.columns(2)
    a.markdown("**Respuesta** (resaltado: no aparece en las fuentes)")
    a.markdown(highlight(r[resp_col], r), unsafe_allow_html=True)
    a.markdown("**Motivos**")
    for mot in str(r["motivos"]).split(" · "):
        a.markdown(f"- {mot}")
    if fuen_col:
        b.markdown("**Fuentes**")
        b.write(r[fuen_col])

with t2:
    st.write("Pega una respuesta y sus fuentes: el Guardián la evalúa con el modelo entrenado.")
    usar_llm = st.checkbox("Usar también el juez LLM (Ollama, ~5 s)")
    fu = st.text_area("Fuentes", height=150)
    rp = st.text_area("Respuesta de la IA", height=100)
    if st.button("Evaluar", type="primary") and rp and fu:
        out = Guardian(OUT / "modelo.json" if (OUT / "modelo.json").exists() else OUT_DIR / "ntt" / "modelo.json",
                       llm=usar_llm).evaluar(rp, fu)
        (st.error if out["alucina"] else st.success)(f"{'Alucina' if out['alucina'] else 'Fiel'} · probabilidad {out['prob']:.2f}")
        for mot in out["motivos"]:
            st.markdown(f"- {mot}")
        st.bar_chart(pd.Series(out["contribuciones"], name="empuje hacia 'alucina'"))

with t3:
    st.json(metrics)
    if "tipo" in res:
        acc = res.assign(ok=res["prediccion"] == res.get("alucina", res["prediccion"])).groupby("tipo")["ok"].mean().reset_index()
        st.plotly_chart(px.bar(acc, x="tipo", y="ok", title="Acierto por tipo de respuesta", range_y=[0, 1]), width="stretch")
    st.plotly_chart(px.histogram(res, x="prob_alucina", color=res["prediccion"].map({1: "alucina", 0: "fiel"}), nbins=20,
                                 title="Distribución de probabilidades"), width="stretch")
    st.caption(f"Informe completo: {OUT / 'informe.html'}")
