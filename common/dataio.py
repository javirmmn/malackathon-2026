"""Lectura y exportación de ficheros de datos (CSV, Excel, JSON, Parquet) con limpieza básica.

    from common.dataio import read_any, normalize_columns, to_number_es
    df = normalize_columns(read_any("data/clientes.xlsx"))
    df["importe"] = to_number_es(df["importe"])
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

import pandas as pd

_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def _sniff_sep(path: Path, encoding: str) -> str:
    with open(path, encoding=encoding, newline="") as f:
        sample = f.read(64_000)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_any(path: str | Path, sheet: str | int | None = 0, **kwargs) -> pd.DataFrame:
    """Lee CSV/TSV/TXT, XLSX/XLS, JSON o Parquet. En CSV detecta codificación y separador.

    En Excel, sheet=None devuelve un dict {hoja: DataFrame}.
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet, **kwargs)
    if ext == ".json":
        return pd.read_json(path, **kwargs)
    if ext == ".parquet":
        return pd.read_parquet(path, **kwargs)
    if ext in {".csv", ".tsv", ".txt"}:
        last_error: Exception | None = None
        for enc in _ENCODINGS:
            try:
                sep = kwargs.pop("sep", None) or _sniff_sep(path, enc)
                return pd.read_csv(path, sep=sep, encoding=enc, **kwargs)
            except UnicodeDecodeError as e:
                last_error = e
        raise ValueError(f"No se pudo leer {path} con {_ENCODINGS}") from last_error
    raise ValueError(f"Extensión no soportada: {ext}")


def slug(text: str) -> str:
    """'Fecha de Alta (€)' -> 'fecha_de_alta'. Válido como identificador de Oracle."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    if not text or not text[0].isalpha():
        text = f"c_{text}"
    return text[:128]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Columnas en snake_case sin tildes ni símbolos, sin duplicados."""
    seen: dict[str, int] = {}
    cols = []
    for c in df.columns:
        s = slug(c)
        if s in seen:
            seen[s] += 1
            s = f"{s}_{seen[s]}"
        else:
            seen[s] = 0
        cols.append(s)
    return df.set_axis(cols, axis=1)


def to_number_es(series: pd.Series) -> pd.Series:
    """'1.234,50' / '1234,50' / '89,99 €' -> float. Lo que no convierte queda NaN."""
    s = (
        series.astype("string")
        .str.replace(r"[^\d,.\-]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(s, errors="coerce")


def to_date_es(series: pd.Series, fmt: str | None = "%d/%m/%Y") -> pd.Series:
    """Fechas DD/MM/YYYY (o el formato dado). fmt=None -> deducir con dayfirst."""
    if fmt is None:
        return pd.to_datetime(series, dayfirst=True, errors="coerce")
    return pd.to_datetime(series, format=fmt, errors="coerce")


def quick_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen por columna: tipo, nulos, únicos y un ejemplo."""
    return pd.DataFrame(
        {
            "tipo": df.dtypes.astype(str),
            "nulos": df.isna().sum(),
            "pct_nulos": (df.isna().mean() * 100).round(1),
            "unicos": df.nunique(),
            "ejemplo": [str(df[c].dropna().iloc[0]) if df[c].notna().any() else "" for c in df],
        }
    )


def export(df: pd.DataFrame, path: str | Path) -> Path:
    """Guarda en CSV (UTF-8 con BOM, abre bien en Excel) o XLSX según la extensión."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
