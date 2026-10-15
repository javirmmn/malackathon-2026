"""Comprobaciones extra, pensadas para nuestro escenario (un único host, 10.66.0.1, con decenas de
servicios simulados detrás): reutilización de certificado TLS, latencia frente al tamaño de la
respuesta (huella de un backend generativo) y coherencia de los recursos enlazados (CSS/JS/imágenes).

    python -m kits.nics.forense_extra --tls
    python -m kits.nics.forense_extra --latencia
    python -m kits.nics.forense_extra --assets
    python -m kits.nics.forense_extra --todo
"""

from __future__ import annotations

import argparse
import hashlib
import re
import socket
import ssl
import time
from collections import defaultdict
from pathlib import Path

import httpx
import pandas as pd

from common import OUT_DIR

HOST = "10.66.0.1"
OUT = OUT_DIR / "nics_entrega"


# --------------------------------------------------------------------------- 1) Certificados TLS
def cert_fingerprint(host: str, port: int, timeout: float = 8.0) -> dict:
    ctx = ssl._create_unverified_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock, \
                ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
            cert = tls.getpeercert()
        sha256 = hashlib.sha256(der).hexdigest()
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))
        return {"puerto": port, "huella_sha256": sha256[:16], "serie": cert.get("serialNumber"),
                "sujeto": subject.get("commonName"), "emisor": issuer.get("commonName"),
                "valido_desde": cert.get("notBefore"), "valido_hasta": cert.get("notAfter"), "error": ""}
    except Exception as e:  # noqa: BLE001
        return {"puerto": port, "error": f"{type(e).__name__}: {e}"}


def check_tls(puertos: list[int]) -> pd.DataFrame:
    df = pd.DataFrame([cert_fingerprint(HOST, p) for p in puertos])
    df.to_csv(OUT / "tls_huellas.csv", index=False, encoding="utf-8-sig")
    ok = df[df["error"] == ""]
    print(f"[TLS] {len(ok)}/{len(df)} con certificado leído")
    dup = ok["huella_sha256"].value_counts()
    dup = dup[dup > 1]
    if len(dup):
        print(f"[TLS] ⚠ {dup.sum()} puertos comparten certificado idéntico en {len(dup)} grupo(s):")
        for h, n in dup.items():
            puertos_grupo = ok[ok["huella_sha256"] == h]["puerto"].tolist()
            print(f"   huella {h}…  ({n} puertos): {puertos_grupo}")
    else:
        print("[TLS] Ningún certificado repetido entre puertos distintos.")
    print(ok[["puerto", "sujeto", "emisor", "huella_sha256"]].to_string(index=False))
    return df


# --------------------------------------------------------------------------- 2) Latencia vs tamaño
def _medir(url: str, n: int = 6, timeout: float = 20.0) -> list[tuple[float, int]]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            r = httpx.get(url, timeout=timeout, verify=False)
            out.append((1000 * (time.perf_counter() - t0), len(r.content)))
        except httpx.HTTPError:
            pass
    return out


def check_latencia(objetivos: dict[str, list[str]], out: Path = OUT) -> pd.DataFrame:
    """objetivos: {nombre_servicio: [rutas de tamaño creciente ya conocido]}"""
    rows = []
    for nombre, urls in objetivos.items():
        print(f"[latencia] {nombre}")
        for url in urls:
            muestras = _medir(url)
            for lat, tam in muestras:
                rows.append({"servicio": nombre, "url": url, "latencia_ms": round(lat, 1), "bytes": tam})
            if muestras:
                lats = [m[0] for m in muestras]
                print(f"   {url[-50:]:50} bytes~{muestras[0][1]:<7} latencia {min(lats):.0f}-{max(lats):.0f} ms")
    df = pd.DataFrame(rows)
    df.to_csv(out / "latencia_vs_tamano.csv", index=False, encoding="utf-8-sig")
    if len(df) > 3:
        corr = df.groupby("servicio").apply(
            lambda g: g["latencia_ms"].corr(g["bytes"]) if g["bytes"].nunique() > 1 and len(g) > 2 else float("nan"),
            include_groups=False,
        )
        print("\n[latencia] Correlación latencia~tamaño por servicio (cerca de 1 = sospechoso; "
              "una base de datos real no debería tardar más por tener más bytes que devolver):")
        print(corr.round(2).to_string())
    return df


# --------------------------------------------------------------------------- 3) Coherencia de assets
def check_assets(paginas: dict[str, str]) -> pd.DataFrame:
    """paginas: {nombre: url_de_la_pagina}. Se descarga la página, se extraen sus <link>/<script>/<img>
    y se comprueba que cargan de verdad (una fachada fabricada suele enlazar a recursos que no existen)."""
    rows = []
    for nombre, url in paginas.items():
        try:
            r = httpx.get(url, timeout=15, verify=False)
        except httpx.HTTPError as e:
            rows.append({"servicio": nombre, "pagina": url, "error": str(e)})
            continue
        base = url.rsplit("/", 1)[0] + "/"
        recursos = set(re.findall(r'(?:href|src)=["\']([^"\'#][^"\']*)["\']', r.text))
        recursos = {r for r in recursos if not r.startswith(("http://", "https://", "mailto:", "data:"))}
        ok = malos = 0
        for rel in list(recursos)[:15]:  # una muestra razonable, no todos si hay muchos
            u = rel if rel.startswith("/") else base + rel
            full = f"{url.split('/', 3)[0]}//{url.split('/', 3)[2]}{u}" if u.startswith("/") else u
            try:
                rr = httpx.head(full, timeout=8, verify=False, follow_redirects=True)
                (ok := ok + 1) if rr.status_code < 400 else (malos := malos + 1)
            except httpx.HTTPError:
                malos += 1
        rows.append({"servicio": nombre, "pagina": url, "recursos_comprobados": ok + malos,
                     "recursos_ok": ok, "recursos_rotos": malos})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "coherencia_assets.csv", index=False, encoding="utf-8-sig")
    print(df.to_string(index=False))
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tls", action="store_true")
    ap.add_argument("--latencia", action="store_true")
    ap.add_argument("--assets", action="store_true")
    ap.add_argument("--todo", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    # Los 18 puertos HTTPS "con TLS" del inventario (los 6 catch-all son HTTP plano, sin certificado)
    todos_los_https = sorted({20150, 20808, 22739, 25461, 25589, 29082, 31885, 34328, 44700,
                              46737, 47163, 48519, 50096, 51999, 56221, 56377, 57238, 59004})
    if a.tls or a.todo:
        check_tls(todos_los_https)

    if a.latencia or a.todo:
        check_latencia({
            "inventario_real": [f"https://{HOST}:20150/api/v1/health", f"https://{HOST}:20150/api/v1/almacenes",
                                f"https://{HOST}:20150/api/v1/movimientos"],
            "elasticsearch_50096": [f"https://{HOST}:50096/", f"https://{HOST}:50096/_cat/indices?v"],
            "blog_real_44700": [f"https://{HOST}:44700/", f"https://{HOST}:44700/?s=prueba_a",
                                f"https://{HOST}:44700/?s=prueba_latencia_bb"],
            "corporativa_real_48519": [f"https://{HOST}:48519/index.html", f"https://{HOST}:48519/empresa.html",
                                       f"https://{HOST}:48519/servicios.html"],
            "gitea_57238": [f"https://{HOST}:57238/", f"https://{HOST}:57238/api/v1/repos/search?limit=10"],
            "grafana_25461": [f"https://{HOST}:25461/login", f"https://{HOST}:25461/api/health"],
        })

    if a.assets or a.todo:
        check_assets({
            "blog_real_44700": f"https://{HOST}:44700/",
            "corporativa_real_48519": f"https://{HOST}:48519/index.html",
            "nas_real_47163": f"https://{HOST}:47163/",
            "gitea_57238": f"https://{HOST}:57238/",
            "owa_real_46737": f"https://{HOST}:46737/owa/auth/logon.aspx",
            "grafana_25461": f"https://{HOST}:25461/login",
        })


if __name__ == "__main__":
    main()
