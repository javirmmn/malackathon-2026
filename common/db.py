"""Conexión a la Autonomous DB `malackathon` con python-oracledb (modo thin, sin Instant Client).

Configuración por variables de entorno (o fichero .env en la raíz del repo, ver .env.example):
    ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN,
    ORACLE_WALLET_DIR, ORACLE_WALLET_PASSWORD   (si se conecta con wallet / mTLS)

Uso rápido:
    from common.db import query_df, df_to_table
    df = query_df("SELECT * FROM clientes WHERE pais = :p", {"p": "España"})
    df_to_table(df, "CLIENTES_COPIA")

Prueba de conexión:
    python -m common.db
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

import oracledb
import pandas as pd
from dotenv import load_dotenv

from common import ROOT

load_dotenv(ROOT / ".env")

_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")


def _env(name: str, required: bool = True) -> str | None:
    value = os.getenv(name) or None
    if required and not value:
        raise RuntimeError(
            f"Falta la variable de entorno {name}. Copia .env.example a .env y rellénalo."
        )
    return value


def get_connection() -> oracledb.Connection:
    """Abre una conexión nueva. Con ORACLE_WALLET_DIR usa el wallet (mTLS); sin él, ORACLE_DSN tal cual."""
    params: dict[str, Any] = {
        "user": _env("ORACLE_USER"),
        "password": _env("ORACLE_PASSWORD"),
        "dsn": _env("ORACLE_DSN"),
    }
    wallet_dir = _env("ORACLE_WALLET_DIR", required=False)
    if wallet_dir:
        params.update(
            config_dir=wallet_dir,
            wallet_location=wallet_dir,
            wallet_password=_env("ORACLE_WALLET_PASSWORD", required=False),
        )
    return oracledb.connect(**params)


@contextmanager
def connection() -> Iterator[oracledb.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql: str, params: dict | list | None = None) -> pd.DataFrame:
    """Ejecuta un SELECT y devuelve un DataFrame (columnas en minúsculas)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d[0].lower() for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def execute(sql: str, params: dict | list | None = None) -> int:
    """Ejecuta DML/DDL, hace commit y devuelve las filas afectadas."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        conn.commit()
        return cur.rowcount


def _check_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Nombre de tabla/columna no válido para Oracle: {name!r}")
    return name.upper()


def _oracle_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "NUMBER(1)"
    if pd.api.types.is_integer_dtype(series):
        return "NUMBER(19)"
    if pd.api.types.is_float_dtype(series):
        return "BINARY_DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    max_len = int(series.dropna().astype(str).str.len().max() or 1)
    return "CLOB" if max_len > 4000 else f"VARCHAR2({max(max_len * 2, 50)} CHAR)"


def create_table_sql(df: pd.DataFrame, table: str) -> str:
    """DDL CREATE TABLE deducido de los tipos del DataFrame."""
    cols = ",\n  ".join(f"{_check_ident(c)} {_oracle_type(df[c])}" for c in df.columns)
    return f"CREATE TABLE {_check_ident(table)} (\n  {cols}\n)"


def _to_python(value: Any) -> Any:
    if value is None or (not isinstance(value, (list, dict, str)) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # escalares numpy -> python
        return value.item()
    return value


def df_to_table(
    df: pd.DataFrame, table: str, if_exists: str = "fail", batch_size: int = 5000
) -> int:
    """Sube un DataFrame a una tabla. if_exists: 'fail' | 'replace' | 'append'.

    Los nombres de columna deben ser identificadores válidos de Oracle
    (usa common.dataio.normalize_columns antes si vienen de un Excel).
    """
    if if_exists not in {"fail", "replace", "append"}:
        raise ValueError("if_exists debe ser 'fail', 'replace' o 'append'")
    name = _check_ident(table)
    cols = [_check_ident(c) for c in df.columns]
    insert = (
        f"INSERT INTO {name} ({', '.join(cols)}) "
        f"VALUES ({', '.join(f':{i + 1}' for i in range(len(cols)))})"
    )
    rows = [tuple(_to_python(v) for v in row) for row in df.itertuples(index=False)]

    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_tables WHERE table_name = :t", {"t": name})
        exists = cur.fetchone()[0] > 0
        if exists and if_exists == "fail":
            raise RuntimeError(f"La tabla {name} ya existe (usa if_exists='replace' o 'append').")
        if exists and if_exists == "replace":
            cur.execute(f"DROP TABLE {name} PURGE")
        if not exists or if_exists == "replace":
            cur.execute(create_table_sql(df, name))
        for start in range(0, len(rows), batch_size):
            cur.executemany(insert, rows[start : start + batch_size])
        conn.commit()
    return len(rows)


def list_tables() -> list[str]:
    return query_df("SELECT table_name FROM user_tables ORDER BY table_name")["table_name"].tolist()


if __name__ == "__main__":
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT USER, SYS_CONTEXT('USERENV', 'DB_NAME') FROM dual")
        user, db_name = cur.fetchone()
        print(f"Conectado a {db_name} como {user} (Oracle {conn.version})")
    print("Tablas del esquema:", list_tables() or "(ninguna)")
