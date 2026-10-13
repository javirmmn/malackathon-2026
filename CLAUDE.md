# Malackathon 2026

Proyecto del equipo para el III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.

- Plan completo: `docs/plan_fuente.html` (fuente legible) y `Plan_Malackathon_2026.pdf` (versión generada). Leer el HTML antes de empezar.
- Para regenerar el PDF tras editar el HTML: Chrome headless con `--print-to-pdf` (Python no está en el PATH; usar el lanzador `py`).
- El reto asignado se conoce el jueves 15 por la mañana. El 14/10 se preparan kits de arranque genéricos para NICS Lab y Mercedes-Benz (apartado 6 del plan): `common/`, `kits/nics/`, `kits/mercedes/`, `docs/`, `data/`.
- Oracle: tenancy `javierroman` (Spain Central/Madrid). Base de datos Always Free `malackathon` con usuario `MALACK` (pendiente de crear el 13/10). Nunca subir contraseñas, wallet ni `.env` al repo.
- `prueba_carga.csv`: fichero de ensayo para practicar la carga de datos en Oracle. Consultas del ensayo en `docs/sql/prueba_carga.sql`.
- Entorno: venv en `.venv` (Python 3.13). Usar siempre `.venv/Scripts/python.exe` (tests: `-m pytest`; dashboard: `.venv/Scripts/streamlit run common/streamlit_app.py`; prueba de Oracle: `-m common.db`, necesita `.env`).
- `common/` ya existe (db, dataio, charts, plantilla Streamlit) y se reutiliza en los kits. pandas 3.x: las columnas de texto no son `object`, usar `pd.api.types`.
- Repo privado en GitHub: `javirmmn/malackathon-2026` (remoto `origin`, rama `main`). `gh` está en `C:\Program Files\GitHub CLI\gh.exe` (no está en el PATH de sesiones antiguas).
