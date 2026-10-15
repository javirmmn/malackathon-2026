"""CLI:  python -m kits.nics.auto --host 10.66.0.1"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import motor
from .pipeline import MANUAL, SALIDA, ejecutar


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m kits.nics.auto",
                                 description="Clasificador automático NICS: real / honeypot clásico / honeypot generativo.")
    ap.add_argument("--host", default="10.66.0.1", help="host a analizar (por defecto el del reto)")
    ap.add_argument("--puertos", help="lista de puertos separados por comas (en vez de escanear)")
    ap.add_argument("--rango", default="1-65535", help="rango a escanear si no se da --puertos/--inventario")
    ap.add_argument("--inventario", type=Path, help="CSV con columna port (y state) para saltar el escaneo")
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--rep", type=int, default=2, help="repeticiones de las pruebas de obediencia (la obediencia es estocástica)")
    ap.add_argument("--rapido", action="store_true", help="menos prefijos y cuerpos en la batería de generativo")
    ap.add_argument("--hilos", type=int, default=6, help="puertos analizados en paralelo")
    ap.add_argument("--reglas", type=Path, default=motor.REGLAS)
    ap.add_argument("--reclasificar", action="store_true", help="reaplica las reglas a los rasgos ya medidos, sin volver a sondear")
    ap.add_argument("--autorizado", action="store_true", help="confirma que el host fuera de redes privadas está autorizado")
    ap.add_argument("--validar", type=Path, default=MANUAL, help="CSV con la verdad de referencia (columnas port, clase)")
    ap.add_argument("--sin-validar", action="store_true")
    ap.add_argument("--sin-ssh-login", action="store_true", help="no probar credenciales triviales en SSH")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.rango.split("-"))
    ejecutar(host=a.host, puertos=[int(p) for p in a.puertos.split(",")] if a.puertos else None, rango=(lo, hi),
             inventario=a.inventario, salida=a.salida, rep=a.rep, rapido=a.rapido, hilos=a.hilos, reglas=a.reglas,
             reclasificar=a.reclasificar, autorizado=a.autorizado, validar_contra=None if a.sin_validar else a.validar,
             sin_ssh_login=a.sin_ssh_login)


if __name__ == "__main__":
    sys.exit(main())
