"""Kit NICS · descubre, sondea y clasifica servicios web: real / honeypot clásico / honeypot generativo.

    python -m kits.nics.run --testbed                                  (ensayo con los 3 servicios locales)
    python -m kits.nics.run --targets data/servicios.csv --scope 10.10.0.0/16
    python -m kits.nics.run --solo-clasificar                          (reclasifica tras editar rules.yaml)

Salidas en out/nics/: evidencias.csv, rasgos.csv, resultados.csv/.json, informe.md, informe.html
Dashboard:  streamlit run kits/nics/app.py
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from common import OUT_DIR

from . import classifier, collector, features, inventory, report

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = OUT_DIR / "nics"


def classify_saved(out: Path = DEFAULT_OUT, rules_path: Path = HERE / "rules.yaml") -> pd.DataFrame:
    """Recalcula rasgos y clases a partir de evidencias.csv (sin volver a tocar la red)."""
    ev = pd.read_csv(out / "evidencias.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""],
                     dtype={"cuerpo": str, "error": str})
    ev["cuerpo"] = ev["cuerpo"].fillna("")
    ev["error"] = ev["error"].fillna("")
    rules = classifier.load_rules(rules_path)
    feats = features.service_features(ev, rules)
    res = classifier.classify(feats, rules)
    feats.to_csv(out / "rasgos.csv", index=False, encoding="utf-8-sig")
    res.drop(columns="evidencias").to_csv(out / "resultados.csv", index=False, encoding="utf-8-sig")
    (out / "resultados.json").write_text(res.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    report.save(res, feats, ev, out)

    targets_file = out / "objetivos.csv"
    if targets_file.exists():
        t = pd.read_csv(targets_file)
        if "etiqueta_real" in t:
            m = res.merge(t[["url", "etiqueta_real"]], left_on="url_base", right_on="url")
            print(f"      Aciertos frente a etiqueta_real: {(m['clase'] == m['etiqueta_real']).sum()}/{len(m)}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", type=Path, help="CSV/YAML con url (o host+port) de cada servicio")
    ap.add_argument("--scope", default="", help="rangos/hosts autorizados, separados por comas (además de localhost)")
    ap.add_argument("--testbed", action="store_true", help="arranca los 3 servicios simulados y los analiza")
    ap.add_argument("--repeticiones", type=int, help="sobrescribe 'repeticiones' de probes.yaml")
    ap.add_argument("--probes", type=Path, default=HERE / "probes.yaml")
    ap.add_argument("--rules", type=Path, default=HERE / "rules.yaml")
    ap.add_argument("--verify-tls", action="store_true", help="validar certificados (por defecto no, por si son autofirmados)")
    ap.add_argument("--solo-clasificar", action="store_true", help="no escanear: reclasificar evidencias.csv")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if not args.solo_clasificar:
        servers = None
        if args.testbed:
            from . import testbed

            servers = testbed.start()
            args.targets = args.targets or HERE / "targets_testbed.csv"
            print("[0/4] Banco de pruebas arrancado en 127.0.0.1:8081-8083")
        if not args.targets:
            ap.error("indica --targets (o --testbed)")
        targets = inventory.load_targets(args.targets)
        inventory.check_scope(targets, [s.strip() for s in args.scope.split(",") if s.strip()])
        targets.to_csv(args.out / "objetivos.csv", index=False)
        print(f"[1/4] {len(targets)} servicios en el inventario (todos dentro del alcance)")

        cfg = collector.load_probes(args.probes)
        print(f"[2/4] Sondeando ({len(cfg['sondas'])} sondas, {args.repeticiones or cfg['repeticiones']} repeticiones)...")
        ev = collector.collect(targets, cfg, args.repeticiones, verify_tls=args.verify_tls)
        ev.to_csv(args.out / "evidencias.csv", index=False, encoding="utf-8-sig")
        if servers:
            testbed.stop(servers)

    print("[3/4] Calculando rasgos y clasificando...")
    res = classify_saved(args.out, args.rules)
    print(f"[4/4] Informe -> {args.out / 'informe.html'}  ({time.time() - t0:.0f} s)\n")
    with pd.option_context("display.max_colwidth", 90, "display.width", 200):
        print(res[["servicio", "clase", "confianza", "que_lo_delato"]].to_string(index=False))


if __name__ == "__main__":
    main()
