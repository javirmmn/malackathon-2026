"""Consolida TODO lo que sabemos (sondas automáticas + interacción manual confirmada hoy) en un
único veredicto por puerto, con el método usado y la evidencia. Es la fuente del dashboard y del CSV final.

    python -m kits.nics.veredicto
    -> out/nics_entrega/veredicto.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from common import OUT_DIR

from . import entrega

OUT = OUT_DIR / "nics_entrega"

# Confirmado hoy por INTERACCIÓN REAL (no solo sondas): protocolo completo / endpoint que no cumple lo
# que promete / función real que funciona. Ver docs/writeup_nics.html apartado 3 para el detalle completo.
CONFIRMADOS = {
    # SSH: banner OpenSSH_8.2p1 Ubuntu -> corta la conexión a medio protocolo (2 clientes distintos lo confirman)
    24226: ("honeypot_clasico", 0.95, "Interacción real: el saludo SSH es correcto pero el servidor corta la conexión "
            "justo tras el KEXINIT, sin completar el intercambio de claves. Confirmado con paramiko y con el cliente OpenSSH nativo."),
    34818: ("honeypot_clasico", 0.95, "Interacción real: mismo comportamiento que el puerto 24226 (mismo banner), "
            "corta la conexión a medio protocolo."),
    # SSH: banner OpenSSH_9.2p1 Debian -> protocolo completo, claves de host distintas
    36474: ("real", 0.75, "Interacción real: completa el intercambio de claves criptográfico correctamente. "
            "Clave de host propia (ssh-ed25519 SHA256:h8kCtc...). No se puede descartar un honeypot de alta interacción sin credenciales válidas."),
    40101: ("real", 0.75, "Interacción real: completa el intercambio de claves criptográfico correctamente. "
            "Clave de host propia y distinta de la del puerto 36474, como se espera de dos procesos reales."),
    # POP3 Dovecot: banner correcto, no responde a USER
    28827: ("honeypot_clasico", 0.9, "Interacción real: responde al saludo (\"+OK Dovecot ready.\") pero no contesta "
            "nada al comando USER, que un Dovecot real respondería al instante."),
    51629: ("honeypot_clasico", 0.9, "Interacción real: mismo comportamiento que el puerto 28827 (mismo banner), "
            "no responde a USER."),
    # Telnet: sin texto de login real, sin respuesta a usuario/contraseña
    45025: ("honeypot_clasico", 0.85, "Interacción real: no muestra ningún prompt de login reconocible y no responde "
            "al enviar usuario y contraseña de prueba."),
    53020: ("honeypot_clasico", 0.85, "Interacción real: mismo comportamiento que el puerto 45025."),
    # API ondalux-inventory: 56221 declara endpoints en su propio esquema OpenAPI y da 404 al llamarlos
    56221: ("honeypot_clasico", 0.95, "Interacción real: su propio esquema OpenAPI declara /api/v1/estadisticas y "
            "/api/v1/movimientos, pero al llamarlos da 404 o un JSON con forma distinta a la declarada — "
            "estructuralmente imposible en una app FastAPI real."),
    20150: ("real", 0.9, "Interacción real: todos los endpoints declarados funcionan y devuelven datos de inventario "
            "coherentes y con fecha de hoy (estadísticas, movimientos, histórico)."),
    # Blog WordPress: 44700 el buscador funciona; 25589/20808 lo ignoran y siempre dan la portada
    44700: ("real", 0.9, "Interacción real: el buscador de WordPress (?s=) funciona correctamente — para una "
            "búsqueda sin resultados posibles devuelve la página de \"no se ha encontrado nada\", no la portada."),
    25589: ("honeypot_clasico", 0.85, "Interacción real: el parámetro de búsqueda (?s=) se ignora por completo y "
            "siempre devuelve la portada, sea cual sea la búsqueda."),
    20808: ("honeypot_clasico", 0.85, "Interacción real: mismo comportamiento que el puerto 25589, ignora la búsqueda."),
    # Web corporativa: 48519 el formulario de contacto funciona (303 -> redirect real); 59004/51999 no lo procesan
    48519: ("real", 0.75, "Interacción real: el formulario de contacto hace POST a /contacto/enviar y responde "
            "303 See Other -> /contacto.html?enviado=1, el patrón correcto de un formulario procesado de verdad. "
            "Matiz: acepta el envío como válido aunque falten campos obligatorios (probado enviando solo el "
            "nombre) — no invalida la clasificación (es común en formularios reales con poca validación), pero "
            "baja algo la confianza frente a los otros \"real\" de esta revisión."),
    59004: ("honeypot_clasico", 0.7, "Interacción real: el formulario de contacto da 403 Forbidden genérico de "
            "nginx — la ruta no está implementada de verdad."),
    51999: ("honeypot_clasico", 0.65, "Interacción real: el formulario de contacto da 404 (con página de error "
            "personalizada, pero la ruta /contacto/enviar no existe)."),
    # NAS Synology: 47163 responde correctamente a una consulta real de su API; 34328/56377 no
    47163: ("real", 0.9, "Interacción real: responde correctamente a una consulta real de la API de Synology "
            "(SYNO.API.Info), con el formato exacto que da un DSM real."),
    34328: ("honeypot_clasico", 0.85, "Interacción real: la página de login (/webman/login.cgi) da 404 y la "
            "consulta a la API devuelve un error de sesión inválida (código 119) que no tiene sentido para una "
            "consulta sin autenticar — comportamiento incorrecto de la API."),
    56377: ("honeypot_clasico", 0.85, "Interacción real: mismo comportamiento que el puerto 34328."),
    # POP3, SMTP, IMAP, FTP sueltos: ninguno responde a un comando válido tras el banner.
    # Confirmado de forma independiente por 3 vías: nuestro script, telnet de Windows (Javier) y
    # telnet de Linux de una compañera ("Connection closed by foreign host" — lo corta el otro lado,
    # no es un firewall local). Parece un único programa mínimo detrás de todos estos puertos, que
    # solo sabe mandar el saludo inicial.
    24755: ("honeypot_clasico", 0.85, "Interacción real: no responde nada al comando USER tras el saludo "
            "(confirmado también desde otra red/equipo, no es un problema local)."),
    46509: ("honeypot_clasico", 0.85, "Interacción real: no responde nada al comando USER tras el saludo."),
    28246: ("honeypot_clasico", 0.9, "Interacción real: no responde nada a EHLO tras el saludo. Confirmado de forma "
            "independiente con 3 herramientas y 2 equipos distintos (telnet de Windows y de Linux): "
            "\"Connection closed by foreign host\", lo corta el servidor, no es cosa de un firewall local."),
    30934: ("honeypot_clasico", 0.85, "Interacción real: no responde nada a CAPABILITY tras el saludo."),
    41328: ("honeypot_clasico", 0.85, "Interacción real: no responde nada a CAPABILITY, aunque el propio saludo "
            "ya incluye una lista de capacidades (patrón válido de Dovecot), el servidor no reacciona a nada más."),
    34282: ("honeypot_clasico", 0.85, "Interacción real: no responde nada al comando USER tras el saludo."),
    # Elasticsearch: comprobación a fondo (aviso de un compañero) con una BÚSQUEDA real sobre un índice
    # inventado, no solo pedir el índice. Un ES real rechaza la búsqueda (index_not_found_exception);
    # aquí se ha destapado que 2 de los 3 no lo hacen bien.
    22739: ("real", 0.95, "Interacción real: una búsqueda (_search) sobre un índice inventado da el error "
            "correcto (index_not_found_exception, con la estructura exacta de un ES real: root_cause como "
            "lista, status 404), igual en repeticiones y con distintos nombres de índice."),
    31885: ("honeypot_clasico", 0.9, "Interacción real: la estructura del error está rota (status 500 en vez de "
            "404, root_cause como objeto en vez de lista, la clave \"error\" aparece duplicada y mal anidada) "
            "— un Elasticsearch real nunca devuelve esa forma. Error fijo y repetible, no varía entre intentos."),
    50096: ("honeypot_clasico", 0.9, "Interacción real: al BUSCAR (no solo pedir) un índice inventado, en vez "
            "de rechazar la búsqueda se inventa un resultado — pero es SIEMPRE el mismo (cliente CLI-0003, "
            "\"Hortofrutícola del Guadalhorce S.A.\", Málaga), probado con 4 nombres de índice distintos. "
            "Al no variar, es una respuesta predefinida (clase 2), no una IA improvisando cada vez (clase 3)."),
    # Grafana (login): /api/health coincide en los dos, pero al probar más endpoints se ve la diferencia real
    25461: ("honeypot_clasico", 0.85, "Interacción real: responde 401 Unauthorized a TODO, incluso a "
            "/api/frontend/settings, que en un Grafana real es público (se usa antes de iniciar sesión). "
            "Negar todo por igual, sin distinguir por endpoint, es un patrón de respuesta única, no de una "
            "aplicación real. Coincidir en /api/health con el puerto 29082 no bastaba: es un endpoint tan "
            "básico que un señuelo simple también lo clava."),
    29082: ("real", 0.9, "Interacción real: a diferencia del puerto 25461, distingue por endpoint — /api/org "
            "da datos reales de la organización (\"Ondalux Logística\"), /api/search da paneles reales y "
            "coherentes con el negocio (rutas, temperatura de naves, stock por almacén)."),
    # Reconfirmación de los 2 catch-all originales (ya detectados el 14/10, hoy comprobado otra vez con una ruta distinta)
    39640: ("honeypot_clasico", 0.8, "Interacción real: respuesta byte a byte idéntica en / y en una ruta "
            "inventada — reconfirmado hoy con una ruta distinta a la de la detección original."),
    51656: ("honeypot_clasico", 0.8, "Interacción real: respuesta byte a byte idéntica en / y en una ruta "
            "inventada — reconfirmado hoy con una ruta distinta a la de la detección original."),
    27381: ("honeypot_clasico", 0.95, "Interacción real: banner OpenSSH_7.9p1 Debian 10, pero corta la conexión "
            "justo tras el KEXINIT, igual que los otros dos SSH falsos — nunca completa el protocolo de verdad."),
    27472: ("honeypot_clasico", 0.85, "Interacción real: no muestra prompt de login reconocible ni responde a "
            "usuario/contraseña de prueba, igual que los otros Telnet."),
    # Últimos 6: 4 catch-all reconfirmados + 2 que resultan ser auténticos al mirarlos de verdad
    24179: ("honeypot_clasico", 0.8, "Interacción real: respuesta idéntica en / y en una ruta inventada "
            "(reconfirmado con una ruta distinta a la original)."),
    35574: ("honeypot_clasico", 0.8, "Interacción real: respuesta idéntica en / y en una ruta inventada."),
    47095: ("honeypot_clasico", 0.8, "Interacción real: respuesta idéntica en / y en una ruta inventada."),
    48200: ("honeypot_clasico", 0.8, "Interacción real: respuesta idéntica en / y en una ruta inventada."),
    46737: ("real", 0.88, "Interacción real: redirige a /owa/auth/logon.aspx, el patrón de redirección exacto y "
            "genuino de un servidor Microsoft Exchange (OWA) real; una ruta inventada da 404 normal, no catch-all. "
            "Respuestas distintas y coherentes por ruta (401 en /ecp/, 308 en ActiveSync, 302 en /owa/) — no es un "
            "bloque homogéneo. Matiz menor: /autodiscover/autodiscover.xml da 404 cuando un Exchange real suele "
            "dar 405 (método no permitido) a una petición GET."),
    57238: ("real", 0.9, "Interacción real: /api/v1/repos/search devuelve un repositorio real de la organización "
            "\"Ondalux Logística\", con fecha de creación coherente con el resto del entorno (13/10/2026)."),
}


def build() -> pd.DataFrame:
    df = entrega.build(
        web_resultados=OUT_DIR / "nics_real" / "resultados.csv",
        web_inventario=Path("data/inventario_completo.csv"),
        protocolo_rasgos=OUT_DIR / "nics_otros" / "rasgos_protocolo.csv",
        out=OUT,
    )
    df["metodo"] = "sondas_automaticas"
    for puerto, (clase, conf, ev) in CONFIRMADOS.items():
        m = df["port"] == puerto
        if not m.any():
            continue
        df.loc[m, ["clase", "confianza", "evidencias", "class", "metodo", "revisar_a_mano"]] = \
            [clase, conf, ev, entrega.CLASE_A_NUM[clase], "interaccion_real", False]

    df = df.sort_values("port").reset_index(drop=True)
    df[["port", "service", "class"]].to_csv(OUT / "entrega.csv", index=False)
    df.to_csv(OUT / "veredicto.csv", index=False, encoding="utf-8-sig")

    print(df["clase"].value_counts().rename("nº").to_string())
    print(f"\nConfirmados por interacción real: {(df['metodo'] == 'interaccion_real').sum()} / {len(df)}")
    pend = df[df["revisar_a_mano"] | ((df["confianza"] < 0.65) & (df["metodo"] == "sondas_automaticas"))]
    if len(pend):
        print(f"\nPendientes de confirmar con interacción real ({len(pend)}):")
        print(pend[["port", "service", "clase", "confianza"]].to_string(index=False))
    return df


if __name__ == "__main__":
    build()
