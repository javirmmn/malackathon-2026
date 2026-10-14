"""Jueces opcionales: LLM local (Ollama) y modelo NLI (transformers). Si no están disponibles, se omiten.

LLM: OLLAMA_URL (por defecto http://127.0.0.1:11434) y OLLAMA_MODEL (por defecto llama3.2:3b).
Las respuestas del LLM se guardan en caché (out/ntt/cache_llm.json) para no repetir llamadas lentas.
NLI (opcional, ~2 GB): pip install torch transformers  y  NTT_NLI_MODEL (por defecto un mDeBERTa XNLI multilingüe).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
NLI_MODEL = os.getenv("NTT_NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")

PROMPT = """Eres un verificador estricto. Compara la RESPUESTA con las FUENTES.
Una respuesta está "respaldada" si TODO lo que afirma (cifras, fechas, nombres, hechos) aparece en las FUENTES
o se deduce directamente de ellas. Si añade, cambia o contradice algo, es "no_respaldada".
IMPORTANTE: que la respuesta sea corta u omita información de las FUENTES NO es motivo para rechazarla.
Comprueba solo si lo que SÍ dice es correcto. Expresiones como "alrededor de" o "casi" con la cifra exacta son correctas.

FUENTES:
{fuentes}

RESPUESTA:
{respuesta}

Contesta SOLO con JSON: {{"veredicto": "respaldada" | "no_respaldada", "motivo": "<frase corta en español>"}}"""


def ollama_available() -> bool:
    try:
        return httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


class LLMJudge:
    def __init__(self, cache_path: Path, model: str = OLLAMA_MODEL):
        self.model, self.cache_path = model, Path(cache_path)
        self.cache = json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}

    def _key(self, respuesta: str, fuentes: str) -> str:
        return hashlib.sha1(f"{self.model}\n{fuentes}\n{respuesta}".encode()).hexdigest()

    def judge(self, respuesta: str, fuentes: str) -> dict:
        key = self._key(respuesta, fuentes)
        if key not in self.cache:
            try:
                r = httpx.post(f"{OLLAMA_URL}/api/generate", timeout=120, json={
                    "model": self.model, "prompt": PROMPT.format(fuentes=fuentes, respuesta=respuesta),
                    "stream": False, "format": "json", "options": {"temperature": 0}})
                data = json.loads(r.json().get("response", "{}"))
                ver = str(data.get("veredicto", "")).lower()
                self.cache[key] = {"no_respaldada": int("no" in ver), "motivo": str(data.get("motivo", ""))[:200]}
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
                return {"no_respaldada": None, "motivo": f"error: {e}"}
        return self.cache[key]

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")


class NLIJudge:
    """Probabilidad de contradicción y de 'no implicación' entre fuentes (premisa) y respuesta (hipótesis)."""

    def __init__(self, model: str = NLI_MODEL):
        from transformers import pipeline  # import perezoso: solo si se pide --nli

        self.pipe = pipeline("text-classification", model=model, top_k=None, truncation=True)

    def judge(self, respuesta: str, fuentes: str) -> dict:
        scores = {d["label"].lower(): d["score"] for d in self.pipe({"text": fuentes, "text_pair": respuesta})}
        return {"nli_contradiccion": round(scores.get("contradiction", 0.0), 3),
                "nli_no_implica": round(1 - scores.get("entailment", 0.0), 3)}
