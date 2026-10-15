"""Sondas genéricas para cualquier servicio web (sin saber qué producto es): referencia, catch-all, buscador,
formularios y esquema OpenAPI. Cada sonda deja rasgos con su detalle concreto (lo que se observó)."""

from __future__ import annotations

import difflib
import re
from urllib.parse import urljoin, urlparse

from .base import Cliente, Rasgos, huella, rnd

SEG_HEADERS = ("x-frame-options", "x-content-type-options", "x-xss-protection", "strict-transport-security",
               "content-security-policy", "referrer-policy")
ESTADOS_OK_FORM = {200, 201, 202, 204, 301, 302, 303}
ESTADOS_KO_FORM = {403, 404, 405, 500, 501, 502, 503}


def _similitud(a: str, b: str) -> float:
    """Parecido entre dos páginas por líneas (0-1)."""
    return difflib.SequenceMatcher(None, a.splitlines()[:600], b.splitlines()[:600], autojunk=False).ratio()


def _cuerpo_error(texto: str) -> str:
    """Si el cuerpo es una página de error (aunque el estado HTTP diga 200), devuelve su título."""
    m = re.search(r"<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>", texto or "", re.I | re.S)
    t = re.sub(r"<[^>]+>", "", (m.group(1) or m.group(2) or "") if m else "").strip()
    return t if re.search(r"(?<![0-9])(40[0-9]|50[0-9])(?![0-9])|forbidden|not found|no encontrad|error", t, re.I) and not re.search(r"(?<![0-9])30[0-9](?![0-9])", t) else ""


def sondear_base(cli: Cliente, r: Rasgos) -> str:
    """Respuesta normal y rutas inventadas. Devuelve el HTML de la raíz para las demás sondas."""
    raiz = cli.get("/", "base", "raíz")
    h = {k.lower(): v for k, v in raiz.headers.items()}
    titulo = re.search(r"<title[^>]*>(.*?)</title>", raiz.text, re.I | re.S)
    r.poner("status_raiz", raiz.status, f"GET / -> {raiz.status}")
    r.poner("servidor", h.get("server", ""))
    r.poner("titulo", (titulo.group(1).strip()[:80] if titulo else ""))
    n_seg = sum(1 for k in SEG_HEADERS if k in h)
    r.poner("cabeceras_seguridad", n_seg, f"{n_seg} de {len(SEG_HEADERS)} cabeceras de seguridad en /")

    tokens = [rnd(9) for _ in range(3)]
    inex = [(t, cli.get("/" + t, "base", "ruta inventada")) for t in tokens]
    estados = [x.status for _, x in inex]
    r.poner("estados_inexistente", ",".join(str(s) for s in estados))
    base_h = huella(raiz.text)
    igual_raiz = [x.status == raiz.status and huella(x.text, t) == base_h for t, x in inex]
    catch_all = bool(raiz.status and raiz.status < 400 and all(igual_raiz))
    r.poner("catch_all", catch_all,
            f"respuesta byte a byte idéntica en / y en 3 rutas inventadas (estado {raiz.status})" if catch_all else "")
    realista = all(s == 404 for s in estados) and not catch_all
    r.poner("notfound_realista", realista, f"las rutas inventadas dan {estados}" if realista else "")
    return raiz.text


def sondear_buscador(cli: Cliente, r: Rasgos, html_raiz: str) -> None:
    """¿Hay un buscador? ¿Busca de verdad o devuelve siempre la portada?"""
    hay = re.search(r"name=[\"']s[\"']|type=[\"']search[\"']|role=[\"']search[\"']|wp-content", html_raiz or "", re.I)
    if not hay:
        r.poner("busqueda_ignorada", False)
        r.poner("busqueda_funciona", False)
        return
    t1, t2 = rnd(10), rnd(10)
    raiz = cli.get("/", "base", "raíz (referencia del buscador)")
    a = cli.get("/", "buscador", f"búsqueda ?s={t1}", params={"s": t1})
    b = cli.get("/", "buscador", f"búsqueda ?s={t2}", params={"s": t2})
    sim_raiz = _similitud(a.text, raiz.text)
    ignorada = bool(a.status == b.status == raiz.status and sim_raiz > 0.97 and _similitud(b.text, raiz.text) > 0.97)
    r.poner("busqueda_ignorada", ignorada,
            f"?s=<texto inventado> devuelve la portada ({sim_raiz:.0%} igual a /) con cualquier búsqueda" if ignorada else "")
    sin_res = re.search(r"no se (ha )?encontr|sin resultados|nothing found|no results|0 resultados", a.text, re.I)
    refleja = t1 in a.text and t2 in b.text and t1 not in b.text
    ignorada = ignorada and not refleja
    funciona = bool(not ignorada and a.status == 200 and (sin_res or refleja or sim_raiz < 0.9))
    r.poner("busqueda_funciona", funciona,
            "el buscador responde distinto de la portada y usa el término buscado (página de resultados)" if funciona else "")


def _formularios(html: str):
    for m in re.finditer(r"<form\b([^>]*)>(.*?)</form>", html or "", re.I | re.S):
        attrs, cuerpo = m.group(1), m.group(2)
        metodo = (re.search(r"method=[\"']?(\w+)", attrs, re.I) or [None, "get"])[1].lower()
        accion = (re.search(r"action=[\"']([^\"']*)", attrs, re.I) or [None, ""])[1]
        campos = [n for _, n in re.findall(r"<(input|textarea|select)\b[^>]*name=[\"']([^\"']+)", cuerpo, re.I)]
        yield metodo, accion, campos


def sondear_formularios(cli: Cliente, r: Rasgos, html_raiz: str) -> None:
    """Envía un formulario de contacto de prueba: ¿hay backend que lo procese?"""
    paginas = [("/", html_raiz)]
    enlaces = re.findall(r"href=[\"']([^\"'#]*contact[^\"'#]*)[\"']", html_raiz or "", re.I)
    candidatos = list(dict.fromkeys(enlaces))[:2] or ["/contacto", "/contacto.html", "/contact"]
    for c in candidatos:
        ruta = urlparse(urljoin("/", c)).path or "/"
        rr = cli.get(ruta, "formulario", f"página de contacto {ruta}")
        if rr.status == 200:
            paginas.append((ruta, rr.text))
    resultados = []
    for ruta_pag, html in paginas:
        for metodo, accion, campos in _formularios(html):
            if metodo != "post" or not campos:
                continue
            destino = urlparse(urljoin(ruta_pag, accion)).path or ruta_pag
            datos = "&".join(f"{c}={'prueba%40example.com' if 'mail' in c.lower() else 'Prueba'}" for c in campos)
            x = cli.post(destino, datos, "application/x-www-form-urlencoded", "formulario", f"POST {destino} (formulario de contacto)")
            titulo_err = _cuerpo_error(x.text)
            resultados.append((destino, x.status if not titulo_err else f"{x.status} con cuerpo «{titulo_err}»"))
    if not resultados:
        r.poner("form_funciona", False)
        r.poner("form_sin_backend", False)
        return
    ok = [x for x in resultados if x[1] in ESTADOS_OK_FORM]
    ko = [x for x in resultados if x[1] in ESTADOS_KO_FORM or isinstance(x[1], str)]
    txt = "; ".join(f"POST {d} -> {s}" for d, s in resultados)
    r.poner("form_funciona", bool(ok) and not ko, txt if ok and not ko else "")
    r.poner("form_sin_backend", bool(ko) and not ok, f"{txt} (no se procesa el envío)" if ko and not ok else "")


def _resolver(spec: dict, s: dict | None) -> dict:
    while s and "$ref" in s:
        s = spec.get("components", {}).get("schemas", {}).get(s["$ref"].split("/")[-1])
    return s or {}


def _forma_ok(spec: dict, op: dict, datos) -> bool:
    """¿La respuesta tiene la forma que el propio esquema declara (claves requeridas / al menos una propiedad)?"""
    try:
        sch = op["responses"]["200"]["content"]["application/json"]["schema"]
    except (KeyError, TypeError):
        return True
    s = _resolver(spec, sch)
    if s.get("type") == "array":
        if not isinstance(datos, list):
            return False
        s, datos = _resolver(spec, s.get("items")), (datos[0] if datos else None)
        if datos is None:
            return True
    props = list((s.get("properties") or {}).keys())
    if not props:
        return True
    if not isinstance(datos, dict):
        return False
    faltan = [k for k in s.get("required", []) if k not in datos]
    return not faltan and any(k in datos for k in props)


def sondear_openapi(cli: Cliente, r: Rasgos) -> None:
    """Si el servicio publica su esquema, llama a cada endpoint declarado: ¿responde y con la forma prometida?"""
    spec = None
    for p in ["/openapi.json", "/swagger.json", "/api/openapi.json", "/api/v1/openapi.json"]:
        x = cli.get(p, "openapi", f"esquema {p}")
        j = x.json() if x.status == 200 else None
        if isinstance(j, dict) and isinstance(j.get("paths"), dict):
            spec = j
            break
    if not spec:
        r.poner("openapi_declarado", False)
        r.poner("openapi_incoherente", False)
        r.poner("openapi_coherente", False)
        return
    llamadas, fallos = 0, []
    for ruta, ops in list(spec["paths"].items())[:14]:
        if "{" in ruta or "get" not in ops or ruta.startswith(("/docs", "/openapi", "/redoc")):
            continue
        x = cli.get(ruta, "openapi", f"endpoint declarado {ruta}")
        llamadas += 1
        j = x.json() if x.status == 200 else None
        try:
            declarados = list(ops["get"]["responses"]["200"]["content"].keys())
        except (KeyError, TypeError):
            declarados = ["application/json"]
        ct = {k.lower(): v for k, v in x.headers.items()}.get("content-type", "").lower()
        descarga = x.status == 200 and not any(t in ct for t in ("json", "html", "text/plain", "xml")) and ct != ""
        if x.status == 200 and ("application/json" not in declarados or descarga):
            continue                      # descarga de archivo (PDF...) o tipo no JSON declarado: basta con que responda
        if x.status != 200 or j is None:
            fallos.append(f"{ruta} -> {x.status}")
        elif not _forma_ok(spec, ops["get"], j):
            fallos.append(f"{ruta} -> 200 pero con forma distinta a la declarada")
    r.poner("openapi_declarado", True, f"publica /openapi.json con {len(spec['paths'])} rutas")
    r.poner("openapi_endpoints", llamadas)
    inco = llamadas >= 2 and len(fallos) / llamadas >= 0.2
    r.poner("openapi_incoherente", inco, ("sus propios endpoints declarados fallan: " + "; ".join(fallos[:4])) if inco else "")
    coh = llamadas >= 2 and not fallos
    r.poner("openapi_coherente", coh, f"los {llamadas} endpoints declarados funcionan y devuelven la forma prometida" if coh else "")
