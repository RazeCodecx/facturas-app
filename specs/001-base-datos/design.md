# Design 001 — Base de datos

**Spec:** [`spec.md`](./spec.md) · **Rol:** Agente 1

> Las cuatro decisiones de esquema quedaron resueltas: **D-00**, **D-01**, **D-02** y
> **D-03**. El DDL de abajo es el definitivo y no lleva comentarios pendientes.

## Migración inicial

Un solo archivo: `app/db/migrations/001_inicial.sql`. Cubre las 5 tablas de
`SCHEMAS.md` §3. Números en `DOUBLE PRECISION` (`CONSTITUTION.md` § Convenciones).

```sql
CREATE TABLE fiscal_profiles (
    id            SERIAL PRIMARY KEY,
    country_code  VARCHAR(2)   NOT NULL UNIQUE,
    name          VARCHAR(80)  NOT NULL,
    currency      VARCHAR(3)   NOT NULL DEFAULT 'VES'
);

CREATE TABLE invoices (
    id               SERIAL PRIMARY KEY,
    supplier_rif     VARCHAR(20),
    serie            VARCHAR(20),
    numero           VARCHAR(40),
    issue_date       DATE,
    fiscal_profile_id INTEGER REFERENCES fiscal_profiles(id),
    dedupe_key       TEXT NOT NULL UNIQUE,
    review_status    VARCHAR(20) NOT NULL DEFAULT 'needs_review',
    review_reason    TEXT,
    values           JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE invoice_items (
    id           SERIAL PRIMARY KEY,
    invoice_id   INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    line_number  INTEGER NOT NULL,
    code         VARCHAR(40),
    description  TEXT,
    quantity     DOUBLE PRECISION,
    unit_price   DOUBLE PRECISION,
    amount       DOUBLE PRECISION
);

CREATE TABLE taxes (
    id          SERIAL PRIMARY KEY,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    item_id     INTEGER REFERENCES invoice_items(id) ON DELETE CASCADE,
    tax_type    VARCHAR(40) NOT NULL,
    rate        DOUBLE PRECISION,
    base_amount DOUBLE PRECISION,
    amount      DOUBLE PRECISION NOT NULL DEFAULT 0
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
```

## Las cuatro decisiones, resueltas

### D-00 — `values JSONB`, con el primer texto adentro

Es la decisión que sostiene el emparejamiento. Un objeto por valor extraído:

```json
[
  { "frase": "Total", "encabezado": "Total a pagar",
    "value": "116.00", "confidence": 92.0, "engine": "tesseract" }
]
```

**El primer texto va guardado porque es la clave del emparejamiento.** Si se
guardara solo el valor, con su posición, el contador podría cambiar
`Total = Base imponible` por `Total = Total factura` después de escanear y cada
columna recibiría el valor de otra. Se cambió de `float` a `JSONB` justamente para que
el primer texto viaje con el valor (`SCHEMAS.md` §1.3, §3.1).

Los cuatro campos de control **sí** van en columnas suyas, porque se filtran y se
indexan. `supplier_rif` acepta `NULL`: sin RIF la factura se guarda igual.

`values` **nunca se purga.** El contador puede volver a exportar cuando quiera.

### D-01 — El motor va por valor, no en `ocr_runs`

EasyOCR entra **por primer texto**, así que una misma foto puede tener valores de
Tesseract y de EasyOCR al mismo tiempo. Un solo campo `engine_version` en `ocr_runs`
no alcanzaría a decir eso, y por eso el motor **va dentro de cada objeto del JSONB**.

En `ocr_runs` queda `engine_version` con el motor **principal** de la foto, para
saber con qué se procesó. El detalle por campo está en `values`.

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

**No hay tablas de campos propios.** Existieron en un borrador y se eliminaron: el
contador escribe pares `primer texto = segundo texto` en `plantilla.csv`
(`SCHEMAS.md` §4). No hay `custom_fields` ni `invoice_custom_values`.

**`review_status` con valor por defecto `needs_review`.** Si una factura se inserta
sin que la 002 la valide, el estado por defecto obliga a revisión.

**`dedupe_key` con `TEXT`, no `VARCHAR`.** Es una clave compuesta de cuatro partes
con separador; una longitud fija artificial cortaría RIFs largos más adelante.

**Sin RIF, la clave se arma igual.** Con `supplier_rif` vacío, la `dedupe_key` queda
`"|" + serie + "|" + numero + "|" + fecha`, que puede chocar entre proveedores
distintos. Es el riesgo asumido de `SCHEMAS.md` §2.1: la factura entra sin
protección contra duplicados y la app avisa con `unreadable_rif`.

**Índices.** Uno en `review_status` y otro en `issue_date`, que son los filtros de
`SCHEMAS.md` §7. Uno en `supplier_rif`, que es filtro de la 003. **Ninguno sobre el
JSONB**: los valores del contador no se filtran, se exportan.

**`raw_text` a veces es `NULL`.** Solo se guarda cuando algún valor salió dudoso o no
coincidió, que es cuando sirve para depurar. `CONSTITUTION.md` regla 4.

**D-04 sigue abierta:** cómo se purga ese texto, y quién lo ejecuta. Es una
sentencia `UPDATE`, no un módulo. Ver `spec.md` § Decisiones pendientes.

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