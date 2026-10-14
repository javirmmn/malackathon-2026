"""Kit NTT DATA · El Guardián: ¿la IA se ha inventado algo respecto a sus fuentes?

    python -m kits.ntt.run --data data/ntt_ensayo.csv                      (señales baratas, segundos)
    python -m kits.ntt.run --data data/ntt_ensayo.csv --llm                (+ juez LLM local con Ollama)
    python -m kits.ntt.run --data data/sorpresa.csv --modelo out/ntt/modelo.json   (prueba sorpresa: sin reentrenar)
    python -m kits.ntt.run --data data/test.csv --modelo out/ntt/modelo.json --entrega out/ntt/entrega.csv

Con columna de etiqueta (alucina / label...) entrena, mide por validación cruzada y guarda out/ntt/modelo.json.
Sin etiqueta aplica el modelo guardado (o pesos por defecto). Dashboard: streamlit run kits/ntt/app.py
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from common import OUT_DIR
from common.dataio import read_any

from . import report, scorer, signals
from .judges import LLMJudge, NLIJudge, ollama_available

DEFAULT_OUT = OUT_DIR / "ntt"
COLS = {
    "respuesta": ["respuesta", "response", "answer", "output", "generated", "generacion", "texto_ia", "respuesta_ia"],
    "fuentes": ["fuentes", "fuente", "contexto", "context", "sources", "source", "documentos", "documents", "passages", "evidence", "referencias"],
    "etiqueta": ["alucina", "alucinacion", "label", "etiqueta", "hallucination", "is_hallucination", "target", "y"],
    "id": ["id", "id_respuesta", "qid", "uid"],
}


def detect(df: pd.DataFrame, overrides: dict) -> dict:
    lower = {c.lower(): c for c in df.columns}
    found = {}
    for role, names in COLS.items():
        col = overrides.get(role) or next((lower[n] for n in names if n in lower), None)
        found[role] = col
    if not found["respuesta"] or not found["fuentes"]:
        raise SystemExit(f"No encuentro las columnas de respuesta/fuentes en {list(df.columns)}. Usa --col-respuesta y --col-fuentes.")
    return found


def _as_text(v) -> str:
    """Las fuentes pueden venir como texto, lista o JSON con varios documentos."""
    if isinstance(v, (list, tuple)):
        return "\n".join(map(str, v))
    if isinstance(v, str) and v.strip().startswith("["):
        try:
            return "\n".join(map(str, json.loads(v)))
        except json.JSONDecodeError:
            pass
    return "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def build_signals(df: pd.DataFrame, cols: dict, llm: bool = False, nli: bool = False, out: Path = DEFAULT_OUT) -> pd.DataFrame:
    resp = df[cols["respuesta"]].map(_as_text)
    fuen = df[cols["fuentes"]].map(_as_text)
    S = pd.DataFrame([signals.compute(r, f) for r, f in zip(resp, fuen)], index=df.index)
    if llm:
        if not ollama_available():
            print("      [aviso] Ollama no responde: sigo sin juez LLM")
        else:
            judge = LLMJudge(out / "cache_llm.json")
            t0 = time.time()
            res = []
            for i, (r, f) in enumerate(zip(resp, fuen), 1):
                res.append(judge.judge(r, f))
                if i % 10 == 0 or i == len(resp):
                    print(f"      juez LLM: {i}/{len(resp)} ({time.time() - t0:.0f} s)")
                    judge.save()
            S["llm_no_respaldada"] = [x["no_respaldada"] for x in res]
            S["_llm_motivo"] = [x["motivo"] for x in res]
    if nli:
        nj = NLIJudge()
        S = S.join(pd.DataFrame([nj.judge(r, f) for r, f in zip(resp, fuen)], index=df.index))
    return S


def run(df: pd.DataFrame, out: Path = DEFAULT_OUT, llm: bool = False, nli: bool = False, model_path: Path | None = None,
        metric: str = "f1", overrides: dict | None = None, entrega: Path | None = None) -> dict:
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    cols = detect(df, overrides or {})
    print(f"[1/4] {len(df)} respuestas · columnas: {cols}")

    S = build_signals(df, cols, llm=llm, nli=nli, out=out)
    feats = [c for c in S.columns if not c.startswith("_") and c != "n_afirmaciones"]
    print(f"[2/4] Señales: {', '.join(feats)}")

    y = df[cols["etiqueta"]].astype(int).to_numpy() if cols["etiqueta"] and not model_path else None
    cv = None
    if model_path:
        model = scorer.load(model_path)
        print(f"[3/4] Modelo aplicado tal cual: {model_path} (umbral {model['threshold']})")
    elif y is not None and len(set(y)) == 2:
        model, cv = scorer.train(S[feats], y, metric=metric)
        scorer.save(model, out / "modelo.json")
        print(f"[3/4] Entrenado con {len(y)} ejemplos · validación cruzada: "
              f"{metric}={cv[metric]} accuracy={cv['accuracy']} AUC={cv.get('auc')} · umbral={model['threshold']}")
    else:
        model = scorer.default_model(feats)
        print("[3/4] Sin etiquetas ni modelo: pesos por defecto (umbral 0,5)")

    prob = scorer.predict_proba(model, S)
    res = df.copy()
    res["prob_alucina"] = prob.round(3)
    res["prediccion"] = (prob >= model["threshold"]).astype(int)
    res["motivos"] = [" · ".join(signals.explain(s)) or "sin indicios" for s in S.to_dict("records")]
    res = res.join(S)
    res.to_csv(out / "resultados.csv", index=False, encoding="utf-8-sig")

    metrics = {"validacion_cruzada": cv}
    if cols["etiqueta"] and cols["etiqueta"] in df:
        metrics["sobre_estos_datos"] = scorer.evaluate(df[cols["etiqueta"]].astype(int).to_numpy(), prob, model["threshold"])
        if "tipo" in df:
            metrics["acierto_por_tipo"] = (res.assign(ok=res["prediccion"] == res[cols["etiqueta"]])
                                           .groupby("tipo")["ok"].mean().round(2).to_dict())
    (out / "metricas.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    report.save(res, cols, model, metrics, out / "informe.html")

    if entrega:
        idc = cols["id"] or "index"
        sub = res.reset_index()[[idc, "prediccion", "prob_alucina"]]
        sub.to_csv(entrega, index=False)
        print(f"      Fichero de entrega -> {entrega} (adaptad nombres de columnas al formato del ranking)")

    print(f"[4/4] Informe -> {out / 'informe.html'}  ({time.time() - t0:.0f} s)")
    if metrics.get("sobre_estos_datos"):
        m = metrics["sobre_estos_datos"]
        print(f"      Sobre estos datos: accuracy={m['accuracy']} f1={m['f1']} · matriz {m['matriz']}")
    if metrics.get("acierto_por_tipo"):
        print(f"      Acierto por tipo: {metrics['acierto_por_tipo']}")
    return {"model": model, "metrics": metrics, "results": res}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True, help="CSV/Excel/JSON con respuesta y fuentes (y etiqueta si la hay)")
    ap.add_argument("--llm", action="store_true", help="añadir el juez LLM local (Ollama). Lento: ~5 s por respuesta, con caché")
    ap.add_argument("--nli", action="store_true", help="añadir el modelo NLI (necesita torch + transformers)")
    ap.add_argument("--modelo", type=Path, help="aplicar un modelo.json ya entrenado (no reentrena)")
    ap.add_argument("--metrica", choices=list(scorer.METRICS), default="f1", help="métrica del ranking para elegir el umbral")
    ap.add_argument("--col-respuesta"), ap.add_argument("--col-fuentes"), ap.add_argument("--col-etiqueta"), ap.add_argument("--col-id")
    ap.add_argument("--entrega", type=Path, help="CSV con id y predicción para subir al ranking")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    df = read_any(a.data)
    if a.data.suffix.lower() == ".jsonl":
        df = pd.read_json(a.data, lines=True)
    overrides = {"respuesta": a.col_respuesta, "fuentes": a.col_fuentes, "etiqueta": a.col_etiqueta, "id": a.col_id}
    run(df, out=a.out, llm=a.llm, nli=a.nli, model_path=a.modelo, metric=a.metrica,
        overrides={k: v for k, v in overrides.items() if v}, entrega=a.entrega)


if __name__ == "__main__":
    main()
