"""Informes HTML autocontenidos (se abren sin internet): EDA y resultados de la segmentación."""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import common.charts  # noqa: F401  (plantilla de gráficos del equipo)
from common.dataio import quick_profile

from .pipeline import Schema, describe_trait

_CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;color:#1d2433;max-width:1200px;margin:24px auto;padding:0 16px;background:#fff}
h1{color:#0b5cad}h2{color:#0b5cad;border-bottom:2px solid #0b5cad;padding-bottom:4px;margin-top:32px}
table{border-collapse:collapse;font-size:13px;margin:8px 0}th,td{border:1px solid #d9dee7;padding:4px 8px;text-align:left}
th{background:#e8f1fb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:12px}
.card{border:1px solid #d9dee7;border-radius:8px;padding:8px 14px;margin:10px 0}.muted{color:#5b6475;font-size:13px}
"""


class _Doc:
    def __init__(self, title: str):
        self.parts = [f"<h1>{html.escape(title)}</h1>"]
        self._js = True  # el primer gráfico incrusta plotly.js; los demás lo reutilizan

    def h2(self, t: str):
        self.parts.append(f"<h2>{html.escape(t)}</h2>")

    def p(self, t: str, cls: str = ""):
        self.parts.append(f"<p class='{cls}'>{t}</p>")

    def table(self, df: pd.DataFrame, index: bool = True):
        self.parts.append(df.to_html(index=index, border=0, float_format=lambda x: f"{x:,.2f}"))

    def fig(self, fig: go.Figure):
        self.parts.append(fig.to_html(full_html=False, include_plotlyjs=self._js))
        self._js = False

    def raw(self, s: str):
        self.parts.append(s)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<!doctype html><meta charset='utf-8'><title>{self.parts[0][4:-5]}</title>"
                        f"<style>{_CSS}</style>" + "\n".join(self.parts), encoding="utf-8")
        return path


def eda_report(df: pd.DataFrame, sch: Schema, conversions: dict[str, str], path: Path) -> Path:
    doc = _Doc("Análisis exploratorio (EDA)")
    doc.p(f"{len(df):,} filas · {df.shape[1]} columnas".replace(",", "."), "muted")

    doc.h2("Columnas y uso en el modelo")
    use = sch.as_rows().set_index("columna")
    prof = quick_profile(df).join(use, how="left")
    if conversions:
        prof["conversión"] = pd.Series(conversions)
    doc.table(prof.fillna(""))

    num = [c for c in sch.numeric if c in df]
    if num:
        doc.h2("Distribuciones numéricas")
        doc.raw("<div class='grid'>")
        for c in num[:16]:
            doc.fig(px.histogram(df, x=c, nbins=40, title=c, height=280, marginal="box"))
        doc.raw("</div>")

        doc.h2("Valores atípicos (regla IQR 1,5)")
        q1, q3 = df[num].quantile(0.25), df[num].quantile(0.75)
        iqr = q3 - q1
        out = ((df[num] < q1 - 1.5 * iqr) | (df[num] > q3 + 1.5 * iqr)).sum()
        doc.table(pd.DataFrame({"atípicos": out, "pct": (100 * out / len(df)).round(1),
                                "min": df[num].min(), "mediana": df[num].median(), "max": df[num].max()}))

        if len(num) > 1:
            doc.h2("Correlaciones (Spearman)")
            corr = df[num].corr(method="spearman").round(2)
            doc.fig(px.imshow(corr, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                              height=max(400, 32 * len(num)), title="Correlación entre variables numéricas"))

    if sch.categorical:
        doc.h2("Variables categóricas")
        doc.raw("<div class='grid'>")
        for c in sch.categorical[:12]:
            vc = df[c].astype("string").fillna("(nulo)").value_counts().head(15).reset_index()
            vc.columns = [c, "clientes"]
            doc.fig(px.bar(vc, x=c, y="clientes", title=c, height=280))
        doc.raw("</div>")

    for c in sch.dates:
        doc.h2(f"Fecha: {c}")
        doc.fig(px.histogram(df, x=c, nbins=40, height=280))
    return doc.save(path)


def _radar(medias: pd.DataFrame, names: dict[int, str]) -> go.Figure:
    norm = (medias - medias.min()) / (medias.max() - medias.min()).replace(0, 1)
    fig = go.Figure()
    for seg, row in norm.iterrows():
        vals = row.tolist()
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=list(norm.columns) + [norm.columns[0]],
                                      fill="toself", opacity=0.55, name=names.get(seg, str(seg))))
    fig.update_layout(title="Perfil de cada segmento (medias normalizadas 0–1 entre segmentos)", height=560,
                      polar=dict(radialaxis=dict(visible=True, range=[0, 1])))
    return fig


def results_report(models: pd.DataFrame, chosen: str, prof: dict[str, pd.DataFrame], seg_df: pd.DataFrame,
                   names: dict[int, str], path: Path) -> Path:
    doc = _Doc("Segmentación de clientes · resultados")
    doc.p(f"Modelo elegido: <b>{html.escape(chosen)}</b> · {len(prof['tamanos'])} segmentos · "
          f"{int(prof['tamanos']['clientes'].sum()):,} clientes".replace(",", "."), "muted")

    doc.h2("Comparación de modelos")
    doc.p("Silhouette: más alto es mejor (−1 a 1). Davies-Bouldin: más bajo es mejor. "
          "Calinski-Harabasz: más alto es mejor. El codo se mira en la inercia de K-Means.", "muted")
    doc.table(models, index=False)
    km = models[models["metodo"] == "K-Means"]
    doc.raw("<div class='grid'>")
    if not km.empty:
        doc.fig(px.line(km, x="k", y="inercia", markers=True, title="Método del codo (K-Means)", height=330))
    scored = models.dropna(subset=["k", "silhouette"])
    doc.fig(px.line(scored, x="k", y="silhouette", color="metodo", markers=True, title="Silhouette por k", height=330))
    doc.raw("</div>")

    doc.h2("Tamaño de los segmentos")
    t = prof["tamanos"].reset_index()
    t["nombre"] = t["segmento"].map(names)
    doc.fig(px.bar(t, x="nombre", y="clientes", text="pct", title="Clientes por segmento", height=360))

    doc.h2("Mapa 2D de los clientes")
    seg_df = seg_df.assign(nombre=seg_df["segmento"].map(names).fillna("ruido"))
    doc.raw("<div class='grid'>")
    for a in ("pca", "umap"):
        if f"{a}_1" in seg_df:
            doc.fig(px.scatter(seg_df, x=f"{a}_1", y=f"{a}_2", color="nombre", opacity=0.6, height=480,
                               title=a.upper(), render_mode="webgl"))
    doc.raw("</div>")

    if not prof["medias"].empty:
        doc.h2("Perfiles")
        doc.fig(_radar(prof["medias"], names))
        doc.table(prof["medias"].rename(index=names))
        if not prof["modas"].empty:
            doc.p("Categoría más frecuente en cada segmento:", "muted")
            doc.table(prof["modas"].rename(index=names))

    doc.h2("Qué distingue a cada segmento")
    for seg in prof["tamanos"].index:
        r = prof["rasgos"][prof["rasgos"]["segmento"] == seg]
        items = "".join(f"<li>{html.escape(describe_trait(x))}</li>" for _, x in r.iterrows())
        size = prof["tamanos"].loc[seg]
        doc.raw(f"<div class='card'><b>{html.escape(names.get(seg, str(seg)))}</b> "
                f"<span class='muted'>· {int(size['clientes'])} clientes ({size['pct']} %)</span><ul>{items}</ul></div>")
    return doc.save(path)


def personas_template(prof: dict[str, pd.DataFrame], names: dict[int, str]) -> str:
    """YAML para rellenar a mano: nombre de 'persona', descripción y acciones de marketing por segmento."""
    lines = ["# Rellenar y guardar como personas.yaml (el dashboard lo lee si existe).", "# Rasgos detectados como pista.", ""]
    for seg in prof["tamanos"].index:
        r = prof["rasgos"][prof["rasgos"]["segmento"] == seg]
        lines.append(f"{int(seg)}:")
        lines.append(f'  nombre: "{names.get(seg, seg)}"')
        lines.append('  descripcion: ""')
        lines.append("  acciones:")
        lines.append('    - ""')
        lines.append("  # rasgos:")
        lines += [f"  #  - {describe_trait(x)}" for _, x in r.iterrows()]
        lines.append("")
    return "\n".join(lines)


def ari_if_known(df: pd.DataFrame, labels: np.ndarray, col: str = "verdad_segmento") -> float | None:
    """Solo con el dataset de ensayo: acuerdo (Adjusted Rand) con los segmentos plantados."""
    if col not in df:
        return None
    from sklearn.metrics import adjusted_rand_score

    return round(float(adjusted_rand_score(df[col], labels)), 3)
