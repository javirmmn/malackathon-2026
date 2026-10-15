"""Motor de reglas ponderadas: rasgos de un servicio -> clase, confianza y evidencias concretas."""

from __future__ import annotations

from pathlib import Path

import yaml

REGLAS = Path(__file__).with_name("reglas.yaml")
CLASE_A_NUM = {"real": 1, "honeypot_clasico": 2, "honeypot_generativo": 3}


def cargar_reglas(path: Path = REGLAS) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _cumple(valor, regla: dict) -> bool:
    if "op" in regla:
        ops = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b,
               "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
        return valor is not None and ops[regla["op"]](valor, regla["valor"])
    return bool(valor)


def clasificar(rasgos: dict, detalles: dict, cfg: dict) -> dict:
    """rasgos: nombre -> valor; detalles: nombre -> texto concreto observado."""
    puntos = {c: 0.0 for c in cfg["clases"]}
    disparadas: list[dict] = []
    for rg in cfg["reglas"]:
        if _cumple(rasgos.get(rg["rasgo"]), rg):
            puntos[rg["clase"]] += rg["peso"]
            disparadas.append({"id": rg["id"], "clase": rg["clase"], "peso": rg["peso"], "que": rg["que"],
                               "detalle": detalles.get(rg["rasgo"], "")})
    um = cfg["umbrales"]
    gen, cla, rea = puntos["honeypot_generativo"], puntos["honeypot_clasico"], puntos["real"]
    if gen >= um["honeypot_generativo"]:
        clase = "honeypot_generativo"
    elif cla >= um["honeypot_clasico"] and cla > rea:
        clase = "honeypot_clasico"
    elif cla > rea:
        clase = "honeypot_clasico"      # evidencia clásica débil pero sin nada a favor de real
    else:
        clase = "real"
    otros = max(v for k, v in puntos.items() if k != clase)
    cf = cfg["confianza"]
    # Un generativo que supera su umbral es decisivo: las señales de «clásico» que lo acompañan (shell falsa, login
    # trivial...) son coherentes con un honeypot de IA y no restan confianza.
    margen = puntos[clase] if clase == "honeypot_generativo" else puntos[clase] - otros
    if not disparadas:
        confianza = cf["base"]
        evidencias = ["Sin señales: no se detectó nada anómalo ni nada que pruebe que funciona de verdad "
                      "(clasificado como real por defecto; conviene revisar a mano)."]
    else:
        confianza = round(min(cf["maximo"], cf["base"] + cf["por_punto"] * margen), 2)
        decisivas = sorted(disparadas, key=lambda d: (d["clase"] != clase, -d["peso"]))
        evidencias = [f"[{d['id']} +{d['peso']:g}] {d['que']}" + (f" — {d['detalle']}" if d["detalle"] else "")
                      for d in decisivas]
    return {"clase": clase, "class": CLASE_A_NUM[clase], "confianza": confianza,
            "revisar": confianza < cf["revisar_por_debajo"],
            "puntos_real": rea, "puntos_clasico": cla, "puntos_generativo": gen,
            "reglas": ",".join(d["id"] for d in disparadas), "evidencias": " | ".join(evidencias)}
