# Design 003 — API de captura

**Spec:** [`spec.md`](./spec.md) · **Design:** [`001-base-datos`](../001-base-datos/design.md) para el SQL

> Las cinco decisiones (A-01 a A-05) están resueltas. No hay `[PENDIENTE]`.
> **La API no lleva autenticación**, por decisión consciente (A-02).

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `app/main.py` | Instancia FastAPI, CORS, `/health`, incluye los routers |
| `app/api/scan.py` | `POST /api/v1/invoices/scan` |
| `app/api/invoices.py` | `GET /invoices`, `GET /invoices/{id}` |
| `app/models/api.py` | Pydantic de request y response |

Los endpoints **no** llevan lógica de negocio: validan, delegan a la 002 y a las
queries de la 001, y traducen excepciones a códigos HTTP.

## Contrato de API

### `GET /health`

```json
{ "status": "ok", "database": "connected" }
```

Responde `200` siempre. Si la base no responde, `"database": "disconnected"` y
queda en `200`: es un diagnóstico, no un fallo del servicio. → CA-23

### `POST /api/v1/invoices/scan`

`multipart/form-data`, campo `file`. **Sin autenticación** (A-02).

| Código | Cuándo | Cuerpo |
|---|---|---|
| `201` | Factura creada | `{ "invoice_id": 1, "review_status": "ok", "warnings": [] }` |
| `409` | Ya existía | `{ "invoice_id": 1, "review_status": "ok", "warnings": [], "detail": "Esta factura ya estaba registrada." }` |
| `413` | Archivo mayor a 10 MB | `{ "detail": "El archivo supera los 10 MB." }` |
| `415` | Content-type no es imagen | `{ "detail": "El archivo debe ser una imagen (JPEG, PNG o HEIC)." }` |
| `422` | Imagen corrupta o ilegible | `{ "detail": "No se pudo leer la imagen." }` |
| `503` | RapidOCR no disponible | `{ "detail": "No hay ningún motor de OCR disponible." }` |

**El `409` lleva el `invoice_id` de la factura que ya existía.** No es solo un error:
es la forma de que el contador vea que su doble toque no creó un segundo registro, y
que la factura está ahí. Con el doble toque del Atajo, es el caso más probable de la
app, así que no puede ser un error opaco.

**Content-type aceptados:** `image/jpeg`, `image/png`, `image/heic`. Se registra el
plugin de `pillow-heif` al arrancar (`PIL.Image.register_mime` y el codecs de HEIF),
para que Pillow abra los `.heic` igual que los `.jpg`.

**Ninguna respuesta incluye `raw_text`, la ruta de la imagen ni la confianza
detallada** (`CONSTITUTION.md` regla 4). → CA-69

**La respuesta del escaneo sí incluye los avisos** de `SCHEMAS.md` §3.3. Son
avisos cortos y legibles, **no el texto reconocido**.

Cada aviso nombra **las dos mitades del par**, porque el Excel del contador no
muestra el primer texto (`SCHEMAS.md` §1.2):

```json
{
  "invoice_id": 1,
  "review_status": "needs_review",
  "warnings": ["no_match:Total a pagar (columna \"Base imponible\")"]
}
```

Los avisos van **también** en `avisos.csv` al exportar, porque en un lote se pierden
al cerrar la app (`SCHEMAS.md` §6.1).

### `GET /api/v1/invoices`

Query opcionales: `supplier_rif`, `issue_date`, `review_status`, `limit`,
`offset`. Respuesta `200` con lista paginada.

### `GET /api/v1/invoices/{id}`

`200` con la factura, sus `invoice_items` y sus `taxes`. `404` si no existe. Sin
texto crudo. Los importes vuelven exactos, porque no hay redondeo en el camino de
lectura. → CA-70

## Guardas obligatorias

**Ninguna excepción de la 002 o la base llega al cliente.** Cada una se traduce:

| Origen | Se traduce a |
|---|---|
| `UnidentifiedImageError` de Pillow | `422` |
| Content-type no en la lista | `415` |
| Archivo mayor a 10 MB | `413` |
| Violación de `dedupe_key` | `409` con el `invoice_id` existente |
| RapidOCR no está instalado o no carga sus modelos | `503` |

El mensaje va en español y **nunca** incluye ruta del sistema, SQL ni excepción
cruda. → CA-04

## Concurrencia

**Paralelo, con pool de 5.** La app es de un solo usuario, así que la concurrencia
real es el doble toque del Atajo.

La carrera la resuelve el propio `INSERT` de la 001, con
`ON CONFLICT (dedupe_key) DO NOTHING`: si dos peticiones de la misma foto llegan
juntas, la segunda recibe `0` filas insertadas y la 003 responde `409` con el
`invoice_id` de la primera. **No hace falta un lock por `dedupe_key`**, porque el
`UNIQUE` es la garantía.

## Imágenes y `ocr_runs`

La 003 guarda **las dos imágenes**: la original tal como llegó y la convertida, en
`original_path` y `converted_path`. La del OCR es la convertida.

`raw_text` **solo se guarda si hizo falta**:

```
if hay no_match, ambiguous o low_confidence:
    raw_text = resultado.raw_text
else:
    raw_text = None
```

Es la regla que hace que `raw_text` sea útil: si todo salió bien no sirve de nada y
ocupa espacio, y si algo salió mal es lo único que explica por qué. → CA-58, CA-59

El motor que leyó la foto va en `engine_version`. RapidOCR es el único motor, así
que los valores del `JSONB` de `invoices` no guardan `engine` (D-01 de la 001).

## Configuración

| Variable | Para qué | Estado |
|---|---|---|
| `MAX_UPLOAD_MB` | Límite de tamaño | `10` |
| `OCR_CONFIDENCE_THRESHOLD` | Umbral de confianza de la 002 | `60` |
| `IMAGE_DIR` | Carpeta de imágenes originales y convertidas | `imagenes/` |

**No hay `API_TOKEN`.** No hay autenticación (A-02).