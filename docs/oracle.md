# Oracle (OCI) · datos del equipo

> **Aquí NO van contraseñas, ni el wallet, ni el `.env`.** Solo datos no secretos.
> Las credenciales de `ADMIN` y `MALACK` van en el gestor de contraseñas y se comparten por un canal seguro.

## Tenancy y base de datos

| Campo | Valor |
|---|---|
| Tenancy | `javierroman` |
| Región | Spain Central (Madrid) |
| Compartimento | `javierroman (root)` |
| Base de datos | Database name `malackathon` · Display name `malackathon-2026` (Autonomous AI Database Serverless 26ai, Transaction Processing, **Always Free**) |
| Fecha de creación | 14/10/2026 |
| Estado | *Available* el 14/10. Si el jueves está *Stopped*, pulsar **Start** |
| Acceso de red | Secure access from everywhere, con mTLS (hace falta el wallet para conectar desde Python) |
| Usuario de trabajo | `MALACK` (cuota UNLIMITED; Graph, OML y REST activados; alias REST `malack`; Spatial desactivado) |

## URL del esquema de `MALACK`

**Es la que se entrega en el formulario de evaluación.**

```
https://g7dd466e4fc1627-malackathon.adb.eu-madrid-1.oraclecloudapps.com/ords/malack/_sdw/
```

## Conexión desde Python (probada el 14/10 ✅)

1. *Database connection* → *Download wallet* (Instance wallet) → poner una contraseña al wallet.
2. Descomprimir el zip **fuera del repo** (p. ej. `C:\Users\<usuario>\oracle\Wallet_malackathon`).
3. Copiar `.env.example` a `.env` y rellenarlo (usuario, contraseña, alias, carpeta del wallet y su contraseña).
4. Probar:

```bash
.venv\Scripts\python -m common.db
```

Debe imprimir `Conectado a ... como MALACK`. Probado el 14/10: Oracle 23.26, carga con `common.load` y
resultados de los dos kits con `--a-oracle` (tablas de ensayo borradas después).

- La contraseña del wallet es la que se pone al descargarlo (el fichero `ewallet.pem` va cifrado). Si se olvida,
  se vuelve a descargar con otra.
- El mismo wallet sirve para SQL Developer (escritorio o extensión de VS Code): tipo de conexión *Cloud Wallet*,
  zip del wallet, usuario `MALACK`, servicio `malackathon_low`. La web (Database Actions) no lo necesita.

## Carga de datos con Data Load (ensayada el 14/10 ✅)

Ensayo con `prueba_carga.csv`: 10 filas cargadas, tildes correctas, fecha y decimal con coma convertidos con SQL y tablas de prueba borradas.

1. Abrir la URL del esquema (mejor en incógnito) e iniciar sesión como `MALACK`.
2. *Carga de datos* → *Cargar datos* → ficheros locales → arrastrar el CSV/Excel.
3. **Pulsar el lápiz** antes de cargar. Configuración que funcionó:
   - *Crear tabla* + nombre de la tabla en mayúsculas.
   - Codificación **AL32UTF8** · cierre de texto `"` · delimitador **coma** · fila de cabecera 1.
   - Fechas, países, decimales con coma y campos raros como **`VARCHAR2`**.
   - *Convertir datos numéricos no válidos en nulos* **desmarcado** (mejor ver los errores).
4. *Iniciar* → *Ejecutar* → check verde → *Listo*. Debe salir "N filas cargadas".
5. Transformar con SQL: ☰ → *Desarrollo* → *SQL*. Patrones en [`sql/prueba_carga.sql`](sql/prueba_carga.sql):
   - Ejecutar consulta a consulta con **Ctrl+Enter** (no F5, que lo ejecuta todo).
   - Decimal con coma: usar la forma robusta `TO_NUMBER(x, '999999999D99', 'NLS_NUMERIC_CHARACTERS = '',.''')`.
   - Tabla limpia con `... DEFAULT NULL ON CONVERSION ERROR` para que una fila mala no tumbe la consulta.
6. `DBTOOLS$EXECUTION_HISTORY` es una tabla interna del historial de la hoja SQL: no borrarla.

## Carga desde Python (alternativa a Data Load)

Con el `.env` y el wallet listos:

```bash
.venv\Scripts\python -m common.load data\reto.xlsx --tabla CLIENTES --simular
.venv\Scripts\python -m common.load data\reto.xlsx --tabla CLIENTES
```

- Normaliza los nombres de columna, convierte fechas DD/MM/YYYY y números con coma, y crea la tabla.
- `--texto` lo sube todo como `VARCHAR2` (como recomienda la guía); `--reemplazar` / `--anadir` si la tabla ya existe.
- Columnas con nombre reservado de Oracle (`date`, `level`, `size`...) se renombran con `_` final.
- Los kits guardan sus resultados con `--a-oracle PREFIJO` (ver su README).

## Límites Always Free

- Como máximo 2 Autonomous DB Always Free por tenancy (queda **1 hueco libre** tras crear `malackathon`).
- 1 OCPU y 20 GB por base de datos.
- 7 días sin uso → se detiene (se arranca con *Start*). ~90 días detenida → se elimina.
- El aviso "No se ha encontrado ningún perfil de IA ni credenciales" de Data Studio no afecta: solo hace falta para funciones de IA o almacenamiento de objetos.
