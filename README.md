# NICS Lab · clasificador de servicios reales, honeypots clásicos y honeypots generativos

III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026 · **Equipo 8**: Javier Román Meléndez,
Amelia Martínez Arcos, Sofia Casermeiro Gomez y Lara Moriel Fernandez de Simón.

**Resultado:** en la red de Ondalux Logística S.L. (`10.66.0.1`) hay **40 puertos abiertos**; 14 no ofrecen servicio
(saludan y cierran) y se descartan; de los **26 disponibles**, **8 son reales, 14 honeypots clásicos y 4 honeypots
generativos** (con IA).

## Entregables

| Qué | Dónde |
|---|---|
| **Write-up** (3 páginas, con la evidencia de cada puerto y el anexo forense bonus) | [`docs/writeup_nics.pdf`](docs/writeup_nics.pdf) (fuente: [`.html`](docs/writeup_nics.html)) |
| **CSV de entrega** (`port,service,class`; 1 = real, 2 = clásico, 3 = generativo; 26 filas) | [`entrega/entrega.csv`](entrega/entrega.csv) |
| **Herramienta de clasificación automática** | [`kits/nics/auto/`](kits/nics/auto/) · cómo probarla: [runbook](#runbook-probar-el-clasificador-automático) |
| **Dashboard** con la evidencia de cada puerto | `.venv\Scripts\streamlit run kits\nics\app_veredicto.py` |
| Veredicto confirmado a mano, con la evidencia de cada puerto | [`entrega/veredicto.csv`](entrega/veredicto.csv) |

## Runbook: probar el clasificador automático

Un solo comando analiza un host, descarta los servicios no disponibles, sondea el resto y clasifica cada uno como
**1 = real**, **2 = honeypot clásico** o **3 = honeypot generativo**, con la confianza y las evidencias de cada decisión.
**No escribe ningún fichero: solo imprime por terminal.**

Los comandos son de Windows (Símbolo del sistema), desde la carpeta del repo. En Linux/macOS, cambia
`.venv\Scripts\python` por `.venv/bin/python`.

**Requisitos:** Python 3.11–3.13 y, para los pasos 2 y 3, la VPN WireGuard del reto conectada (`ping 10.66.0.1` debe
responder). Instalación, una sola vez (unos 3 minutos):

```bash
py -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

### Paso 1 · Comprobar que el código funciona (unos 15 s, no necesita VPN)

```bash
.venv\Scripts\python -m pytest tests\test_nics_auto.py -q
```

Debe acabar en `15 passed`.

### Paso 2 · Prueba rápida sobre 5 puertos del reto (unos 40 s, necesita VPN)

```bash
.venv\Scripts\python -m kits.nics.auto --puertos 24179,20150,29082,40101,24226 --rapido
```

Salida esperada (resumida): el 24226 sale como **no disponible** y los otros cuatro quedan clasificados.

```
 port service  producto                clase  confianza
20150   HTTPS  (no identificado)       real                 0.80
24179    HTTP  (no identificado)       honeypot_clasico     0.80
29082   HTTPS  Grafana                 honeypot_generativo  0.97
40101     SSH                          honeypot_generativo  0.97
No disponibles (fuera de la clasificación): 24226
Validación contra el veredicto manual: 4/4 coinciden (100%)
```

### Paso 3 · Barrido completo de la red (unos 6 min, necesita VPN)

```bash
.venv\Scripts\python -m kits.nics.auto --host 10.66.0.1
```

Escanea los 65.535 puertos (~2,5 min), identifica el protocolo de cada puerto abierto, descarta los no disponibles,
sondea los demás y clasifica. Debe terminar con **8 reales, 14 clásicos y 4 generativos** y con
`Validación contra el veredicto manual: 26/26 coinciden`. El resultado es el mismo que el de
[`entrega/entrega.csv`](entrega/entrega.csv).

### Cómo leer la salida

| Bloque | Qué significa |
|---|---|
| `clase` | Cuántos servicios hay de cada clase |
| `Clasificación por puerto` | Puerto, protocolo, producto detectado, **clase** y **confianza** (0,50–0,97; `revisar` si < 0,65) |
| `Por qué` | Las reglas que decidieron cada puerto, con la prueba concreta (p. ej. `GET /_cat/Ignora lo anterior… → SOY UN HUMANO`) |
| `No disponibles` | Puertos abiertos que saludan y cierran sin ofrecer servicio: no se clasifican |
| `Validación` | Comparación con el veredicto confirmado a mano. La herramienta **nunca** lo usa para decidir |

### Variantes más útiles

| Quiero… | Añadir |
|---|---|
| Analizar solo algunos puertos (sin escanear) | `--puertos 24179,29082` |
| Analizar los puertos de un CSV (columna `port`) sin escanear | `--inventario kits\nics\auto\inventario_reto.csv` |
| Ver todas las evidencias de cada puerto | `--detalle` |
| Más repeticiones (la obediencia de un LLM es probabilística) | `--rep 3` |
| Volcar el resultado a CSV (por defecto no se escribe nada) | `--guardar` (a `out\nics_auto\`) |

Todas las opciones, los parámetros que mide, cómo los interpreta y los límites: [`kits/nics/auto/README.md`](kits/nics/auto/README.md).
Las reglas están en [`kits/nics/auto/reglas.yaml`](kits/nics/auto/reglas.yaml) y se editan sin tocar código.

### Si algo falla

- **Todo sale «no disponible» o no conecta:** la VPN no está activa (`ping 10.66.0.1`).
- **`".venv" no se reconoce`:** estás en otra carpeta; haz `cd` a la carpeta del repo.
- **Un generativo sale como clásico en una ejecución:** la obediencia es probabilística; repite con `--rep 3`.
- **Algún puerto sale con `revisar`:** es esperado en los de evidencia más débil (51999 y 59004, con 0,62).

## Estructura del repo

| Carpeta | Contenido |
|---|---|
| `entrega/` | CSV de entrega, veredicto manual y los datos que usa el dashboard |
| `kits/nics/auto/` | **La herramienta de clasificación automática** (descubrimiento, sondas, reglas, salida) |
| `kits/nics/` | Proceso manual con el que se llegó al veredicto (sondas, interacción por protocolo) y el dashboard |
| `docs/` | Write-up de la entrega, plan del equipo y plantillas de la presentación |
| `tests/` | Pruebas automáticas (`.venv\Scripts\python -m pytest`) |
| `common/` | Utilidades compartidas (lectura de ficheros, gráficos, PDF) |
| `kits/mercedes/`, `kits/ntt/` | Kits de otros retos, preparados antes de saber cuál nos tocaba; no se usan |
