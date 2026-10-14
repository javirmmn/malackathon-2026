"""El kit de NTT detecta las alucinaciones plantadas y reutiliza el modelo en datos nuevos (prueba sorpresa)."""

from kits.ntt import scorer, signals
from kits.ntt.guardian import Guardian
from kits.ntt.run import run
from kits.ntt.sample_data import generate


def test_senales_basicas():
    fuentes = "Datanova fue fundada en 2009 en Sevilla. Tiene 1.350 empleados y la dirige Elena Castro."
    fiel = signals.compute("Datanova se fundó en Sevilla en 2009 y cuenta con 1350 empleados.", fuentes)
    assert fiel["cifras_no_en_fuentes"] == 0 and fiel["nombres_no_en_fuentes"] == 0
    malo = signals.compute("Datanova se fundó en 2011 y la dirige Raúl Ortega.", fuentes)
    assert malo["cifras_no_en_fuentes"] == 1 and malo["nombres_no_en_fuentes"] >= 1
    assert signals.compute("La empresa no tiene sede en Sevilla.", fuentes)["negacion_nueva"] == 1


def test_entrena_y_aplica_a_datos_nuevos(tmp_path):
    res = run(generate(n=100, seed=1), out=tmp_path)
    assert res["metrics"]["validacion_cruzada"]["f1"] > 0.85
    nuevo = run(generate(n=60, seed=99), out=tmp_path / "sorpresa", model_path=tmp_path / "modelo.json")
    assert nuevo["metrics"]["sobre_estos_datos"]["accuracy"] > 0.85


def test_guardian_sin_modelo_usa_pesos_por_defecto(tmp_path):
    g = Guardian(modelo=tmp_path / "no_existe.json")
    out = g.evaluar("La facturación fue de 950 millones.", ["La facturación fue de 233 millones de euros."])
    assert out["alucina"] and any("950" in m for m in out["motivos"])
    assert scorer.default_model(["cifras_no_en_fuentes"])["threshold"] == 0.5
