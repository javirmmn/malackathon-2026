"""HTML -> PDF (o PNG) con Chrome/Edge en modo headless. Sirve para la presentación y para el plan.

    python -m common.pdf docs/presentacion/nics.html              -> docs/presentacion/nics.pdf
    python -m common.pdf docs/plan_fuente.html --out Plan_Malackathon_2026.pdf
    python -m common.pdf docs/arquitectura/nics.svg --png --size 1136,400
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str:
    for c in _CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    raise FileNotFoundError("No encuentro Chrome ni Edge para generar el PDF.")


def render(src: Path, out: Path, png: bool = False, size: tuple[int, int] = (1280, 720)) -> Path:
    src, out = Path(src).resolve(), Path(out).resolve()
    args = [find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--hide-scrollbars"]
    if png:
        args += [f"--screenshot={out}", f"--window-size={size[0]},{size[1]}"]
    else:
        args += [f"--print-to-pdf={out}"]
    subprocess.run(args + [src.as_uri()], check=True, capture_output=True, timeout=120)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--size", default="1280,720", help="ancho,alto para --png")
    args = ap.parse_args()
    out = args.out or args.src.with_suffix(".png" if args.png else ".pdf")
    w, h = (int(x) for x in args.size.split(","))
    print(render(args.src, out, args.png, (w, h)))


if __name__ == "__main__":
    main()
