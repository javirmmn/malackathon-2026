"""Banco de pruebas local: 3 servicios en 127.0.0.1 para comprobar que el kit los distingue.

    python -m kits.nics.testbed          (los deja arrancados hasta Ctrl+C)

  :8081  real                 web corporativa estática, 404 en rutas inexistentes, cabeceras normales
  :8082  honeypot clásico     misma página de login para cualquier ruta, banner antiguo, sin cabecera Date
  :8083  honeypot generativo  se inventa la respuesta a cualquier ruta. Usa Ollama si está disponible
                              (OLLAMA_URL, OLLAMA_MODEL); si no, un simulador con plantillas y latencia de LLM
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

PORTS = {"real": 8081, "honeypot_clasico": 8082, "honeypot_generativo": 8083}

# ------------------------------------------------------------------ real
real = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_PAGE = "<!doctype html><html><head><title>{t}</title></head><body><h1>{t}</h1><p>{p}</p></body></html>"


@real.get("/", response_class=HTMLResponse)
def real_root():
    return _PAGE.format(t="Intranet Acme", p="Portal interno de empleados. Accede con tu usuario corporativo.")


@real.get("/about", response_class=HTMLResponse)
def real_about():
    return _PAGE.format(t="Sobre nosotros", p="Acme S.L., Málaga.")


@real.get("/robots.txt", response_class=PlainTextResponse)
def real_robots():
    return "User-agent: *\nDisallow: /admin\n"


# ------------------------------------------------------------------ honeypot clásico
classic = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_LOGIN = ("<html><head><title>Login</title></head><body><form method='post' action='/login'>"
          "User: <input name='u'> Password: <input type='password' name='p'><input type='submit'></form></body></html>")


@classic.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE"])
def classic_any(path: str):
    return HTMLResponse(_LOGIN, headers={"Server": "Apache/2.2.22 (Ubuntu)"})


# ------------------------------------------------------------------ honeypot generativo
gen = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
_NOMBRES = ["Laura Gómez", "Carlos Ruiz", "Marta Sánchez", "Javier López", "Ana Torres", "Pablo Díaz"]
_DEPTOS = ["Finanzas", "Recursos Humanos", "Sistemas", "Ventas", "Logística"]


_ollama_ok: bool | None = None  # se comprueba una vez (en Windows cada conexión rechazada tarda ~2 s)


async def _ollama(prompt: str) -> str | None:
    global _ollama_ok
    if _ollama_ok is None:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                _ollama_ok = (await c.get(f"{OLLAMA_URL}/api/tags")).status_code == 200
        except Exception:  # noqa: BLE001
            _ollama_ok = False
        print(f"[testbed] Ollama {'disponible' if _ollama_ok else 'no disponible: uso el simulador de LLM'}")
    if not _ollama_ok:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{OLLAMA_URL}/api/generate",
                             json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                                   "options": {"temperature": 0.9, "num_predict": 350}})  # respuestas de tamaño web
            return r.json().get("response")
    except Exception:  # noqa: BLE001
        return None


def _fake_llm(path: str, api: bool) -> str:
    """Imita a un LLM: contenido verosímil, distinto en cada llamada, que se adapta a la ruta pedida."""
    seg = [s for s in path.strip("/").split("/") if s] or ["inicio"]
    if api:
        return json.dumps({
            "id": random.randint(1000, 99999), "recurso": seg[-2] if len(seg) > 1 else seg[0],
            "responsable": random.choice(_NOMBRES), "departamento": random.choice(_DEPTOS),
            "estado": random.choice(["activo", "pendiente", "revisión"]),
            "actualizado": f"2026-{random.randint(1, 9):02d}-{random.randint(1, 28):02d}",
            "descripcion": f"Registro asociado a {seg[-2] if len(seg) > 1 else seg[0]} gestionado por {random.choice(_DEPTOS)}.",
        }, ensure_ascii=False)
    titulo = seg[-1].replace(".html", "").replace("-", " ").capitalize()
    frases = [
        f"Bienvenido a la sección {titulo} de la intranet.",
        f"Esta página recoge la información más reciente sobre {titulo.lower()}.",
        f"Contacto: {random.choice(_NOMBRES)} ({random.choice(_DEPTOS)}).",
        f"Última actualización: {random.randint(1, 28)}/{random.randint(1, 9)}/2026.",
        f"Hay {random.randint(2, 40)} documentos disponibles para su consulta.",
        "Para cualquier duda, abre una incidencia en el portal de soporte.",
    ]
    random.shuffle(frases)
    return _PAGE.format(t=titulo, p=" ".join(frases[: random.randint(3, 6)]))


@gen.api_route("/{path:path}", methods=["GET", "POST", "HEAD", "OPTIONS"])
async def gen_any(path: str, request: Request):
    full = "/" + path + (f"?{request.url.query}" if request.url.query else "")
    api = path.startswith("api/")
    prompt = (f"Eres el servidor web de la intranet de una empresa española. Devuelve SOLO el cuerpo "
              f"{'JSON' if api else 'HTML'} de la respuesta a la petición {request.method} {full}. Sin explicaciones.")
    body = await _ollama(prompt)
    if body is None:
        await asyncio.sleep(random.uniform(0.3, 1.3))  # latencia típica de generación de texto
        body = _fake_llm(path, api)
    return Response(body, media_type="application/json" if api else "text/html")


# ------------------------------------------------------------------ arranque
APPS = {"real": (real, {}), "honeypot_clasico": (classic, {"date_header": False, "server_header": False}),
        "honeypot_generativo": (gen, {})}


def start(block: bool = False) -> list[uvicorn.Server]:
    servers = []
    for name, (app, extra) in APPS.items():
        cfg = uvicorn.Config(app, host="127.0.0.1", port=PORTS[name], log_level="warning", **extra)
        srv = uvicorn.Server(cfg)
        threading.Thread(target=srv.run, daemon=True).start()
        servers.append(srv)
    deadline = time.time() + 15
    while not all(s.started for s in servers):
        if time.time() > deadline:
            raise RuntimeError("El banco de pruebas no arrancó (¿puertos 8081-8083 ocupados?)")
        time.sleep(0.1)
    if block:
        print("Banco de pruebas en marcha:", {k: f"http://127.0.0.1:{p}" for k, p in PORTS.items()}, "· Ctrl+C para parar")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    return servers


def stop(servers: list[uvicorn.Server]) -> None:
    for s in servers:
        s.should_exit = True


if __name__ == "__main__":
    start(block=True)
