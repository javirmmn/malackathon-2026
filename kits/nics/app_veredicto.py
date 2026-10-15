"""Dashboard único con los 40 puertos y nuestro veredicto (web + no-web). Antes: python -m kits.nics.veredicto

    streamlit run kits/nics/app_veredicto.py
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

OUT = OUT_DIR / "nics_entrega"
ETIQUETA = {"real": "Real", "honeypot_clasico": "Honeypot clásico", "honeypot_generativo": "Honeypot generativo (IA)"}
COLOR = {"real": "#1d7a46", "honeypot_clasico": "#e07a1f", "honeypot_generativo": "#b4410c"}
METODO = {"interaccion_real": "🟢 Interacción real", "sondas_automaticas": "⚪ Solo sondas automáticas"}

st.set_page_config(page_title="NICS · Veredicto completo", page_icon="🕵️", layout="wide")

if not (OUT / "veredicto.csv").exists():
    st.error("No hay veredicto. Ejecuta antes:  python -m kits.nics.veredicto")
    st.stop()


@st.cache_data
def load(stamp: float):
    v = pd.read_csv(OUT / "veredicto.csv", encoding="utf-8-sig")
    ev_web = pd.read_csv(OUT_DIR / "nics_real" / "evidencias.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    rasgos_otros = pd.read_csv(OUT_DIR / "nics_otros" / "rasgos_protocolo.csv", encoding="utf-8-sig")
    interacciones = {}
    carpeta_int = OUT_DIR / "nics_interaccion"
    if carpeta_int.exists():
        for f in carpeta_int.glob("interaccion_*.json"):
            for r in json.loads(f.read_text(encoding="utf-8")):
                interacciones[r["port"]] = r
    return v, ev_web, rasgos_otros, interacciones


v, ev_web, rasgos_otros, interacciones = load((OUT / "veredicto.csv").stat().st_mtime)
v["clasificación"] = v["clase"].map(ETIQUETA)
v["método"] = v["metodo"].map(METODO)

st.title(f"NICS Lab · Veredicto de los {len(v)} servicios abiertos y disponibles")
if (OUT / "excluidos.csv").exists():
    _ex = pd.read_csv(OUT / "excluidos.csv", encoding="utf-8-sig")
    st.info("Fuera del análisis por no estar disponibles (sin conexión): " + ", ".join(map(str, _ex["port"])))
st.caption("Red de Ondalux Logística S.L. (10.66.0.1) · III Malackathon 2026")

c = st.columns(5)
c[0].metric("Servicios", len(v))
for i, k in enumerate(ETIQUETA, 1):
    c[i].metric(ETIQUETA[k], int((v["clase"] == k).sum()))
c[4].metric("Confirmados interactuando", int((v["metodo"] == "interaccion_real").sum()))

st.sidebar.title("Filtros")
clases_f = st.sidebar.multiselect("Clase", list(ETIQUETA), default=list(ETIQUETA), format_func=ETIQUETA.get)
solo_pend = st.sidebar.checkbox("Solo pendientes de confirmar (confianza < 0,65 o gemelo sin resolver)")
vista = v[v["clase"].isin(clases_f)]
if solo_pend:
    vista = vista[(vista["confianza"] < 0.65) | (vista["revisar_a_mano"])]

st.dataframe(
    vista[["port", "service", "clasificación", "confianza", "método", "evidencias"]].sort_values("port"),
    width="stretch", hide_index=True,
    column_config={
        "port": st.column_config.NumberColumn("Puerto", format="%d"),
        "confianza": st.column_config.ProgressColumn("confianza", min_value=0, max_value=1, format="%.2f"),
        "evidencias": st.column_config.TextColumn("Evidencia", width="large"),
    },
)

st.plotly_chart(
    px.bar(v.groupby(["service", "clase"]).size().reset_index(name="n"), x="service", y="n", color="clase",
          color_discrete_map=COLOR, title="Servicios por protocolo y clase", height=320),
    width="stretch",
)

st.header("Barrido de generativos")
st.caption("Qué delata a un LLM (no solo que algo cambie): obedece instrucciones metidas en la petición (ruta, query, "
           "cabeceras, cuerpo, shell SSH), responde en prosa, da una salida distinta por variante de ruta "
           "(salta la caché por ruta), tarda segundos en rutas nuevas o solo actúa con métodos no-GET. "
           "`python -m kits.nics.barrido_generativo`")
_bg = OUT / "barrido_generativo.csv"
if _bg.exists():
    bg = pd.read_csv(_bg, encoding="utf-8-sig").fillna("")
    bg["clasificación"] = bg["clase"].map(ETIQUETA)
    cols = [c for c in ["port", "service", "clasificación", "n_flags", "flag_obedece", "flag_prosa", "flag_variantes",
                        "flag_metodos", "flag_latencia", "obedece", "prosa_ante_instruccion"] if c in bg.columns]
    st.dataframe(bg[cols].sort_values(["n_flags", "port"], ascending=[False, True]), width="stretch", hide_index=True,
                 column_config={"port": st.column_config.NumberColumn("Puerto", format="%d"),
                                "n_flags": st.column_config.NumberColumn("señales")})
    st.caption("Ojo: variantes de ruta distintas en un servicio real (Elasticsearch, Grafana) son errores técnicos "
               "estructurados, no prosa; por eso 22739 y 25461 se revisaron a mano y siguen siendo reales.")
else:
    st.info("Aún no hay barrido: `python -m kits.nics.barrido_generativo`")

st.header("Detalle de un puerto")
puerto = st.selectbox("Puerto", vista["port"].tolist() or v["port"].tolist())
fila = v[v["port"] == puerto].iloc[0]
st.subheader(f"{puerto} · {fila['service']} · {ETIQUETA.get(fila['clase'], fila['clase'])} ({fila['confianza']:.0%})")
st.markdown(f"**Método:** {METODO.get(fila['metodo'], fila['metodo'])}")
st.markdown(f"**Evidencia:** {fila['evidencias']}")

if fila["service"] in ("HTTP", "HTTPS"):
    nombre_servicio = f"p{puerto}"
    g = ev_web[ev_web["servicio"] == nombre_servicio]
    if len(g):
        st.markdown("**Respuestas capturadas (sondas HTTP)**")
        for sonda, gg in g.groupby("sonda", sort=False):
            with st.expander(f"{sonda} · {gg['metodo'].iat[0]} {gg['ruta'].iat[0]} · status {sorted(set(gg['status'].dropna().astype(int)))}"):
                for _, x in gg.head(2).iterrows():
                    st.code(str(x["cuerpo"])[:1200] or "(vacío)", language="html")
else:
    r = rasgos_otros[rasgos_otros["puerto"] == puerto]
    if len(r):
        st.markdown("**Banner capturado (repetido 5 veces)**")
        st.code(r.iloc[0]["banner_ejemplo"] or "(sin banner)")
        st.caption(f"Latencia media: {r.iloc[0]['latencia_media_ms']} ms · "
                  f"{r.iloc[0]['intentos_ok']} de {r.iloc[0]['intentos_ok'] + r.iloc[0]['sin_banner']} conexiones con respuesta")
    if puerto in interacciones:
        st.markdown("**Interacción real (lo que probamos a mano/con el script)**")
        st.json(interacciones[puerto])
    elif fila["service"] not in ("HTTP", "HTTPS"):
        st.info("Este puerto aún no se ha probado con interacción real (solo banner). "
               "`python -m kits.nics.interactuar --puertos "
               f"{puerto} --protocolo {fila['service'].lower()}`")

st.divider()
st.caption(f"CSV de entrega: `{OUT / 'entrega.csv'}` · Detalle completo: `{OUT / 'veredicto.csv'}`")
