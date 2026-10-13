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

Si los tests pasan, todo está bien. Luego:

```bash
.venv\Scripts\streamlit run common\streamlit_app.py
```

### Conexión a Oracle (opcional hasta saber el reto)

1. Pedir al equipo, **por un canal seguro**, la contraseña de `MALACK` y el wallet.
2. Descomprimir el wallet **fuera del repo**.
3. `copy .env.example .env` y rellenarlo.
4. `.venv\Scripts\python -m common.db` → debe decir `Conectado a ... como MALACK`.

Más detalle en [`docs/oracle.md`](docs/oracle.md).

## Estructura

| Carpeta | Contenido |
|---|---|
| `common/` | `db.py` (Oracle: `query_df`, `execute`, `df_to_table`), `dataio.py` (leer CSV/Excel con tildes y comas decimales, normalizar columnas, exportar), `charts.py` (estilo de gráficos), `streamlit_app.py` (plantilla de dashboard) |
| `kits/nics/` | Kit de clasificación de servicios (apartado 6.2) |
| `kits/mercedes/` | Kit de clustering de clientes (apartado 6.3) |
| `docs/` | Plan, `oracle.md` (URL del esquema, **sin contraseñas**), `sql/` con consultas |
| `data/` | Datos locales, **no se suben** |
| `tests/` | Pruebas de `common/` sin Oracle |

## Normas del repo

- **Nunca** subir contraseñas, wallet ni `.env` (están en `.gitignore`; revisad `git status` antes de cada commit).
- `main` siempre funcionando; ramas cortas para lo demás.
- Entrega el jueves 15 **antes de las 20:00** por el Campus Virtual.
