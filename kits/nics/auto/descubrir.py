"""Etapas 1-3: descubrir puertos abiertos, identificar el protocolo y comprobar que el servicio está DISPONIBLE.

Criterio de la organización: solo cuentan los servicios abiertos y disponibles. Un puerto que acepta la conexión,
saluda y cierra (o se queda mudo) sin contestar a un comando válido NO ofrece servicio: queda fuera de la clasificación.
"""

from __future__ import annotations

import re
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor

from .base import Cliente

CRLF = bytes([13, 10])
PROTOS_WEB = ("http", "https")


def escanear(host: str, rango: tuple[int, int] = (1, 65535), hilos: int = 500, timeout: float = 1.2) -> list[int]:
    """Escaneo TCP connect del rango. Devuelve los puertos que aceptan la conexión."""

    def abierto(p: int) -> int | None:
        try:
            with socket.create_connection((host, p), timeout=timeout):
                return p
        except OSError:
            return None

    with ThreadPoolExecutor(hilos) as ex:
        return sorted(p for p in ex.map(abierto, range(rango[0], rango[1] + 1)) if p)


def _leer(s: socket.socket, n: int = 400, espera: float = 3.0) -> bytes:
    s.settimeout(espera)
    try:
        return s.recv(n)
    except (socket.timeout, OSError):
        return b""


def identificar(host: str, port: int) -> dict:
    """Protocolo del puerto a partir del saludo (o, si no saluda, probando TLS y HTTP)."""
    banner = b""
    try:
        with socket.create_connection((host, port), timeout=6) as s:
            banner = _leer(s, 400, 2.5)
    except OSError:
        return {"service": "cerrado", "banner": ""}
    t = banner.decode("latin1", "replace").strip()
    if banner:
        if t.startswith("SSH-"):
            return {"service": "ssh", "banner": t}
        if banner[0] == 255:
            return {"service": "telnet", "banner": t}
        if t.startswith("+OK"):
            return {"service": "pop3", "banner": t}
        if t.startswith("* OK"):
            return {"service": "imap", "banner": t}
        if t.startswith("220"):
            if re.search(r"smtp|postfix|exim|sendmail", t, re.I):
                return {"service": "smtp", "banner": t}
            if re.search(r"ftp|filezilla", t, re.I):
                return {"service": "ftp", "banner": t}
            return {"service": "ftp", "banner": t}
        if t.startswith("HTTP/"):
            return {"service": "http", "banner": t}
    # no saluda: ¿TLS?
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=6) as raw, ctx.wrap_socket(raw) as s:
            s.settimeout(5)
            s.sendall(b"GET / HTTP/1.0" + CRLF + b"Host: x" + CRLF + CRLF)
            r = s.recv(200).decode("latin1", "replace")
            return {"service": "https" if r.startswith("HTTP/") else "tls_desconocido", "banner": r[:80]}
    except (OSError, ssl.SSLError):
        pass
    try:
        with socket.create_connection((host, port), timeout=6) as s:
            s.sendall(b"GET / HTTP/1.0" + CRLF + b"Host: x" + CRLF + CRLF)
            r = _leer(s, 200, 4).decode("latin1", "replace")
            if r.startswith("HTTP/"):
                return {"service": "http", "banner": r[:80]}
    except OSError:
        pass
    return {"service": "desconocido", "banner": t}


_CMD = {"pop3": b"USER prueba" + CRLF, "smtp": b"EHLO prueba" + CRLF, "imap": b"a1 CAPABILITY" + CRLF,
        "ftp": b"USER prueba" + CRLF, "telnet": b"admin" + CRLF}
_VALIDA = {"pop3": re.compile(r"^(\+OK|-ERR)", re.I), "smtp": re.compile(r"^[2-5]\d\d"),
           "imap": re.compile(r"^(\*|a1)\s", re.I), "ftp": re.compile(r"^[1-5]\d\d"), "telnet": re.compile(r".")}


def disponibilidad(host: str, port: int, service: str) -> tuple[bool, str]:
    """(disponible, motivo). Disponible = ofrece servicio: contesta a un comando válido del protocolo."""
    if service in PROTOS_WEB:
        cli = Cliente(host, port, service, timeout=15)
        for _ in range(3):
            if cli.get("/", "disponibilidad", "GET /").ok:
                return True, "responde HTTP"
        return False, "no contesta a peticiones HTTP"
    if service == "ssh":
        import paramiko

        try:
            with socket.create_connection((host, port), timeout=8) as s:
                tr = paramiko.Transport(s)
                tr.start_client(timeout=10)
                ok = tr.is_active()
                tr.close()
                return ok, "completa el intercambio de claves" if ok else "no completa el intercambio de claves"
        except Exception as e:  # noqa: BLE001
            return False, f"saluda (banner SSH) y corta antes de completar el intercambio de claves ({type(e).__name__})"
    if service in _CMD:
        try:
            with socket.create_connection((host, port), timeout=8) as s:
                saludo = _leer(s, 400, 3)
                s.sendall(_CMD[service])
                r = _leer(s, 400, 4)
                if r.strip() and _VALIDA[service].search(r.decode("latin1", "replace").strip()):
                    return True, "contesta a un comando válido"
                if not r:
                    return False, "saluda y cierra/calla sin contestar al comando (saludo: " + saludo[:40].decode("latin1", "replace").strip() + ")"
                return True, "contesta (formato no estándar)"
        except OSError as e:
            return False, f"error de conexión ({type(e).__name__})"
    return False, "protocolo no identificado o sin respuesta"
