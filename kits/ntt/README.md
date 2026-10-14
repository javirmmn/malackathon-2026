# Kit NTT DATA · El Guardián: ¿la IA se ha inventado algo?

Recibe la **respuesta de una IA** y las **fuentes** en las que debía basarse, y decide si se ha inventado algo
(alucinación), explicando el motivo: "cifra que no aparece en las fuentes: 195", "nombre nuevo: Raúl Ortega"...
Especificación original: apartado **12** del plan.

## Probarlo con el dataset de ensayo (1 minuto)

```bash
.venv\Scripts\python -m kits.ntt.sample_data
```

```bash
.venv\Scripts\python -m kits.ntt.run --data data\ntt_ensayo.csv
```

```bash
.venv\Scripts\streamlit run kits\ntt\app.py
```

El dataset es **sintético** (120 respuestas sobre empresas inventadas): la mitad fieles y la otra mitad con un tipo de
alucinación plantado (cifra cambiada, fecha cambiada, nombre cambiado, dato añadido o negación). Resultado esperado:
~98 % de acierto. **Es optimista**: las respuestas reales parafrasean más y escriben cifras con letras.

## Cómo decide (señales)

| Señal | Qué mide | Coste |
|---|---|---|
| `cifras_no_en_fuentes` | Números de la respuesta que no están en las fuentes (normaliza `1.234,5` / `1,234.5`) | Gratis |
| `meses_no_en_fuentes` | Meses mencionados que no están en las fuentes | Gratis |
| `nombres_no_en_fuentes` | Nombres propios nuevos (palabras en mayúscula) | Gratis |
| `negacion_nueva` | "no", "nunca"... que las fuentes no tienen (posible contradicción) | Gratis |
| `apoyo_min` / `apoyo_medio` / `afirmaciones_debiles` | Cada frase de la respuesta frente a la frase más parecida de las fuentes | Gratis |
| `palabras_nuevas_pct` | % de palabras con contenido que no aparecen en las fuentes | Gratis |
| `llm_no_respaldada` (`--llm`) | Un LLM local (Ollama) juzga si está respaldada | ~5 s por respuesta (con caché) |
| `nli_*` (`--nli`) | Modelo NLI multilingüe: contradicción / no implicación | Requiere instalar ~2 GB |

Las señales se combinan en una **probabilidad**:
- **Con etiquetas** (columna `alucina`, `label`...): regresión logística, métricas por validación cruzada y
  umbral elegido para la métrica del ranking (`--metrica f1|accuracy|precision|recall`). Se guarda en `out\ntt\modelo.json`.
- **Sin etiquetas:** pesos por defecto (una cifra, nombre, fecha o negación nueva basta para marcarla; la paráfrasis sola no).

## El jueves, con los datos del reto

1. **Primera hora:** poner en marcha el bot de ejemplo de NTT y hacer una primera entrega al ranking (lo pide el plan).
2. Pasar sus datos por el kit (detecta solo las columnas; si no, `--col-respuesta`, `--col-fuentes`, `--col-etiqueta`):

```bash
.venv\Scripts\python -m kits.ntt.run --data data\reto.csv
```

3. Si van bien de tiempo, añadir el juez LLM (`--llm`) y comparar métricas.
4. **Generar la entrega** con el formato del ranking (ajustar los nombres de columna a lo que pidan):

```bash
.venv\Scripts\python -m kits.ntt.run --data data\test.csv --modelo out\ntt\modelo.json --entrega out\ntt\entrega.csv
```

5. **Prueba sorpresa a mitad de evento:** aplicar el modelo ya guardado, **sin reentrenar**, con el mismo comando
   `--modelo out\ntt\modelo.json`. Las reglas son generales (no dependen del tema), así que no sobreajustan.
6. **Integrarlo en su bot** (si la entrega es un bot y no un CSV):

```python
from kits.ntt.guardian import Guardian
g = Guardian("out/ntt/modelo.json", llm=False)
g.evaluar(respuesta, fuentes)   # -> {"alucina": True, "prob": 0.93, "motivos": [...], ...}
```

## Opciones

| Opción | Para qué |
|---|---|
| `--llm` | Añade el juez LLM local (Ollama + `llama3.2:3b`; cambiar con `OLLAMA_MODEL`) |
| `--nli` | Añade el modelo NLI. Antes: `.venv\Scripts\python -m pip install torch transformers` (~2 GB) |
| `--modelo out\ntt\modelo.json` | Aplica un modelo entrenado sin reentrenar (prueba sorpresa, test) |
| `--metrica f1` | Métrica para elegir el umbral (la del ranking) |
| `--entrega fichero.csv` | CSV con id, predicción y probabilidad |
| `--col-respuesta`, `--col-fuentes`, `--col-etiqueta`, `--col-id` | Si las columnas tienen nombres raros |

## Lo aprendido al ensayar con Ollama (14/10)

- Un LLM pequeño (3B) tiende a marcar como "inventado" lo que solo es **incompleto**. El prompt dice expresamente que
  omitir información no es alucinar; con eso acertó 17 de 18 en una muestra, pero a veces da **motivos equivocados**.
  Por eso es una señal más, no el juez final.
- La paráfrasis ("la dirige" frente a "está dirigida por") activa las señales "suaves"; por eso pesan poco.

## Salidas (`out/ntt/`, no se suben)

`resultados.csv` (cada respuesta con probabilidad, predicción, motivos y señales), `metricas.json`, `modelo.json`,
`informe.html` (respuestas con lo inventado resaltado), `cache_llm.json`.
