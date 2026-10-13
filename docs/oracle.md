# Oracle (OCI) · datos del equipo

> **Aquí NO van contraseñas, ni el wallet, ni el `.env`.** Solo datos no secretos.
> Las credenciales de `ADMIN` y `MALACK` van en el gestor de contraseñas y se comparten por un canal seguro.

## Tenancy y base de datos

| Campo | Valor |
|---|---|
| Tenancy | `javierroman` |
| Región | Spain Central (Madrid) |
| Compartimento | `javierroman (root)` |
| Base de datos | `malackathon` (Autonomous AI Database, Transaction Processing, **Always Free**) |
| Fecha de creación | _pendiente (13/10)_ |
| Estado comprobado el 14/10 | _pendiente_ (si está *Stopped*, pulsar **Start**) |
| Usuario de trabajo | `MALACK` (cuota UNLIMITED, roles Graph / OML / REST) |

## URL del esquema de `MALACK`

**Es la que se entrega en el formulario de evaluación.**

```
PEGAR AQUÍ LA URL (Database actions -> Database Users -> tarjeta de MALACK)
```

## Conexión desde Python

1. *Database connection* → *Download wallet* → poner una contraseña al wallet.
2. Descomprimir el zip **fuera del repo** (p. ej. `C:\Users\<usuario>\oracle\Wallet_malackathon`).
3. Copiar `.env.example` a `.env` y rellenarlo (usuario, contraseña, alias, carpeta del wallet y su contraseña).
4. Probar:

```bash
.venv\Scripts\python -m common.db
```

Debe imprimir la versión de la base de datos y el usuario conectado.

## Carga de datos con Data Load (guía de la organización)

1. Abrir la URL del esquema e iniciar sesión como `MALACK`.
2. *Data Load* → *Load Data* → arrastrar el CSV/Excel.
3. **Pulsar el lápiz** antes de cargar: fechas, países, decimales con coma y campos raros como `VARCHAR2`.
4. *Start* → *Done*.
5. Transformar con SQL después (ver [`sql/prueba_carga.sql`](sql/prueba_carga.sql)).

## Límites Always Free

- Como máximo 2 Autonomous DB Always Free por tenancy (queda **1 hueco libre** tras crear `malackathon`).
- 1 OCPU y 20 GB por base de datos.
- 7 días sin uso → se detiene (se arranca con *Start*). ~90 días detenida → se elimina.
