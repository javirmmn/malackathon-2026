# Malackathon 2026

Proyecto del equipo para el III Malackathon de la ETSI Informática (UMA), 15 y 16 de octubre de 2026.

- Plan completo: `docs/plan_fuente.html` (fuente legible) y `Plan_Malackathon_2026.pdf` (versión generada). Leer el HTML antes de empezar.
- Para regenerar el PDF tras editar el HTML: `.venv/Scripts/python.exe -m common.pdf docs/plan_fuente.html --out Plan_Malackathon_2026.pdf` (Chrome headless).
- **Reto asignado (15/10): NICS Lab** (nuestra 1.ª opción). Enunciado completo en el apartado 10 del plan. Ya no se trabaja en `kits/mercedes` ni `kits/ntt`.
- Escenario: red de "Ondalux Logística S.L.". Clasificar cada servicio **abierto** como 1=real, 2=honeypot clásico, 3=honeypot generativo. Entrega: write-up ≤3 páginas + CSV `port,service,class`.
- Acceso: VPN WireGuard a `10.66.0.1`, IP propia `10.66.T.M` (T=equipo, M=miembro). **El fichero de configuración WireGuard y las claves privadas NUNCA se suben al repo ni se pegan en el chat** (están en `.gitignore`: `*.conf`, `*wireguard*`).
- Oracle: tenancy `javierroman` (Spain Central/Madrid). Base de datos Always Free `malackathon` (Display name `malackathon-2026`) con usuario `MALACK`, creada el 14/10; URL del esquema en `docs/oracle.md`. Nunca subir contraseñas, wallet ni `.env` al repo.
- `prueba_carga.csv`: fichero de ensayo para practicar la carga de datos en Oracle. Consultas del ensayo en `docs/sql/prueba_carga.sql`.
- Entorno: venv en `.venv` (Python 3.13). Usar siempre `.venv/Scripts/python.exe` (tests: `-m pytest`; dashboard: `.venv/Scripts/streamlit run common/streamlit_app.py`; prueba de Oracle: `-m common.db`, necesita `.env`).
- `common/` ya existe (db, dataio, charts, plantilla Streamlit) y se reutiliza en los kits. pandas 3.x: las columnas de texto no son `object`, usar `pd.api.types`.
- Repo privado en GitHub: `javirmmn/malackathon-2026` (remoto `origin`, rama `main`). `gh` está en `C:\Program Files\GitHub CLI\gh.exe` (no está en el PATH de sesiones antiguas).
- Kits hechos y probados (14/10): `kits/nics` (`-m kits.nics.run --testbed`; reglas en `rules.yaml`; solo escanea localhost salvo `--scope`) y `kits/mercedes` (`-m kits.mercedes.sample_data` + `-m kits.mercedes.run --data ...`). Salidas en `out/` (ignorado). 9 tests.
- Ollama instalado (14/10) con `llama3.2:3b`; el testbed de NICS lo usa si está en marcha (~2–3 min). Los tests fuerzan el simulador.
- Oracle desde Python: `-m common.load <fichero> --tabla T [--simular]` y `--a-oracle PREFIJO` en los kits. Probado contra la BD real el 14/10 (wallet en `C:\Users\jrmro\oracle\Wallet_malackathon`, `.env` en la raíz, ignorado).
- Presentación: plantillas en `docs/presentacion/` (nics, mercedes, generica; huecos en `<mark>`), diagramas en `docs/arquitectura/`.
- Kit NTT (14/10 noche): `kits/ntt` (`-m kits.ntt.sample_data` + `-m kits.ntt.run --data data/ntt_ensayo.csv [--llm] [--modelo out/ntt/modelo.json]`). Señales en `signals.py`, pesos/umbral en `scorer.py`, juez Ollama en `judges.py`, API para el bot en `guardian.py`.
- NICS `--targets` acepta csv/xlsx/yaml, txt (host:puerto) y resultados guardados .xml/.gnmap; no descubre servicios por sí mismo. `--scope` obligatorio fuera de localhost (hoy: `10.66.T.0/24`, T=número de equipo).
- Pendiente para la entrega real: exportador del CSV `port,service,class` (el kit aún no lo genera) y el write-up de 3 páginas; cubrir servicios no-HTTP (el kit solo sondea/clasifica HTTP).
