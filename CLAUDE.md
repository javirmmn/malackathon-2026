# Malackathon 2026

Proyecto del equipo para el III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.

- Plan completo (histórico): `docs/plan_fuente.html` y `Plan_Malackathon_2026.pdf`. Regenerar el PDF tras editar el HTML:
  `.venv/Scripts/python.exe -m common.pdf docs/plan_fuente.html --out Plan_Malackathon_2026.pdf` (Chrome headless).
- Write-up de la entrega: `docs/writeup_nics.html` -> `docs/writeup_nics.pdf` (mismo comando de `common.pdf`; debe seguir en 3 páginas).

## Reto: NICS Lab (equipo 8) — clasificación terminada el 15/10

- Red de "Ondalux Logística S.L.", único host alcanzable por la VPN: `10.66.0.1`. 40 puertos abiertos con `nmap` completo.
  **14 se descartan como "no disponibles"** (solo saludo y cierran; criterio de la organización: solo cuentan los servicios
  abiertos y DISPONIBLES; lista `EXCLUIDOS` en `kits/nics/veredicto.py`).
- **Resultado final (26 disponibles): 8 real, 14 honeypot clásico, 4 honeypot generativo (31885, 29082, 25589, 40101)**,
  confirmados por interacción real. CSV de entrega: `entrega/entrega.csv` (`port,service,class`). Veredicto manual con la
  evidencia: `entrega/veredicto.csv`. Dashboard: `entrega/dashboard.html` (un solo HTML autocontenido). Evidencia capturada: `entrega/datos/`.
- Las claves de WireGuard y el fichero de configuración **nunca se suben al repo ni se pegan en el chat** (en
  `.gitignore`: `*.conf`, `*wireguard*`). El repo es **público**: nada de secretos, wallets ni `.env`.
- Los kits de Mercedes-Benz y NTT DATA (preparados el 14/10, antes de saber el reto) no se usan. Oracle tampoco se usa en
  este reto (se retiró del repo).

## Herramienta automática (entregable)

- `.venv/Scripts/python.exe -m kits.nics.auto --host 10.66.0.1` (~6 min, un solo barrido) imprime por terminal y **no
  escribe ficheros** (`--guardar` los vuelca a `out/nics_auto/`). Runbook en el `README.md` raíz; formato, parámetros y
  límites en `kits/nics/auto/README.md`; reglas editables en `kits/nics/auto/reglas.yaml`. Tests: `tests/test_nics_auto.py`.
- No usa el veredicto manual para clasificar; solo lo compara al final (`entrega/veredicto.csv`).
- Dashboard: `entrega/dashboard.html` (se abre con doble clic en el navegador; los datos van embebidos).
- Proceso manual que originó el veredicto (genera ficheros en `out/`, ignorado por git): `-m kits.nics.veredicto`,
  `-m kits.nics.barrido_generativo`, `-m kits.nics.capturar_evidencia`. Si se regeneran, copiar a `entrega/` lo que cambie.

## Entorno y repo

- venv en `.venv` (Python 3.13). Usar siempre `.venv/Scripts/python.exe` (tests: `-m pytest`).
- `common/` (dataio, charts, pdf, plantilla Streamlit) se reutiliza en los kits. pandas 3.x: las columnas de texto no son
  `object`, usar `pd.api.types`.
- Repo público en GitHub: `javirmmn/malackathon-2026` (remoto `origin`, rama `main`). `gh` está en
  `C:\Program Files\GitHub CLI\gh.exe` (no está en el PATH de sesiones antiguas).
