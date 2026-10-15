"""Interacción real (no solo banner) con los servicios de autenticación: SSH, POP3, Telnet.

El enunciado avisa de que "se delata cuando lo usas en serio". Este módulo hace, de forma
automatizada y con una sola conexión por servicio (nada de fuerza bruta), lo que se haría a mano:
- SSH: handshake completo, huella de la clave de host, un intento de contraseña (usuario/clave
  de ensayo, nunca reales) y qué algoritmos ofrece el servidor.
- POP3: USER/PASS de ensayo y el texto exacto de cada respuesta.
- Telnet: negociación de opciones + usuario/clave de ensayo, capturando el prompt que aparece.

    python -m kits.nics.interactuar --puertos 24226,34818 --protocolo ssh
    python -m kits.nics.interactuar --puertos 28827,51629 --protocolo pop3
    python -m kits.nics.interactuar --puertos 45025,53020 --protocolo telnet
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from common import OUT_DIR

HOST = "10.66.0.1"
USUARIO_ENSAYO, CLAVE_ENSAYO = "test", "test123"


def ssh_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    import paramiko

    info: dict = {"host": host, "port": port}
    sock = None
    try:
        sock = socket_connect(host, port, timeout)
        t = paramiko.Transport(sock)
        t.start_client(timeout=timeout)
        key = t.get_remote_server_key()
        info["version_remota"] = t.remote_version
        info["huella_clave_host"] = f"{key.get_name()} {key.get_fingerprint().hex()}"
        info["algoritmos_kex"] = t.get_security_options().kex
        try:
            t.auth_password(USUARIO_ENSAYO, CLAVE_ENSAYO)
            info["auth"] = "ACEPTADA (raro con credenciales de ensayo: revisar)"
        except paramiko.AuthenticationException as e:
            info["auth"] = f"rechazada: {e}"
            info["metodos_auth_permitidos"] = getattr(e, "allowed_types", None)
        t.close()
    except Exception as e:  # noqa: BLE001 — queremos capturar cualquier fallo de protocolo como evidencia
        info["error"] = f"{type(e).__name__}: {e}"
    finally:
        if sock:
            sock.close()
    return info


def socket_connect(host: str, port: int, timeout: float):
    import socket

    s = socket.create_connection((host, port), timeout=timeout)
    return s


async def _leer(reader: asyncio.StreamReader, timeout: float, n: int = 4096) -> bytes:
    try:
        return await asyncio.wait_for(reader.read(n), timeout=timeout)
    except (asyncio.TimeoutError, ConnectionError):
        return b""


async def pop3_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    info: dict = {"host": host, "port": port, "dialogo": []}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        info["dialogo"].append(("<", (await _leer(reader, timeout)).decode(errors="replace").strip()))
        for cmd in (f"USER {USUARIO_ENSAYO}", f"PASS {CLAVE_ENSAYO}", "STAT", "QUIT"):
            writer.write((cmd + "\r\n").encode())
            await writer.drain()
            resp = (await _leer(reader, timeout)).decode(errors="replace").strip()
            info["dialogo"].append((f"> {cmd}", resp))
            if not resp:
                break
        writer.close()
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def _strip_telnet_iac(data: bytes) -> tuple[bytes, bytes]:
    """Separa el texto visible de las secuencias de negociación IAC (RFC 854) y genera la respuesta mínima."""
    IAC, DO, DONT, WILL, WONT = 255, 253, 254, 251, 252
    texto, respuesta, i = bytearray(), bytearray(), 0
    while i < len(data):
        if data[i] == IAC and i + 2 < len(data):
            cmd, opt = data[i + 1], data[i + 2]
            if cmd in (DO, WILL):
                respuesta += bytes([IAC, WONT if cmd == DO else DONT, opt])
            i += 3
        else:
            texto.append(data[i])
            i += 1
    return bytes(texto), bytes(respuesta)


async def smtp_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    """EHLO real (no un comando inventado): un Postfix/Exim real contesta con su lista de extensiones."""
    info: dict = {"host": host, "port": port, "dialogo": []}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        info["dialogo"].append(("<", (await _leer(reader, timeout)).decode(errors="replace").strip()))
        for cmd in ("EHLO malackathon.local", "MAIL FROM:<test@malackathon.local>", "RCPT TO:<test@ondalux.local>", "QUIT"):
            writer.write((cmd + "\r\n").encode())
            await writer.drain()
            resp = (await _leer(reader, timeout)).decode(errors="replace").strip()
            info["dialogo"].append((f"> {cmd}", resp))
            if not resp:
                break
        writer.close()
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


async def imap_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    """CAPABILITY real: todo servidor IMAP conforme al RFC debe responder a esto, lo primero que hace cualquier cliente."""
    info: dict = {"host": host, "port": port, "dialogo": []}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        info["dialogo"].append(("<", (await _leer(reader, timeout)).decode(errors="replace").strip()))
        for cmd in ("a1 CAPABILITY", f"a2 LOGIN {USUARIO_ENSAYO} {CLAVE_ENSAYO}", "a3 LOGOUT"):
            writer.write((cmd + "\r\n").encode())
            await writer.drain()
            resp = (await _leer(reader, timeout)).decode(errors="replace").strip()
            info["dialogo"].append((f"> {cmd}", resp))
            if not resp:
                break
        writer.close()
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


async def ftp_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    """USER/PASS/PWD/SYST reales: un FTP real siempre contesta algo a cada uno, aunque rechace el login."""
    info: dict = {"host": host, "port": port, "dialogo": []}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        info["dialogo"].append(("<", (await _leer(reader, timeout)).decode(errors="replace").strip()))
        for cmd in (f"USER {USUARIO_ENSAYO}", f"PASS {CLAVE_ENSAYO}", "SYST", "PWD", "QUIT"):
            writer.write((cmd + "\r\n").encode())
            await writer.drain()
            resp = (await _leer(reader, timeout)).decode(errors="replace").strip()
            info["dialogo"].append((f"> {cmd}", resp))
            if not resp:
                break
        writer.close()
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


async def telnet_probe(host: str, port: int, timeout: float = 15.0) -> dict:
    info: dict = {"host": host, "port": port, "dialogo": []}
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        raw = await _leer(reader, timeout)
        texto, respuesta_iac = _strip_telnet_iac(raw)
        if respuesta_iac:
            writer.write(respuesta_iac)
            await writer.drain()
            raw2 = await _leer(reader, 3.0)
            texto += _strip_telnet_iac(raw2)[0]
        info["dialogo"].append(("<", texto.decode(errors="replace").strip()))
        for linea in (USUARIO_ENSAYO, CLAVE_ENSAYO):
            writer.write((linea + "\r\n").encode())
            await writer.drain()
            resp = _strip_telnet_iac(await _leer(reader, timeout))[0].decode(errors="replace").strip()
            info["dialogo"].append((f"> {linea}", resp))
        writer.close()
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    return info


async def main_async(puertos: list[int], protocolo: str, out: Path) -> list[dict]:
    resultados = []
    for p in puertos:  # uno detrás de otro, no en paralelo: una sola conexión por servicio, sin prisa
        print(f"--- {protocolo} :{p} ---")
        if protocolo == "ssh":
            r = await asyncio.to_thread(ssh_probe, HOST, p)
        elif protocolo == "pop3":
            r = await pop3_probe(HOST, p)
        elif protocolo == "smtp":
            r = await smtp_probe(HOST, p)
        elif protocolo == "imap":
            r = await imap_probe(HOST, p)
        elif protocolo == "ftp":
            r = await ftp_probe(HOST, p)
        else:
            r = await telnet_probe(HOST, p)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        resultados.append(r)
        await asyncio.sleep(1)
    out.mkdir(parents=True, exist_ok=True)
    fichero = out / f"interaccion_{protocolo}.json"
    previos = json.loads(fichero.read_text(encoding="utf-8")) if fichero.exists() else []
    por_puerto = {r["port"]: r for r in previos}
    por_puerto.update({r["port"]: r for r in resultados})  # añade/actualiza, no pierde lo que ya había
    fichero.write_text(json.dumps(list(por_puerto.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    return resultados


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puertos", required=True, help="lista separada por comas")
    ap.add_argument("--protocolo", choices=["ssh", "pop3", "telnet", "smtp", "imap", "ftp"], required=True)
    ap.add_argument("--out", type=Path, default=OUT_DIR / "nics_interaccion")
    a = ap.parse_args()
    asyncio.run(main_async([int(p) for p in a.puertos.split(",")], a.protocolo, a.out))


if __name__ == "__main__":
    main()
