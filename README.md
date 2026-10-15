# Malackathon 2026 · equipo de Javier Román (equipo 8)

III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.
Plan completo: [`docs/plan_fuente.html`](docs/plan_fuente.html) (y `Plan_Malackathon_2026.pdf`).

## Reto: NICS Lab — clasificación terminada

**40 puertos abiertos en la red de Ondalux Logística S.L.; 14 se descartan por no estar disponibles (solo saludo y
cierran). De los 26 disponibles, confirmados por interacción real: 8 real, 14 honeypot clásico, 4 honeypot generativo.**

| | |
|---|---|
| Write-up (3 páginas, con la evidencia de cada puerto) | [`docs/writeup_nics.html`](docs/writeup_nics.html) |
| Cómo se hizo (herramientas, metodología) | [`kits/nics/README.md`](kits/nics/README.md) |
| CSV de entrega (`port,service,class`) | `out/nics_entrega/entrega.csv` (se genera con `python -m kits.nics.veredicto`) |
| Dashboard con los 26 puertos disponibles | `.venv\Scripts\streamlit run kits\nics\app_veredicto.py` |

Los kits de Mercedes-Benz y NTT DATA (preparados el 14/10, antes de saber qué reto nos tocaba) ya no se usan; se
quedan en el repo como referencia — [`kits/mercedes/README.md`](kits/mercedes/README.md),
[`kits/ntt/README.md`](kits/ntt/README.md).

---

## 1. Instalar desde cero (Windows, unos 10 minutos)

**Requisitos:**
- Python 3.11–3.13 ([python.org](https://www.python.org/downloads/)). Comprobar con `py --version`.
  En Windows se usa siempre el lanzador `py`, no `python`.
- **Una de las dos:** [GitHub Desktop](https://desktop.github.com/) **o** [Git](https://git-scm.com/download/win)
  (comprobar con `git --version`).
- Haber **aceptado la invitación** al repo (es privado) y tener la sesión de GitHub iniciada.

**Pasos 1 y 2: clonar el repo y abrir una terminal en su carpeta**

| | Con GitHub Desktop | Con comandos (Git) |
|---|---|---|
| 1. Clonar | *File → Clone repository → `javirmmn/malackathon-2026` → Clone* | Abrir *Símbolo del sistema* (tecla Windows, escribir `cmd`) y ejecutar `git clone https://github.com/javirmmn/malackathon-2026.git`. La primera vez se abre el navegador para iniciar sesión en GitHub |
| 2. Abrir terminal en la carpeta | *Repository → Open in Command Prompt* | `cd malackathon-2026` |

**Paso 3: crear el entorno e instalarlo todo** (un solo comando instala lo común y lo de los dos kits):

```bash
py -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

**Paso 4: comprobar que todo funciona** (tarda ~30 s; debe acabar en `passed`. Un `skipped` es normal la primera vez):

```bash
.venv\Scripts\python -m pytest
```

Todos los comandos de este README se escriben **desde la carpeta del repo** y empiezan por `.venv\Scripts\...`.

## 2. Ver el resultado del reto / probar los kits

### Kit NICS: clasificador automático (entregable final)

Un solo barrido descubre los puertos, descarta los no disponibles, los sondea y clasifica (real / honeypot clásico /
honeypot generativo). Necesita la VPN del reto activa:

```bash
.venv\Scripts\python -m kits.nics.auto --host 10.66.0.1
.venv\Scripts\streamlit run kits\nics\app_auto.py
```

Tarda unos 6 minutos y deja `out\nics_auto\clasificacion.csv` (y `entrega.csv`). Para saltarse el escaneo:
`--inventario kits\nics\auto\inventario_reto.csv` (los 42 puertos del reto, incluido en el repo) o
`--puertos 24179,29082`. Formato, opciones y límites en [`kits/nics/auto/README.md`](kits/nics/auto/README.md).

### Kit NICS: el proceso manual de hoy (veredicto confirmado a mano)

```bash
.venv\Scripts\python -m kits.nics.veredicto
.venv\Scripts\streamlit run kits\nics\app_veredicto.py
```

El primer comando reconstruye `out\nics_entrega\entrega.csv` y `veredicto.csv` a partir de todo lo investigado hoy
(sondas automáticas + interacción real). El segundo abre el dashboard con los 26 puertos disponibles, su
clasificación, la confianza y la evidencia de cada uno. Detalle completo en
[`kits/nics/README.md`](kits/nics/README.md).

<details>
<summary>Banco de pruebas del 14/10 (antes de saber el reto; referencia histórica)</summary>

```bash
.venv\Scripts\python -m kits.nics.run --testbed
.venv\Scripts\streamlit run kits\nics\app.py
```

Arranca 3 servicios de prueba en tu portátil (uno real, un honeypot clásico y uno con IA) y debe terminar con
**Aciertos: 3/3**. Sirvió para comprobar las sondas automáticas; no sustituyó la interacción real que hizo falta
con el reto de verdad.
</details>

### Kits que ya no se usan (Mercedes-Benz, NTT DATA): referencia histórica

<details>
<summary>Cómo probarlos, si hace falta volver a mirarlos</summary>

**Mercedes-Benz** (segmentación de clientes):
```bash
.venv\Scripts\python -m kits.mercedes.sample_data
.venv\Scripts\python -m kits.mercedes.run --data data\clientes_ensayo.csv --model kmeans_k5
.venv\Scripts\streamlit run kits\mercedes\app.py
```

**NTT DATA** (detector de alucinaciones):
```bash
.venv\Scripts\python -m kits.ntt.sample_data
.venv\Scripts\python -m kits.ntt.run --data data\ntt_ensayo.csv
.venv\Scripts\streamlit run kits\ntt\app.py
```
</details>

**Sobre los dashboards (Streamlit):** se abren solos en el navegador (`http://localhost:8501`), solo los ves tú.
La primera vez Streamlit pide un email en la terminal: dejarlo vacío y pulsar **Enter**. Se cierran con **Ctrl+C**
en la terminal. El botón *Deploy* no se usa.

## 3. Conectar con Oracle (solo si vas a trabajar con la base de datos desde tu portátil)

La web de la base de datos (Database Actions) **no necesita nada de esto**: basta con la URL de `docs/oracle.md`,
el usuario `MALACK` y su contraseña. Para conectar desde Python o SQL Developer:

1. Pedir a Javier, **por un canal seguro** (nunca por el grupo ni por el repo), la contraseña de `MALACK`, el zip
   del wallet y la contraseña del wallet.
2. Descomprimir el wallet **fuera del repo**, p. ej. `C:\Users\<tu_usuario>\oracle\Wallet_malackathon`.
3. Crear el `.env` en la carpeta del repo y rellenarlo (usuario, contraseña, `malackathon_low`, carpeta del wallet y
   contraseña del wallet). Desde el Explorador: copiar `.env.example`, renombrar la copia a `.env` y abrirla con el
   Bloc de notas. Con comandos: `copy .env.example .env` y luego `notepad .env`.
4. Comprobar:

```bash
.venv\Scripts\python -m common.db
```

Debe decir `Conectado a ... como MALACK`. A partir de ahí:

- Subir un fichero del reto a Oracle: `.venv\Scripts\python -m common.load data\reto.xlsx --tabla CLIENTES`
- Guardar los resultados de un kit en Oracle: añadir `--a-oracle PREFIJO` a su comando `run`.

## 4. Estructura

| Carpeta | Contenido |
|---|---|
| `common/` | `db.py` (Oracle: `query_df`, `execute`, `df_to_table`), `dataio.py` (leer CSV/Excel con tildes y comas decimales, normalizar columnas, exportar), `charts.py` (estilo de gráficos), `streamlit_app.py` (dashboard genérico), `load.py` (fichero → tabla de Oracle), `pdf.py` (HTML → PDF con Chrome) |
| `kits/nics/` | **El reto de verdad.** Sondas automáticas, interacción real por protocolo, martillo de consistencia, veredicto final y dashboard de los 40 puertos |
| `kits/mercedes/`, `kits/ntt/` | Kits de los otros retos preparados el 14/10; no usados hoy, quedan de referencia |
| `docs/` | Plan, `oracle.md`, `writeup_nics.html` (**el write-up de la entrega**), `sql/` (consultas de ensayo), `presentacion/` (plantillas y guion), `arquitectura/` (diagramas) |
| `tests/` | Pruebas automáticas (`.venv\Scripts\python -m pytest`), no necesitan Oracle |
| `data/` | Datos locales, **no se suben** |
| `out/` | Resultados generados por los kits, **no se suben** |

## 5. Trabajo diario con el repo

| Qué | Con GitHub Desktop | Con comandos (Git) |
|---|---|---|
| Traer lo último de los demás (**siempre antes de empezar**) | *Fetch origin* → *Pull origin* | `git pull` |
| Ver qué has cambiado | Pestaña *Changes* | `git status` |
| Guardar tus cambios (commit) | Escribir el mensaje en *Summary* → *Commit to main* | `git add -A` y luego `git commit -m "mensaje"` |
| Subirlos a GitHub (push) | *Push origin* | `git push` |

Si después de traer cambios ha cambiado `requirements.txt`, volver a ejecutar el comando de instalación del paso 3.

## 6. Normas del repo

- **Nunca** subir contraseñas, wallet ni `.env` (están en `.gitignore`). Antes de cada commit, mirar la lista de
  ficheros (*Changes* en GitHub Desktop o `git status`): no debe aparecer ninguno de ellos.
- `main` siempre funcionando: antes de hacer push, `.venv\Scripts\python -m pytest`.
- Entrega el jueves 15 **antes de las 20:00** por el Campus Virtual.
