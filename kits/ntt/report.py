"""Informe HTML: métricas, pesos del modelo y cada respuesta con sus motivos."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

CSS = ("body{font-family:'Segoe UI',Arial,sans-serif;max-width:1150px;margin:24px auto;padding:0 16px;color:#1d2433}"
       "h1,h2{color:#0b5cad}table{border-collapse:collapse;font-size:13px}th,td{border:1px solid #d9dee7;padding:4px 8px;"
       "text-align:left;vertical-align:top}th{background:#e8f1fb}.si{color:#fff;background:#b4410c;border-radius:4px;padding:1px 6px}"
       ".no{color:#fff;background:#1d7a46;border-radius:4px;padding:1px 6px}mark{background:#ffd8c2}.muted{color:#5b6475}")


def highlight(text: str, row: pd.Series) -> str:
    """Resalta en la respuesta las cifras y nombres que no están en las fuentes."""
    out = html.escape(str(text))
    for field in ("_cifras", "_nombres", "_meses", "_negaciones"):
        for tok in [t.strip() for t in str(row.get(field, "") or "").split(",") if t.strip()]:
            out = re.sub(rf"(?<![\w.,]){re.escape(html.escape(tok))}(?![\w])", lambda m: f"<mark>{m.group(0)}</mark>", out)
    return out


def save(res: pd.DataFrame, cols: dict, model: dict, metrics: dict, path: Path) -> Path:
    parts = [f"<!doctype html><meta charset='utf-8'><title>El Guardián</title><style>{CSS}</style>",
             "<h1>El Guardián · detección de alucinaciones</h1>",
             f"<p class='muted'>{len(res)} respuestas · {int(res['prediccion'].sum())} marcadas como alucinación · "
             f"modelo: {model.get('tipo')} · umbral {model['threshold']}</p>"]
    for name, m in metrics.items():
        if isinstance(m, dict) and "accuracy" in m:
            parts.append(f"<h2>Métricas ({name.replace('_', ' ')})</h2><table><tr>" +
                         "".join(f"<th>{k}</th>" for k in m if k != "matriz") + "<th>matriz</th></tr><tr>" +
                         "".join(f"<td>{v}</td>" for k, v in m.items() if k != "matriz") + f"<td>{m['matriz']}</td></tr></table>")
    if metrics.get("acierto_por_tipo"):
        parts.append("<h2>Acierto por tipo</h2><table>" + "".join(
            f"<tr><td>{k}</td><td>{v:.0%}</td></tr>" for k, v in metrics["acierto_por_tipo"].items()) + "</table>")
    parts.append("<h2>Peso de cada señal</h2><p class='muted'>Positivo empuja hacia 'alucina'.</p><table>" + "".join(
        f"<tr><td>{f}</td><td>{c:+.2f}</td></tr>" for f, c in sorted(model["coef"].items(), key=lambda kv: -abs(kv[1]))) + "</table>")
    parts.append("<h2>Respuestas</h2><table><tr><th>id</th><th>¿Alucina?</th><th>prob</th><th>Respuesta (resaltado: no está en las fuentes)</th><th>Motivos</th></tr>")
    order = res.sort_values("prob_alucina", ascending=False)
    for i, r in order.iterrows():
        rid = r[cols["id"]] if cols.get("id") else i
        tag = "<span class='si'>sí</span>" if r["prediccion"] else "<span class='no'>no</span>"
        parts.append(f"<tr><td>{rid}</td><td>{tag}</td><td>{r['prob_alucina']:.2f}</td>"
                     f"<td>{highlight(r[cols['respuesta']], r)}</td><td>{html.escape(str(r['motivos']))}</td></tr>")
    parts.append("</table>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
