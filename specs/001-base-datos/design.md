# Design 001 — Base de datos

**Spec:** [`spec.md`](./spec.md) · **Rol:** Agente 1

> Las decisiones de esquema **D-00**, **D-01**, **D-02** y **D-03** están
> resueltas. El DDL de abajo es el definitivo.

## Migración inicial

Un solo archivo: `app/db/migrations/001_inicial.sql`. Cubre las 2 tablas de
`SCHEMAS.md` §3.

```sql
CREATE TABLE invoices (
    id            SERIAL PRIMARY KEY,
    review_status VARCHAR(20) NOT NULL DEFAULT 'needs_review',
    review_reason TEXT,
    values        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ocr_runs (
    id             SERIAL PRIMARY KEY,
    invoice_id     INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    original_path  TEXT NOT NULL,
    converted_path TEXT,
    raw_text       TEXT,
    engine_version VARCHAR(80) NOT NULL,
    confidence     DOUBLE PRECISION,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_invoices_review_status ON invoices(review_status);
CREATE INDEX idx_ocr_runs_invoice       ON ocr_runs(invoice_id);
```

## Las decisiones, resueltas

### D-00 — `values JSONB`, con el primer texto adentro

Un objeto por valor extraído, y **solo por las columnas que pidió el contador**:

```json
[
  { "frase": "Total a pagar", "encabezado": "Base imponible",
    "value": 116.0, "confidence": 92.0 },
  { "frase": "RIF", "encabezado": "RIF del proveedor",
    "value": "J-31245678-7", "confidence": 88.5 }
]
```

**El primer texto va guardado porque es la clave del emparejamiento.** Si se
guardara solo el valor, con su posición, el contador podría cambiar
`Total = Base imponible` por `Total = Total factura` después de escanear y cada
columna recibiría el valor de otra (`SCHEMAS.md` §1.3, §3.1).

`value` es un número cuando el valor leído es numérico. Es texto cuando el
contador pidió explícitamente una columna no numérica. La app **no inventa
columnas de control** ni busca RIF, fecha, serie o número de factura por su
cuenta.

`values` **nunca se purga.** El contador puede volver a exportar cuando quiera.

### D-01 — El motor no se guarda por valor

El motor de OCR es un dato interno de la corrida, no un dato del contador. Por eso
`invoices.values` **no lleva `engine`**.

`ocr_runs.engine_version` guarda el motor que procesó la foto, para saber con qué
se leyó. RapidOCR es el único motor; el detalle por valor no se guarda.

### D-02 — La imagen en disco

`original_path` y `converted_path`. El iPhone manda HEIC, la app convierte con
`pillow-heif`, y **guarda las dos**: la original por fidelidad y la convertida para
reprocesar sin volver a convertir.

Disco y no `BYTEA` porque son unos pocos MB por factura, la base no tiene por qué
crecer con fotos, y respaldar es copiar una carpeta.

### D-03 — Se eliminó la columna `operator`

La app es local y **no tiene autenticación**, así que no hay quién sea el operador.
Una columna que siempre queda en `NULL` es ruido, y crearla ahora sería más difícil
de quitar después (`CONSTITUTION.md` regla 1).

## Notas de diseño

**Las líneas de la factura no se modelan.** Una foto puede traer una o varias
líneas; la app no las separa ni crea ítems. Solo guarda los valores de las columnas
pedidas.

**No hay tablas de campos propios.** El contador escribe pares
`primer texto = segundo texto` en `plantilla.csv` (`SCHEMAS.md` §4). No hay
`custom_fields` ni `invoice_custom_values`.

**Sin deduplicación.** Cada foto crea su propia fila. No hay `dedupe_key` ni
comparación de imágenes, textos o datos.

**`review_status` con valor por defecto `needs_review`.** Si una factura se inserta
sin que la 002 la valide, el estado por defecto obliga a revisión.

**`review_status` y `review_reason` no van al Excel.** Se exponen en la API para
que el contador vea qué columna falló, pero el CSV solo lleva los valores pedidos.
`review_reason` alimenta `avisos.csv`.

**Índices.** Uno en `review_status`, que es el filtro de la API, y otro en
`ocr_runs.invoice_id`, que es la relación con la factura. **Ninguno sobre el
JSONB**: los valores del contador no se filtran, se exportan.

**`raw_text` a veces es `NULL`.** Solo se guarda cuando algún valor salió dudoso o
no coincidió, que es cuando sirve para depurar. Es dato interno
(`CONSTITUTION.md` regla 4) y no hay purga automática.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `app/db/migrations/001_inicial.sql` | El esquema de arriba |
| `app/db/pool.py` | Connection pool de psycopg, leído de `.env` |
| `app/db/queries.py` | INSERT y SELECT. **Ningún SQL fuera de este archivo** |

## Configuración

| Variable | Para qué | Estado |
|---|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL | `postgresql://facturas_app:clave@localhost:5433/facturas` |
| `DB_POOL_SIZE` | Conexiones simultáneas | 5. La app es de un solo usuario |

## Fuera de esta feature

La 002 escribe en `invoices` y `ocr_runs`. La 003 expone las queries por HTTP. La
004 lee y empareja por primer texto. **No hay feature 005:** los pares viven en
`plantilla.csv`, no en una tabla.
