"""Orquestador del clasificador automático: de un host a clasificacion.csv en un solo barrido."""

from __future__ import annotations

import ipaddress
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from common import OUT_DIR

from . import motor
from .base import Cliente, Rasgos, recortar
from .descubrir import CRLF, PROTOS_WEB, _CMD, _leer, disponibilidad, escanear, identificar
from .generativo import sondear_generativo
from .http_generico import sondear_base, sondear_buscador, sondear_formularios, sondear_openapi
from .productos import sondear_productos
from .proto import CREDS_TRIVIALES, sondear_protocolo, sondear_ssh

SALIDA = OUT_DIR / "nics_auto"
MANUAL = OUT_DIR / "nics_entrega" / "veredicto.csv"


def _alcance(host: str, autorizado: bool) -> None:
    """Control de alcance: solo hosts de redes privadas/locales salvo autorización explícita."""
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
    except (OSError, ValueError):
        raise SystemExit(f"No se puede resolver {host}")
    if not (ip.is_private or ip.is_loopback) and not autorizado:
        raise SystemExit(f"{host} ({ip}) no es una red privada. Escanea solo lo autorizado: añade --autorizado si lo está.")


def _descartado(host: str, port: int, service: str, motivo: str) -> list[dict]:
    """Evidencia de un puerto no disponible: el saludo y qué pasa al enviar un comando."""
    log: list[dict] = []
    if service in _CMD:
        try:
            t0 = time.time()
            with socket.create_connection((host, port), timeout=8) as s:
                saludo = _leer(s, 400, 3).decode("latin1", "replace").strip()
                log.append({"port": port, "grupo": "descartado", "prueba": "saludo al conectar", "peticion": f"telnet {host} {port}",
                            "estado": "-", "ms": round((time.time() - t0) * 1000), "respuesta": recortar(saludo, 300)})
                cmd = _CMD[service]
                t1 = time.time()
                s.sendall(cmd)
                r = _leer(s, 400, 4)
                log.append({"port": port, "grupo": "descartado", "prueba": f"comando enviado: {cmd.decode().strip()}",
                            "peticion": f"telnet {host} {port}  →  {cmd.decode().strip()}", "estado": "-",
                            "ms": round((time.time() - t1) * 1000),
                            "respuesta": r.decode("latin1", "replace").strip() or "(la conexión se cierra o calla sin contestar)"})
        except OSError as e:
            log.append({"port": port, "grupo": "descartado", "prueba": "conexión", "peticion": f"telnet {host} {port}",
                        "estado": "ERR", "ms": 0, "respuesta": f"{type(e).__name__}: {e}"})
    else:
        log.append({"port": port, "grupo": "descartado", "prueba": "disponibilidad", "peticion": f"{service} {host}:{port}",
                    "estado": "-", "ms": 0, "respuesta": motivo})
    return log


def analizar(host: str, port: int, opc: dict) -> dict:
    ident = identificar(host, port)
    service = ident["service"]
    fila = {"port": port, "service": service, "banner": ident["banner"][:120]}
    if service == "cerrado":
        return {**fila, "disponible": False, "motivo": "cerrado", "log": []}
    disp, motivo = disponibilidad(host, port, service)
    fila.update(disponible=disp, motivo=motivo)
    if not disp:
        return {**fila, "log": _descartado(host, port, service, motivo)}
    r = Rasgos()
    log: list[dict] = []
    if service in PROTOS_WEB:
        cli = Cliente(host, port, service)
        html = sondear_base(cli, r)
        sondear_buscador(cli, r, html)
        sondear_formularios(cli, r, html)
        sondear_openapi(cli, r)
        sondear_productos(cli, r, html)
        sondear_generativo(cli, r, rep=opc["rep"], rapido=opc["rapido"])
        log = cli.log
        fila["clave_gemelo"] = f"{service}|{r.get('servidor')}|{r.get('titulo')}|{r.get('producto')}"
    elif service == "ssh":
        sondear_ssh(host, port, r, log, creds=opc["creds"])
        fila["clave_gemelo"] = f"ssh|{ident['banner']}"
    else:
        sondear_protocolo(host, port, service, r, log)
        fila["clave_gemelo"] = f"{service}|{ident['banner']}"
    return {**fila, "rasgos": r.v, "detalle": r.detalle, "log": log}


def clasificar_todo(servicios: list[dict], cfg: dict) -> pd.DataFrame:
    filas = []
    for s in servicios:
        c = motor.clasificar(s["rasgos"], s["detalle"], cfg)
        filas.append({"port": s["port"], "service": s["service"].upper(), "producto": s["rasgos"].get("producto", ""),
                      "clase": c["clase"], "class": c["class"], "confianza": c["confianza"], "revisar": c["revisar"],
                      "reglas": c["reglas"], "evidencias": c["evidencias"], "puntos_real": c["puntos_real"],
                      "puntos_clasico": c["puntos_clasico"], "puntos_generativo": c["puntos_generativo"],
                      "clave_gemelo": s.get("clave_gemelo", "")})
    df = pd.DataFrame(filas).sort_values("port").reset_index(drop=True)
    grupos = df.groupby("clave_gemelo")["port"].apply(list).to_dict()
    df["gemelos"] = [",".join(str(p) for p in grupos[k] if p != port) for k, port in zip(df["clave_gemelo"], df["port"])]
    return df.drop(columns="clave_gemelo")


def guardar(df: pd.DataFrame, servicios: list[dict], descartados: list[dict], salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    df.to_csv(salida / "clasificacion.csv", index=False, encoding="utf-8-sig")
    df[["port", "service", "class"]].to_csv(salida / "entrega.csv", index=False)
    rasgos = pd.DataFrame([{"port": s["port"], "service": s["service"], **s["rasgos"]} for s in servicios]).sort_values("port")
    rasgos.to_csv(salida / "rasgos.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{k: d.get(k) for k in ("port", "service", "motivo", "banner")} for d in descartados]) \
        .sort_values("port").to_csv(salida / "no_disponibles.csv", index=False, encoding="utf-8-sig")
    pruebas = [x for s in servicios + descartados for x in s.get("log", [])]
    pd.DataFrame(pruebas).sort_values("port", kind="stable").to_csv(salida / "pruebas.csv", index=False, encoding="utf-8-sig")
    (salida / "rasgos.json").write_text(json.dumps(
        {"servicios": [{k: s[k] for k in ("port", "service", "rasgos", "detalle", "clave_gemelo") if k in s} for s in servicios],
         "descartados": [{k: d.get(k) for k in ("port", "service", "motivo", "banner")} for d in descartados]},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def validar(df: pd.DataFrame, salida: Path, manual: Path = MANUAL) -> pd.DataFrame | None:
    """Compara con el veredicto confirmado a mano (la verdad de referencia), nunca se usa para clasificar."""
    if not manual.exists():
        return None
    m = pd.read_csv(manual, encoding="utf-8-sig")[["port", "clase"]].rename(columns={"clase": "manual"})
    v = df[["port", "service", "clase", "confianza", "reglas"]].rename(columns={"clase": "auto"}).merge(m, on="port", how="outer")
    v["coincide"] = v["auto"] == v["manual"]
    v.sort_values("port").to_csv(salida / "validacion.csv", index=False, encoding="utf-8-sig")
    return v


def ejecutar(host: str = "10.66.0.1", puertos: list[int] | None = None, rango: tuple[int, int] = (1, 65535),
             inventario: Path | None = None, salida: Path = SALIDA, rep: int = 2, rapido: bool = False, hilos: int = 6,
             reglas: Path = motor.REGLAS, reclasificar: bool = False, autorizado: bool = False,
             validar_contra: Path | None = MANUAL, sin_ssh_login: bool = False) -> pd.DataFrame:
    cfg = motor.cargar_reglas(reglas)
    t0 = time.time()
    if reclasificar:
        datos = json.loads((salida / "rasgos.json").read_text(encoding="utf-8"))
        servicios, descartados = datos["servicios"], datos["descartados"]
        print(f"[reclasificar] {len(servicios)} servicios con las reglas de {reglas}")
        prev = pd.read_csv(salida / "pruebas.csv", encoding="utf-8-sig") if (salida / "pruebas.csv").exists() else None
        for s in servicios:
            s["log"] = prev[prev["port"] == s["port"]].to_dict("records") if prev is not None else []
        for d in descartados:
            d["log"] = prev[prev["port"] == d["port"]].to_dict("records") if prev is not None else []
    else:
        _alcance(host, autorizado)
        if puertos:
            abiertos = sorted(puertos)
            print(f"[1/5] Puertos indicados: {len(abiertos)}")
        elif inventario:
            inv = pd.read_csv(inventario)
            if "state" in inv.columns:
                inv = inv[inv["state"] == "open"]
            abiertos = sorted(int(p) for p in inv["port"])
            print(f"[1/5] Inventario {inventario}: {len(abiertos)} puertos abiertos")
        else:
            print(f"[1/5] Escaneando {host} puertos {rango[0]}-{rango[1]} ...")
            abiertos = escanear(host, rango)
            print(f"      {len(abiertos)} puertos abiertos ({time.time() - t0:.0f} s)")
        opc = {"rep": rep, "rapido": rapido, "creds": [] if sin_ssh_login else CREDS_TRIVIALES}
        print(f"[2-4/5] Identificando, filtrando no disponibles y sondeando {len(abiertos)} puertos ({hilos} en paralelo) ...")
        hechos = []

        def uno(p):
            res = analizar(host, p, opc)
            estado = "DISPONIBLE" if res["disponible"] else "no disponible"
            print(f"      {p:>5} {res['service']:<8} {estado}", flush=True)
            return res

        with ThreadPoolExecutor(hilos) as ex:
            hechos = list(ex.map(uno, abiertos))
        servicios = [h for h in hechos if h["disponible"]]
        descartados = [h for h in hechos if not h["disponible"]]
    print(f"[5/5] Clasificando {len(servicios)} servicios disponibles ({len(descartados)} descartados)")
    df = clasificar_todo(servicios, cfg)
    guardar(df, servicios, descartados, salida)
    print(f"\nResultado ({time.time() - t0:.0f} s) -> {salida}")
    print(df["clase"].value_counts().rename("nº").to_string())
    print(f"\nA revisar (confianza baja): {int(df['revisar'].sum())}")
    if validar_contra:
        v = validar(df, salida, validar_contra)
        if v is not None:
            comp = v.dropna(subset=["auto", "manual"])
            ok = int(comp["coincide"].sum())
            print(f"\nValidación contra el veredicto manual: {ok}/{len(comp)} coinciden ({ok / max(len(comp), 1):.0%})")
            for _, x in comp[~comp["coincide"]].iterrows():
                print(f"   ✗ {int(x['port'])} {x['service']}: auto={x['auto']} · manual={x['manual']} · reglas {x['reglas']}")
    return df
