"""Clasificador para los servicios no-HTTP (SSH, FTP, Telnet, SMTP, POP3, IMAP).

Con solo el banner (sin interacción real: login, comandos válidos) hay poca señal. Por eso:
- Las reglas solo distinguen casos claros (firma conocida de honeypot, versión repetida en dos puertos).
- Todo lo demás queda en "real" con confianza media y la etiqueta "revisar" para que el equipo lo
  mire a mano en cuanto haya red: encaja con el aviso del enunciado ("se delata cuando lo usas en serio").
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent

# Banners por defecto de honeypots SSH/Telnet/FTP conocidos (Cowrie, Kippo, Dionaea...).
# Pista, no certeza: hay que confirmarla si se puede (el software cambia de versión con el tiempo).
FIRMAS_HONEYPOT_PROTOCOLO = [
    r"SSH-2\.0-OpenSSH_6\.0p1 Debian-4\+deb7u2",   # banner por defecto de Cowrie
    r"SSH-2\.0-OpenSSH_5\.1p1 Debian-5",            # banner por defecto de Kippo
    r"220[- ]Welcome to the ftp service",           # banner por defecto de Dionaea (FTP)
]


def load_rules(path: Path = HERE / "rules.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def classify(feats: pd.DataFrame) -> pd.DataFrame:
    rules = load_rules()
    firmas_extra = [re.compile(p, re.I) for p in FIRMAS_HONEYPOT_PROTOCOLO]
    duplicados = feats["banner_ejemplo"].value_counts()
    duplicados = set(duplicados[duplicados > 1].index) - {""}

    rows = []
    for _, f in feats.iterrows():
        banner = f["banner_ejemplo"] or ""
        evidencias, clase, confianza, revisar = [], "real", 0.55, False

        if not banner and f["protocolo"] not in ("imap",):
            clase, confianza = "honeypot_clasico", 0.5
            evidencias.append("No manda ningún banner al conectar, algo raro en un servicio real")
        elif any(p.search(banner) for p in firmas_extra):
            clase, confianza = "honeypot_clasico", 0.85
            evidencias.append(f"El banner coincide con la firma por defecto de un software de honeypot conocido: {banner!r}")
        elif banner in duplicados:
            revisar = True
            evidencias.append(f"Banner IDÉNTICO a otro servicio del mismo protocolo ({banner!r}); "
                              "probable pareja real/clon — hace falta interactuar de verdad para distinguirlos")
        else:
            evidencias.append(f"Banner: {banner!r} (coherente, sin firma conocida de honeypot ni duplicado)")

        if f["sin_banner"] > 0:
            evidencias.append(f"{f['sin_banner']} de {f['sin_banner'] + f['intentos_ok']} conexiones no dieron banner")

        rows.append({"servicio": f["servicio"], "puerto": f["puerto"], "protocolo": f["protocolo"], "clase": clase,
                     "confianza": confianza, "revisar_a_mano": revisar, "que_lo_delato": evidencias[0],
                     "evidencias": " · ".join(evidencias)})
    return pd.DataFrame(rows)
