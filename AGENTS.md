# App de Facturas

App local que recibe fotos de facturas desde un iPhone, las procesa con Tesseract
y EasyOCR, guarda los datos estructurados en PostgreSQL y exporta un CSV que el
contador abre y edita en Excel. Además, el valor extraído de la imagen se envía en
tiempo real al Excel cuya ruta exacta se indica en `plantilla.csv`.

El usuario final son contadores, en su mayoría no técnicos, que procesan lotes de
facturas al día. Región inicial: Venezuela. **El contador es el actor final:** la
app produce el CSV y ahí termina, no reimporta ni valida lo que él escriba
después. Todo corre en la PC local, sin servicios externos.

**La app no lleva autenticación**, pero el servidor escucha en `0.0.0.0`: toda la red
Wi-Fi puede exportar los datos fiscales. Que la red sea privada y con clave.

## Comandos

- `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
  — arranca el servidor en local
- `.\.venv\Scripts\python.exe -m pytest`
  — ejecuta los tests (deben pasar antes de cada commit)
- `.\.venv\Scripts\python.exe -m ruff check .`
  — revisa el estilo (antes de cada PR)

## Estructura del proyecto

- `app/` — código de la aplicación
- `app/api/` — routers de FastAPI; un archivo por recurso
- `app/ocr/` — preprocesado de imagen, Tesseract, EasyOCR, búsqueda de los primeros
  textos del contador y parseo a campos
- `app/db/` — conexión psycopg, pool, migraciones y queries
- `app/export/` — lectura de `plantilla.csv`, emparejamiento por primer texto,
  generación del CSV y escritura en tiempo real del Excel de salida
- `app/models/` — dataclasses/TypedDict; Pydantic solo en request/response
- `specs/` — artefactos SDD por feature: spec.md, design.md, tasks.md
- `tests/` — suite pytest, con `mocks` de imágenes y texto OCR
**No hay carpeta `docs/`.** No existe material de consulta suelto: todo lo que hay son
reglas, contratos y specs.

## No hagas

- No inventes datos de negocio: los campos y sus nombres salen de
  `SCHEMAS.md`. Si no está, pregunta.
- No acumules varias tareas en un solo cambio grande. Una a la vez.


## Roles

- **Backend y SQL** (Agente 1) — endpoints, esquema, migraciones, exportación
  CSV. No toca OCR: consume el resultado del Agente 2.
- **Visión y OCR** (Agente 2) — limpieza de imagen, Tesseract, parseo a objeto
  estructurado. No escribe en PostgreSQL: entrega el objeto al Agente 1.
- **QA** (Agente 3) — pytest, validación de contratos de API y del CSV. No
  implementa funcionalidad: si encuentra un defecto, lo reporta con la spec y
  el criterio de aceptación que incumple.

## Documentación

- `CONSTITUTION.md` — stack, reglas inquebrantables, workflow, convenciones,
  checklist de calidad. **Leer antes de escribir código.**
- `SCHEMAS.md` — extracción, `plantilla.csv`, campos de control, tablas SQL,
  formato del CSV, contrato de API. **Consultar antes de tocar la base o el CSV.**
