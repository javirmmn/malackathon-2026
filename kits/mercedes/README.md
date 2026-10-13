# Kit Mercedes-Benz · clustering de clientes (pareja B, 14/10)

Pendiente de construir mañana. Especificación: apartado **6.3** de [`docs/plan_fuente.html`](../../docs/plan_fuente.html).

Piezas: dataset de ensayo (Kaggle) → EDA automática → preprocesado configurable → búsqueda de modelos (K-Means, GMM, HDBSCAN, K-Prototypes) con métricas → perfilado y "personas" → PCA/UMAP → dashboard con simulador.

**Hecho cuando:** con el dataset de ensayo, un solo comando genera la EDA, la comparación de modelos y los perfiles, y el dashboard muestra los segmentos.

```bash
.venv\Scripts\python -m pip install -r kits\mercedes\requirements.txt
```

Ya disponible en `common/`: `read_any`, `normalize_columns`, `to_number_es`, `quick_profile` (dataio), plantilla de gráficos (charts) y carga/lectura en Oracle (db).
