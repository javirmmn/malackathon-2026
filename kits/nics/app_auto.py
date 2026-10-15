"""Dashboard del clasificador automático. Lee lo que deja `python -m kits.nics.auto` (por defecto out/nics_auto/).

    streamlit run kits/nics/app_auto.py                      # usa out/nics_auto
    streamlit run kits/nics/app_auto.py -- --dir out/otra    # otra carpeta de resultados
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import streamlit as st

import common.charts  # noqa: F401
from common import OUT_DIR

_ap = argparse.ArgumentParser()
_ap.add_argument("--dir", default=str(OUT_DIR / "nics_auto"))
DIR = Path(_ap.parse_known_args(sys.argv[1:])[0].dir)

ETIQUETA = {"real": "Real", "honeypot_clasico": "Honeypot clásico", "honeypot_generativo": "Honeypot generativo (IA)"}
COLOR = {"real": "#1d7a46", "honeypot_clasico": "#e07a1f", "honeypot_generativo": "#b4410c"}
GRUPOS = {
    "base": "Respuesta normal (referencia)", "inyeccion": "Instrucción metida en la petición: ¿obedece o solo refleja?",
    "lenguaje": "Petición en lenguaje natural: ¿responde en prosa?", "variantes": "Variantes de la misma ruta (salta la caché)",
    "metodos": "Métodos distintos de GET a rutas nuevas", "repeticion": "Misma ruta repetida (latencia, caché)",
    "buscador": "Buscador", "formulario": "Formularios", "openapi": "Esquema OpenAPI y endpoints declarados",
    "producto": "Comprobaciones del producto (Elasticsearch, Grafana, Synology...)", "generativo": "Referencia del barrido de generativo",
    "shell": "Sesión SSH (credenciales triviales de ensayo)", "protocolo": "Comandos del protocolo", "descartado": "Puerto descartado: saludo y comando",
    "disponibilidad": "Comprobación de disponibilidad",
}

st.set_page_config(page_title="NICS · Clasificador automático", page_icon="🤖", layout="wide")
if not (DIR / "clasificacion.csv").exists():
    st.error(f"No hay resultados en {DIR}. Ejecuta antes:  python -m kits.nics.auto --host 10.66.0.1")
    st.stop()


def _csv(name, **kw):
    f = DIR / name
    return pd.read_csv(f, encoding="utf-8-sig", **kw) if f.exists() else None


@st.cache_data
def cargar(stamp):
    return (_csv("clasificacion.csv"), _csv("rasgos.csv"), _csv("no_disponibles.csv"),
            _csv("pruebas.csv", keep_default_na=False), _csv("validacion.csv"))


stamp = tuple((DIR / f).stat().st_mtime if (DIR / f).exists() else 0 for f in ("clasificacion.csv", "pruebas.csv", "validacion.csv"))
cl, rasgos, nodisp, pruebas, val = cargar(stamp)
cl["clasificación"] = cl["clase"].map(ETIQUETA)

st.title("NICS Lab · Clasificación automática")
st.caption(f"Resultados de `{DIR}` · un solo barrido: descubrir → filtrar no disponibles → sondear → reglas → CSV")
c = st.columns(6)
c[0].metric("Servicios disponibles", len(cl))
for i, k in enumerate(ETIQUETA, 1):
    c[i].metric(ETIQUETA[k], int((cl["clase"] == k).sum()))
c[4].metric("No disponibles", 0 if nodisp is None else len(nodisp))
c[5].metric("A revisar (confianza baja)", int(cl["revisar"].sum()))

st.sidebar.title("Filtros")
clases = st.sidebar.multiselect("Clase", list(ETIQUETA), default=list(ETIQUETA), format_func=ETIQUETA.get)
solo_rev = st.sidebar.checkbox("Solo los que hay que revisar")
vista = cl[cl["clase"].isin(clases)]
if solo_rev:
    vista = vista[vista["revisar"]]

tab_res, tab_det, tab_nd, tab_val, tab_met = st.tabs(["Resumen", "Evidencia por puerto", "No disponibles", "Validación", "Cómo decide"])

with tab_res:
    st.dataframe(vista[["port", "service", "producto", "clasificación", "confianza", "revisar", "gemelos", "evidencias"]],
                 hide_index=True, width="stretch",
                 column_config={"port": st.column_config.NumberColumn("Puerto", format="%d"),
                                "confianza": st.column_config.ProgressColumn("confianza", min_value=0, max_value=1, format="%.2f"),
                                "evidencias": st.column_config.TextColumn("Evidencias (reglas que se cumplieron)", width="large")})
    st.plotly_chart(px.bar(cl.groupby(["service", "clase"]).size().reset_index(name="n"), x="service", y="n", color="clase",
                           color_discrete_map=COLOR, title="Servicios por protocolo y clase", height=300), width="stretch")
    st.download_button("Descargar entrega.csv (port, service, class)", (DIR / "entrega.csv").read_bytes(), "entrega.csv", "text/csv")

with tab_det:
    puerto = st.selectbox("Puerto", vista["port"].tolist() or cl["port"].tolist())
    f = cl[cl["port"] == puerto].iloc[0]
    st.subheader(f"{puerto} · {f['service']} · {f['producto'] or ''} · {ETIQUETA[f['clase']]} ({f['confianza']:.0%})")
    st.caption(f"Puntos: real {f['puntos_real']:g} · clásico {f['puntos_clasico']:g} · generativo {f['puntos_generativo']:g} · "
               f"reglas: {f['reglas']}" + (f" · comparte perfil con: {f['gemelos']}" if isinstance(f['gemelos'], str) and f['gemelos'] else ""))
    if f["revisar"]:
        st.warning("Confianza baja: conviene revisar a mano.")
    st.markdown("**Por qué se clasificó así (reglas que se cumplieron)**")
    for e in str(f["evidencias"]).split(" | "):
        st.markdown(f"- {e}")
    if rasgos is not None:
        rs = rasgos[rasgos["port"] == puerto].iloc[0].dropna()
        with st.expander("Todos los rasgos medidos"):
            st.dataframe(rs.rename("valor").astype(str).to_frame(), width="stretch")
    st.markdown("**Pruebas realizadas (petición → respuesta)**")
    if pruebas is not None:
        p = pruebas[pruebas["port"] == puerto]
        for g in [g for g in GRUPOS if g in set(p["grupo"])] + [g for g in set(p["grupo"]) if g not in GRUPOS]:
            gg = p[p["grupo"] == g]
            with st.expander(f"{GRUPOS.get(g, g)} · {len(gg)}", expanded=g in ("inyeccion", "shell", "descartado")):
                st.dataframe(gg[["prueba", "peticion", "estado", "ms", "respuesta"]], hide_index=True, width="stretch",
                             column_config={"peticion": st.column_config.TextColumn("Petición (reproducible)", width="large"),
                                            "respuesta": st.column_config.TextColumn("Respuesta (recortada)", width="large")})

with tab_nd:
    st.markdown("Puertos **abiertos pero no disponibles**: aceptan la conexión, saludan y cierran (o callan) sin contestar a un "
                "comando válido. Criterio de la organización: no se cuentan ni se clasifican.")
    if nodisp is not None and len(nodisp):
        st.dataframe(nodisp, hide_index=True, width="stretch", column_config={"motivo": st.column_config.TextColumn(width="large")})
        if pruebas is not None:
            d = pruebas[pruebas["grupo"] == "descartado"]
            st.dataframe(d[["port", "prueba", "peticion", "respuesta"]], hide_index=True, width="stretch")

with tab_val:
    if val is None:
        st.info("Sin validación. Ejecuta con `--validar <csv con port,clase>` (por defecto, el veredicto confirmado a mano).")
    else:
        comp = val.dropna(subset=["auto", "manual"])
        ok = int(comp["coincide"].sum())
        st.metric("Coinciden con el veredicto manual", f"{ok}/{len(comp)}", f"{ok / max(len(comp), 1):.0%}")
        st.caption("La verdad de referencia es el veredicto confirmado a mano durante la sesión; el clasificador automático "
                   "NUNCA la usa para clasificar, solo se compara después.")
        cm = pd.crosstab(comp["manual"].map(ETIQUETA), comp["auto"].map(ETIQUETA))
        st.dataframe(cm, width="stretch")
        st.dataframe(val[~val["coincide"].fillna(False)] if (~val["coincide"].fillna(False)).any() else val.head(0),
                     hide_index=True, width="stretch")

with tab_met:
    st.markdown("""
**Flujo:** descubrir puertos (escaneo TCP) → identificar protocolo por el saludo → **filtrar no disponibles** (contesta a un
comando válido) → sondear: genéricas (catch-all, buscador, formularios, OpenAPI) + por producto (Elasticsearch, Grafana,
Synology, Gitea, Exchange, WordPress) + batería de generativo + SSH/protocolos → motor de reglas ponderadas
(`kits/nics/auto/reglas.yaml`).

**Generativo** (una señal fuerte basta): obedece una instrucción metida en la petición, responde en prosa, da salidas
distintas por variante de ruta (salta la caché por ruta), tarda segundos en rutas nuevas o solo actúa con métodos no-GET.
**Clásico:** respuestas predefinidas que no aguantan el uso real. **Real:** el servicio funciona de verdad.

**No es evidencia:** que un dato cambie (un script aleatorio también), que el error refleje tu texto, o una única
respuesta negativa (la obediencia es estocástica; se repite).

**Confianza:** nuestro juicio sobre el margen de la evidencia (base 0,50 + 0,06 por punto de margen, máx. 0,97), no una
probabilidad. Por debajo de 0,65 se marca «revisar».
""")
