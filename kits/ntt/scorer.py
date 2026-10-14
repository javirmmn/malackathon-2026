"""Combina las señales en una probabilidad de alucinación y elige el umbral.

- Sin etiquetas: pesos por defecto razonables (reglas).
- Con etiquetas: regresión logística (pocas variables -> no sobreajusta y los pesos se pueden explicar),
  métricas honestas por validación cruzada y umbral elegido para la métrica del ranking.
El modelo se guarda en JSON para aplicarlo tal cual a datos nuevos (prueba sorpresa) sin reentrenar.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Pesos por defecto (sin etiquetas): cada señal empuja hacia "alucina"
DEFAULT = {
    # Una sola cifra, fecha, nombre o negación que no está en las fuentes basta para superar el umbral 0,5
    "intercept": -1.5,
    "coef": {"cifras_no_en_fuentes": 3.0, "meses_no_en_fuentes": 2.5, "nombres_no_en_fuentes": 2.5,
             # señales "suaves": una paráfrasis las activa, así que solas no deben bastar
             "negacion_nueva": 3.0, "afirmaciones_debiles": 0.5, "palabras_nuevas_pct": 0.02,
             "apoyo_min": -0.03, "apoyo_medio": 0.0, "llm_no_respaldada": 1.5, "nli_contradiccion": 3.0,
             "nli_no_implica": 1.0},
    "center": {"apoyo_min": 70.0, "palabras_nuevas_pct": 30.0},
    "threshold": 0.5,
}

METRICS = {"f1": f1_score, "accuracy": accuracy_score, "precision": precision_score, "recall": recall_score}


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


def default_model(features: list[str]) -> dict:
    return {"tipo": "reglas", "features": features, "intercept": DEFAULT["intercept"],
            "coef": {f: DEFAULT["coef"].get(f, 0.0) for f in features}, "mean": {f: DEFAULT["center"].get(f, 0.0) for f in features},
            "scale": {f: 1.0 for f in features}, "threshold": DEFAULT["threshold"]}


def predict_proba(model: dict, X: pd.DataFrame) -> np.ndarray:
    z = np.full(len(X), model["intercept"], dtype=float)
    for f in model["features"]:
        x = X[f].astype(float).fillna(model["mean"][f]) if f in X else pd.Series(model["mean"][f], index=X.index)
        z += model["coef"][f] * (x.to_numpy() - model["mean"][f]) / model["scale"][f]
    return _sigmoid(z)


def contributions(model: dict, row: pd.Series) -> dict:
    """Cuánto empuja cada señal hacia 'alucina' (+) o 'fiel' (−) en un caso concreto."""
    out = {}
    for f in model["features"]:
        v = row.get(f)
        v = model["mean"][f] if v is None or v != v else float(v)
        out[f] = round(model["coef"][f] * (v - model["mean"][f]) / model["scale"][f], 2)
    return dict(sorted(out.items(), key=lambda kv: -abs(kv[1])))


def best_threshold(y: np.ndarray, p: np.ndarray, metric: str) -> tuple[float, float]:
    fn = METRICS[metric]
    grid = np.round(np.arange(0.05, 0.96, 0.01), 2)
    scores = [fn(y, (p >= t).astype(int), **({"zero_division": 0} if metric != "accuracy" else {})) for t in grid]
    i = int(np.argmax(scores))
    return float(grid[i]), float(scores[i])


def evaluate(y: np.ndarray, p: np.ndarray, t: float) -> dict:
    yhat = (p >= t).astype(int)
    out = {"n": int(len(y)), "umbral": t, "accuracy": accuracy_score(y, yhat), "precision": precision_score(y, yhat, zero_division=0),
           "recall": recall_score(y, yhat, zero_division=0), "f1": f1_score(y, yhat, zero_division=0)}
    if len(set(y)) > 1:
        out["auc"] = roc_auc_score(y, p)
    out["matriz"] = {"VP": int(((yhat == 1) & (y == 1)).sum()), "FP": int(((yhat == 1) & (y == 0)).sum()),
                     "FN": int(((yhat == 0) & (y == 1)).sum()), "VN": int(((yhat == 0) & (y == 0)).sum())}
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items()}


def train(X: pd.DataFrame, y: np.ndarray, metric: str = "f1", seed: int = 42) -> tuple[dict, dict]:
    """Ajusta la logística. Devuelve (modelo, métricas de validación cruzada)."""
    feats = [f for f in X.columns if X[f].notna().any() and X[f].nunique() > 1]
    Xf = X[feats].astype(float).fillna(X[feats].median())
    pipe = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000))
    folds = StratifiedKFold(n_splits=min(5, int(np.bincount(y).min())), shuffle=True, random_state=seed)
    p_cv = cross_val_predict(pipe, Xf, y, cv=folds, method="predict_proba")[:, 1]
    t, _ = best_threshold(y, p_cv, metric)
    cv = evaluate(y, p_cv, t)

    pipe.fit(Xf, y)
    sc, lr = pipe.named_steps["standardscaler"], pipe.named_steps["logisticregression"]
    model = {"tipo": "logistica", "features": feats, "intercept": float(lr.intercept_[0]),
             "coef": dict(zip(feats, map(float, lr.coef_[0]))), "mean": dict(zip(feats, map(float, sc.mean_))),
             "scale": dict(zip(feats, map(float, np.where(sc.scale_ == 0, 1, sc.scale_)))), "threshold": t,
             "metrica": metric, "entrenado": datetime.now().isoformat(timespec="minutes"), "n_entrenamiento": int(len(y))}
    return model, cv


def save(model: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
