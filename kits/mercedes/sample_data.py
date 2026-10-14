"""Dataset sintético de clientes para ENSAYAR el pipeline (no son datos del reto).

Tiene 5 segmentos "plantados" (columna `verdad_segmento`, que el modelo nunca ve) para comprobar que
el clustering los recupera, y defectos típicos: nulos, valores atípicos, fechas
DD/MM/YYYY en texto e importes con coma decimal.

    python -m kits.mercedes.sample_data            -> data/clientes_ensayo.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from common import DATA_DIR

TRUTH_COL = "verdad_segmento"  # solo en el ensayo; run.py la excluye siempre del modelo

SEGMENTOS = {
    # nombre: (peso, edad, ingresos k€, modelos, gasto k€, visitas taller, app/mes, pruebas, antigüedad años, canal, financiación, hijos, eléctrico)
    "Ejecutivo premium": (0.18, (52, 6), (140, 25), ["Clase S", "Clase E", "EQS"], (95, 20), (3, 1), (4, 2), (1, 1), (9, 3), "Concesionario", "Renting", (2, 1), 0.35),
    "Familia SUV": (0.27, (41, 5), (75, 12), ["GLC", "GLE", "EQB"], (55, 12), (2, 1), (8, 3), (1, 1), (5, 2), "Concesionario", "Préstamo", (2.3, 0.8), 0.25),
    "Joven urbano": (0.25, (28, 3), (38, 8), ["Clase A", "CLA", "EQA"], (32, 7), (1, 1), (22, 6), (2, 1), (1.5, 1), "Online", "Préstamo", (0.2, 0.4), 0.30),
    "Entusiasta AMG": (0.12, (38, 7), (110, 20), ["AMG GT", "C 63 AMG", "AMG A 45"], (120, 30), (4, 1), (12, 4), (6, 2), (6, 3), "Eventos", "Contado", (0.8, 0.8), 0.10),
    "Sénior fiel": (0.18, (67, 5), (60, 15), ["Clase C", "Clase E", "GLA"], (45, 10), (5, 2), (1, 1), (0.3, 0.5), (18, 5), "Concesionario", "Contado", (2, 1), 0.05),
}
PROVINCIAS = ["Málaga", "Madrid", "Barcelona", "Sevilla", "Valencia", "Bilbao", "Zaragoza", "Granada"]


def generate(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    nombres = list(SEGMENTOS)
    pesos = np.array([SEGMENTOS[s][0] for s in nombres])
    seg = rng.choice(nombres, size=n, p=pesos / pesos.sum())
    ref = pd.Timestamp("2026-09-30")

    rows = []
    for i, s in enumerate(seg):
        _, edad, ing, modelos, gasto, taller, app, pruebas, antig, canal, fin, hijos, elec = SEGMENTOS[s]
        antig_anos = max(0.1, rng.normal(*antig))
        canal_real = canal if rng.random() < 0.75 else rng.choice(["Concesionario", "Online", "Eventos", "Teléfono"])
        fin_real = fin if rng.random() < 0.7 else rng.choice(["Renting", "Préstamo", "Contado", "Leasing"])
        rows.append(
            {
                "id_cliente": f"CL{i + 1:05d}",
                "fecha_alta": (ref - pd.Timedelta(days=int(antig_anos * 365))).strftime("%d/%m/%Y"),
                "edad": int(np.clip(rng.normal(*edad), 18, 90)),
                "genero": rng.choice(["H", "M"], p=[0.6, 0.4]),
                "provincia": rng.choice(PROVINCIAS),
                "ingresos_anuales": round(max(12, rng.normal(*ing)) * 1000, 2),
                "modelo_actual": rng.choice(modelos),
                "gasto_total_eur": f"{max(5, rng.normal(*gasto)) * 1000:.2f}".replace(".", ","),
                "visitas_taller_12m": int(max(0, round(rng.normal(*taller)))),
                "interacciones_app_mes": int(max(0, round(rng.normal(*app)))),
                "pruebas_conduccion_12m": int(max(0, round(rng.normal(*pruebas)))),
                "ultima_compra": (ref - pd.Timedelta(days=int(rng.uniform(10, min(antig_anos, 6) * 365 + 30)))).strftime("%d/%m/%Y"),
                "canal_preferido": canal_real,
                "financiacion": fin_real,
                "hijos": int(max(0, round(rng.normal(*hijos)))),
                "satisfaccion": int(np.clip(round(rng.normal(8 if s == "Sénior fiel" else 7, 1.5)), 1, 10)),
                "interes_electrico": "Sí" if rng.random() < elec else "No",
                TRUTH_COL: s,
            }
        )
    df = pd.DataFrame(rows)

    # Defectos típicos de datos reales
    for col, frac in [("ingresos_anuales", 0.04), ("satisfaccion", 0.06), ("canal_preferido", 0.03), ("hijos", 0.02)]:
        df.loc[df.sample(frac=frac, random_state=seed).index, col] = None
    outliers = df.sample(n=max(1, n // 200), random_state=seed + 1).index
    df.loc[outliers, "ingresos_anuales"] = df.loc[outliers, "ingresos_anuales"] * 12
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=DATA_DIR / "clientes_ensayo.csv")
    args = ap.parse_args()
    df = generate(args.n, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8")
    print(f"{len(df)} clientes -> {args.out}")
    print(df[TRUTH_COL].value_counts().to_string())


if __name__ == "__main__":
    main()
