"""Clasificador por reglas con pesos (rules.yaml): clase, confianza y evidencias legibles por servicio."""

from __future__ import annotations

import operator
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent

_OPS = {
    ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne,
    "en": lambda a, b: a in b, "contiene": lambda a, b: str(b).lower() in str(a).lower(),
}


def load_rules(path: Path = HERE / "rules.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _fires(rule: dict, feats: dict) -> bool:
    value = feats.get(rule["variable"])
    if value is None or (isinstance(value, float) and value != value):  # None o NaN: la regla no aplica
        return False
    try:
        return bool(_OPS[rule["op"]](value, rule["valor"]))
    except TypeError:
        return False


def _text(rule: dict, feats: dict) -> str:
    try:
        return rule["evidencia"].format(**feats)
    except (KeyError, ValueError, IndexError):
        return rule["evidencia"]


def classify(features: pd.DataFrame, rules: dict) -> pd.DataFrame:
    rows = []
    for _, f in features.iterrows():
        feats = f.to_dict()
        scores = dict(rules.get("previa", {}))
        for c in rules["clases"]:
            scores.setdefault(c, 0.0)
        fired = []
        for r in rules["reglas"]:
            if _fires(r, feats):
                scores[r["clase"]] += r["peso"]
                fired.append({"regla": r["id"], "clase": r["clase"], "peso": r["peso"], "texto": _text(r, feats)})
        total = sum(scores.values()) or 1.0
        best = max(scores, key=scores.get)
        delata = [e for e in sorted(fired, key=lambda e: -e["peso"]) if e["clase"] == best]
        rows.append({
            "servicio": feats["servicio"],
            "url_base": feats["url_base"],
            "clase": best,
            "confianza": round(scores[best] / total, 2),
            **{f"puntos_{c}": round(s, 2) for c, s in scores.items()},
            "que_lo_delato": delata[0]["texto"] if delata else "sin evidencias claras",
            "evidencias": fired,
        })
    return pd.DataFrame(rows)
