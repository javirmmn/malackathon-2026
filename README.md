# Malackathon 2026 · equipo de Javier Román

III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.
Plan completo: [`docs/plan_fuente.html`](docs/plan_fuente.html) (y `Plan_Malackathon_2026.pdf`).

**Qué hay aquí:** tres *kits de arranque* (herramientas listas para usar con los datos del reto) para nuestros tres
retos preferidos, utilidades comunes (Oracle, lectura de ficheros, dashboards) y plantillas para la presentación.

| Si el reto es… | Empezar por |
|---|---|
| **NICS Lab** (detectar honeypots e IAs impostoras) | [`kits/nics/README.md`](kits/nics/README.md) |
| **Mercedes-Benz** (segmentar clientes) | [`kits/mercedes/README.md`](kits/mercedes/README.md) |
| **NTT DATA** (detectar alucinaciones de una IA) | [`kits/ntt/README.md`](kits/ntt/README.md) |
| Otro (Indra, Google, Betsson) | `common/` (Oracle, lectura de ficheros, dashboard genérico) y apartados 12–15 del plan |
| Presentación del viernes | [`docs/presentacion/README.md`](docs/presentacion/README.md) |
| Base de datos Oracle | [`docs/oracle.md`](docs/oracle.md) (URL del esquema y cómo conectar) |

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

## 2. Probar los kits con datos de ensayo

### Kit NICS (unos 20 s; ~2 min si tienes Ollama instalado)

```bash
.venv\Scripts\python -m kits.nics.run --testbed
```

Arranca 3 servicios de prueba en tu portátil (uno real, un honeypot clásico y uno con IA), los analiza y
debe terminar con **Aciertos: 3/3**. Para verlo en el navegador:

```bash
.venv\Scripts\streamlit run kits\nics\app.py
```

### Kit Mercedes (unos 40 s)

```bash
.venv\Scripts\python -m kits.mercedes.sample_data
```

```bash
.venv\Scripts\python -m kits.mercedes.run --data data\clientes_ensayo.csv --model kmeans_k5
```

Crea 2.000 clientes inventados, los segmenta y genera informes. Para verlo en el navegador:

```bash
.venv\Scripts\streamlit run kits\mercedes\app.py
```

**Sobre los dashboards (Streamlit):** se abren solos en el navegador (`http://localhost:8501`), solo los ves tú.
La primera vez Streamlit pide un email en la terminal: dejarlo vacío y pulsar **Enter**. Se cierran con **Ctrl+C**
en la terminal. El botón *Deploy* no se usa.

### Kit NTT DATA (unos 5 s; ~10 min con el juez LLM `--llm`)

```bash
.venv\Scripts\python -m kits.ntt.sample_data
```

```bash
.venv\Scripts\python -m kits.ntt.run --data data\ntt_ensayo.csv
```

Crea 120 respuestas de IA (la mitad con datos inventados) y detecta cuáles se inventan algo. Para verlo en el navegador:

```bash
.venv\Scripts\streamlit run kits\ntt\app.py
```

**Informes** (doble clic para abrir): `out\nics\informe.html`, `out\mercedes\informe.html`, `out\mercedes\eda.html`, `out\ntt\informe.html`.

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
| `kits/nics/` | Kit de clasificación de servicios: sondas, rasgos, reglas en YAML, informe, dashboard y banco de pruebas |
| `kits/mercedes/` | Kit de segmentación: EDA, comparación de modelos, perfiles, personas, dashboard con simulador y dataset de ensayo |
| `kits/ntt/` | Kit detector de alucinaciones: señales (cifras, nombres, fechas, negaciones, apoyo), juez LLM local, modelo reutilizable, dashboard y dataset de ensayo |
| `docs/` | Plan, `oracle.md`, `sql/` (consultas de ensayo), `presentacion/` (plantillas y guion), `arquitectura/` (diagramas) |
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
