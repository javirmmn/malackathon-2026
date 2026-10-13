# Kit NICS Lab · clasificación de servicios (pareja A, 14/10)

Pendiente de construir mañana. Especificación: apartado **6.2** de [`docs/plan_fuente.html`](../../docs/plan_fuente.html).

Piezas: inventario → recolector de evidencias → rasgos por servicio → clasificador por reglas con pesos (YAML) → dashboard + informe. Banco de pruebas local con 3 servicios simulados (real, honeypot clásico, honeypot generativo con Ollama).

**Hecho cuando:** `python -m kits.nics.run --targets targets.csv` clasifica bien los 3 servicios simulados y el dashboard los muestra con sus evidencias.

```bash
.venv\Scripts\python -m pip install -r kits\nics\requirements.txt
```

Para el dashboard: partir de una copia de `common/streamlit_app.py`.
