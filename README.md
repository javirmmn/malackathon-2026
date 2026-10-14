# Malackathon 2026 · equipo de Javier Román

III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.
Plan completo: [`docs/plan_fuente.html`](docs/plan_fuente.html) (y `Plan_Malackathon_2026.pdf`).

## Arrancar en 5 minutos (Windows)

Requisitos: Python 3.11–3.13 (en Windows usar el lanzador `py`) y Git.

```bash
git clone <URL_DEL_REPO> Malackathon_2026
cd Malackathon_2026
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest
```

Si los tests pasan, todo está bien. Instala también lo de los kits:

```bash
.venv\Scripts\python -m pip install -r kits\nics\requirements.txt -r kits\mercedes\requirements.txt
```

### Probar los kits (2 minutos cada uno)

| Kit | Ensayo | Dashboard |
|---|---|---|
| **NICS** (clasificar servicios) | `.venv\Scripts\python -m kits.nics.run --testbed` | `.venv\Scripts\streamlit run kits\nics\app.py` |
| **Mercedes** (segmentar clientes) | `.venv\Scripts\python -m kits.mercedes.sample_data` y luego `.venv\Scripts\python -m kits.mercedes.run --data data\clientes_ensayo.csv --model kmeans_k5` | `.venv\Scripts\streamlit run kits\mercedes\app.py` |
| Genérico (cualquier tabla) | — | `.venv\Scripts\streamlit run common\streamlit_app.py` |

Cómo usarlos el jueves con los datos del reto: [`kits/nics/README.md`](kits/nics/README.md) y [`kits/mercedes/README.md`](kits/mercedes/README.md).

### Conexión a Oracle (opcional hasta saber el reto)

1. Pedir al equipo, **por un canal seguro**, la contraseña de `MALACK` y el wallet.
2. Descomprimir el wallet **fuera del repo**.
3. `copy .env.example .env` y rellenarlo.
4. `.venv\Scripts\python -m common.db` → debe decir `Conectado a ... como MALACK`.

Subir cualquier fichero del reto a una tabla (alternativa a *Data Load*; `--simular` enseña el `CREATE TABLE` sin conectar):

```bash
.venv\Scripts\python -m common.load data\reto.xlsx --tabla CLIENTES
```

Más detalle en [`docs/oracle.md`](docs/oracle.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| `common/` | `db.py` (Oracle: `query_df`, `execute`, `df_to_table`), `dataio.py` (leer CSV/Excel con tildes y comas decimales, normalizar columnas, exportar), `charts.py` (estilo de gráficos), `streamlit_app.py` (plantilla de dashboard), `load.py` (fichero → tabla de Oracle), `pdf.py` (HTML → PDF con Chrome) |
| `kits/nics/` | Kit de clasificación de servicios: sondas, rasgos, reglas en YAML, informe, dashboard y banco de pruebas (apartado 6.2) |
| `kits/mercedes/` | Kit de segmentación: EDA, comparación de modelos, perfiles, personas, dashboard con simulador y dataset de ensayo (apartado 6.3) |
| `out/` | Salidas generadas por los kits (informes, CSV, modelos), **no se suben** |
| `docs/` | Plan, `oracle.md` (URL del esquema, **sin contraseñas**), `sql/` con consultas, `presentacion/` (plantillas de 7 diapositivas y guion), `arquitectura/` (diagramas) |
| `data/` | Datos locales, **no se suben** |
| `tests/` | Pruebas de `common/` y de los dos kits, sin Oracle (`python -m pytest`) |

## Normas del repo

- **Nunca** subir contraseñas, wallet ni `.env` (están en `.gitignore`; revisad `git status` antes de cada commit).
- `main` siempre funcionando; ramas cortas para lo demás.
- Entrega el jueves 15 **antes de las 20:00** por el Campus Virtual.
