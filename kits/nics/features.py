"""Rasgos por servicio a partir de las evidencias: consistencia, latencia, coherencia del protocolo y firmas."""

from __future__ import annotations

import itertools
import json
import re

import numpy as np
import pandas as pd
from rapidfuzz import fuzz


def _similarity(bodies: list[str]) -> float:
    """Similitud media (0–100) entre todas las parejas de respuestas a la misma petición."""
    bodies = [b for b in bodies if isinstance(b, str)]
    if len(bodies) < 2:
        return np.nan
    pairs = list(itertools.combinations(bodies, 2))
    return float(np.mean([fuzz.ratio(a[:5000], b[:5000]) for a, b in pairs]))


def _mode(s: pd.Series):
    s = s.dropna()
    return s.mode().iat[0] if not s.empty else None


def _int(v):
    return int(v) if v is not None and v == v else None


def _matches(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, re.I)]


def service_features(ev: pd.DataFrame, rules: dict) -> pd.DataFrame:
    rows = []
    for name, g in ev.groupby("servicio", sort=False):
        ok = g[g["error"].fillna("") == ""]
        by = {k: v for k, v in ok.groupby("sonda")}
        root = by.get("raiz", ok.iloc[:0])
        nonex = by.get("inexistente", ok.iloc[:0])
        api = by.get("api_inventada", ok.iloc[:0])
        opts = by.get("options", ok.iloc[:0])

        headers = [json.loads(h) for h in ok["cabeceras"]]
        lower = [{k.lower(): v for k, v in h.items()} for h in headers]
        servers = sorted({h.get("server", "") for h in lower} - {""})
        all_text = "\n".join(ok["cuerpo"].fillna("").tolist() + [json.dumps(h) for h in headers])
        gen_text = "\n".join(pd.concat([root, nonex, api])["cuerpo"].fillna(""))

        root_body = _mode(root["cuerpo"]) or ""
        nonex_status = _mode(nonex["status"])
        nonex_vs_root = fuzz.ratio(root_body[:5000], (_mode(nonex["cuerpo"]) or "")[:5000]) if len(nonex) else np.nan
        eco = any(t in b for t, b in zip(pd.concat([nonex, api])["token"], pd.concat([nonex, api])["cuerpo"].fillna("")))
        api_ok = api[api["status"] == 200]
        api_json = bool(len(api_ok)) and any(
            "json" in json.loads(h).get("content-type", json.loads(h).get("Content-Type", "")) or str(b).lstrip().startswith(("{", "["))
            for h, b in zip(api_ok["cabeceras"], api_ok["cuerpo"])
        )
        firmas = _matches(rules.get("firmas_honeypot", []), all_text)
        llm = _matches(rules.get("marcas_llm", []), gen_text)
        lat = ok["latencia_ms"].astype(float).sort_values()
        lat = lat.iloc[: max(2, len(lat) - max(1, len(lat) // 20))]  # sin el 5 % más lento (abrir conexión, picos)

        rows.append({
            "servicio": name,
            "url_base": g["url_base"].iat[0],
            "respuestas_ok": len(ok),
            "errores": int((g["error"].fillna("") != "").sum()),
            "status_raiz": _int(_mode(root["status"])),
            "consistencia_raiz": round(_similarity(root["cuerpo"].tolist()), 1),
            "hashes_distintos_raiz": int(root["sha1"].nunique()),
            "inexistente_status": _int(nonex_status),
            "consistencia_inexistente": round(_similarity(nonex["cuerpo"].tolist()), 1),
            "inexistente_vs_raiz": round(nonex_vs_root, 1) if nonex_vs_root == nonex_vs_root else np.nan,
            "catch_all": bool(nonex_status == 200 and nonex_vs_root >= 95),
            "eco_token_200": bool(eco and nonex_status == 200),
            "api_json_inventado": bool(api_json),
            "latencia_media_ms": round(lat.mean(), 1),
            "latencia_std_ms": round(lat.std(ddof=0), 1),
            "latencia_cv": round(lat.std(ddof=0) / lat.mean(), 3) if lat.mean() else 0.0,
            # con pocos ms cualquier variación parece grande: solo cuenta si además es lenta
            "latencia_irregular": bool(lat.mean() > 100 and lat.std(ddof=0) / lat.mean() > 0.35),
            "timeouts": int(g["error"].fillna("").str.contains("Timeout").sum()),
            "server": ", ".join(servers),
            "server_variable": len(servers) > 1,
            "server_obsoleto": bool(_matches(rules.get("server_obsoleto", []), " ".join(servers))),
            "falta_date": bool(lower) and not all("date" in h for h in lower),
            "metodos_igual_respuesta": bool(len(opts)) and fuzz.ratio(root_body[:5000], (_mode(opts["cuerpo"]) or "")[:5000]) >= 95 and len(root_body) > 0,
            "firmas_honeypot": len(firmas),
            "firmas_honeypot_txt": ", ".join(firmas),
            "marcas_llm": len(llm),
            "marcas_llm_txt": ", ".join(llm),
        })
    return pd.DataFrame(rows)
