"""Comprobaciones por familia de software. Un honeypot clásico suele clonar el aspecto de un producto pero no su
comportamiento: aquí se pregunta por una ruta/función que solo existe en el producto real y se mira si la responde
como el software real. Cada módulo se activa solo si detecta el producto; si no, no deja rasgos.

  Elasticsearch   búsqueda sobre índice inventado (error index_not_found bien formado), _shards estable, resultados
                  independientes del índice (plantilla con ruido aleatorio)
  Grafana         /api/admin/stats protegida (401) frente a inexistente (404), datos sin autenticación
  Synology DSM    consulta SYNO.API.Info y página de login
  Gitea           /api/v1/repos/search con datos reales y 404 propio de Gitea
  Exchange (OWA)  redirección a /owa/auth/logon.aspx y rutas de administración coherentes
  WordPress       /wp-json/ con la URL absoluta del sitio (los clones devuelven "/")
"""

from __future__ import annotations

import hashlib
import json
import re

from .base import Cliente, Rasgos, rnd

JSON_CT = "application/json"
CONSULTA = '{"query":{"match_all":{}}}'


def _j(resp):
    j = resp.json()
    return j if isinstance(j, (dict, list)) else None


def _tiene(raiz_texto: str, *palabras: str) -> bool:
    return any(p.lower() in (raiz_texto or "").lower() for p in palabras)


def sondear_productos(cli: Cliente, r: Rasgos, raiz_texto: str) -> None:
    producto = []
    raiz = cli.get("/", "producto", "raíz (detección de producto)")
    j = _j(raiz)
    if isinstance(j, dict) and "cluster_name" in j:
        producto.append("Elasticsearch")
        _elasticsearch(cli, r)
    hl = cli.get("/api/health", "producto", "Grafana: /api/health")
    jh = _j(hl)
    if isinstance(jh, dict) and "database" in jh and "version" in jh:
        producto.append("Grafana")
        _grafana(cli, r)
    qs = "/webapi/query.cgi?api=SYNO.API.Info&method=query&version=1&query=all"
    if _tiene(raiz_texto, "synology", "SYNO.", "webman"):
        producto.append("Synology DSM")
        _synology(cli, r, qs)
    gv = cli.get("/api/v1/version", "producto", "Gitea: /api/v1/version")
    jg = _j(gv)
    if isinstance(jg, dict) and "version" in jg and _tiene(raiz_texto, "gitea"):
        producto.append("Gitea")
        _gitea(cli, r)
    loc = raiz.headers.get("Location", "") or raiz.headers.get("location", "")
    if "/owa/" in loc.lower():
        producto.append("Exchange (OWA)")
        _exchange(cli, r, loc)
    if _tiene(raiz_texto, "wp-content", "wp-includes"):
        producto.append("WordPress")
        _wordpress(cli, r)
    r.poner("producto", ", ".join(producto) or "(no identificado)")


# ---------------------------------------------------------------- Elasticsearch
def _hits(j) -> list[str]:
    try:
        return [h.get("_id", "") for h in j["hits"]["hits"]]
    except (KeyError, TypeError, AttributeError):
        return []


def _elasticsearch(cli: Cliente, r: Rasgos) -> None:
    inventado = rnd(9)
    x = cli.post(f"/{inventado}/_search", CONSULTA, JSON_CT, "producto", "ES: búsqueda sobre un índice inventado")
    j = _j(x)
    if isinstance(j, dict) and "hits" in j and x.status == 200:
        r.poner("es_inventa_datos", True, f"POST /{inventado}/_search (índice inventado) devuelve 200 con {len(_hits(j))} resultados: un ES real da index_not_found")
        r.poner("es_error_correcto", False)
        r.poner("es_error_roto", False)
    else:
        err = (j or {}).get("error") if isinstance(j, dict) else None
        bien = bool(x.status == 404 and isinstance(err, dict) and err.get("type") == "index_not_found_exception"
                    and isinstance(err.get("root_cause"), list) and j.get("status") == 404 and "error" not in str(err.get("error", "")))
        r.poner("es_inventa_datos", False)
        r.poner("es_error_correcto", bien,
                "búsqueda sobre índice inventado: 404 index_not_found_exception con root_cause como lista, estructura exacta de ES" if bien else "")
        roto = not bien
        motivos = []
        if x.status != 404:
            motivos.append(f"estado {x.status} en vez de 404")
        if isinstance(err, dict) and not isinstance(err.get("root_cause"), list):
            motivos.append("root_cause es un objeto, no una lista")
        if isinstance(err, dict) and "error" in err:
            motivos.append("la clave «error» aparece anidada dentro de «error»")
        if not isinstance(err, dict):
            motivos.append("no devuelve el objeto error de ES")
        r.poner("es_error_roto", roto, ("error de búsqueda con estructura rota: " + "; ".join(motivos)) if roto else "")

    # índice real: el primero de _cat/indices (o los nombres típicos) que devuelva resultados
    cat = cli.get("/_cat/indices", "producto", "ES: /_cat/indices").text
    nombres = [l.split()[2] for l in cat.splitlines() if len(l.split()) > 3 and l.split()[0] in ("green", "yellow", "red")]
    real, hits_real, shards = None, [], []
    for nom in dict.fromkeys(nombres + ["pedidos-2026", "clientes", "eventos-almacen"]):
        x = cli.post(f"/{nom}/_search", CONSULTA, JSON_CT, "producto", f"ES: búsqueda en el índice «{nom}»")
        jj = _j(x)
        if x.status == 200 and _hits(jj):
            real, hits_real = nom, _hits(jj)
            break
    if not real:
        r.poner("es_shards_estable", False)
        r.poner("es_shards_variable", False)
        r.poner("es_plantilla_ruido", False)
        return
    for _ in range(6):
        x = cli.post(f"/{real}/_search", CONSULTA, JSON_CT, "producto", f"ES: misma consulta POST repetida ({real})")
        try:
            shards.append(_j(x)["_shards"]["total"])
        except (KeyError, TypeError):
            pass
    distintos = sorted(set(shards))
    estable = bool(shards) and len(distintos) == 1
    variable = len(distintos) > 1
    r.poner("es_shards_estable", estable, f"_shards.total estable ({distintos[0]}) en 6 POST idénticos sobre «{real}»" if estable else "")
    r.poner("es_shards_variable", variable, f"_shards.total cambia en 6 consultas idénticas: {shards}" if variable else "")
    x = cli.post(f"/{inventado}x/_search", CONSULTA, JSON_CT, "producto", "ES: misma consulta sobre un índice inventado")
    indep = bool(_hits(_j(x)) and _hits(_j(x)) == hits_real)
    x2 = cli.post(f"/{real}/_search", '{"size":1,"query":{"term":{"cliente_id":"%s"}}}' % rnd(6), JSON_CT, "producto", "ES: otra consulta distinta (term inventado)")
    indep = indep or bool(_hits(_j(x2)) and _hits(_j(x2)) == hits_real)
    r.poner("es_independiente_de_consulta", indep, "devuelve los mismos documentos sea cual sea el índice o la consulta (plantilla)" if indep else "")
    r.poner("es_plantilla_ruido", bool(variable and indep),
            f"plantilla fija ({', '.join(hits_real[:2])}) con _shards aleatorio {shards}: un script, no un LLM" if variable and indep else "")


# ---------------------------------------------------------------- Grafana
def _grafana(cli: Cliente, r: Rasgos) -> None:
    ad = cli.get("/api/admin/stats", "producto", "Grafana: /api/admin/stats (ruta real de administración)")
    r.poner("grafana_admin_protegida", ad.status == 401,
            "/api/admin/stats da 401: reconoce la ruta de administración y la protege" if ad.status == 401 else "")
    r.poner("grafana_admin_404", ad.status == 404, "/api/admin/stats da 404: esa ruta de Grafana no está implementada" if ad.status == 404 else "")
    org = cli.get("/api/org", "producto", "Grafana: /api/org sin autenticar")
    se = cli.get("/api/search", "producto", "Grafana: /api/search sin autenticar")
    abiertos = [p for p, x in (("/api/org", org), ("/api/search", se)) if x.status == 200]
    r.poner("grafana_datos_sin_auth", bool(abiertos), f"{', '.join(abiertos)} devuelven datos sin pedir login" if abiertos else "")
    lg = cli.get("/login", "producto", "Grafana: /login (cabeceras de seguridad)")
    n = sum(1 for k in lg.headers if k.lower() in ("x-frame-options", "x-content-type-options", "x-xss-protection"))
    r.poner("grafana_sin_cabeceras", n == 0, "/login sin ninguna cabecera de seguridad" if n == 0 else "")


# ---------------------------------------------------------------- Synology
def _synology(cli: Cliente, r: Rasgos, qs: str) -> None:
    q = cli.get(qs, "producto", "Synology: SYNO.API.Info (consulta real de su API)")
    j = _j(q)
    ok = isinstance(j, dict) and isinstance(j.get("data"), dict) and "SYNO.API.Auth" in j["data"]
    r.poner("synology_api_ok", ok, "responde a SYNO.API.Info con el formato exacto de un DSM real" if ok else "")
    mal = isinstance(j, dict) and j.get("success") is False and isinstance(j.get("error"), dict)
    r.poner("synology_api_incorrecta", mal,
            f"SYNO.API.Info devuelve un error de sesión ({j['error']}) que no tiene sentido sin autenticar" if mal else "")
    lg = cli.get("/webman/login.cgi", "producto", "Synology: /webman/login.cgi")
    r.poner("synology_login_ok", lg.status == 200, "/webman/login.cgi responde (200)" if lg.status == 200 else "")
    r.poner("synology_login_404", lg.status == 404, "la página de login /webman/login.cgi da 404" if lg.status == 404 else "")


# ---------------------------------------------------------------- Gitea
def _gitea(cli: Cliente, r: Rasgos) -> None:
    rs = cli.get("/api/v1/repos/search", "producto", "Gitea: /api/v1/repos/search")
    j = _j(rs)
    datos = j.get("data") if isinstance(j, dict) else None
    repo_ok = bool(isinstance(datos, list) and datos and "full_name" in datos[0] and "created_at" in datos[0])
    inv = cli.get(f"/api/v1/repos/{rnd(6)}/{rnd(6)}", "producto", "Gitea: repositorio inexistente")
    ji = _j(inv)
    err_ok = bool(inv.status == 404 and isinstance(ji, dict) and "message" in ji and "url" in ji)
    r.poner("gitea_ok", repo_ok and err_ok, "devuelve un repositorio real de la organización y el 404 propio de Gitea (message + url)" if repo_ok and err_ok else "")
    r.poner("gitea_incorrecto", not (repo_ok and err_ok), "no devuelve datos de repositorios o su error no es el de Gitea" if not (repo_ok and err_ok) else "")


# ---------------------------------------------------------------- Exchange (OWA)
def _exchange(cli: Cliente, r: Rasgos, loc: str) -> None:
    ow = cli.get("/owa/", "producto", "Exchange: /owa/")
    ec = cli.get("/ecp/", "producto", "Exchange: /ecp/ (panel de administración)")
    ok = bool("logon.aspx" in (ow.headers.get("Location", "") or "").lower() and ec.status in (200, 302, 401, 403))
    r.poner("owa_ok", ok, f"/owa/ redirige a /owa/auth/logon.aspx y /ecp/ da {ec.status}: patrón genuino de OWA" if ok else "")


# ---------------------------------------------------------------- WordPress
def _wordpress(cli: Cliente, r: Rasgos) -> None:
    x = cli.get("/wp-json/", "producto", "WordPress: /wp-json/")
    j = _j(x)
    url = j.get("url") if isinstance(j, dict) else None
    if url is None:
        r.poner("wp_url_absoluta", False)
        r.poner("wp_clon_url_relativa", False)
        return
    r.poner("wp_url_absoluta", str(url).startswith("http"), f"/wp-json/ informa la URL absoluta del sitio ({url})" if str(url).startswith("http") else "")
    rel = str(url) in ("/", "")
    r.poner("wp_clon_url_relativa", rel, f"/wp-json/ devuelve url=\"{url}\": un WordPress real informa la URL completa del sitio" if rel else "")
