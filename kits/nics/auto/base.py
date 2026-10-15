"""Utilidades comunes: cliente HTTP que registra cada prueba (petición -> respuesta), normalización de respuestas."""

from __future__ import annotations

import hashlib
import json
import random
import re
import string
import time
from dataclasses import dataclass
from urllib.parse import quote, unquote, unquote_plus, urlencode

import requests
import urllib3

urllib3.disable_warnings()
MAX_LOG = 500


def rnd(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


@dataclass
class Resp:
    status: int | None
    ms: float
    text: str
    headers: dict

    @property
    def ok(self) -> bool:
        return self.status is not None

    def json(self):
        try:
            return json.loads(self.text)
        except (ValueError, TypeError):
            return None


def norm(texto: str, *tokens: str) -> str:
    """Texto sin espacios y con el nombre inventado de la ruta sustituido: dos respuestas «iguales salvo el nombre»
    dan el mismo resultado (un servicio real refleja la ruta en sus errores, eso no es una diferencia)."""
    t = texto or ""
    for tok in tokens:
        if not tok:
            continue
        for v in {tok, tok.upper(), tok.lower(), quote(tok), unquote(tok), quote(tok, safe="")}:
            t = re.sub(re.escape(v), "<T>", t, flags=re.I)
    return re.sub(r"\s+", "", t)


def huella(texto: str, *tokens: str) -> str:
    return hashlib.md5(norm(texto, *tokens).encode("utf8", "ignore")).hexdigest()


def recortar(texto: str, n: int = 220) -> str:
    return " ⏎ ".join((texto or "").strip().splitlines())[:n]


def decodificado(texto: str) -> str:
    """Un reflejo codificado (%20, +) sigue siendo un reflejo."""
    return unquote_plus(unquote(texto or ""))


class Cliente:
    """Un puerto web. Cada petición queda en `self.log` con el grupo de prueba al que pertenece."""

    def __init__(self, host: str, port: int, esquema: str, timeout: float = 30.0):
        self.host, self.port, self.esquema, self.timeout = host, port, esquema, timeout
        self.base = f"{esquema}://{host}:{port}"
        self.log: list[dict] = []
        self.n = 0

    def req(self, metodo: str, ruta: str, grupo: str, prueba: str, data: str | None = None, ct: str | None = None,
            params: dict | None = None, headers: dict | None = None) -> Resp:
        h = dict(headers or {})
        if data is not None and ct:
            h["Content-Type"] = ct
        t0 = time.time()
        try:
            r = requests.request(metodo, self.base + ruta, data=data.encode("utf8") if isinstance(data, str) else data,
                                 params=params, headers=h or None, verify=False, timeout=self.timeout,
                                 allow_redirects=False)
            resp = Resp(r.status_code, (time.time() - t0) * 1000, r.text, dict(r.headers))
        except Exception as e:  # noqa: BLE001
            resp = Resp(None, (time.time() - t0) * 1000, f"ERR {type(e).__name__}: {e}", {})
        self.n += 1
        curl = f"curl -sk{'' if metodo == 'GET' else ' -X ' + metodo}"
        for k, v in h.items():
            curl += f' -H "{k}: {v}"'
        if data is not None:
            curl += f' -d "{data}"'
        curl += f' "{self.base}{ruta}{("?" + urlencode(params)) if params else ""}"'
        self.log.append({"port": self.port, "grupo": grupo, "prueba": prueba, "peticion": curl,
                         "estado": resp.status if resp.status is not None else "ERR", "ms": round(resp.ms),
                         "respuesta": recortar(resp.text, MAX_LOG)})
        return resp

    def get(self, ruta: str, grupo: str = "base", prueba: str = "", **kw) -> Resp:
        return self.req("GET", ruta, grupo, prueba or f"GET {ruta}", **kw)

    def post(self, ruta: str, data: str, ct: str, grupo: str = "base", prueba: str = "", **kw) -> Resp:
        return self.req("POST", ruta, grupo, prueba or f"POST {ruta}", data=data, ct=ct, **kw)


class Rasgos:
    """Valores calculados por las sondas, cada uno con el detalle concreto que lo justifica."""

    def __init__(self) -> None:
        self.v: dict[str, object] = {}
        self.detalle: dict[str, str] = {}

    def poner(self, nombre: str, valor, detalle: str = "") -> None:
        self.v[nombre] = valor
        if detalle:
            self.detalle[nombre] = detalle

    def get(self, nombre: str, defecto=None):
        return self.v.get(nombre, defecto)
