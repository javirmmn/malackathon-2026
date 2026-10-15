"""Clasificador para servicios que NO son HTTP: SSH, FTP, Telnet, SMTP, POP3, IMAP.

La mayoría mandan un "banner" nada más conectar. Se repite la conexión varias veces (igual que la
sonda "raíz" de HTTP) y se mide si el banner es siempre igual (real/clásico) o cambia (sospecha de IA).
Para SMTP/POP3/IMAP/FTP se manda además un comando inocuo no válido, que un servidor real responde con
un código de error de protocolo fijo; un backend generativo tiende a "explicar" el error con texto libre.

    python -m kits.nics.protocolo --targets data/targets_otros.csv --repeticiones 5 --out out/nics_otros
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

from common import OUT_DIR

DEFAULT_OUT = OUT_DIR / "nics_otros"

# comando inocuo que no existe en el protocolo, para ver cómo reacciona al error (como la ruta inventada en HTTP)
COMANDO_INVALIDO = {"ftp": "ZQNOEXISTE\r\n", "smtp": "ZQNOEXISTE\r\n", "pop3": "ZQNOEXISTE\r\n", "imap": "a1 ZQNOEXISTE\r\n"}


@dataclass
class Resultado:
    servicio: str
    host: str
    puerto: int
    protocolo: str
    intento: int
    banner: str
    error_banner: str
    respuesta_invalida: str
    error_invalida: str
    latencia_ms: float


async def _leer(reader: asyncio.StreamReader, timeout: float) -> str:
    try:
        data = await asyncio.wait_for(reader.read(2048), timeout=timeout)
        return data.decode("utf-8", errors="replace").strip()
    except (asyncio.TimeoutError, ConnectionError):
        return ""


async def _probe_once(host: str, port: int, protocolo: str, timeout: float) -> tuple[str, str, str, str, float]:
    t0 = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    except (OSError, asyncio.TimeoutError) as e:
        return "", f"{type(e).__name__}: {e}", "", "", round(1000 * (time.perf_counter() - t0), 1)

    banner, err_banner, resp_inv, err_inv = "", "", "", ""
    try:
        banner = await _leer(reader, timeout)
        cmd = COMANDO_INVALIDO.get(protocolo)
        if cmd:
            if protocolo == "imap" and not banner:  # IMAP a veces no manda banner hasta el primer comando
                pass
            try:
                writer.write(cmd.encode())
                await writer.drain()
                resp_inv = await _leer(reader, timeout)
            except (ConnectionError, OSError) as e:
                err_inv = f"{type(e).__name__}: {e}"
    except (ConnectionError, OSError) as e:
        err_banner = f"{type(e).__name__}: {e}"
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
    return banner, err_banner, resp_inv, err_inv, round(1000 * (time.perf_counter() - t0), 1)


async def _probe_service(sem: asyncio.Semaphore, row: pd.Series, repeticiones: int, timeout: float) -> list[Resultado]:
    out = []
    for i in range(1, repeticiones + 1):
        async with sem:
            banner, eb, ri, ei, lat = await _probe_once(row["host"], int(row["port"]), row["protocolo"], timeout)
        out.append(Resultado(row["name"], row["host"], int(row["port"]), row["protocolo"], i, banner, eb, ri, ei, lat))
        await asyncio.sleep(0.1)
    return out


async def _collect(targets: pd.DataFrame, repeticiones: int, timeout: float, concurrencia: int) -> pd.DataFrame:
    sem = asyncio.Semaphore(concurrencia)
    rows = list(itertools.chain.from_iterable(
        await asyncio.gather(*[_probe_service(sem, r, repeticiones, timeout) for _, r in targets.iterrows()])
    ))
    return pd.DataFrame([r.__dict__ for r in rows])


def features(ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, g in ev.groupby("servicio", sort=False):
        banners = [b for b in g["banner"] if b]
        sim = (sum(fuzz.ratio(a, b) for a, b in itertools.combinations(banners, 2)) /
               max(1, len(list(itertools.combinations(banners, 2))))) if len(banners) > 1 else (100.0 if banners else 0.0)
        invalidas = [r for r in g["respuesta_invalida"] if r]
        sim_inv = (sum(fuzz.ratio(a, b) for a, b in itertools.combinations(invalidas, 2)) /
                   max(1, len(list(itertools.combinations(invalidas, 2))))) if len(invalidas) > 1 else (100.0 if invalidas else 0.0)
        lat = g["latencia_ms"].astype(float)
        rows.append({
            "servicio": name, "host": g["host"].iat[0], "puerto": int(g["puerto"].iat[0]), "protocolo": g["protocolo"].iat[0],
            "intentos_ok": int((g["banner"] != "").sum()), "sin_banner": int((g["banner"] == "").sum()),
            "banner_ejemplo": banners[0] if banners else "",
            "consistencia_banner": round(sim, 1), "hay_banner": bool(banners),
            "respuesta_invalida_ejemplo": invalidas[0] if invalidas else "",
            "consistencia_invalida": round(sim_inv, 1),
            "latencia_media_ms": round(lat.mean(), 1), "latencia_cv": round(lat.std(ddof=0) / lat.mean(), 3) if lat.mean() else 0.0,
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", type=Path, required=True, help="CSV con name,host,port,protocolo")
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--concurrencia", type=int, default=4)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    targets = pd.read_csv(a.targets)
    print(f"[1/2] {len(targets)} servicios no-HTTP · {a.repeticiones} repeticiones")
    ev = asyncio.run(_collect(targets, a.repeticiones, a.timeout, a.concurrencia))
    ev.to_csv(a.out / "evidencias_protocolo.csv", index=False, encoding="utf-8-sig")
    f = features(ev)
    f.to_csv(a.out / "rasgos_protocolo.csv", index=False, encoding="utf-8-sig")
    print(f"[2/2] -> {a.out / 'rasgos_protocolo.csv'}")
    with pd.option_context("display.max_colwidth", 60, "display.width", 200):
        print(f[["servicio", "protocolo", "intentos_ok", "consistencia_banner", "consistencia_invalida",
                "latencia_media_ms", "banner_ejemplo"]].to_string(index=False))


if __name__ == "__main__":
    main()
