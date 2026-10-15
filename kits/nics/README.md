# Kit NICS Lab · ¿real, honeypot clásico o honeypot generativo?

## Resultado final (15/10, red del reto: Ondalux Logística S.L.)

**40 puertos abiertos; 14 se descartan por no estar disponibles (solo saludo y cierran, criterio de la organización,
lista en `EXCLUIDOS` de `veredicto.py`). Los 26 disponibles, confirmados por interacción real** (no solo apariencia):
**8 real, 17 honeypot clásico, 1 honeypot generativo.** Detalle completo, evidencia de cada puerto y niveles de confianza (con la regla de
cómo leerlos) en `docs/writeup_nics.html` y en el dashboard:

```bash
.venv\Scripts\python -m kits.nics.veredicto         # -> out/nics_entrega/veredicto.csv y entrega.csv
.venv\Scripts\streamlit run kits\nics\app_veredicto.py
```

### Lo que hizo falta para llegar ahí

Las sondas automáticas (lo que este kit traía hecho antes del evento) clasifican bien lo evidente, pero el enunciado
avisaba: *"un buen honeypot engaña a simple vista; se delata cuando lo usas en serio"*. Hizo falta un segundo nivel,
de interacción real, puerto por puerto:

| Herramienta | Qué hace |
|---|---|
| `inventory.py` + `collector.py` + `features.py` + `classifier.py` | Sondas automáticas sobre HTTP/HTTPS (consistencia, ruta inventada, latencia, firmas) — primera pasada, rápida |
| `protocolo.py` + `classifier_protocolo.py` | Banner repetido y firmas conocidas en SSH/FTP/Telnet/SMTP/POP3/IMAP |
| `interactuar.py` | Interacción real por protocolo: handshake SSH completo, `USER`/`EHLO`/`CAPABILITY`/`SYST` válidos en POP3/SMTP/IMAP/FTP, login y comandos en Telnet |
| `forense_extra.py` | Certificado TLS compartido, latencia frente al tamaño de la respuesta, coherencia de los recursos enlazados |
| `martillo_consistencia.py` | Repite la **misma** petición (`GET`/`POST`, mismo cuerpo) varias veces en cada ruta conocida de cada puerto, y avisa si algo que debería ser fijo varía — la prueba que encontró al generativo |
| `veredicto.py` | Consolida todo lo anterior en un único veredicto con método y evidencia por puerto |
| `app_veredicto.py` | Dashboard con los 26 puertos disponibles, filtros y detalle de cada uno |

### El caso del generativo (puerto 50096): la lección de método del día

Con `GET` simple, `50096` (un Elasticsearch falso) parecía tener un error fijo y correcto — coló como "real" en una
primera pasada. Lo que lo destapó: repetir la **misma consulta `POST`** (la forma normal de usar Elasticsearch)
varias veces seguidas. Un dato interno que en un Elasticsearch real nunca cambia (`_shards.total`) variaba en cada
llamada idéntica, y el resultado era el mismo (fabricado) tanto preguntando por un índice real como por uno
inventado. **`GET` no bastaba; hizo falta `POST` repetido para verlo.** Por eso `martillo_consistencia.py` prueba
ambos métodos en todo lo que tiene API.

**Revisión por pares:** un compañero del equipo, con su propia clasificación independiente, encontró 2 errores reales
en la nuestra (confirmados aquí antes de aceptarlos, nunca a ciegas): una pareja de Grafana que teníamos invertida
(se resolvió probando una ruta de administración real, `/api/admin/stats`), y el par SSH que creíamos real resultó
tener una *shell* emulada detrás (se entra con `root:toor`, y dentro `echo $((7*13))` no sabe hacer aritmética). Con
esto, **ningún SSH de los 5 descubiertos es real** — completar el protocolo criptográfico solo prueba que hay un
proceso hablando SSH, no que la shell de detrás lo sea.

## Ficheros

| Fichero | Qué es |
|---|---|
| `probes.yaml` | Sondas HTTP (raíz repetida, ruta inventada, API inventada, robots, HEAD, OPTIONS) |
| `rules.yaml` | Reglas con pesos por clase para la primera pasada automática. **Se edita en caliente** |
| `inventory.py` / `collector.py` / `features.py` / `classifier.py` | Inventario, sondeo HTTP asíncrono, rasgos y clasificación por reglas |
| `protocolo.py` / `classifier_protocolo.py` | Banner y clasificación de los protocolos no-web |
| `interactuar.py` | Interacción real por protocolo (SSH/POP3/SMTP/IMAP/FTP/Telnet) |
| `forense_extra.py` | Certificado TLS, latencia vs tamaño, coherencia de recursos |
| `martillo_consistencia.py` | Repetición de peticiones `GET`/`POST` para detectar variación oculta |
| `entrega.py` | Exportador al CSV `port,service,class` |
| `veredicto.py` | Consolida todo en el veredicto final (fuente del dashboard y del CSV) |
| `app.py` | Dashboard original, solo HTTP/HTTPS (24 puertos) |
| `app_veredicto.py` | **Dashboard final, los 26 puertos disponibles** |
| `testbed.py` | Banco de pruebas de ayer (3 servicios simulados), ver abajo |

## Banco de pruebas de ayer (14/10), referencia histórica

Antes de conocer el reto, el kit se probó con 3 servicios simulados en `127.0.0.1:8081-8083` (real, honeypot clásico
y honeypot generativo, este último con Ollama si estaba instalado). Resultado: 3/3. Sirvió para comprobar que las
sondas automáticas funcionaban, pero **no sustituyó la interacción real** que hizo falta hoy con el reto de verdad.

```bash
.venv\Scripts\python -m kits.nics.run --testbed
```

## Salidas (no se suben al repo)

`out/nics/` (sondas HTTP), `out/nics_otros/` (protocolos no-web), `out/nics_interaccion/` (diálogos de la
interacción real), `out/nics_entrega/` (**veredicto.csv, entrega.csv — el que se sube — y entrega_detalle.csv**).
