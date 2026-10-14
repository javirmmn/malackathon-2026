# Presentación del viernes (7 minutos, un solo ponente, demo en directo)

Plantillas de 7 diapositivas 16:9 que siguen el guion del apartado 9 del plan:

| Fichero | Para |
|---|---|
| `nics.html` | Reto NICS Lab (con diagrama `../arquitectura/nics.svg`) |
| `mercedes.html` | Reto Mercedes-Benz (con diagrama `../arquitectura/mercedes.svg`) |
| `generica.html` | Cualquier otro reto |

## Cómo se usa

1. Abrir el `.html` en VS Code y rellenar todo lo que está entre `<mark>…</mark>` (sale **resaltado en amarillo**:
   si queda algo amarillo, falta por rellenar). Quitar las etiquetas `<mark>` al terminar.
2. Capturas del dashboard en `docs/presentacion/capturas/` (Win+Shift+S) y enlazarlas donde indica la plantilla.
3. Ver el resultado: doble clic en el `.html` (se abre en el navegador).
4. Exportar a PDF:

```bash
.venv\Scripts\python -m common.pdf docs\presentacion\nics.html
```

5. Copiar el PDF **y el vídeo de la demo** a un USB.

## Guion (7:00 máximo, ensayar a 6:45)

| Tiempo | Diapositiva | Qué decir |
|---|---|---|
| 0:00–0:30 | 1–2 | El problema en una frase y por qué le importa a la empresa |
| 0:30–1:30 | 3 | El enfoque con el diagrama. Una idea clave, no todos los detalles |
| 1:30–5:30 | 4 + demo | **Un caso concreto de principio a fin** en el dashboard. Lo más memorable de la charla |
| 5:30–6:30 | 5 | Resultados con números y el insight principal |
| 6:30–7:00 | 6–7 | Limitaciones honestas, siguientes pasos y cierre |

Antes de presentar: dashboard ya abierto en el navegador, datos cargados, zoom del navegador al 125 %,
notificaciones desactivadas, portátil enchufado y vídeo de respaldo a mano.

## Preguntas probables del jurado (que cada uno sepa explicar su parte)

- **¿Por qué este método?** NICS: reglas explicables porque el reto pide justificar cada clasificación y hay pocos
  ejemplos para entrenar un modelo. Mercedes: comparamos varios algoritmos con métricas y elegimos el más
  interpretable para negocio.
- **¿Cómo lo habéis validado?** Banco de pruebas con 3 servicios conocidos (3/3, también contra una IA real con
  Ollama) / dataset sintético con segmentos conocidos (ARI 0,96) + métricas sobre los datos del reto.
- **¿Cómo escala?** Peticiones asíncronas con concurrencia limitada / pipeline en scikit-learn, datos en Oracle.
- **¿Qué haríais con más tiempo?** Ver la diapositiva 6.
- **Enseñadnos la arquitectura / el código:** diagrama de `docs/arquitectura/` y el README de cada kit.
- **¿Qué traíais preparado?** Con naturalidad: infraestructura genérica (conexión a Oracle, plantillas, esqueleto de
  los kits y un banco de pruebas). El análisis y los resultados se hicieron el jueves con los datos del reto.
