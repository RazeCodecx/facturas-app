# Tasks 001 — Base de datos

**Spec:** [`spec.md`](./spec.md) · **Design:** [`design.md`](./design.md)

> Checklist en orden. Cada tarea dice cómo se comprueba. Los criterios `CA-xx` son
> los de la spec. **Una tarea a la vez** (`AGENTS.md` § No hagas).

**Las decisiones de esquema (D-00 a D-03) están resueltas** y escritas en
`design.md`. Esta feature no tiene bloqueos.

---

## Fase 1 — Entorno

Ninguna tarea de esta fase bloquea a ninguna.

- [X] **T1.1** Crear el `.venv` con Python 3.12.10.
      *Verificable:* `.\.venv\Scripts\python.exe --version` dice 3.12.10.
- [X] **T1.2** Dependencias instaladas en `.venv`: `fastapi`, `uvicorn`,
      `python-multipart`, `pydantic`, `rapidocr`, `onnxruntime`, `numpy`,
      `psycopg[binary]`, `Pillow`, `pillow-heif`, y `pytest` y `ruff` como
      desarrollo.
      *Verificable:* el entorno importa cada dependencia sin errores. Si pide algo
      fuera de esta lista, **parar y preguntar**.
- [X] **T1.3** `.gitignore` con `.venv/`, `__pycache__/`, `.env`, `imagenes/`.
- [X] **T1.4** `.env.example` con `DATABASE_URL`, `DB_POOL_SIZE`,
      `OCR_CONFIDENCE_THRESHOLD`, `MAX_UPLOAD_MB`, `IMAGE_DIR`. `.env` real con
      la cadena de conexión.
      *Verificable:* `.env` nunca se versiona.
- [X] **T1.5** Estructura de paquetes: `app/`, `app/api/`, `app/ocr/`,
      `app/db/`, `app/db/migrations/`, `app/export/`, `app/models/`, `tests/`.
      *Verificable:* coincide con `AGENTS.md` § Estructura del proyecto.

---

## Fase 2 — Esquema y acceso

- [X] **T2.1** `app/db/migrations/001_inicial.sql` con el esquema de
      `design.md`, **sin comentarios pendientes**. Solo `invoices` y `ocr_runs`.
      *Verificable:* corre limpia contra una base vacía.
- [X] **T2.2** `invoices` lleva `values JSONB NOT NULL DEFAULT '[]'` y **sin
      columna `operator` ni campos de control**.
      *Verificable:* una factura se inserta sin RIF, serie, número ni fecha.
- [X] **T2.3** No existe `fiscal_profiles` ni ninguna tabla de líneas o
      impuestos.
      *Verificable:* `information_schema.tables` solo devuelve `invoices`,
      `ocr_runs` y `schema_migrations`.
- [X] **T2.4** `app/db/pool.py` con el connection pool de psycopg.
      *Verificable:* abre y cierra conexión contra la base real.
- [X] **T2.5** `app/db/queries.py` con el INSERT de factura y de `ocr_runs`, y
      los SELECT de listado y detalle. Sin items ni taxes.
      *Verificable:* **ningún endpoint contiene SQL**.
- [X] **T2.6** `tests/test_db.py`: crea el esquema en una base aislada, inserta
      dos veces la misma factura y verifica que quedan **dos filas**.
      *Verificable:* pasa sin tocar la base del usuario. → CA-12
- [X] **T2.7** `tests/test_db.py` verifica que un importe entero se relee exacto,
      que `values` conserva `frase`, `encabezado`, `value` y `confidence`
      **sin `engine`**, y que el detalle no trae `raw_text`.
      *Verificable:* pasa. → CA-13, CA-14, CA-51
- [X] **T2.8** `tests/test_db.py` con una factura con columnas sin coincidencia y
      con `raw_text` solo cuando hubo dudas.
      *Verificable:* se guarda con `value` en `NULL`, `needs_review` y el motivo
      correspondiente. → CA-52
- [X] **T2.9** `ruff check .` sin hallazgos y `pytest` en verde.
