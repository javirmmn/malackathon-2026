"""Genera el CSV de entrega (port,service,class) uniendo la clasificación web y la de protocolo.

    python -m kits.nics.entrega
    -> out/nics_entrega/entrega.csv        (el que se sube: port,service,class)
    -> out/nics_entrega/entrega_detalle.csv (con clase, confianza, evidencias y "revisar_a_mano", para nosotros)
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from common import OUT_DIR

from . import classifier_protocolo

CLASE_A_NUM = {"real": 1, "honeypot_clasico": 2, "honeypot_generativo": 3}
SERVICE_LABEL = {"ssh": "SSH", "ftp": "FTP", "telnet": "TELNET", "smtp": "SMTP", "pop3": "POP3", "imap": "IMAP",
                 "http": "HTTP", "ssl/http": "HTTPS"}


def web_rows(resultados_path: Path, inventario_path: Path) -> pd.DataFrame:
    res = pd.read_csv(resultados_path, encoding="utf-8-sig")
    inv = pd.read_csv(inventario_path, encoding="utf-8-sig").set_index("port")
    rows = []
    for _, r in res.iterrows():
        port = int(re.sub(r"^p", "", r["servicio"]))
        nmap_service = inv.loc[port, "service"] if port in inv.index else ("https" if "https" in r["url_base"] else "http")
        rows.append({"port": port, "service": SERVICE_LABEL.get(nmap_service, nmap_service.upper()),
                     "class": CLASE_A_NUM[r["clase"]], "clase": r["clase"], "confianza": r["confianza"],
                     "revisar_a_mano": bool(re.search(r"idéntic|gemel", str(r.get("que_lo_delato", "")), re.I)),
                     "evidencias": r["que_lo_delato"]})
    return pd.DataFrame(rows)


def protocolo_rows(rasgos_path: Path) -> pd.DataFrame:
    feats = pd.read_csv(rasgos_path, encoding="utf-8-sig")
    clas = classifier_protocolo.classify(feats)
    rows = []
    for _, r in clas.iterrows():
        rows.append({"port": int(r["puerto"]), "service": SERVICE_LABEL.get(r["protocolo"], r["protocolo"].upper()),
                     "class": CLASE_A_NUM[r["clase"]], "clase": r["clase"], "confianza": r["confianza"],
                     "revisar_a_mano": bool(r["revisar_a_mano"]), "evidencias": r["evidencias"]})
    return pd.DataFrame(rows)


def build(web_resultados: Path, web_inventario: Path, protocolo_rasgos: Path, out: Path) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    df = pd.concat([web_rows(web_resultados, web_inventario), protocolo_rows(protocolo_rasgos)], ignore_index=True)
    df = df.sort_values("port").reset_index(drop=True)

    df[["port", "service", "class"]].to_csv(out / "entrega.csv", index=False)
    df.to_csv(out / "entrega_detalle.csv", index=False, encoding="utf-8-sig")

    pendientes = df[df["revisar_a_mano"]]
    low_conf = df[(df["confianza"] < 0.65) & ~df["revisar_a_mano"]]
    print(f"{len(df)} servicios -> {out / 'entrega.csv'}")
    print(df["clase"].value_counts().rename("nº servicios").to_string())
    if len(pendientes):
        print(f"\n⚠ {len(pendientes)} marcados 'revisar_a_mano' (gemelos idénticos, clasificados por defecto "
              f"con confianza baja — confirmar antes de entregar):")
        print(pendientes[["port", "service", "class", "confianza"]].to_string(index=False))
    if len(low_conf):
        print(f"\n⚠ {len(low_conf)} más con confianza < 0,65 (sin ser gemelos; revisar si da tiempo):")
        print(low_conf[["port", "service", "class", "confianza"]].to_string(index=False))
    return df


if __name__ == "__main__":
    build(
        web_resultados=OUT_DIR / "nics_real" / "resultados.csv",
        web_inventario=Path("data/inventario_completo.csv"),
        protocolo_rasgos=OUT_DIR / "nics_otros" / "rasgos_protocolo.csv",
        out=OUT_DIR / "nics_entrega",
    )
