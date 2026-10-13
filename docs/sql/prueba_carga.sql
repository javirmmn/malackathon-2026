-- =====================================================================
-- Ensayo de carga (apartado 5.1 del plan) · ejecutar como MALACK
-- Database Actions -> SQL. Ejecutar bloque a bloque (seleccionar + Ctrl+Enter)
-- o todo con F5 (Run Script).
--
-- Se asume que prueba_carga.csv se cargó con Data Load en la tabla
-- PRUEBA_CARGA y que, con el lápiz, FECHA, PAIS e IMPORTE se pusieron
-- como VARCHAR2.
-- =====================================================================

-- 1) ¿Están las 10 filas?  -> esperado: 10
SELECT COUNT(*) AS filas FROM PRUEBA_CARGA;

-- 2) ¿Qué tipos ha creado Data Load?
--    Esperado: FECHA, PAIS, IMPORTE = VARCHAR2. ID puede ser NUMBER.
SELECT column_name, data_type, data_length
FROM   user_tab_columns
WHERE  table_name = 'PRUEBA_CARGA'
ORDER  BY column_id;

-- 3) Vista rápida de los datos tal cual
SELECT * FROM PRUEBA_CARGA ORDER BY id;

-- 4) Tildes bien cargadas (UTF-8)?  -> España = 4, sin caracteres raros
SELECT pais, COUNT(*) AS n
FROM   PRUEBA_CARGA
GROUP  BY pais
ORDER  BY n DESC, pais;

-- 5) Conversiones: fecha DD/MM/YYYY y decimal con coma.
--    Forma del plan: REPLACE(',' -> '.') depende de que la sesión use '.'
--    como separador decimal (en Autonomous DB es lo habitual).
--    Forma robusta: indicar NLS_NUMERIC_CHARACTERS en la propia llamada.
SELECT id,
       nombre,
       TO_DATE(fecha, 'DD/MM/YYYY')                                AS fecha_dt,
       TO_NUMBER(REPLACE(importe, ',', '.'))                       AS importe_plan,
       TO_NUMBER(importe, '999999999D99',
                 'NLS_NUMERIC_CHARACTERS = '',.''')                AS importe_robusto
FROM   PRUEBA_CARGA
ORDER  BY id;

-- 6) Detectar filas que NO convierten (útil con datos reales del reto).
--    VALIDATE_CONVERSION devuelve 0 si el valor no se puede convertir.
SELECT id, fecha, importe
FROM   PRUEBA_CARGA
WHERE  VALIDATE_CONVERSION(fecha AS DATE, 'DD/MM/YYYY') = 0
   OR  VALIDATE_CONVERSION(importe AS NUMBER, '999999999D99',
                           'NLS_NUMERIC_CHARACTERS = '',.''') = 0;
-- esperado: ninguna fila

-- 7) Patrón para el jueves: tabla "limpia" tipada a partir de la cruda.
--    DEFAULT NULL ON CONVERSION ERROR evita que una fila mala tumbe la consulta.
CREATE TABLE PRUEBA_LIMPIA AS
SELECT CAST(id AS NUMBER)                                          AS id,
       TRIM(nombre)                                                AS nombre,
       TO_DATE(fecha DEFAULT NULL ON CONVERSION ERROR, 'DD/MM/YYYY') AS fecha,
       TRIM(pais)                                                  AS pais,
       TO_NUMBER(importe DEFAULT NULL ON CONVERSION ERROR, '999999999D99',
                 'NLS_NUMERIC_CHARACTERS = '',.''')                AS importe,
       TRIM(categoria)                                             AS categoria
FROM   PRUEBA_CARGA;

-- 8) Comprobar la tabla limpia con una agregación
--    esperado: Premium 4 filas / 6065,34 · Estándar 3 / 1540,95 · Básico 3 / 165,19
SELECT categoria,
       COUNT(*)                     AS clientes,
       SUM(importe)                 AS total,
       ROUND(AVG(importe), 2)       AS media,
       MIN(fecha)                   AS primera,
       MAX(fecha)                   AS ultima
FROM   PRUEBA_LIMPIA
GROUP  BY categoria
ORDER  BY total DESC;

-- 9) Limpieza: borrar SOLO las tablas de prueba.
--    La base de datos y el usuario MALACK se quedan para el jueves.
DROP TABLE PRUEBA_LIMPIA PURGE;
DROP TABLE PRUEBA_CARGA  PURGE;

-- 10) Comprobar que el esquema queda vacío -> esperado: sin filas
SELECT table_name FROM user_tables;
