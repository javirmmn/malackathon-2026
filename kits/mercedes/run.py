"""Kit Mercedes · un comando: EDA + comparación de modelos + perfiles + artefactos para el dashboard.

    python -m kits.mercedes.run --data data/clientes_ensayo.csv
    python -m kits.mercedes.run --data data/reto.xlsx --exclude columna1,columna2 --kmax 8
    python -m kits.mercedes.run --sql "SELECT * FROM CLIENTES"          (lee de Oracle, necesita .env)
    python -m kits.mercedes.run --data ... --model kmeans_k5            (forzar un modelo concreto)

Salidas en out/mercedes/: eda.html, informe.html, modelos.csv, perfiles_*.csv,
clientes_segmentados.csv, personas_plantilla.yaml y modelo.joblib (lo usa el dashboard).
Dashboard:  streamlit run kits/mercedes/app.py
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import joblib
import pandas as pd

from common import OUT_DIR
from common.dataio import normalize_columns, read_any, slug

from . import pipeline as pl
from . import report
from .sample_data import TRUTH_COL

DEFAULT_OUT = OUT_DIR / "mercedes"


def load(args) -> pd.DataFrame:
    if args.sql:
        from common.db import query_df

        return query_df(args.sql)
    df = read_any(args.data, sheet=args.sheet) if args.sheet is not None else read_any(args.data)
    return df


def save_to_oracle(prefix: str, seg_df: pd.DataFrame, prof: dict, names: dict, models: pd.DataFrame) -> None:
    """<PREFIJO>_CLIENTES (cada cliente con su segmento), <PREFIJO>_SEGMENTOS (perfil) y <PREFIJO>_MODELOS."""
    from common.db import df_to_table

    p = prefix.upper()
    clientes = seg_df.assign(nombre_segmento=seg_df["segmento"].map(names))
    segmentos = prof["tamanos"].join(prof["medias"]).reset_index()
    segmentos.insert(1, "nombre_segmento", segmentos["segmento"].map(names))
    for table, data in [(f"{p}_CLIENTES", clientes), (f"{p}_SEGMENTOS", segmentos), (f"{p}_MODELOS", models)]:
        n = df_to_table(data, table, if_exists="replace")
        print(f"      Oracle: {table} ({n} filas)")


def run(df: pd.DataFrame, out: Path = DEFAULT_OUT, exclude: tuple[str, ...] = (), kmin: int = 2, kmax: int = 10,
        scaler: str = "standard", cat_weight: float = 0.5, model: str | None = None, umap: bool = True,
        kprototypes: bool = False, seed: int = 42, eda: bool = True, oracle_prefix: str | None = None) -> dict:
    t0 = time.time()
    out.mkdir(parents=True, exist_ok=True)
    df = normalize_columns(df)
    exclude = tuple(slug(c) for c in exclude) + (TRUTH_COL,)
    df, conversions = pl.coerce_types(df)
    sch = pl.infer_schema(df, exclude=exclude)
    print(f"[1/5] {len(df)} filas · numéricas={len(sch.numeric)} categóricas={len(sch.categorical)} "
          f"fechas={len(sch.dates)} descartadas={list(sch.dropped)}")
    if conversions:
        print(f"      conversiones: {conversions}")

    if eda:
        report.eda_report(df, sch, conversions, out / "eda.html")
        print(f"[2/5] EDA -> {out / 'eda.html'}")

    X, num_cols, ref_date = pl.build_features(df, sch)
    pre = pl.make_preprocessor(num_cols, sch.categorical, scaler=scaler, cat_weight=cat_weight)
    Z = pre.fit_transform(X)
    print(f"[3/5] Matriz del modelo: {Z.shape[0]} × {Z.shape[1]} (tras one-hot y escalado)")

    models, labels = pl.search_models(Z, range(kmin, kmax + 1), seed=seed, X_raw=X, num_cols=num_cols,
                                      cat_cols=sch.categorical, kprototypes=kprototypes)
    models.to_csv(out / "modelos.csv", index=False)
    chosen = model or pl.choose_model(models)
    if chosen not in labels:
        raise SystemExit(f"Modelo '{chosen}' no existe. Opciones: {', '.join(labels)}")
    lab = labels[chosen]
    best = models.set_index("modelo").loc[chosen]
    print(f"[4/5] Modelo elegido: {chosen} (silhouette={best['silhouette']}, DB={best['davies_bouldin']}, "
          f"segmentos={int(best['n_clusters'])})")
    top = models.dropna(subset=["silhouette"]).nlargest(3, "silhouette")
    print("      Candidatos (si están cerca, elegid el más interpretable con --model):")
    for _, r in top.iterrows():
        print(f"        {r['modelo']:<16} segmentos={int(r['n_clusters'])}  silhouette={r['silhouette']:.3f}  "
              f"DB={r['davies_bouldin']:.2f}  ruido={r['ruido_pct']} %")

    prof = pl.profile(X, lab, num_cols, sch.categorical)
    names = {int(s): f"S{int(s)} · {pl.suggested_name(prof['rasgos'], s)}" for s in prof["tamanos"].index}
    emb = pl.embed_2d(Z, seed=seed, umap=umap)
    seg_df = pd.concat([df.reset_index(drop=True), emb], axis=1).assign(segmento=lab)
    seg_df.to_csv(out / "clientes_segmentados.csv", index=False, encoding="utf-8-sig")
    for k, v in prof.items():
        v.to_csv(out / f"perfiles_{k}.csv", encoding="utf-8-sig")
    report.results_report(models, chosen, prof, seg_df, names, out / "informe.html")
    (out / "personas_plantilla.yaml").write_text(report.personas_template(prof, names), encoding="utf-8")

    cents = pl.centroids(Z, lab)
    defaults = {c: (float(X[c].median()) if c in num_cols else X[c].mode().iat[0]) for c in X.columns}
    choices = {c: sorted(X[c].dropna().unique().tolist()) for c in sch.categorical}
    joblib.dump({"preprocessor": pre, "centroids": cents, "names": names, "num_cols": num_cols,
                 "cat_cols": sch.categorical, "dates": sch.dates, "ref_date": ref_date, "defaults": defaults,
                 "choices": choices, "chosen": chosen}, out / "modelo.joblib")

    if oracle_prefix:
        save_to_oracle(oracle_prefix, seg_df, prof, names, models)

    ari = report.ari_if_known(df, lab)
    print(f"[5/5] Informe -> {out / 'informe.html'}  ({time.time() - t0:.0f} s)")
    if ari is not None:
        print(f"      Dataset de ensayo: acuerdo con los segmentos plantados (ARI) = {ari}")
    print(prof["tamanos"].rename(index=names).to_string())
    return {"chosen": chosen, "labels": lab, "models": models, "profile": prof, "ari": ari, "names": names}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", type=Path, help="CSV/Excel/JSON/Parquet con una fila por cliente")
    src.add_argument("--sql", help="consulta a Oracle (usa .env)")
    ap.add_argument("--sheet", help="hoja del Excel (nombre o número)")
    ap.add_argument("--exclude", default="", help="columnas a no usar, separadas por comas")
    ap.add_argument("--kmin", type=int, default=2)
    ap.add_argument("--kmax", type=int, default=10)
    ap.add_argument("--scaler", choices=["standard", "robust"], default="standard")
    ap.add_argument("--cat-weight", type=float, default=0.5, help="peso de las categóricas (one-hot)")
    ap.add_argument("--model", help="forzar modelo, p. ej. kmeans_k5, gmm_k4, hdbscan")
    ap.add_argument("--no-umap", action="store_true", help="omitir UMAP (más rápido)")
    ap.add_argument("--no-eda", action="store_true")
    ap.add_argument("--kprototypes", action="store_true", help="probar también K-Prototypes (lento)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--a-oracle", metavar="PREFIJO", help="guarda resultados en Oracle: PREFIJO_CLIENTES, _SEGMENTOS, _MODELOS")
    args = ap.parse_args()
    if args.sheet is not None and args.sheet.isdigit():
        args.sheet = int(args.sheet)

    run(load(args), out=args.out, exclude=tuple(c.strip() for c in args.exclude.split(",") if c.strip()),
        kmin=args.kmin, kmax=args.kmax, scaler=args.scaler, cat_weight=args.cat_weight, model=args.model,
        umap=not args.no_umap, kprototypes=args.kprototypes, seed=args.seed, eda=not args.no_eda,
        oracle_prefix=args.a_oracle)


if __name__ == "__main__":
    main()
