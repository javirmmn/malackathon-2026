"""Sube un fichero (CSV/Excel/JSON/Parquet) a una tabla de la Autonomous DB, alternativa a Data Load.

    python -m common.load data/reto.xlsx --tabla CLIENTES
    python -m common.load data/reto.csv --tabla CLIENTES --reemplazar
    python -m common.load data/reto.xlsx --tabla CLIENTES_RAW --texto     (todo VARCHAR2, como recomienda la guía)
    python -m common.load data/reto.xlsx --tabla CLIENTES --simular       (solo muestra el CREATE TABLE, sin conectar)

Por defecto normaliza los nombres de columna (sin tildes ni espacios) y convierte fechas DD/MM/YYYY y
números con coma decimal. Necesita .env y wallet (ver docs/oracle.md), salvo con --simular.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from common.dataio import coerce_types, normalize_columns, read_any


def prepare(path: Path, sheet: str | int | None = None, as_text: bool = False):
    df = read_any(path, sheet=sheet) if sheet is not None else read_any(path)
    df = normalize_columns(df)
    if as_text:
        return df.astype("string").astype(object).where(df.notna(), None), {}
    return coerce_types(df)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichero", type=Path)
    ap.add_argument("--tabla", required=True, help="nombre de la tabla en Oracle")
    ap.add_argument("--hoja", help="hoja del Excel (nombre o número)")
    ap.add_argument("--texto", action="store_true", help="todas las columnas como texto (VARCHAR2)")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--reemplazar", action="store_true", help="borra la tabla si existe y la vuelve a crear")
    modo.add_argument("--anadir", action="store_true", help="añade filas a una tabla existente")
    ap.add_argument("--simular", action="store_true", help="no conecta: enseña el CREATE TABLE y las conversiones")
    args = ap.parse_args()
    sheet = int(args.hoja) if args.hoja and args.hoja.isdigit() else args.hoja

    from common.db import create_table_sql

    df, log = prepare(args.fichero, sheet, args.texto)
    print(f"{len(df)} filas · {df.shape[1]} columnas")
    if log:
        print("Conversiones:", log)
    print(create_table_sql(df, args.tabla))
    if args.simular:
        return

    from common.db import df_to_table, query_df

    modo = "replace" if args.reemplazar else "append" if args.anadir else "fail"
    n = df_to_table(df, args.tabla, if_exists=modo)
    total = query_df(f"SELECT COUNT(*) AS n FROM {args.tabla.upper()}")["n"].iat[0]
    print(f"Subidas {n} filas a {args.tabla.upper()} (la tabla tiene ahora {total}).")


if __name__ == "__main__":
    main()
