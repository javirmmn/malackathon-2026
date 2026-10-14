"""Pruebas de common/ que no necesitan conexión a Oracle.  Ejecutar:  python -m pytest"""

import pandas as pd

from common import ROOT
from common.dataio import normalize_columns, read_any, slug, to_date_es, to_number_es
from common.db import create_table_sql


def test_lee_prueba_carga():
    df = read_any(ROOT / "prueba_carga.csv")
    assert df.shape == (10, 6)
    assert (df["pais"] == "España").sum() == 4  # tildes bien leídas


def test_conversiones_es():
    df = read_any(ROOT / "prueba_carga.csv")
    importe = to_number_es(df["importe"])
    assert importe.notna().all()
    assert round(importe.sum(), 2) == 7771.48
    assert to_number_es(pd.Series(["1.234,50 €"])).iloc[0] == 1234.5
    fechas = to_date_es(df["fecha"])
    assert fechas.notna().all()
    assert fechas.min() == pd.Timestamp("2025-01-03")


def test_slug_y_columnas():
    assert slug("Fecha de Alta (€)") == "fecha_de_alta"
    assert slug("2024 ventas") == "c_2024_ventas"
    df = normalize_columns(pd.DataFrame(columns=["País", "pais", "Importe Total"]))
    assert list(df.columns) == ["pais", "pais_1", "importe_total"]


def test_ddl_desde_dataframe():
    df = read_any(ROOT / "prueba_carga.csv")
    df["importe"] = to_number_es(df["importe"])
    df["fecha"] = to_date_es(df["fecha"])
    ddl = create_table_sql(df, "prueba")
    assert ddl.startswith("CREATE TABLE PRUEBA")
    assert "ID NUMBER(19)" in ddl
    assert "IMPORTE NUMBER," in ddl
    assert "FECHA TIMESTAMP" in ddl
    assert "NOMBRE VARCHAR2(" in ddl


def test_palabras_reservadas_y_textos_largos():
    df = pd.DataFrame({"date": ["01/02/2025"], "level": [3], "nota": ["x" * 3000], "ok": [True]})
    ddl = create_table_sql(df, "t")
    assert "DATE_ VARCHAR2" in ddl and "LEVEL_ NUMBER(19)" in ddl
    assert "NOTA CLOB" in ddl and "OK NUMBER(1)" in ddl
