# Malackathon 2026

Proyecto del equipo para el III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.

- Plan completo: `docs/plan_fuente.html` (fuente legible) y `Plan_Malackathon_2026.pdf` (versión generada). Leer el HTML antes de empezar.
- Para regenerar el PDF tras editar el HTML: `.venv/Scripts/python.exe -m common.pdf docs/plan_fuente.html --out Plan_Malackathon_2026.pdf` (Chrome headless).

## Reto: NICS Lab (equipo 8) — clasificación terminada el 15/10

- Red de "Ondalux Logística S.L.", único host alcanzable por la VPN: `10.66.0.1` (la tabla de rutas del túnel no da
  acceso a nada más). 40 puertos abiertos con `nmap` completo, cada uno en un puerto distinto. **14 se descartan como "no disponibles"** (solo saludo y cierran; aviso de la organización: solo cuentan servicios abiertos y DISPONIBLES; lista `EXCLUIDOS` en `veredicto.py`).
- **Resultado final (26 disponibles): 8 real, 14 honeypot clásico, 4 honeypot generativo (31885, 29082, 25589, 40101)**, los 26 confirmados por **interacción
  real** (no solo sondas): `docs/writeup_nics.html` (write-up de 3 páginas) y `kits/nics/README.md` tienen el
  detalle completo. CSV de entrega: `entrega/entrega.csv` (`port,service,class`; copia versionada, `out/` está ignorado).
- Reconstruir el veredicto tras cualquier cambio: `.venv/Scripts/python.exe -m kits.nics.veredicto`. Dashboard:
  `.venv/Scripts/streamlit run kits/nics/app_veredicto.py`.
  Barrido de generativos: `-m kits.nics.barrido_generativo` (obediencia a instrucciones, variantes de ruta por la caché,
  métodos no-GET, shell SSH). Evidencia concreta para el dashboard: `-m kits.nics.capturar_evidencia` (orden: veredicto →
  barrido_generativo → capturar_evidencia → streamlit).
- Confianza en `veredicto.py`: regla documentada en la cabecera del fichero (no es una probabilidad estadística).
- Las claves de WireGuard y el fichero de configuración **nunca se suben al repo ni se pegan en el chat** (en
  `.gitignore`: `*.conf`, `*wireguard*`).
- Los kits de Mercedes-Benz y NTT DATA (preparados el 14/10, antes de saber el reto) ya no se usan.

## Clasificador automático (entregable final)

- `python -m kits.nics.auto --host 10.66.0.1` (~6 min, un solo barrido) -> **solo terminal, no escribe ficheros** (`--guardar` los vuelca a `out/nics_auto/`:
  `clasificacion.csv`,
  `entrega.csv`, `rasgos.csv`, `pruebas.csv`, `no_disponibles.csv`, `validacion.csv`). Dashboard:
  `.venv/Scripts/streamlit run kits/nics/app_auto.py`. Reglas editables en `kits/nics/auto/reglas.yaml`
  (`--reclasificar` sin volver a sondear). Formato y límites: `kits/nics/auto/README.md`. Tests: `tests/test_nics_auto.py`.
- El camino automático NO usa los veredictos manuales para clasificar; solo los compara después (`validacion.csv`).

## Oracle

Tenancy `javierroman` (Spain Central/Madrid). Autonomous DB Always Free `malackathon` (Display name
`malackathon-2026`) con usuario `MALACK`; URL del esquema en `docs/oracle.md`. Conexión desde Python probada
(wallet en `C:\Users\jrmro\oracle\Wallet_malackathon`, `.env` en la raíz, ignorado). Nunca subir contraseñas,
wallet ni `.env` al repo. Carga de ficheros: `-m common.load <fichero> --tabla T`; los kits guardan resultados
con `--a-oracle PREFIJO`.

## Entorno y repo

- venv en `.venv` (Python 3.13). Usar siempre `.venv/Scripts/python.exe` (tests: `-m pytest`, 16 en verde).
- `common/` (db, dataio, charts, plantilla Streamlit) se reutiliza en los kits. pandas 3.x: las columnas de texto
  no son `object`, usar `pd.api.types`.
- Repo público en GitHub: `javirmmn/malackathon-2026` (remoto `origin`, rama `main`). `gh` está en
  `C:\Program Files\GitHub CLI\gh.exe` (no está en el PATH de sesiones antiguas).
- Presentación: plantillas en `docs/presentacion/` (nics, mercedes, generica; huecos en `<mark>`), diagramas en
  `docs/arquitectura/`.
