# Spec 003 — API de captura

**Estado:** borrador · **Feature:** `003-api-captura` · **Rol:** Agente 1

El contexto del proyecto está en `AGENTS.md`. Los contratos de datos salen de
`SCHEMAS.md`.

## Necesidad

Como contador, quiero mandar una foto desde el iPhone con un Atajo y que la app me
conteste qué pasó, sin tener que abrir una pantalla. Y quiero que el error venga
en un mensaje que entienda, no en una traza técnica.

## Alcance

El endpoint de captura, el de estado del servicio, y los endpoints de consulta.
Orquesta a la 002 y persiste con las queries de la 001.

**Los endpoints no llevan lógica de negocio.** Validan, delegan y traducen errores
(`CONSTITUTION.md` § Convenciones).

## Criterios de aceptación

- **CA-01.** Dado un Atajo en el iPhone, cuando envío una foto a
  `POST /api/v1/invoices/scan`, entonces responde `201` con el `invoice_id`, el
  `review_status` y los avisos de `SCHEMAS.md` §3.3. Cada aviso nombra **el primer
  texto y la columna**, porque el Excel no muestra el primer texto. → CA-43
- **CA-02.** Dado un archivo que no es imagen, cuando lo envío, entonces responde
  `415` y no toca la base.
- **CA-03.** Dado un archivo mayor al límite, cuando lo envío, entonces responde
  `413` y no toca la base.
- **CA-04.** Dado un archivo corrupto que ni Pillow puede abrir, cuando lo envío,
  entonces responde `422` con un mensaje en español, sin filtrar rutas del
  sistema.
- **CA-68.** Dada una factura ya escaneada, cuando mando la misma foto otra vez,
  entonces nunca se crea un segundo registro contable.
- **CA-69.** Dada una factura persistida, cuando la consulto por `invoice_id`,
  entonces devuelve el detalle con sus items, **sin el texto crudo**.
- **CA-70.** Dada cualquier factura guardada, cuando la consulto, entonces los
  importes conservan su valor exacto.
- **CA-21.** Dado el servidor arrancado en `0.0.0.0:8000`, cuando el iPhone manda
  una foto por Wi-Fi, entonces la petición llega.
- **CA-22.** Dado el servidor sin los pesos de EasyOCR descargados, cuando
  escaneo, entonces avisa y sigue con Tesseract solamente, sin caerse.
- **CA-23.** Dado el servicio arrancado, cuando consulto `GET /health`, entonces
  responde el estado del servicio y el de la conexión a PostgreSQL.
- **CA-43.** Dado un escaneo donde un primer texto no encontró nada, cuando leo la
  respuesta, entonces el aviso dice **qué se buscó y en qué columna va**:
  `no_match:Total a pagar (columna "Base imponible")`.
- **CA-49.** Como contador, cuando escaneo **sin haber escrito nada** en
  `plantilla.csv`, entonces responde `201` con la factura creada y **ningún aviso
  sobre la plantilla**. Las columnas por defecto son internas: no me las anuncia ni
  me sugiere escribirlas.
- **CA-50.** Como contador, cuando escaneo con una sola línea escrita en
  `plantilla.csv`, entonces la factura guarda **una sola columna**. Lo que no
  escribí, no existe, y no se me avisa de que faltó.
- **CA-57.** Como contador, cuando mando una foto **en HEIC** desde el iPhone,
  entonces responde `201`. La app la convierte con `pillow-heif`, guarda **las dos
  imágenes** y escanea la convertida.
- **CA-58.** Como contador, cuando mando una foto y **todos los valores salieron
  bien**, entonces `ocr_runs.raw_text` queda en `NULL`. No se guarda el texto
  reconocido.
- **CA-59.** Como contador, cuando mando una foto y **algún valor salió dudoso o no
  coincidió**, entonces `ocr_runs.raw_text` guarda el texto reconocido, para poder
  depurar por qué.

## Fuera de alcance

- **La lógica de OCR.** Eso es la 002.
- **El SQL.** Eso es la 001.
- **El CSV.** Eso es la 004.
- **La plantilla de pares.** Eso es la 004, y se edita en `plantilla.csv`, no por
  API.
- **CORS abierto a internet.** Es una app local; el Atajo viene de la red Wi-Fi.

## Decisiones tomadas

| # | Decisión | Por qué |
|---|---|---|
| **A-01** | Ante un duplicado responde **`409`** con el `invoice_id` de la factura que ya existía y sus avisos | Con un Atajo el botón se puede pulsar dos veces. Un `409` le dice al contador "ya la tenía" sin meter un registro contable nuevo, y `409` no es un error de red, así que el Atajo no lo reporta como fallo |
| **A-02** | **Sin autenticación** | Es una app local de un solo usuario. Pero el servidor escucha en `0.0.0.0`, así que **toda** la red Wi-Fi puede exportar datos fiscales. Es una decisión consciente, y por eso `AGENTS.md` exige que el Wi-Fi sea privado |
| **A-03** | Límite de **10 MB** | Una foto de iPhone ronda 2-4 MB. 10 MB deja margen sin abrir la puerta a archivos grandes |
| **A-04** | **Se acepta HEIC** y se convierte con `pillow-heif` | Es lo que manda el iPhone. Rechazarlo sería que la app no funcione en el primer uso real |
| **A-05** | **Paralelo**, con pool de 5 y `ON CONFLICT` en el INSERT | La app es de un solo usuario, así que la concurrencia real es doble toque del Atajo. `dedupe_key` UNIQUE resuelve la carrera sin bloqueos |

Ninguna se implementa por inventada.