"""El "martillo de consistencia": para cada dirección conocida de cada puerto, repite la MISMA
petición (GET o POST, con el mismo cuerpo) varias veces y compara las respuestas byte a byte.

Es la prueba que destapó el puerto 50096 (Elasticsearch generativo): con GET simple el contenido
parecía fijo, pero repitiendo la misma consulta POST varias veces, un dato interno que debería ser
fijo (_shards.total) cambiaba en cada llamada. Aquí se aplica esa misma prueba a los 40 puertos.

    python -m kits.nics.martillo_consistencia                 (todos los puertos del catálogo)
    python -m kits.nics.martillo_consistencia --puerto 50096  (solo uno, para depurar)
    python -m kits.nics.martillo_consistencia --repeticiones 8
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pandas as pd

from common import OUT_DIR

HOST = "10.66.0.1"
OUT = OUT_DIR / "nics_entrega"


@dataclass
class Peticion:
    metodo: str
    ruta: str
    cuerpo: dict | None = None

    @property
    def etiqueta(self) -> str:
        return f"{self.metodo} {self.ruta}" + (f" {json.dumps(self.cuerpo)}" if self.cuerpo else "")


@dataclass
class Puerto:
    puerto: int
    clase_actual: str
    peticiones: list[Peticion] = field(default_factory=list)


# ---------------------------------------------------------------------- catálogo de endpoints conocidos
def _p(metodo: str, ruta: str, cuerpo: dict | None = None) -> Peticion:
    return Peticion(metodo, ruta, cuerpo)


SEARCH_BODY = {"query": {"match_all": {}}, "size": 1}

CATALOGO: list[Puerto] = [
    # ---------------- Clase 1: real ----------------
    Puerto(22739, "real", [_p("GET", "/"), _p("GET", "/_cat/indices?v"),
                           _p("POST", "/eventos-almacen/_search", SEARCH_BODY),
                           _p("POST", "/clientes/_search", SEARCH_BODY)]),
    Puerto(20150, "real", [_p("GET", "/api/v1/health"), _p("GET", "/api/v1/almacenes"),
                           _p("GET", "/api/v1/estadisticas"), _p("GET", "/api/v1/movimientos"),
                           _p("GET", "/api/v1/items/SKU-NO-EXISTE-999"),
                           _p("POST", "/api/v1/items", {"sku": "TEST", "nombre": "prueba"})]),
    Puerto(44700, "real", [_p("GET", "/"), _p("GET", "/?s=prueba_consistencia")]),
    Puerto(48519, "real", [_p("GET", "/index.html"), _p("GET", "/empresa.html"),
                           _p("POST", "/contacto/enviar", {"nombre": "X", "email": "x@x.com"})]),
    Puerto(47163, "real", [_p("GET", "/webapi/query.cgi?api=SYNO.API.Info&version=1&method=query")]),
    Puerto(46737, "real", [_p("GET", "/owa/"), _p("GET", "/ecp/"),
                           _p("GET", "/Microsoft-Server-ActiveSync")]),
    Puerto(57238, "real", [_p("GET", "/api/v1/repos/search?limit=10"),
                           _p("GET", "/api/v1/repos/ondalux/no-existe")]),
    Puerto(29082, "real", [_p("GET", "/api/org"), _p("GET", "/api/search"), _p("GET", "/api/health")]),
    # ---------------- Clase 2: honeypot clásico ----------------
    Puerto(24179, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-1")]),
    Puerto(35574, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-2")]),
    Puerto(39640, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-3")]),
    Puerto(47095, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-4")]),
    Puerto(48200, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-5")]),
    Puerto(51656, "clasico", [_p("GET", "/"), _p("GET", "/ruta-aleatoria-6")]),
    Puerto(56221, "clasico", [_p("GET", "/api/v1/health"), _p("GET", "/api/v1/almacenes"),
                              _p("GET", "/api/v1/estadisticas"), _p("GET", "/api/v1/movimientos")]),
    Puerto(20808, "clasico", [_p("GET", "/"), _p("GET", "/?s=prueba_consistencia")]),
    Puerto(25589, "clasico", [_p("GET", "/"), _p("GET", "/?s=prueba_consistencia")]),
    Puerto(51999, "clasico", [_p("GET", "/index.html"),
                              _p("POST", "/contacto/enviar", {"nombre": "X", "email": "x@x.com"})]),
    Puerto(59004, "clasico", [_p("GET", "/index.html"),
                              _p("POST", "/contacto/enviar", {"nombre": "X", "email": "x@x.com"})]),
    Puerto(34328, "clasico", [_p("GET", "/webapi/query.cgi?api=SYNO.API.Info&version=1&method=query")]),
    Puerto(56377, "clasico", [_p("GET", "/webapi/query.cgi?api=SYNO.API.Info&version=1&method=query")]),
    Puerto(31885, "clasico", [_p("GET", "/"), _p("POST", "/eventos-almacen/_search", SEARCH_BODY),
                              _p("POST", "/indice-inventado-xyz/_search", SEARCH_BODY)]),
    Puerto(25461, "clasico", [_p("GET", "/api/org"), _p("GET", "/api/search"), _p("GET", "/api/health")]),
    # ---------------- Clase 3: generativo (control, debe seguir variando) ----------------
    Puerto(50096, "generativo", [_p("GET", "/"), _p("POST", "/pedidos-2026/_search", SEARCH_BODY),
                                 _p("POST", "/indice-inventado-xyz/_search", SEARCH_BODY)]),
]


# ---------------------------------------------------------------------- ejecución
def _ejecutar(client: httpx.Client, puerto: int, pet: Peticion) -> str:
    url = f"https://{HOST}:{puerto}{pet.ruta}"
    try:
        r = client.request(pet.metodo, url, json=pet.cuerpo, timeout=15)
        return r.text
    except httpx.HTTPError as e:
        return f"__ERROR__ {type(e).__name__}: {e}"


def _diferencia_clave(textos: list[str]) -> str:
    """Intenta explicar EN QUÉ varían, comparando como JSON si se puede."""
    try:
        docs = [json.loads(t) for t in textos]
    except (json.JSONDecodeError, TypeError):
        a, b = textos[0], textos[-1]
        diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0))
        return " | ".join(diff[2:6]) if len(diff) > 2 else "(texto distinto, sin JSON)"

    def _aplanar(d, prefijo=""):
        out = {}
        if isinstance(d, dict):
            for k, v in d.items():
                out.update(_aplanar(v, f"{prefijo}.{k}" if prefijo else k))
        elif isinstance(d, list):
            for i, v in enumerate(d[:3]):
                out.update(_aplanar(v, f"{prefijo}[{i}]"))
        else:
            out[prefijo] = d
        return out

    planos = [_aplanar(d) for d in docs]
    claves = set().union(*[p.keys() for p in planos])
    variables = [k for k in sorted(claves) if len({p.get(k, "<ausente>") for p in planos}) > 1]
    detalle = ", ".join(f"{k}={[p.get(k) for p in planos]}" for k in variables[:4])
    return detalle or "(varía el JSON pero no he sabido localizar el campo)"


def hammer(catalogo: list[Puerto], repeticiones: int = 6) -> pd.DataFrame:
    filas = []
    with httpx.Client(verify=False) as client:
        for pz in catalogo:
            for pet in pz.peticiones:
                textos = [_ejecutar(client, pz.puerto, pet) for _ in range(repeticiones)]
                hashes = {hashlib.sha1(t.encode()).hexdigest() for t in textos}
                estable = len(hashes) == 1
                print(f"  {'estable ' if estable else '¡VARÍA! '} {pz.puerto} {pz.clase_actual:10} {pet.etiqueta}")
                filas.append({
                    "puerto": pz.puerto, "clase_actual": pz.clase_actual, "peticion": pet.etiqueta,
                    "estable": estable, "n_respuestas_distintas": len(hashes),
                    "detalle_variacion": "" if estable else _diferencia_clave(textos),
                })
    return pd.DataFrame(filas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puerto", type=int, help="limitar a un puerto del catálogo")
    ap.add_argument("--repeticiones", type=int, default=6)
    ap.add_argument("--out", type=Path, default=OUT / "martillo_consistencia.csv")
    a = ap.parse_args()
    catalogo = [pz for pz in CATALOGO if a.puerto is None or pz.puerto == a.puerto]
    print(f"Martillo de consistencia: {sum(len(p.peticiones) for p in catalogo)} peticiones × "
          f"{a.repeticiones} repeticiones, sobre {len(catalogo)} puertos\n")
    df = hammer(catalogo, a.repeticiones)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")

    varia = df[~df["estable"]]
    print(f"\n{'=' * 70}\n{len(varia)} de {len(df)} peticiones VARÍAN entre repeticiones idénticas:\n{'=' * 70}")
    if len(varia):
        for _, r in varia.iterrows():
            print(f"\n  puerto {r['puerto']} ({r['clase_actual']}) · {r['peticion']}")
            print(f"    {r['detalle_variacion'][:300]}")
    else:
        print("  (ninguna)")
    sospechosos = varia[~varia["puerto"].isin([50096])]
    if len(sospechosos):
        print(f"\n⚠ {len(sospechosos)} puertos varían y NO son el generativo ya confirmado — revisar a mano:")
        print(sospechosos[["puerto", "clase_actual", "peticion"]].drop_duplicates("puerto").to_string(index=False))


if __name__ == "__main__":
    main()
