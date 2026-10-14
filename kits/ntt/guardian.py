"""API de una sola llamada para enchufar el detector al bot de ejemplo del reto.

    from kits.ntt.guardian import Guardian
    g = Guardian("out/ntt/modelo.json", llm=False)
    g.evaluar(respuesta="...", fuentes=["doc 1", "doc 2"])
    -> {"alucina": True, "prob": 0.93, "motivos": ["Cifras que no aparecen en las fuentes: 195"], ...}
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from common import OUT_DIR

from . import scorer, signals
from .judges import LLMJudge, ollama_available


class Guardian:
    def __init__(self, modelo: str | Path | None = OUT_DIR / "ntt" / "modelo.json", llm: bool = False):
        self.model = scorer.load(modelo) if modelo and Path(modelo).exists() else None
        self.llm = LLMJudge(OUT_DIR / "ntt" / "cache_llm.json") if llm and ollama_available() else None

    def evaluar(self, respuesta: str, fuentes: str | list[str]) -> dict:
        fuentes = "\n".join(fuentes) if isinstance(fuentes, (list, tuple)) else str(fuentes)
        sig = signals.compute(respuesta, fuentes)
        if self.llm:
            j = self.llm.judge(respuesta, fuentes)
            sig["llm_no_respaldada"], sig["_llm_motivo"] = j["no_respaldada"], j["motivo"]
            self.llm.save()
        feats = [k for k in sig if not k.startswith("_") and k != "n_afirmaciones"]
        model = self.model or scorer.default_model(feats)
        row = pd.DataFrame([sig])
        prob = float(scorer.predict_proba(model, row)[0])
        return {"alucina": prob >= model["threshold"], "prob": round(prob, 3), "motivos": signals.explain(sig),
                "contribuciones": scorer.contributions(model, row.iloc[0]), "senales": sig}
