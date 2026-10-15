"""Utilidades comunes a todos los retos: carga de ficheros, gráficos y PDF."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
