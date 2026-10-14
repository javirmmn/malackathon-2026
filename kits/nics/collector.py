"""Recolector de evidencias: envía las sondas de probes.yaml a cada servicio y guarda todo lo observado."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
MAX_BODY = 20_000


def load_probes(path: Path = HERE / "probes.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def _probe_service(client: httpx.AsyncClient, sem: asyncio.Semaphore, target: pd.Series, cfg: dict,
                         repeats: int) -> list[dict]:
    rows = []
    for probe in cfg["sondas"]:
        token = "zq" + secrets.token_hex(5)
        path = probe["ruta"].replace("{token}", token)
        n = repeats if probe.get("repetir") else 1
        for attempt in range(1, n + 1):
            url = target["url"] + path
            rec = {"servicio": target["name"], "url_base": target["url"], "sonda": probe["id"], "intento": attempt,
                   "metodo": probe["metodo"], "ruta": path, "token": token,
                   "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.request(probe["metodo"], url)
                    body = r.text[:MAX_BODY]
                    rec |= {"status": r.status_code, "latencia_ms": round(1000 * (time.perf_counter() - t0), 1),
                            "cabeceras": json.dumps(dict(r.headers), ensure_ascii=False), "cuerpo": body,
                            "longitud": len(r.content), "sha1": hashlib.sha1(r.content).hexdigest()[:16], "error": ""}
                except httpx.HTTPError as e:
                    rec |= {"status": None, "latencia_ms": round(1000 * (time.perf_counter() - t0), 1),
                            "cabeceras": "{}", "cuerpo": "", "longitud": 0, "sha1": "", "error": f"{type(e).__name__}: {e}"}
            rows.append(rec)
            await asyncio.sleep(cfg.get("pausa_ms", 0) / 1000)
    return rows


async def _collect(targets: pd.DataFrame, cfg: dict, repeats: int, verify_tls: bool) -> list[dict]:
    sem = asyncio.Semaphore(cfg.get("concurrencia", 6))
    limits = httpx.Limits(max_connections=cfg.get("concurrencia", 6))
    headers = {"User-Agent": cfg.get("user_agent", "malackathon-nics-kit")}
    async with httpx.AsyncClient(timeout=cfg.get("timeout_s", 20), verify=verify_tls, follow_redirects=False,
                                 limits=limits, headers=headers) as client:
        tasks = [_probe_service(client, sem, t, cfg, repeats) for _, t in targets.iterrows()]
        out = []
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            rows = await coro
            out += rows
            print(f"      [{i}/{len(tasks)}] {rows[0]['servicio']}: {len(rows)} respuestas")
        return out


def collect(targets: pd.DataFrame, cfg: dict | None = None, repeats: int | None = None, verify_tls: bool = False) -> pd.DataFrame:
    cfg = cfg or load_probes()
    return pd.DataFrame(asyncio.run(_collect(targets, cfg, repeats or cfg.get("repeticiones", 5), verify_tls)))
