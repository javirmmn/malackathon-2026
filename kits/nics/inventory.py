"""Inventario de servicios a analizar y control de alcance (solo se escanea lo autorizado).

Formatos aceptados (CSV o YAML), columnas:
    url                                  -> http://10.0.0.5:8080/
    host, port[, path][, scheme]         -> se compone la URL
    name (opcional), etiqueta_real (opcional, solo para medir aciertos en ensayos)
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import yaml

from common.dataio import read_any

LOCAL = ["127.0.0.0/8", "::1/128", "localhost"]


def load_targets(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        df = pd.DataFrame(data["servicios"] if isinstance(data, dict) else data)
    else:
        df = read_any(path)
    df.columns = [c.strip().lower() for c in df.columns]

    if "url" not in df:
        if not {"host", "port"} <= set(df.columns):
            raise ValueError("El inventario necesita una columna 'url' o las columnas 'host' y 'port'.")
        scheme = df["scheme"] if "scheme" in df else df["port"].map(lambda p: "https" if int(p) in (443, 8443) else "http")
        pth = df["path"].fillna("/") if "path" in df else "/"
        df["url"] = scheme + "://" + df["host"].astype(str) + ":" + df["port"].astype(int).astype(str) + pth
    df["url"] = df["url"].astype(str).str.strip().str.rstrip("/")
    if "name" not in df:
        df["name"] = df["url"].map(lambda u: urlparse(u).netloc)
    df = df.drop_duplicates("url").reset_index(drop=True)
    return df[["name", "url"] + [c for c in df.columns if c not in ("name", "url")]]


def _in_scope(host: str, allowed: list[str]) -> bool:
    try:
        ips = {ipaddress.ip_address(host)}
    except ValueError:
        if host in allowed:
            return True
        ips = {ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(host, None)}
    nets = []
    for a in allowed:
        try:
            nets.append(ipaddress.ip_network(a, strict=False))
        except ValueError:
            try:
                nets += [ipaddress.ip_network(x[4][0]) for x in socket.getaddrinfo(a, None)]
            except socket.gaierror:
                pass
    return all(any(ip in n for n in nets) for ip in ips)


def check_scope(targets: pd.DataFrame, scope: list[str] | None) -> None:
    """Aborta si algún objetivo está fuera del alcance autorizado (por defecto solo localhost)."""
    allowed = (scope or []) + LOCAL
    fuera = [u for u in targets["url"] if not _in_scope(urlparse(u).hostname or "", allowed)]
    if fuera:
        raise SystemExit(
            "Objetivos FUERA del alcance autorizado (no se escanea nada):\n  " + "\n  ".join(fuera)
            + "\nIndica el rango del reto con --scope, p. ej. --scope 10.10.0.0/16"
        )
