# CONSTITUTION.md — App de Facturas

> Leer junto a `AGENTS.md` y `SCHEMAS.md`. El contexto del proyecto está en `AGENTS.md`. Aquí están las reglas que se aplican **siempre**.

## Stack

- Lenguaje: Python 3.12.10 estricto. Tests: pytest
- Framework / runtime: FastAPI + uvicorn en `0.0.0.0:8000`
- OCR: Tesseract nativo vía `pytesseract` y EasyOCR, idiomas `eng+spa`. **EasyOCR entra por primer texto**, solo donde Tesseract falló
- Base de datos: PostgreSQL local vía `psycopg` v3
- Salida: CSV con la biblioteca estándar (UTF-8 con BOM, se abre en Excel)

Dependencias autorizadas, y ninguna más: `fastapi`, `uvicorn`, `python-multipart`, `pydantic`, `pytesseract`, `easyocr`, `psycopg[binary]`, `Pillow`, `pillow-heif`, `opencv-python-headless`, y las transitivas que arrastren (EasyOCR exige PyTorch y numpy).

`pillow-heif` está autorizada porque el iPhone manda las fotos en HEIC y Pillow no lo abre sin ella (`SCHEMAS.md` §7).

`opencv-python-headless` está autorizada porque el preprocesado necesita quitar ruido y enderezar la imagen. Es transitiva de EasyOCR, pero se declara explícita para que el preprocesado no dependa de que EasyOCR siga instalado.

Para las pruebas se autoriza `httpx`, que es lo que exige el `TestClient` de FastAPI. **No la usa la app en producción.**

## Reglas inviolables

Si una tarea parece requerir romper una de estas reglas, **detenerse y preguntar al usuario**.

1. **Formatos existentes.** Prohibido alterar el esquema SQL, los contratos de los endpoints, el orden de las columnas del CSV y las reglas de extracción. Lo que falte se agrega al lado, nunca se modifica. Lo único flexible es `plantilla.csv`, que es del contador: sus dos textos por línea, su orden y cuántas columnas haya (`SCHEMAS.md` §4). Editar ese archivo **no** cuenta como cambiar un formato. Lo que sigue inmutable son los 4 campos de control de `SCHEMAS.md` §2 y el texto crudo de OCR.
2. **Entorno.** Todo en `.venv`, invocado como `.\.venv\Scripts\python.exe`.
3. **Secretos.** Solo en `.env`. Nunca en código, logs ni respuestas de la API.
4. **Texto crudo de OCR.** Dato interno: no aparece en el CSV ni en ningún endpoint de lectura. La fila 1 del CSV sale del **segundo texto** de cada línea de `plantilla.csv`, que escribe el contador; **nunca** de texto reconocido por el OCR, ni del primer texto.

## Workflow

Cada feature vive en `specs/NNN-slug/`, con NNN correlativo.

1. **`spec.md`** — Qué necesita el contador, con criterios de aceptación verificables, en español.
2. **`design.md`** — Contrato de cada endpoint, esquema SQL de las tablas que cambian y formato del CSV.
3. **`tasks.md`** — Checklist en orden, con lo verificable al lado.
4. **Implementación, verificación y `CHANGELOG.md`.** Una spec no se cierra sin probarse con una **imagen real de factura**, no con un texto inventado. Si el código se desvía de la spec, primero se revierte el código.
5. **Antes de empezar:** si no estás seguro al 80%, pregunta. Una tarea no trivial empieza con un plan en `specs/NNN-slug/spec.md` y espera OK.

Al terminar, reporta lo que cambiaste y lo que quedó sin hacer, sin adornos.

## Convenciones

- **Los endpoints no llevan lógica de negocio:** validan, delegan y traducen errores. El parseo vive en `app/ocr/`, las queries en `app/db/`, el CSV en `app/export/`.
- **Todo anotado:** sin `any`, sin funciones sin tipar, cada parámetro y retorno con su tipo. **Validar toda entrada antes de usarla:** Pydantic en los endpoints, y tipo y content-type del archivo en la carga.
- **Docstrings** en toda función pública, explicando qué hace. Sin comentarios de relleno: uno solo se justifica si explica *por qué*.
- **Identificadores en inglés;** mensajes al usuario y documentación en español.
- **El CSV se genera en un solo punto** (`app/export/`), que escribe la fila 1 con los **segundos textos** de `plantilla.csv`. El archivo solo se lee, con la excepción única de L46.
- **Cada línea de `plantilla.csv` tiene dos textos separados por `=`.** El primer texto es lo que se busca en la foto; el segundo texto es lo que titula la columna en el Excel. El `=` **solo marca dónde termina el primer texto**, y se parte por el primero. Segundo texto vacío = se usa el primer texto. Primer texto repetido = error (`SCHEMAS.md` §1, §4.1).
- **`plantilla.csv` se entrega vacío y la app solo lo escribe una vez.** **Excepción única y acotada:** si el archivo está **completamente vacío**, la app escribe la línea de formato con su mensaje, para que el contador sepa qué acepta el archivo. Después de eso **nunca más lo toca**: ni ejemplos, ni comentarios, ni una línea de ayuda. Los referentes viven en `COLUMNAS_POR_DEFECTO`, en el código, y se usan **solo** si el contador no escribió ninguna línea. Si escribió una, la suya es la única que existe: **prohibido** agregarle columnas, completarle las que faltan, avisarle que le faltan, o sugerirlas (`SCHEMAS.md` §4.2, §4.3).
- **Cualquier línea de `plantilla.csv` que empiece con `#` es configuración**, y no produce columna. Acepta `miles`, `decimal` y `acentos`. Por defecto `miles=,` y `decimal=.` Una línea de configuración mal escrita **no es error**: la app usa el valor por defecto y sigue (`SCHEMAS.md` §4.4).
- **El emparejamiento valor-columna es por primer texto, no por posición.** Por eso el contador puede renombrar, reordenar o agregar columnas después de escanear. Es la razón por la que el primer texto se guarda en el `JSONB` de `invoices` (`SCHEMAS.md` §1.3).
- **El primer texto nunca llega al Excel.** Si no coincide, la columna sale vacía y el aviso nombra el par completo (`SCHEMAS.md` §1.2).
- **Los avisos van aparte, en `avisos.csv`.** Nunca en el Excel del contador: ahí no puede ir ni el texto reconocido ni el estado de revisión (`SCHEMAS.md` §6.1).
- **Una columna que no encuentra nada queda vacía.** Nunca se inventa un valor ni se adivina entre varias coincidencias (`SCHEMAS.md` §5.3).
- **El signo de un importe se queda tal cual.** La app no le quita el menos a una retención ni lo pone en ninguna parte (`SCHEMAS.md` §4.1).
- **La app no cuadra totales.** No existe `unbalanced_total`: con columnas arbitrarias no puede saber cuál es la base y cuál el IVA (`SCHEMAS.md` §3.3).
- **Preprocesado de imagen: el orden es fijo y no se negociable.** Gris → ruido → inclinación → umbral → escalado. **Umbralizar antes de quitar el ruido y de enderezar deja los bordes de las letras rotos**, y eso destruye justo el texto que el OCR necesita leer. Los pasos se agregan al lado, nunca en medio.
- **Números:** `float` en Python y `DOUBLE PRECISION` en PostgreSQL, para que los importes enteros se conserven exactos. Redondeo a 2 decimales solo al exportar.
- **Pruebas** en `tests/`, junto a lo que prueban, con `fixtures` de pytest, en entornos aislados: sin datos reales ni Tesseract real.

## Checklist de calidad

- [ ] ¿Arranca y responde en `/health`, con una imagen real de factura?
- [ ] ¿Los importes se conservan exactos y llegan normalizados al CSV?
- [ ] ¿No cambié ningún formato existente, ni introduje dependencias fuera de la lista? Editar `plantilla.csv` no cuenta.
- [ ] ¿Un par sin coincidencia dejó la columna **vacía**, y no un valor inventado?
- [ ] ¿La fila 1 del CSV lleva **solo los segundos textos**, y no los primeros?
- [ ] ¿`plantilla.csv` quedó como el contador lo dejó, con su línea de formato, y los referentes están en el código?
- [ ] ¿El contador tiene el control real: no le agregué columnas, no le completé las suyas, no le sugerí nada?
- [ ] ¿El CSV se **abrió en Excel** sin romper acentos ni la `ñ`, y los números se leen como número?
- [ ] ¿El emparejamiento es por primer texto: renombré una columna y el valor no se corrió?
- [ ] ¿Los avisos salieron en `avisos.csv` y **no** en el Excel de facturas?
- [ ] ¿El texto crudo de OCR sigue sin salir por la API ni por el CSV?
- [ ] ¿Pasan `pytest` y `ruff check .`?

**Detenerse y preguntar**, sin adivinar, si: la tarea pide una dependencia fuera de la lista; pide cambiar un formato existente en vez de agregar al lado; pide lógica de negocio en un endpoint; expone texto crudo de OCR al usuario; adivina un valor cuando un primer texto no encontró nada; escribe el primer texto en el Excel en vez del segundo texto; escribe en `plantilla.csv` que no sea la línea de formato en un archivo vacío; empareja valores por posición en vez de por primer texto; le agrega, completa o sugiere columnas al contador; pone un motivo o un estado de revisión en el Excel; cierra una spec sin imagen real.