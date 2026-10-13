"""Estilo común de gráficos (plotly) para que dashboard, informe y PDF se vean igual.

    import common.charts  # registra y activa la plantilla "malack"
    import plotly.express as px
    px.bar(df, x="segmento", y="clientes")
"""

import plotly.graph_objects as go
import plotly.io as pio

PALETTE = [
    "#0b5cad",  # azul (color del plan)
    "#e07a1f",  # naranja
    "#1d7a46",  # verde
    "#b4410c",  # teja
    "#6f4fb3",  # violeta
    "#2a9db5",  # turquesa
    "#c2457a",  # frambuesa
    "#7a8394",  # gris
]

pio.templates["malack"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Segoe UI, Arial, sans-serif", size=13, color="#1d2433"),
        colorway=PALETTE,
        title=dict(x=0.01, xanchor="left", font=dict(size=17)),
        margin=dict(l=50, r=20, t=60, b=45),
        legend=dict(orientation="h", y=-0.18),
        hoverlabel=dict(font_size=12),
    )
)
pio.templates.default = "plotly_white+malack"
