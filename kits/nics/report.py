"""Informe "qué delató a cada impostor": Markdown (para el repo/entrega) y HTML (para enseñar)."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd

ETIQUETA = {"real": "Real", "honeypot_clasico": "Honeypot clásico", "honeypot_generativo": "Honeypot generativo (IA)"}
COLOR = {"real": "#1d7a46", "honeypot_clasico": "#e07a1f", "honeypot_generativo": "#b4410c"}
RASGOS_CLAVE = ["status_raiz", "inexistente_status", "consistencia_raiz", "consistencia_inexistente", "catch_all",
                "eco_token_200", "api_json_inventado", "latencia_media_ms", "latencia_cv", "server", "falta_date",
                "firmas_honeypot_txt", "marcas_llm_txt"]


def _sample(ev: pd.DataFrame, servicio: str, sonda: str, n: int = 400) -> str:
    r = ev[(ev["servicio"] == servicio) & (ev["sonda"] == sonda)]
    if r.empty:
        return ""
    x = r.iloc[0]
    return f"{x['metodo']} {x['ruta']} -> {x['status']} ({x['latencia_ms']} ms)\n{str(x['cuerpo'])[:n]}"


def markdown(res: pd.DataFrame, feats: pd.DataFrame, ev: pd.DataFrame) -> str:
    f = feats.set_index("servicio")
    out = [f"# Informe de clasificación de servicios\n",
           f"Generado el {datetime.now():%d/%m/%Y %H:%M} · {len(res)} servicios\n",
           "| Servicio | URL | Clasificación | Confianza | Qué lo delató |", "|---|---|---|---|---|"]
    for _, r in res.iterrows():
        out.append(f"| {r['servicio']} | {r['url_base']} | **{ETIQUETA.get(r['clase'], r['clase'])}** | "
                   f"{r['confianza']:.0%} | {r['que_lo_delato']} |")
    out.append("\n## Detalle por servicio\n")
    for _, r in res.iterrows():
        out.append(f"### {r['servicio']} · {ETIQUETA.get(r['clase'], r['clase'])} ({r['confianza']:.0%})\n")
        out.append(f"`{r['url_base']}`\n")
        out.append("**Evidencias:**\n")
        for e in sorted(r["evidencias"], key=lambda e: -e["peso"]):
            out.append(f"- [{e['regla']} → {ETIQUETA.get(e['clase'], e['clase'])}, +{e['peso']}] {e['texto']}")
        if not r["evidencias"]:
            out.append("- (ninguna regla se ha cumplido)")
        out.append("\n**Rasgos medidos:**\n")
        out.append("| Rasgo | Valor |\n|---|---|")
        for k in RASGOS_CLAVE:
            if k in f.columns:
                out.append(f"| {k} | {f.loc[r['servicio'], k]} |")
        for sonda in ("raiz", "inexistente"):
            s = _sample(ev, r["servicio"], sonda)
            if s:
                out.append(f"\n**Muestra `{sonda}`:**\n\n```\n{s}\n```")
        out.append("")
    return "\n".join(out)


def html_report(res: pd.DataFrame, feats: pd.DataFrame, ev: pd.DataFrame) -> str:
    f = feats.set_index("servicio")
    css = ("body{font-family:'Segoe UI',Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d2433}"
           "h1,h2{color:#0b5cad}table{border-collapse:collapse;font-size:13px}th,td{border:1px solid #d9dee7;padding:4px 8px;text-align:left;vertical-align:top}"
           "th{background:#e8f1fb}.tag{color:#fff;border-radius:4px;padding:1px 8px;font-weight:600}"
           ".card{border:1px solid #d9dee7;border-radius:8px;padding:6px 14px;margin:14px 0}pre{background:#f2f4f8;padding:8px;white-space:pre-wrap;font-size:12px}")
    rows = "".join(
        f"<tr><td>{html.escape(r['servicio'])}</td><td>{html.escape(r['url_base'])}</td>"
        f"<td><span class='tag' style='background:{COLOR.get(r['clase'], '#555')}'>{ETIQUETA.get(r['clase'], r['clase'])}</span></td>"
        f"<td>{r['confianza']:.0%}</td><td>{html.escape(r['que_lo_delato'])}</td></tr>" for _, r in res.iterrows())
    parts = [f"<!doctype html><meta charset='utf-8'><title>Informe NICS</title><style>{css}</style>",
             f"<h1>Infiltrados en la red · informe</h1><p>{datetime.now():%d/%m/%Y %H:%M} · {len(res)} servicios</p>",
             "<table><tr><th>Servicio</th><th>URL</th><th>Clase</th><th>Confianza</th><th>Qué lo delató</th></tr>",
             rows, "</table><h2>Detalle</h2>"]
    for _, r in res.iterrows():
        ev_items = "".join(f"<li><b>{e['regla']}</b> (+{e['peso']} {ETIQUETA.get(e['clase'], e['clase'])}): {html.escape(e['texto'])}</li>"
                           for e in sorted(r["evidencias"], key=lambda e: -e["peso"])) or "<li>Sin evidencias</li>"
        feat_rows = "".join(f"<tr><td>{k}</td><td>{html.escape(str(f.loc[r['servicio'], k]))}</td></tr>"
                            for k in RASGOS_CLAVE if k in f.columns)
        samples = "".join(f"<p><b>{s}</b></p><pre>{html.escape(_sample(ev, r['servicio'], s))}</pre>"
                          for s in ("raiz", "inexistente") if _sample(ev, r["servicio"], s))
        parts.append(f"<div class='card'><h3>{html.escape(r['servicio'])} · "
                     f"<span class='tag' style='background:{COLOR.get(r['clase'], '#555')}'>{ETIQUETA.get(r['clase'], r['clase'])}</span> "
                     f"{r['confianza']:.0%}</h3><ul>{ev_items}</ul><table>{feat_rows}</table>{samples}</div>")
    return "\n".join(parts)


def save(res: pd.DataFrame, feats: pd.DataFrame, ev: pd.DataFrame, out: Path) -> None:
    (out / "informe.md").write_text(markdown(res, feats, ev), encoding="utf-8")
    (out / "informe.html").write_text(html_report(res, feats, ev), encoding="utf-8")
