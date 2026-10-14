"""Inventario de servicios a analizar y control de alcance (solo se escanea lo autorizado).

Formatos aceptados (CSV o YAML), columnas:
    url                                  -> http://10.0.0.5:8080/
    host, port[, path][, scheme]         -> se compone la URL
    name (opcional), etiqueta_real (opcional, solo para medir aciertos en ensayos)
"""

from __future__ import annotations

import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import yaml

from common.dataio import read_any

LOCAL = ["127.0.0.0/8", "::1/128", "localhost"]


def _fmt_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _web_url(host: str, port: int, name: str = "", tunnel: str = "") -> str:
    ssl = tunnel == "ssl" or "https" in name or "ssl" in name or port in (443, 8443)
    return f"{'https' if ssl else 'http'}://{_fmt_host(host)}:{port}"


def _from_xml(path: Path) -> pd.DataFrame:
    """Lista de servicios web abiertos a partir de un resultado XML guardado (formato nmap -oX)."""
    rows = []
    for host in ET.parse(path).getroot().iter("host"):
        addr = next((a.get("addr") for a in host.findall("address") if a.get("addrtype") in ("ipv4", "ipv6")), None)
        for p in host.iter("port"):
            st, svc = p.find("state"), p.find("service")
            name = (svc.get("name") or "") if svc is not None else ""
            if addr and st is not None and st.get("state") == "open" and "http" in name:
                rows.append({"url": _web_url(addr, int(p.get("portid")), name, (svc.get("tunnel") or "") if svc is not None else "")})
    return pd.DataFrame(rows, columns=["url"])


_GNMAP_PORT = re.compile(r"(\d+)/open/tcp//([^/]*)/")


def _from_gnmap(path: Path) -> pd.DataFrame:
    """Idem a partir del formato "grepable" guardado (nmap -oG)."""
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"Host:\s+(\S+)", line)
        if m and "Ports:" in line:
            for port, name in _GNMAP_PORT.findall(line):
                if "http" in name:
                    rows.append({"url": _web_url(m.group(1), int(port), name)})
    return pd.DataFrame(rows, columns=["url"])


def _from_text(path: Path) -> pd.DataFrame:
    """Un servicio por línea: URL completa o host:puerto. Se ignoran líneas vacías y las que empiezan por #."""
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            rows.append({"url": line})
        else:
            host, _, port = line.rpartition(":")
            if not host or not port.isdigit():
                raise ValueError(f"Línea no válida (usa host:puerto o una URL): {line!r}")
            rows.append({"url": _web_url(host, int(port))})
    return pd.DataFrame(rows, columns=["url"])


def load_targets(path: str | Path) -> pd.DataFrame:
    """Inventario desde CSV/YAML/XLSX, desde un .txt (host:puerto o URL por línea) o desde un resultado guardado
    de descubrimiento (.xml / .gnmap). Ver check_scope: nada se sondea sin comprobar el alcance autorizado."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext in {".yaml", ".yml"}:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        df = pd.DataFrame(data["servicios"] if isinstance(data, dict) else data)
    elif ext == ".xml":
        df = _from_xml(path)
    elif ext in {".gnmap", ".nmap"}:
        df = _from_gnmap(path)
    elif ext == ".txt":
        df = _from_text(path)
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
