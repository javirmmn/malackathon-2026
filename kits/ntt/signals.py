"""Señales de alucinación: comparan la respuesta de la IA con sus fuentes (texto en español).

Todas devuelven números fáciles de explicar ("hay 2 cifras en la respuesta que no están en las fuentes").
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

MESES = {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "setiembre",
         "octubre", "noviembre", "diciembre"}
STOP = set("""a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo bien cada casi como con
contra cual cuales cuando cuanto de del desde donde dos el ella ellas ellos en entre era eran es esa esas ese eso esos
esta estaba estado estan estar estas este esto estos fue fueron gran ha habia han hasta hay la las le les lo los mas me
mi mientras mismo muy nada ni no nos nuestra nuestro o os otra otras otro otros para pero poco por porque que quien se
sea segun ser si sido siempre sin sobre solo son su sus tambien tan tanto te tenia tiene tienen todo todos tras tu un
una uno unos usted ya y yo ademas alrededor cerca principalmente sobre todo actualmente""".split())
NEGACIONES = {"no", "nunca", "jamas", "ningun", "ninguna", "ninguno", "tampoco", "nadie", "nada"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", str(text).strip())
    return [p.strip() for p in parts if len(p.split()) >= 3]


def numbers(text: str) -> set[str]:
    """Cifras normalizadas: '1.234,5' / '1,234.5' / '1234.5' -> '1234.5'; '12 %' -> '12'."""
    out = set()
    for raw in re.findall(r"\d+(?:[.,]\d+)*", str(text)):
        s = raw
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".") if len(s.split(",")[-1]) != 3 else s.replace(",", "")
        elif s.count(".") >= 1 and all(len(g) == 3 for g in s.split(".")[1:]):
            s = s.replace(".", "")
        try:
            v = float(s)
            out.add(str(int(v)) if v.is_integer() else str(v))
        except ValueError:
            pass
    return out


def entities(text: str) -> set[str]:
    """Nombres propios aproximados: secuencias de palabras en mayúscula que no abren frase."""
    ents = set()
    for sent in sentences(text) or [str(text)]:
        tokens = re.findall(r"[A-ZÁÉÍÓÚÑa-záéíóúñü][\wáéíóúñü]*", sent)
        cur = []
        for i, tok in enumerate(tokens):
            if tok[0].isupper() and (i > 0 or len(tokens) == 1) and norm(tok) not in STOP:
                cur.append(tok)
            else:
                if cur:
                    ents.add(" ".join(cur))
                cur = []
        if cur:
            ents.add(" ".join(cur))
    return {e for e in ents if len(e) > 2}


def content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]+", norm(text)) if len(w) > 3 and w not in STOP]


def _stem(w: str) -> str:
    return w[:6]


def best_support(claim: str, source_sents: list[str]) -> float:
    """0–100: cuánto se parece la afirmación a la frase más parecida de las fuentes."""
    if not source_sents:
        return 0.0
    c = norm(claim)
    return max(fuzz.token_set_ratio(c, norm(s)) for s in source_sents)


def compute(respuesta: str, fuentes: str) -> dict:
    src_n = norm(fuentes)
    src_sents = sentences(fuentes)
    claims = sentences(respuesta) or [str(respuesta)]

    nums_r, nums_s = numbers(respuesta), numbers(fuentes)
    nums_bad = sorted(nums_r - nums_s, key=len)
    meses_r = {m for m in MESES if re.search(rf"\b{m}\b", norm(respuesta))}
    meses_bad = sorted(m for m in meses_r if not re.search(rf"\b{m}\b", src_n))
    ents_bad = sorted(e for e in entities(respuesta) if norm(e) not in src_n)

    src_stems = {_stem(w) for w in content_words(fuentes)}
    words = content_words(respuesta)
    new_words = [w for w in words if _stem(w) not in src_stems]

    supports = [best_support(c, src_sents) for c in claims]
    weak = [c for c, s in zip(claims, supports) if s < 70]

    neg_r = {w for w in re.findall(r"[a-z]+", norm(respuesta)) if w in NEGACIONES}
    neg_s = {w for w in re.findall(r"[a-z]+", src_n) if w in NEGACIONES}

    return {
        "n_afirmaciones": len(claims),
        "cifras_no_en_fuentes": len(nums_bad),
        "meses_no_en_fuentes": len(meses_bad),
        "nombres_no_en_fuentes": len(ents_bad),
        "palabras_nuevas_pct": round(100 * len(new_words) / max(1, len(words)), 1),
        "apoyo_min": round(min(supports), 1),
        "apoyo_medio": round(sum(supports) / len(supports), 1),
        "afirmaciones_debiles": len(weak),
        "negacion_nueva": int(bool(neg_r - neg_s)),
        # detalle para explicar la decisión
        "_cifras": ", ".join(nums_bad),
        "_meses": ", ".join(meses_bad),
        "_nombres": ", ".join(ents_bad),
        "_palabras_nuevas": ", ".join(sorted(set(new_words))[:12]),
        "_debiles": " | ".join(weak),
        "_negaciones": ", ".join(sorted(neg_r - neg_s)),
    }


FEATURES = ["cifras_no_en_fuentes", "meses_no_en_fuentes", "nombres_no_en_fuentes", "palabras_nuevas_pct",
            "apoyo_min", "apoyo_medio", "afirmaciones_debiles", "negacion_nueva"]


def explain(sig: dict) -> list[str]:
    """Motivos legibles para el informe y el dashboard."""
    out = []
    if sig["cifras_no_en_fuentes"]:
        out.append(f"Cifras que no aparecen en las fuentes: {sig['_cifras']}")
    if sig["meses_no_en_fuentes"]:
        out.append(f"Fechas (meses) que no aparecen en las fuentes: {sig['_meses']}")
    if sig["nombres_no_en_fuentes"]:
        out.append(f"Nombres propios que no aparecen en las fuentes: {sig['_nombres']}")
    if sig["negacion_nueva"]:
        out.append(f"Introduce una negación que las fuentes no tienen ({sig['_negaciones']}): posible contradicción")
    if sig["afirmaciones_debiles"]:
        out.append(f"Afirmaciones sin una frase parecida en las fuentes: {sig['_debiles']}")
    if sig["palabras_nuevas_pct"] >= 35:
        out.append(f"{sig['palabras_nuevas_pct']:.0f} % de palabras con contenido que no están en las fuentes "
                   f"({sig['_palabras_nuevas']})")
    if sig.get("llm_no_respaldada"):
        out.append(f"El juez LLM la considera no respaldada: {sig.get('_llm_motivo', '')}")
    if sig.get("nli_contradiccion", 0) > 0.5:
        out.append(f"El modelo NLI detecta contradicción ({sig['nli_contradiccion']:.2f})")
    return out
