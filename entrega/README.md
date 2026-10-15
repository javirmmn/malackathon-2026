# entrega/

Resultado final del reto NICS Lab (equipo 8), versionado para que cualquiera lo tenga sin regenerarlo.

| Fichero | Contenido |
|---|---|
| [`entrega.csv`](entrega.csv) | **CSV de entrega**: cabecera `port,service,class`, una fila por servicio abierto y disponible (26). `class`: 1 = real, 2 = honeypot clásico, 3 = honeypot generativo. Los 14 puertos abiertos pero no disponibles no figuran |
| [`dashboard.html`](dashboard.html) | **Dashboard** del resultado: mapa de los 26 puertos con su clase y confianza, ficha con la prueba clave y la evidencia de cada uno, gemelos, cómo se delata una IA, criterios y puertos descartados. Es un solo fichero HTML con los datos embebidos: descárgalo y ábrelo en el navegador |
| [`veredicto.csv`](veredicto.csv) | Veredicto confirmado a mano, con la evidencia, el método y la confianza de cada puerto. Es la verdad de referencia con la que el clasificador automático se compara (`Validación: 26/26`); la herramienta **nunca** la usa para clasificar |
| [`datos/`](datos/) | Evidencia de apoyo: pruebas capturadas (petición → respuesta), barrido de generativos, puertos descartados, sondas e interacciones por protocolo. Se pueden regenerar con `kits.nics.capturar_evidencia` y `kits.nics.barrido_generativo`, y copiar aquí |

El clasificador automático (`python -m kits.nics.auto`, ver el [README raíz](../README.md#runbook-probar-el-clasificador-automático))
reproduce este CSV: las mismas 26 filas y las mismas clases.
