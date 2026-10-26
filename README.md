# App de Facturas

App **local** para Windows que recibe fotos de facturas desde un iPhone, las lee
con OCR, guarda los datos en PostgreSQL y exporta un CSV que el contador abre y
edita en Excel.

Todo corre en la PC del contador: no hay servicios externos, no hay nube y no hay
autenticación. El servidor escucha en la red Wi-Fi, así que **la red debe ser
privada y con clave**.

---

## Cómo funciona

```
iPhone (Atajo)
   │  POST /api/v1/invoices/scan  (multipart, campo "file")
   ▼
FastAPI ──► 1. valida tipo, tamaño y que la imagen se abra
   │        2. guarda el original y una copia JPEG
   │        3. preprocesa y lee con OCR
   │        4. extrae los valores pedidos
   ▼
PostgreSQL ──► invoices, ocr_runs
   │
   ▼
GET /api/v1/export/invoices.csv  ──►  Excel del contador
GET /api/v1/export/avisos.csv    ──►  diagnóstico de columnas vacías
```

### 1. Captura

El iPhone manda la foto con un Atajo al endpoint de escaneo. Se aceptan
`image/jpeg`, `image/png` y `image/heic` (lo que manda el iPhone por defecto).
Las fotos HEIC se convierten con `pillow-heif`.

La app guarda **dos imágenes**: la original tal como llegó y una copia JPEG
orientada según los datos EXIF, que es la que va al OCR.

### 2. Lectura

El preprocesado sigue un orden fijo: gris → quitar ruido → enderezar →
umbralizar → escalar. Umbralizar antes de quitar el ruido rompe los bordes de las
letras, así que el orden no se cambia.

Después:

1. **RapidOCR** lee la imagen con sus modelos PP-OCRv6 locales en español.
2. La app prueba varias variantes de la misma foto y se queda con la lectura que
   encuentra más valores, en la línea correcta y con mayor confianza.
3. Si RapidOCR no está instalado o no puede cargar sus modelos, el escaneo
   responde `503`.

RapidOCR y sus modelos vienen incluidos en el paquete: no hay que instalar un OCR
nativo ni descargar pesos por separado.

### 3. Extracción

La app busca en el texto reconocido el **primer texto** de cada línea de
`plantilla.csv`. Las reglas son estrictas:

- Coincidencia completa, sin distinguir mayúsculas.
- Sin distinguir tildes, salvo que el archivo diga `#acentos=0`.
- Nunca coincidencias parciales.
- Si hay **varias** coincidencias, la columna queda vacía y se avisa (`ambiguous`).
- Si no hay ninguna, la columna queda vacía y se avisa (`no_match`).
- **Nunca se inventa un valor ni se adivina entre varios.**

El valor que sigue al primer texto se normaliza a número. Si no hay ningún número,
se guarda el primer texto leído tal cual; así funcionan las columnas de texto que
el contador pidió explícitamente, como `RIF` o `Moneda`.

La app **no busca RIF, fecha, serie ni número de factura por su cuenta**. Solo
busca las columnas que estén en `plantilla.csv`. Las fechas no se convierten: si el
contador pide una, se guarda el texto tal como se leyó.

### 4. Sin deduplicación

Cada foto crea una fila. Si la misma foto se envía dos veces, se registra dos
veces.

### 5. Exportación

El CSV de facturas **no se arma por posición**: cada valor guardado recuerda el
primer texto que lo produjo, y al exportar se busca la columna cuyo primer texto
coincide. Por eso el contador puede renombrar, reordenar o borrar líneas de
`plantilla.csv` después de escanear, y los números siguen en su columna.

```csv
Base imponible,Monto del IVA,Total a pagar
100.00,16.00,116.00
```

- Una sola fila de cabecera, con los **segundos textos** del archivo.
- Una fila por factura, incluidas las que quedaron en revisión.
- Codificación `utf-8-sig` (BOM) para que Excel respete acentos y `ñ`.
- Separador coma. Los valores vacíos salen como celda vacía.
- Redondeo a 2 decimales solo al escribir.
- El primer texto, el texto crudo del OCR, las rutas de imagen, la confianza y el
  estado de revisión **nunca** aparecen en el CSV.

Los avisos van en un archivo aparte, `avisos.csv`, que sale **siempre**, aunque
solo tenga la cabecera:

```csv
invoice_id,frase,columna,motivo
142,Total a pagar,Base imponible,no_match
142,IVA,Monto del IVA,low_confidence
```

---

## Requisitos

- Windows con Python **3.12**.
- PostgreSQL local (en esta máquina, puerto **5433**).
- PC e iPhone en la misma red Wi-Fi privada.

---

## Instalación

### 1. Entorno y dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn python-multipart pydantic rapidocr onnxruntime numpy "psycopg[binary]" Pillow pillow-heif opencv-python-headless
```

Para los tests hace falta además `httpx` (no lo usa la app en producción):

```powershell
.\.venv\Scripts\python.exe -m pip install httpx
```

La lista de dependencias autorizadas está en `CONSTITUTION.md`. RapidOCR y ONNX
Runtime son las dependencias nuevas del motor OCR.

### 2. Base de datos

Crear la base y el usuario (una sola vez), por ejemplo:

```sql
CREATE ROLE facturas_app LOGIN PASSWORD 'CAMBIAR';
CREATE DATABASE facturas OWNER facturas_app;
```

### 3. Configuración

```powershell
Copy-Item .env.example .env
```

Completar `.env` con los valores reales. Las variables principales:

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | Conexión de la app a PostgreSQL |
| `DB_POOL_SIZE` | Conexiones del pool (por defecto 5) |
| `OCR_CONFIDENCE_THRESHOLD` | Confianza mínima (0-100); por debajo, queda en revisión |
| `MAX_UPLOAD_MB` | Tamaño máximo de la foto |
| `IMAGE_DIR` | Carpeta de imágenes originales y convertidas |
| `TEST_ADMIN_DATABASE_URL` | Solo tests: usuario con `CREATE DATABASE` |

Los secretos viven **solo** en `.env`, que no se versiona.

### 4. Aplicar el esquema

```powershell
.\.venv\Scripts\python.exe -c "from app.db.queries import aplicar_migraciones; aplicar_migraciones()"
```

Aplica en orden los archivos de `app/db/migrations/` que falten. Los ya aplicados
no se reescriben nunca.

### 5. Arrancar

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Comprobar en el navegador de la PC:

```
http://127.0.0.1:8000/health
```

```json
{"status": "ok", "database": "connected"}
```

Responde `200` aunque la base esté caída; en ese caso `database` dice
`"disconnected"`.

---

## Configurar el Atajo del iPhone

1. Averiguar la IP de la PC en la Wi-Fi con `ipconfig` (por ejemplo
   `192.168.1.50`).
2. En la app **Atajos**, crear uno nuevo con:
   - **Tomar foto** (o elegir una foto existente).
   - **Obtener contenido de URL**:
     - URL: `http://192.168.1.50:8000/api/v1/invoices/scan`
     - Método: `POST`
     - Cuerpo de la petición: `Formulario`
     - Campo de formulario: `file` con la foto.
3. Ejecutarlo desde el iPhone, con la PC encendida y el servidor corriendo.

Si la petición no llega, casi siempre es el **firewall de Windows** bloqueando el
puerto 8000: *Configuración de Windows → Seguridad de Windows → Firewall y
protección de la red → Permitir una aplicación a través del Firewall*, marcando
Python en redes privadas.

---

## `plantilla.csv`: el archivo del contador

Es el único archivo que el contador edita. Cada línea tiene **dos textos
separados por `=`**:

```
primer texto = segundo texto
```

- **Primer texto:** lo que se busca en la foto. **No aparece en el Excel.**
- **Segundo texto:** el título de la columna en el Excel.
- Se parte por el **primer** `=`.
- Si el segundo texto queda vacío, se usa el primero como título (`Moneda =`).
- Un primero texto repetido es **error** y detiene el escaneo.
- Las líneas que empiezan con `#` son configuración y no producen columna.

Ejemplo:

```
RIF = RIF del proveedor
Base = Base imponible
IVA = Monto del IVA
Total = Total a pagar
```

El archivo se entrega **vacío**. Si está completamente vacío, la app le escribe
una sola vez un mensaje con el formato que acepta; después nunca más lo toca. Si
no hay al menos una línea de columna, la app se detiene con un error: **no hay
columnas por defecto**.

### Formato de números

Por defecto: **coma para miles** y **punto para decimales** (`1,234.56`). Se
cambia con líneas de configuración:

```
#miles=. #decimal=, #acentos=1
```

| Opción | Valores | Por defecto |
|---|---|---|
| `miles` | Un carácter | `,` |
| `decimal` | Un carácter | `.` |
| `acentos` | `1` ignora tildes, `0` no | `1` |

Una línea de configuración mal escrita no es error: se usa el valor por defecto.
La app no adivina el separador: si las facturas usan coma decimal, hay que poner
`#miles=. #decimal=,`.

---

## API

Sin autenticación. Prefijo `/api/v1`.

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/health` | Estado del servicio y de PostgreSQL |
| `POST` | `/api/v1/invoices/scan` | Recibe la foto, la procesa y la guarda |
| `GET` | `/api/v1/invoices` | Lista paginada de facturas |
| `GET` | `/api/v1/invoices/{id}` | Detalle con líneas e impuestos |
| `GET` | `/api/v1/export/invoices.csv` | CSV para Excel |
| `GET` | `/api/v1/export/avisos.csv` | CSV de avisos |

**Escaneo:** `multipart/form-data`, campo `file`.

```json
{
  "invoice_id": 1,
  "review_status": "needs_review",
  "warnings": ["no_match:Total a pagar (columna \"Base imponible\")"]
}
```

**Códigos de error:**

| Código | Cuándo |
|---|---|
| `413` | El archivo supera el tamaño máximo |
| `415` | El contenido no es una imagen aceptada |
| `422` | La imagen está corrupta o no se puede abrir |
| `503` | No hay ningún motor de OCR disponible |

**Lista:** filtros `review_status`, `limit` y `offset`.

**Exportación:** filtro `review_status`, aplicado en el `SELECT`. Las dos
respuestas son `text/csv; charset=utf-8`.

---

## Base de datos

Dos tablas (`app/db/migrations/001_inicial.sql`):

| Tabla | Contenido |
|---|---|
| `invoices` | Estado de revisión y valores del contador en `JSONB` |
| `ocr_runs` | Imágenes y texto crudo, solo para depurar |

Cada valor del `JSONB` guarda `frase`, `encabezado`, `value` y `confidence`. El
motor no se guarda dentro de `values`: `ocr_runs.engine_version` conserva el motor
principal como dato interno. El texto crudo del OCR **solo** se guarda si hubo
`no_match`, `ambiguous` o `low_confidence`; si todo salió bien, queda en `NULL`.

---

## Tests y calidad

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Los tests de base de datos crean y destruyen una base `facturas_test_<hex>`; no
tocan la base real. Para eso necesitan `TEST_ADMIN_DATABASE_URL` en `.env` con un
usuario que tenga `CREATE DATABASE`.

Los tests de OCR no usan RapidOCR real: trabajan con texto simulado.

---

## Estructura

```
app/
  main.py              FastAPI, CORS, /health, routers
  config.py            lectura de .env
  api/                 endpoints (scan, invoices, export)
  models/              dataclasses de extracción y modelos de la API
  ocr/                 preprocesado, RapidOCR, extracción, pipeline
  db/                  pool, queries y migraciones
  export/              plantilla.csv, CSV de facturas y avisos.csv
specs/                 spec, design y tasks de cada feature
tests/                 pytest, con base y OCR aislados
plantilla.csv          el archivo del contador
CONSTITUTION.md        reglas del proyecto
SCHEMAS.md             contratos de datos y de la API
```

---

## Estado y limitaciones

- **La app no cuadra totales** ni valida que la suma de las columnas cierre: con
  columnas arbitrarias no puede saber cuál es la base y cuál el IVA.
- **Sin deduplicación:** si la misma foto se envía dos veces, se registra dos veces.
- **Fotos reales pendientes:** las specs 002, 003 y 004 todavía no se cierran
  porque faltan las pruebas con fotos reales, con el Atajo del iPhone y con el CSV
  abierto en Excel.
- **Sin autenticación:** cualquiera en la misma Wi-Fi puede consultar y exportar
  los datos fiscales. Usar una red privada y con clave.
