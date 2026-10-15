# Kit Mercedes-Benz · segmentación de clientes

Un comando hace la EDA, compara modelos, perfila los segmentos y deja todo listo para el dashboard.
Especificación original: apartado **6.3** del plan.

## Probarlo con el dataset de ensayo (2 minutos)

```bash
.venv\Scripts\python -m kits.mercedes.sample_data
.venv\Scripts\python -m kits.mercedes.run --data data\clientes_ensayo.csv --model kmeans_k5
.venv\Scripts\streamlit run kits\mercedes\app.py
```

El dataset de ensayo es **sintético**: 2.000 clientes con 5 segmentos plantados (Ejecutivo premium, Familia SUV,
Joven urbano, Entusiasta AMG, Sénior fiel), nulos, atípicos, fechas DD/MM/YYYY e importes con coma.
Con `kmeans_k5` el pipeline los recupera con un acuerdo (ARI) de ~0,96.

## El jueves, con los datos del reto

```bash
.venv\Scripts\python -m kits.mercedes.run --data data\<fichero_del_reto>.xlsx
```

1. Mira la salida `[1/5]`: qué columnas usa y cuáles descarta (identificadores, texto libre, >60 % nulos).
   Si se cuela alguna que no tiene sentido para segmentar, añade `--exclude col1,col2`.
2. Abre `out\mercedes\eda.html` y entiende los datos (atípicos, nulos, correlaciones).
3. Mira los **candidatos** que imprime `[4/5]`. Si dos están cerca, elegid el que mejor se explica a negocio
   y relanzad con `--model kmeans_k5` (o `gmm_k4`, `hdbscan`...).
4. Abre `out\mercedes\informe.html`: perfiles, radar, mapa 2D y rasgos que distinguen cada segmento.
5. **Lo que gana el reto es el storytelling:** copia `out\mercedes\personas_plantilla.yaml` a
   `out\mercedes\personas.yaml` y rellena nombre de *persona*, descripción y acciones de marketing.
   El dashboard lo lee automáticamente.

## Opciones

| Opción | Para qué |
|---|---|
| `--sql "SELECT ..."` | Leer desde la Autonomous DB (necesita `.env` y wallet) en vez de un fichero |
| `--sheet 1` | Hoja del Excel |
| `--exclude a,b` | Columnas que no deben usarse |
| `--kmin 2 --kmax 10` | Rango de k |
| `--scaler robust` | Escalado robusto si hay muchos atípicos |
| `--cat-weight 0.5` | Peso de las categóricas frente a las numéricas (0 = ignorarlas) |
| `--model kmeans_k5` | Forzar un modelo concreto |
| `--kprototypes` | Probar también K-Prototypes (lento; útil con muchas categóricas) |
| `--no-umap` / `--no-eda` | Más rápido |

## Qué hace por dentro (`pipeline.py`)

1. **Tipos:** texto que es fecha → fecha; texto con formato `1.234,50` → número.
2. **Esquema:** numéricas, categóricas (≤30 valores), fechas → `dias_desde_<col>` (recencia tipo RFM); descarta IDs.
3. **Preprocesado:** imputación (mediana/moda), recorte de atípicos (p1–p99), escalado, one-hot con peso 0,5.
4. **Modelos:** K-Means y GMM para cada k, HDBSCAN (de scikit-learn) y K-Prototypes opcional.
   Métricas: silhouette, Davies-Bouldin, Calinski-Harabasz, inercia (codo) y BIC.
5. **Elección automática:** mejor silhouette entre 3 y 8 segmentos con <20 % de ruido (se puede forzar).
6. **Perfiles:** tamaños, medias, modas y rasgos distintivos (diferencia en desviaciones típicas o en puntos %).
7. **Simulador:** asigna clientes nuevos al centroide más cercano (vale para cualquier método).

## Salidas (`out/mercedes/`, no se suben al repo)

`eda.html`, `informe.html`, `modelos.csv`, `perfiles_*.csv`, `clientes_segmentados.csv` (con segmento y coordenadas 2D),
`personas_plantilla.yaml`, `modelo.joblib`.
