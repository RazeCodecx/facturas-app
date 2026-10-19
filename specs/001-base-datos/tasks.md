# Tasks 001 — Base de datos

**Spec:** [`spec.md`](./spec.md) · **Design:** [`design.md`](./design.md)

> Checklist en orden. Cada tarea dice cómo se comprueba. Los criterios `CA-xx` son
> los de la spec. **Una tarea a la vez** (`AGENTS.md` § No hagas).

**Las cuatro decisiones de esquema (D-00 a D-03) están resueltas** y escritas en
`design.md`. Esta feature ya no tiene bloqueos.

---

## Fase 1 — Entorno

Ninguna tarea de esta fase bloquea a ninguna.

- [X] **T1.1** Crear el `.venv` con Python 3.12.10.
      *Verificable:* `.\.venv\Scripts\python.exe --version` dice 3.12.10.
- [X] **T1.2** `requirements.txt` con `fastapi`, `uvicorn`, `python-multipart`,
      `pydantic`, `pytesseract`, `easyocr`, `psycopg[binary]`, `Pillow`,
      `pillow-heif`, y `pytest` y `ruff` como desarrollo.
      *Verificable:* `pip install -r requirements.txt` sin errores. Si pide algo
      fuera de esta lista, **parar y preguntar**.
- [X] **T1.3** `.gitignore` con `.venv/`, `__pycache__/`, `.env`, `imagenes/`.
- [X] **T1.4** `.env.example` con `DATABASE_URL`, `DB_POOL_SIZE`,
      `TESSERACT_CMD`, `EASYOCR_MODEL_DIR`, `OCR_CONFIDENCE_THRESHOLD`,
      `MAX_UPLOAD_MB`, `EXPORT_DIR`. `.env` real con la cadena de conexión.
      *Verificable:* `.env` nunca se versiona.
- [X] **T1.5** Estructura de paquetes: `app/`, `app/api/`, `app/ocr/`,
      `app/db/`, `app/db/migrations/`, `app/export/`, `app/models/`, `tests/`.
      *Verificable:* coincide con `AGENTS.md` § Estructura del proyecto.

---

## Fase 2 — Esquema y acceso

- [X] **T2.1** `app/db/migrations/001_inicial.sql` con el esquema de
      `design.md`, **sin comentarios pendientes**. Todos los importes en
      `DOUBLE PRECISION`, nunca `NUMERIC` ni `FLOAT`.
      *Verificable:* corre limpia contra una base vacía.
- [X] **T2.2** El bloque `invoices` lleva `values JSONB NOT NULL DEFAULT '[]'` y
      **sin columna `operator`**.
      *Verificable:* el `INSERT` de una factura sin RIF funciona con
      `supplier_rif` en `NULL`. → CA-52
- [X] **T2.3** Fila de Venezuela en `fiscal_profiles`.
      *Verificable:* `SELECT * FROM fiscal_profiles` devuelve una fila `VE`/`VES`.
- [X] **T2.4** `app/db/pool.py` con el connection pool de psycopg.
      *Verificable:* abre y cierra conexión contra la base real.
- [X] **T2.5** `app/db/queries.py` con el INSERT de factura, items, taxes y
      `ocr_runs`, y los SELECT de listado y detalle.
      *Verificable:* **ningún endpoint contiene SQL**.
- [X] **T2.6** `tests/test_db.py`: crea el esquema en una base aislada, inserta
      una factura con sus items y taxes, la consulta, y verifica que
      `dedupe_key` rechaza el duplicado.
      *Verificable:* pasa sin tocar la base del usuario. → CA-12
- [X] **T2.7** `tests/test_db.py` verifica que un importe entero se relee exacto,
      que los valores del contador sobreviven un ciclo de escritura y lectura
      **con su primer texto intacto**, y que el detalle no trae `raw_text`.
      *Verificable:* pasa. → CA-13, CA-14, CA-51
- [X] **T2.8** `tests/test_db.py` con una factura sin `supplier_rif`.
      *Verificable:* se guarda con `NULL` y `review_reason` con `unreadable_rif`.
      → CA-52
- [X] **T2.9** `ruff check .` sin hallazgos y `pytest` en verde.
