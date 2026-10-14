"""Los resultados de los kits se pueden subir a Oracle: DDL válido y filas convertibles (sin conectar)."""

import common.db as db
from kits.mercedes.run import run as run_mercedes
from kits.mercedes.sample_data import generate
from kits.nics import run as nics_run


def _fake_df_to_table(captured):
    def fake(df, table, if_exists="fail", batch_size=5000):
        ddl = db.create_table_sql(df, table)
        assert ddl.count(",") >= len(df.columns) - 1
        for row in df.itertuples(index=False):
            for v in row:
                v = db._to_python(v)
                assert v is None or isinstance(v, (str, int, float)) or hasattr(v, "year"), (table, type(v))
        captured[table] = ddl
        return len(df)
    return fake


def test_mercedes_a_oracle(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(db, "df_to_table", _fake_df_to_table(captured))
    run_mercedes(generate(n=300, seed=3), out=tmp_path, kmax=4, model="kmeans_k3", umap=False, eda=False,
                 oracle_prefix="merc")
    assert set(captured) == {"MERC_CLIENTES", "MERC_SEGMENTOS", "MERC_MODELOS"}
    assert "FECHA_ALTA TIMESTAMP" in captured["MERC_CLIENTES"]


def test_nics_a_oracle(monkeypatch):
    if not (nics_run.DEFAULT_OUT / "evidencias.csv").exists():
        import pytest
        pytest.skip("ejecuta antes: python -m kits.nics.run --testbed")
    captured = {}
    monkeypatch.setattr(db, "df_to_table", _fake_df_to_table(captured))
    nics_run.save_to_oracle("nics")
    assert set(captured) == {"NICS_RESULTADOS", "NICS_RASGOS", "NICS_EVIDENCIAS"}
