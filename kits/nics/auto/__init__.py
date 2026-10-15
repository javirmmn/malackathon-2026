"""Clasificador automático NICS: un solo barrido sobre un host, un CSV y un dashboard.

    python -m kits.nics.auto --host 10.66.0.1

Etapas: descubrir puertos -> identificar protocolo -> filtrar no disponibles (saludo y cierre) -> sondear cada servicio
(genéricas + por producto + generativo + SSH/protocolos) -> tabla de rasgos -> motor de reglas ponderadas (reglas.yaml)
-> clasificacion.csv, entrega.csv, rasgos.csv, pruebas.csv -> dashboard (kits/nics/app_auto.py).

Ver kits/nics/auto/README.md para el formato de cada fichero y cómo se decide cada clase.
"""
