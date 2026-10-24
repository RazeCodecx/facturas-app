# CHANGELOG

## 006 — Sin columnas ni campos prefabricados (2026-10-21)

### Hecho

- `plantilla.csv` es la única fuente de columnas. Se eliminó
  `COLUMNAS_POR_DEFECTO`; un archivo sin líneas de columna es error.
- `app/ocr/extract.py`: se eliminaron los cuatro campos de control (RIF, serie,
  número y fecha) y la conversión de fechas. Solo se busca lo que pide el
  contador. El valor es numérico cuando se puede leer como número; si no, se
  guarda el primer texto tal cual.
- El motor de OCR ya no se guarda dentro de `invoices.values`; queda solo como
  dato interno en `ocr_runs.engine_version`.
- `app/ocr/normalize.py`: se eliminaron `fecha()` y `formatear_numero()`.
- `invoices` queda con `id`, `review_status`, `review_reason`, `values` y
  `created_at`. Se eliminaron los campos de control, `fiscal_profile_id` y
  `dedupe_key`.
- Sin deduplicación: cada foto crea una fila, aunque sea la misma foto.
- API: la lista y la exportación solo filtran por `review_status`; el detalle ya
  no trae líneas ni impuestos; se eliminó el `409`.
- `SCHEMAS.md`, `CONSTITUTION.md`, `AGENTS.md` y `README.md` actualizados.

## 005 — Excel de salida en tiempo real (2026-10-20)

### Hecho

- `app/export/plantilla.py`: nueva opción `#excel=<ruta absoluta>` en las líneas
  `#`; `Plantilla.salida` (aditiva). Ruta relativa, extensión distinta de `.xlsx` o
  línea mal escrita se ignoran. Sin la línea, no se sincroniza nada.
- `app/export/excel.py`: escribe el libro indicado en una hoja `Facturas`,
  conservando las demás hojas. Agrega solo las facturas nuevas usando un cursor por
  canal en `.excel_estado.json` (raíz del proyecto). Guardado atómico, respaldo
  `*.bak` al rehacer y reintento en el siguiente escaneo si el libro está bloqueado.
- `app/export/avisos.py`: `escribir_avisos` y `agregar_avisos` para el `avisos.csv`
  que vive junto al Excel.
- `app/api/scan.py`: una llamada a `sincronizar(plantilla)` después de registrar la
  factura; un fallo del Excel no cambia la respuesta del escaneo.
- `app/export/csv.py`: `valores_por_frase` pasó a público para reutilizarlo.
- `CONSTITUTION.md`: `openpyxl` autorizada. `AGENTS.md`: el valor extraído se envía
  en tiempo real al Excel indicado en `plantilla.csv`.
- `tests/test_excel.py` (12 pruebas) y ampliaciones en `tests/test_plantilla.py` y
  `tests/test_api.py`.

### Decisiones tomadas en esta implementación

- **El cursor vive en la raíz del proyecto**, como se pidió, y no en una tabla.
- **No se crean carpetas**: si la carpeta destino no existe, se registra el motivo y
  no se escribe.
- **Sin SQL nuevo**: se reutiliza `listar_para_exportar()` y se filtra por `id` en
  memoria, para no tocar `queries.py`.
- **Primer volcado completo**: si falta el estado, desapareció el libro o cambiaron
  los encabezados, se respalda y se reescribe solo la hoja `Facturas` (y
  `avisos.csv`), en vez de arriesgar filas desalineadas o duplicadas.

## 004 — Plantilla y CSV (2026-10-19)

**Estado:** implementada y verificada con datos simulados. **La spec no se cierra**:
faltan las pruebas de punta a punta con foto y Excel (T7.6 a T7.12).

### Hecho

- `app/export/plantilla.py`: pares `primer texto = segundo texto`, líneas `#`,
  `COLUMNAS_POR_DEFECTO` (11 pares), los cuatro errores con número de línea y la
  excepción de escritura del mensaje de formato.
- `app/export/csv.py`: una sola cabecera, emparejamiento **por primer texto** con la
  misma normalización que la búsqueda, `utf-8-sig`, `None` como celda vacía y
  redondeo a 2 decimales solo al escribir.
- `app/export/avisos.py`: `invoice_id,frase,columna,motivo`, siempre con cabecera.
- `app/api/export.py`: los dos endpoints, con `review_status` e `issue_date`
  aplicados en el `SELECT`, y error de plantilla como `500` sin CSV a medias.
- `tests/test_plantilla.py` (17 pruebas) y `tests/test_export.py` (14 pruebas).
- `app/ocr/extract.py`: se expuso `normalizar_frase` para no duplicar la
  normalización en el export.

### Decisiones tomadas en esta implementación

- **"Una sola vez" sobrevive a un reinicio** con un archivo centinela
  `.plantilla_escrita` al lado de `plantilla.csv`. Sin él, borrar el mensaje y
  reiniciar lo volvería a escribir, que es justo lo que prohíbe T2.8. Es la única
  desviación del diseño y no toca `plantilla.csv`.
- **Primer texto repetido** se detecta con la normalización de la búsqueda (sin
  mayúsculas y, si `#acentos=0`, con tildes). Así `Total` y `TOTAL` también son
  error, porque producirían dos columnas con el mismo origen.
- **Orden del CSV:** por `created_at ASC, id ASC`, para que el lote salga en el
  orden en que se escaneó.

## 003 — API de captura (2026-10-19)

**Estado:** implementada y verificada con base y OCR mockeados. **La spec no se
cierra**: falta la prueba manual con el Atajo del iPhone (T4.7).

### Hecho

- `app/main.py`: FastAPI, CORS limitado a la red local, `pillow-heif` registrado,
  `/health` y los tres routers.
- `app/models/api.py`: modelos de respuesta sin `raw_text` ni rutas; `ScanResponse`
  con `warnings`.
- `app/api/scan.py`: valida content-type, tamaño y que Pillow abra la imagen;
  guarda original y convertida; delega en la 002 y traduce cada error a `413`,
  `415`, `422`, `409` o `503`.
- `app/api/invoices.py`: lista con filtros y paginación, y detalle con items y
  taxes.
- `app/db/queries.py`: `armar_dedupe_key` pasó a ser público y se agregó
  `listar_para_exportar` (sin paginar, con los mismos filtros).
- `tests/test_api.py` (17 pruebas): las cuatro rutas, los seis errores, HEIC,
  doble toque simultáneo, EasyOCR ausente y búsqueda de datos internos en todas
  las respuestas.
- `tests/conftest.py`: el pool ahora se reapunta a la config de la base aislada
  aunque `app.db.pool` se haya importado antes (por ejemplo, al importar
  `app.main`). Sin eso, los tests de base escribían en la base real.

### Pendiente

- **T4.7**: probar el Atajo real del iPhone sobre la Wi-Fi. Si no llega, revisar el
  firewall de Windows en el puerto 8000.
- La spec **no se cierra** hasta hacer esa prueba.

### Limitaciones conocidas

- **Formato numérico por defecto sin resolver:** sigue siendo `miles=,` /
  `decimal=.` (`SCHEMAS.md` §4.4). Con ese default, una factura venezolana escrita
  `116,00` no se parsea: el contador debe poner `#miles=. #decimal=,`. Cambiar el
  default a la convención venezolana requiere una decisión del diseño.
- El `409` consulta la factura existente para devolver su `review_status` y sus
  avisos; es una lectura extra, solo en el caso de doble toque.

---

## 002 — Extracción de factura (2026-10-19)

**Estado:** implementada y verificada con texto simulado. **La spec no se cierra**:
faltan las tareas que exigen fotos reales (ver *Pendiente*).

### Hecho

- `app/models/invoice.py`: `Columna` (inmutable), `Formato`, `ExtractedValue`,
  `ControlFields` y `ExtractionResult`.
- `app/ocr/preprocess.py`: los 5 pasos en el orden fijo (gris, ruido, inclinación,
  umbral, escalado), con OpenCV.
- `app/ocr/tesseract_engine.py`: `--psm 6 --oem 3 -l eng+spa`, texto en orden de
  lectura y confianza por palabra.
- `app/ocr/easyocr_engine.py`: arranque perezoso, `gpu=False`, `['es','en']`,
  confianza llevada a 0-100. Sin pesos devuelve `None` y avisa.
- `app/ocr/normalize.py`: separadores configurables, signo conservado, `NaN`/`inf`
  rechazados y fechas a ISO.
- `app/ocr/extract.py`: búsqueda por primer texto, coincidencias completas,
  `ambiguous`, `no_match`, los 4 campos de control y la combinación con EasyOCR.
- `app/ocr/pipeline.py`: une preprocesado, motores y extracción.
- `tests/test_extract.py` (42 pruebas) y `tests/test_preprocess.py` (4 pruebas).

### Pendiente

- **T4.7** y **T4.9** requieren fotos reales: fondos de color, sombra, dobladura,
  grapa y recibo térmico desvanecido. La carpeta `imagenes/` está vacía.
- Por lo mismo, la spec **no se cierra** (`CONSTITUTION.md` § Workflow, paso 4).

### Decisiones tomadas en esta implementación

- **OpenCV autorizado** en `CONSTITUTION.md` L13 como `opencv-python-headless`.
- **`TOTAL IVA`:** `Total` sí coincide con una palabra aparte, así que queda
  ambiguo. Se corrigieron `SCHEMAS.md` §5.2 y `design.md` L104, que decían lo
  contrario.
- **`items` queda vacío.** T3.3 lo permite y el diseño no define cómo parsear las
  líneas de la factura.
- **EasyOCR corre sobre la imagen completa**, como máximo una vez por escaneo, y
  su texto se reutiliza para todas las columnas que fallaron. Fijarlo a "solo ese
  primer texto" es imposible: EasyOCR recibe una imagen, no una frase.
- **T1.4 se implementó al final**, después de `extract.py`, porque la combinación
  de motores necesita la búsqueda.
- **Fechas:** día primero (`DD/MM/AAAA`), más `AAAA-MM-DD`.
- **RIF:** se normaliza a `J-31245678-7`. Si no se puede leer, va `None` y se avisa
  con `unreadable_rif`.

### Limitaciones conocidas

- El formato por defecto es coma de miles y punto decimal (`SCHEMAS.md` §5.4). Una
  factura venezolana escrita `116,00` **no se parsea** con el valor por defecto: el
  contador tiene que poner `#miles=. #decimal=,`. No se adivina el separador para
  no producir un número equivocado.
- Si Tesseract inserta un espacio dentro del RIF (`J-312456 78-7`), el RIF queda
  ilegible y la factura pierde la protección contra duplicados. Se avisa.

---

## 001 — Base de datos

- Esquema aplicado (`001_inicial.sql`): 5 tablas, 14 índices, `schema_migrations`.
- Pool de conexiones propio, sin `psycopg_pool`.
- `app/db/queries.py` como único lugar con SQL.
- 24 pruebas de persistencia, deduplicación, JSONB y filtros.
