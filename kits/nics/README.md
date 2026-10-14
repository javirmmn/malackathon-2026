# Kit NICS Lab · ¿real, honeypot clásico o honeypot generativo?

Sondea cada servicio web con peticiones inocuas, mide rasgos (consistencia, latencia, coherencia del protocolo,
firmas) y lo clasifica con reglas con pesos, explicando **qué delató a cada impostor**.
Especificación original: apartado **6.2** del plan.

## Probarlo con el banco de pruebas (1 minuto)

```bash
.venv\Scripts\python -m kits.nics.run --testbed
.venv\Scripts\streamlit run kits\nics\app.py
```

`--testbed` arranca 3 servicios en `127.0.0.1:8081-8083` (real, honeypot clásico y honeypot generativo) y los analiza.
Resultado esperado: **3/3 aciertos**. El generativo usa Ollama si está instalado; si no, un simulador que imita a un LLM
(contenido verosímil distinto en cada petición y latencia de generación).

## El jueves, con la red del reto

1. **Alcance:** solo se analizan los servicios que da la organización. Por defecto el kit **se niega a escanear
   nada fuera de localhost**; hay que pasarle el rango autorizado con `--scope`.
2. Crear `data\servicios.csv` con una columna `url` (o `host,port[,path]`), una fila por servicio.
3. Ejecutar:

```bash
.venv\Scripts\python -m kits.nics.run --targets data\servicios.csv --scope 10.10.0.0/16
```

4. Revisar `out\nics\informe.html` y el dashboard. Las dudosas (confianza baja) se miran a mano en la pestaña
   *Detalle* → *Respuestas*.
5. **Guardar en Oracle** (el esquema de `MALACK` es lo que se entrega): añadir `--a-oracle NICS` para crear
   `NICS_RESULTADOS`, `NICS_RASGOS` y `NICS_EVIDENCIAS`.
6. **Afinar sin volver a escanear:** editar pesos/umbrales o añadir firmas en `rules.yaml` y pulsar
   *Reclasificar* en el dashboard (o `python -m kits.nics.run --solo-clasificar`).

Si los servicios no son HTTP o hay que descubrirlos primero (puertos), se descubren con las herramientas que
autorice la organización y el resultado se mete en el CSV.

## Ficheros

| Fichero | Qué es |
|---|---|
| `probes.yaml` | Sondas (raíz repetida, ruta inventada, API inventada, robots, HEAD, OPTIONS), repeticiones, concurrencia, pausas |
| `rules.yaml` | Reglas con pesos por clase, previa, firmas de honeypot, marcas de LLM y banners obsoletos. **Se edita en caliente** |
| `inventory.py` | Carga el inventario (CSV/YAML) y comprueba el alcance |
| `collector.py` | Envía las sondas (asíncrono, con límite de concurrencia) y guarda status, cabeceras, cuerpo, hash y latencia |
| `features.py` | Rasgos por servicio |
| `classifier.py` | Puntuación por clase, confianza y evidencias |
| `report.py` | Informe Markdown y HTML |
| `testbed.py` | Los 3 servicios simulados |
| `app.py` | Dashboard |

## Rasgos principales y qué indican

| Rasgo | Real | Honeypot clásico | Honeypot generativo |
|---|---|---|---|
| `consistencia_raiz` (misma petición repetida) | ~100 % | ~100 % | **< 90 %** |
| `inexistente_status` (ruta inventada) | **404** | 200 | 200 |
| `catch_all` (la ruta inventada devuelve lo mismo que /) | no | **sí** | no |
| `eco_token_200` (se inventa una página con el nombre pedido) | no | no | **sí** |
| `api_json_inventado` | no | no | **sí** |
| `latencia_media_ms` / `latencia_irregular` | baja | baja | **alta e irregular** (segundos) |
| `timeouts` (sin respuesta en 60 s) | no | no | **a veces** |
| `falta_date`, `server_obsoleto`, `firmas_honeypot` | no | **a menudo** | — |
| `marcas_llm` ("como modelo de lenguaje", "```"…) | no | no | **a veces** |

## Salidas (`out/nics/`, no se suben al repo)

`objetivos.csv`, `evidencias.csv` (todas las respuestas), `rasgos.csv`, `resultados.csv/.json`, `informe.md`, `informe.html`.

## Ollama (banco de pruebas con una IA de verdad)

Instalado en el portátil de Javier con `llama3.2:3b` (2 GB, funciona con el procesador). Si Ollama está en marcha,
`--testbed` lo usa solo para el servicio generativo (el ensayo tarda ~3 min en vez de ~20 s). Variables:
`OLLAMA_URL` (por defecto `http://127.0.0.1:11434`) y `OLLAMA_MODEL` (por defecto `llama3.2:3b`).

Lo aprendido al ensayar con la IA real (14/10):
- **No siempre repite la ruta inventada** (como hacía el simulador), así que `eco_token_200` no basta.
  Lo que la delata: contenido distinto a la misma petición, JSON inventado para APIs que no existen,
  latencias de segundos, bloques de código (`` ``` ``) en una "web" y peticiones que superan los 20 s.
- Por eso el timeout es de 60 s y los timeouts cuentan como evidencia (G8).
- La variación de latencia solo cuenta si además es lenta (>100 ms): con 5–30 ms cualquier web real "varía mucho".
