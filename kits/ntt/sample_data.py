"""Dataset sintético en español para ENSAYAR el detector (no son datos del reto).

Cada fila: pregunta, fuentes (texto), respuesta de una "IA" y etiqueta `alucina` (1 = se inventa algo).
Tipos de alucinación plantados: número cambiado, fecha cambiada, nombre cambiado, dato añadido y negación.

    python -m kits.ntt.sample_data          -> data/ntt_ensayo.csv
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

from common import DATA_DIR

EMPRESAS = ["Aceitunas del Sur", "Transportes Ibéricos", "Solaris Energía", "Grupo Malacitano", "Datanova", "Viñedos Altamira"]
CIUDADES = ["Málaga", "Sevilla", "Valencia", "Bilbao", "Zaragoza", "Granada", "Córdoba", "Murcia"]
PERSONAS = ["Lucía Herrera", "Andrés Molina", "Carmen Vidal", "Sergio Navarro", "Elena Castro", "Raúl Ortega"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "septiembre", "octubre", "noviembre"]
PRODUCTOS = ["placas solares", "aceite de oliva", "software de gestión", "vino tinto", "servicios logísticos"]
PREMIOS = ["el Premio Nacional de Innovación", "una medalla de la Cámara de Comercio", "el sello europeo de calidad"]


def _facts(rng: random.Random) -> dict:
    return {
        "empresa": rng.choice(EMPRESAS), "ciudad": rng.choice(CIUDADES), "persona": rng.choice(PERSONAS),
        "anio": rng.randint(1975, 2015), "empleados": rng.randint(40, 4800), "facturacion": rng.randint(5, 900),
        "anio_fact": rng.randint(2019, 2025), "mes": rng.choice(MESES), "producto": rng.choice(PRODUCTOS),
        "exporta": rng.randint(5, 70), "paises": rng.randint(3, 40),
    }


def _sources(f: dict) -> str:
    return (f"{f['empresa']} fue fundada en {f['mes']} de {f['anio']} en {f['ciudad']}. "
            f"La compañía se dedica principalmente a {f['producto']} y cuenta con {f['empleados']} empleados. "
            f"En {f['anio_fact']} su facturación alcanzó los {f['facturacion']} millones de euros, "
            f"y el {f['exporta']} % de sus ventas procedió del extranjero, con presencia en {f['paises']} países. "
            f"Desde 2021 la dirige {f['persona']}, que sustituyó al fundador.")


_PREGUNTAS = [
    ("¿Cuándo y dónde se fundó {empresa}?", "{empresa} se fundó en {ciudad} en {mes} de {anio}."),
    ("¿Cuántos empleados tiene {empresa} y a qué se dedica?", "Se dedica sobre todo a {producto} y tiene una plantilla de {empleados} personas."),
    ("¿Cuánto facturó {empresa}?", "En {anio_fact} facturó {facturacion} millones de euros."),
    ("¿Qué peso tienen las exportaciones en {empresa}?", "Alrededor del {exporta} % de sus ventas viene del exterior y opera en {paises} países."),
    ("¿Quién dirige {empresa}?", "La empresa está dirigida por {persona} desde 2021."),
]


def _hallucinate(resp: str, f: dict, kind: str, rng: random.Random) -> str:
    g = dict(f)
    if kind == "numero":
        key = rng.choice([k for k in ("empleados", "facturacion", "exporta", "paises") if f"{{{k}}}" in resp] or ["facturacion"])
        g[key] = f[key] + rng.choice([-1, 1]) * max(2, int(f[key] * rng.uniform(0.2, 0.6)))
        return resp.format(**g) if f"{{{key}}}" in resp else resp.format(**g) + f" Su facturación fue de {g['facturacion']} millones."
    if kind == "fecha":
        g["anio"] = f["anio"] + rng.choice([-7, -3, 4, 9])
        g["anio_fact"] = f["anio_fact"] - rng.choice([2, 3])
        g["mes"] = rng.choice([m for m in MESES if m != f["mes"]])
        out = resp.format(**g)
        return out if out != resp.format(**f) else out + f" La compañía se fundó en {g['anio']}."
    if kind == "nombre":
        g["persona"] = rng.choice([p for p in PERSONAS if p != f["persona"]])
        g["ciudad"] = rng.choice([c for c in CIUDADES if c != f["ciudad"]])
        out = resp.format(**g)
        return out if out != resp.format(**f) else out + f" Su sede central está en {g['ciudad']}."
    if kind == "anadido":
        extra = rng.choice([
            f" Además, en {rng.randint(2010, 2024)} recibió {rng.choice(PREMIOS)}.",
            f" También cotiza en bolsa desde {rng.randint(1999, 2020)}.",
            f" Su principal accionista es un fondo de inversión de Luxemburgo.",
        ])
        return resp.format(**f) + extra
    # negación / contradicción
    neg = {"se fundó en": "no se fundó en", "tiene una plantilla": "no llega a tener una plantilla",
           "facturó": "no superó", "viene del exterior": "no viene del exterior", "está dirigida": "ya no está dirigida"}
    out = resp.format(**f)
    for a, b in neg.items():
        if a in out:
            return out.replace(a, b, 1)
    return out + " No tiene actividad internacional."


def generate(n: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    kinds = ["numero", "fecha", "nombre", "anadido", "negacion"]
    for i in range(n):
        f = _facts(rng)
        q, tmpl = rng.choice(_PREGUNTAS)
        halluc = rng.random() < 0.5
        kind = rng.choice(kinds) if halluc else ""
        resp = _hallucinate(tmpl, f, kind, rng) if halluc else tmpl.format(**f)
        rows.append({"id": i + 1, "pregunta": q.format(**f), "fuentes": _sources(f), "respuesta": resp,
                     "alucina": int(halluc), "tipo": kind or "fiel"})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=DATA_DIR / "ntt_ensayo.csv")
    args = ap.parse_args()
    df = generate(args.n, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8")
    print(f"{len(df)} respuestas -> {args.out}")
    print(df["tipo"].value_counts().to_string())


if __name__ == "__main__":
    main()
