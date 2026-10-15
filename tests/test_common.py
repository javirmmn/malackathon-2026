"""Pruebas de common/ (lectura y limpieza de ficheros).  Ejecutar:  python -m pytest"""

from pathlib import Path

import pandas as pd

from common.dataio import normalize_columns, read_any, slug, to_date_es, to_number_es

FIXTURE = Path(__file__).with_name("prueba_carga.csv")


def test_lee_prueba_carga():
    df = read_any(FIXTURE)
    assert df.shape == (10, 6)
    assert (df["pais"] == "España").sum() == 4  # tildes bien leídas


def test_conversiones_es():
    df = read_any(FIXTURE)
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
