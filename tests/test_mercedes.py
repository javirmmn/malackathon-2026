"""El kit de Mercedes recupera los segmentos plantados del dataset de ensayo y genera sus artefactos."""

import pandas as pd

from kits.mercedes import pipeline as pl
from kits.mercedes.run import run
from kits.mercedes.sample_data import TRUTH_COL, generate


def test_coerce_types_formatos_es():
    df = pd.DataFrame({"f": ["03/01/2025", "15/02/2025"], "imp": ["1.234,50", "89,99"], "txt": ["a", "b"]})
    out, log = pl.coerce_types(df)
    assert pd.api.types.is_datetime64_any_dtype(out["f"]) and out["f"].iloc[0].month == 1
    assert out["imp"].tolist() == [1234.5, 89.99]
    assert set(log) == {"f", "imp"}


def test_pipeline_recupera_segmentos(tmp_path):
    df = generate(n=800, seed=7)
    res = run(df, out=tmp_path, kmax=6, model="kmeans_k5", umap=False, eda=False)
    assert res["ari"] > 0.8
    assert TRUTH_COL not in res["profile"]["medias"].columns  # el modelo nunca ve la respuesta
    for f in ["modelos.csv", "informe.html", "clientes_segmentados.csv", "modelo.joblib", "personas_plantilla.yaml"]:
        assert (tmp_path / f).exists(), f
