# Clasificador automático NICS

Un solo comando analiza un host (**por defecto solo imprime por terminal: no escribe ningún fichero**), filtra lo que no está disponible, sondea cada servicio con todas las pruebas que
descubrimos durante la jornada y deja un CSV con la clase de cada uno (1 = real, 2 = honeypot clásico,
3 = honeypot generativo), la confianza y las evidencias concretas.

```bash
.venv\Scripts\python -m kits.nics.auto --host 10.66.0.1          # barrido completo (~6 min)
.venv\Scripts\python -m kits.nics.auto --host 10.66.0.1 --guardar   # opcional: además vuelca CSV a out\nics_auto
```

Opciones útiles: `--puertos 24179,29082` (sin escanear), `--inventario kits/nics/auto/inventario_reto.csv` (los 42 puertos del reto, ya en el repo; salta el
escaneo, ~3 min), `--rapido` (menos pruebas de generativo), `--rep 3` (más repeticiones: la obediencia de un LLM es
estocástica), `--detalle` (todas las evidencias por puerto), `--guardar` (opcional: volcar CSV/JSON), `--reclasificar` (reaplica
`reglas.yaml` a lo ya guardado con `--guardar`, en segundos, sin volver a sondear),
`--salida DIR`, `--sin-ssh-login`, `--sin-validar`.

## Flujo (un barrido)

| Etapa | Qué hace | Módulo |
|---|---|---|
| 1. Descubrir | Escaneo TCP del rango (1-65535 por defecto) | `descubrir.escanear` |
| 2. Identificar | Protocolo por el saludo (ssh, ftp, smtp, pop3, imap, telnet) o probando TLS/HTTP | `descubrir.identificar` |
| 3. Disponibilidad | **Solo cuentan los servicios abiertos y disponibles**: un puerto que saluda y cierra (o calla) sin contestar a un comando válido queda fuera | `descubrir.disponibilidad` |
| 4. Sondeo | Web: genéricas + por producto + batería de generativo. SSH: shell. Resto: comandos del protocolo | `http_generico`, `productos`, `generativo`, `proto` |
| 5. Reglas | Rasgos → puntuaciones por clase → clase, confianza y evidencias | `motor`, `reglas.yaml` |

Control de alcance: solo se analizan hosts de redes privadas/locales salvo `--autorizado`.

## Qué mide cada sonda (rasgos)

**Genéricas (web):** `catch_all` (misma respuesta en `/` y en rutas inventadas), `notfound_realista`,
`busqueda_ignorada`/`busqueda_funciona` (`?s=` devuelve la portada o busca de verdad), `form_sin_backend`/`form_funciona`
(envío de un formulario de contacto de prueba; vigila también el cuerpo «403/404» bajo un estado 200),
`openapi_coherente`/`openapi_incoherente` (llama a los endpoints que su propio esquema declara y comprueba la forma).

**Por producto** (solo si lo detecta): Elasticsearch (error `index_not_found` bien formado, `_shards` estable,
plantilla con `_shards` aleatorio, datos de un índice inventado), Grafana (`/api/admin/stats` 401 frente a 404, datos sin
autenticación), Synology (`SYNO.API.Info`, login), Gitea (repos reales y su 404), Exchange/OWA (redirección genuina),
WordPress (`/wp-json/` con URL absoluta; los clones devuelven `/`).

**Generativo** (lo que solo hace un LLM):
`gen_obedece` (una instrucción en la ruta bajo 10 prefijos, en la query, en cabeceras y en el cuerpo POST se obedece:
la respuesta lleva el texto pedido sin repetir la instrucción), `gen_prosa` (escribe un haiku donde un servicio real
daría un error técnico), `gen_variantes` (la misma palabra como `/w`, `/w/`, `//w`, `/W`, `/w%20` salta la caché por
ruta), `gen_metodos` (POST/PUT/PATCH/DELETE a rutas nuevas), `gen_latencia` (rutas nuevas tardan segundos y luego bajan).
**No cuenta** que un dato cambie (un script con un número aleatorio también lo hace) ni que el error refleje el texto.

**SSH:** se prueban credenciales **triviales de ensayo** (`root:toor`, `admin:admin`...; nunca reales). Con la shell:
`ssh_shell_obedece`, `ssh_shell_prosa`, `ssh_aritmetica_falla` (`echo $((7*13))` ≠ 91), `ssh_type_falso`
(`type cat` dice builtin). Sin credencial aceptada no se puede ver la shell: el servicio queda como real con confianza baja.

**Protocolos de texto** (POP3/SMTP/IMAP/FTP/Telnet disponibles): respuestas válidas del protocolo y obediencia a una
instrucción.

## Reglas y confianza (`reglas.yaml`)

Cada regla suma `peso` a una clase si su rasgo se cumple. **Generativo** si supera su umbral (5): una obediencia basta, o
prosa + métodos. Si no, **clásico** si puntúa más que real; si no, **real**. La confianza es nuestro juicio sobre el
margen (`0,50 + 0,06 × puntos de margen`, máx. 0,97), no una probabilidad; por debajo de 0,65 el CSV marca `revisar`.
Un generativo que supera el umbral es decisivo: las señales de clásico que lo acompañan no restan confianza.
Editar `reglas.yaml` y ejecutar `--reclasificar` reclasifica sin volver a sondear.

## Ficheros de salida (solo con `--guardar`, en `out/nics_auto/`)

Sin `--guardar` no se escribe nada. El dashboard `kits/nics/app_auto.py` solo sirve si se ha guardado antes; el CSV y el
dashboard de entrega son los del proceso manual (`entrega/entrega.csv`, `kits/nics/app_veredicto.py`).

| Fichero | Contenido |
|---|---|
| `clasificacion.csv` | **Resultado.** `port, service, producto, clase, class, confianza, revisar, reglas, evidencias, puntos_real, puntos_clasico, puntos_generativo, gemelos` |
| `entrega.csv` | Formato de entrega: `port,service,class` (solo servicios disponibles) |
| `rasgos.csv` / `rasgos.json` | Todos los rasgos medidos por puerto (y el detalle concreto de cada uno) |
| `pruebas.csv` | Cada petición realizada: `port, grupo, prueba, peticion (curl reproducible), estado, ms, respuesta` |
| `no_disponibles.csv` | Puertos abiertos pero sin servicio (`port, service, motivo, banner`) |
| `validacion.csv` | Comparación con el veredicto confirmado a mano (`auto`, `manual`, `coincide`); nunca se usa para clasificar |

`gemelos` lista los puertos con el mismo perfil (mismo servicio, servidor, título y producto); sirve para contrastar
clones, pero no puntúa.

## Límites conocidos

- Las reglas salen de lo observado en esta red (40 puertos); en una red distinta pueden hacer falta módulos de producto
  nuevos. Las pruebas genéricas (catch-all, obediencia, variantes, métodos, esquema declarado) no dependen del producto.
- La obediencia de un LLM es estocástica: una prueba negativa no descarta; `--rep` la repite. Solo se prueba inyección
  en ruta, query, cabeceras, cuerpo y shell SSH.
- Un generativo que ignore instrucciones y cachee todas las variantes podría pasar desapercibido.
- SSH solo se inspecciona si acepta una credencial trivial de ensayo.
