# Tasks 003 — API de captura

**Spec:** [`spec.md`](./spec.md) · **Design:** [`design.md`](./design.md)

> Checklist en orden. Cada tarea dice cómo se comprueba. **Una tarea a la vez**
> (`AGENTS.md` § No hagas).
>
> Los endpoints no llevan lógica de negocio: validan, delegan y traducen errores.

**Las cinco decisiones (A-01 a A-05) están resueltas** y escritas en `design.md`.
**No hay autenticación**, por decisión consciente: el servidor escucha en
`0.0.0.0` y toda la red Wi-Fi puede exportar datos fiscales.

**Precondición:** requiere la 001 (queries) y la 002 (motor). T2.1 puede empezar
antes, es andamiaje.

---

## Fase 1 — Andamiaje

- [X] **T1.1** `app/main.py`: instancia FastAPI, CORS limitado a la red local,
      y la inclusión de los routers.
      *Verificable:* el servidor arranca en `0.0.0.0:8000` sin errores.
- [X] **T1.2** `app/models/api.py` con los modelos Pydantic de request y
      response. **`ScanResponse` no tiene campo para texto crudo, e incluye la
      lista de avisos de `SCHEMAS.md` §3.3.**
      *Verificable:* el modelo no tiene `raw_text` ni `image_path`, y sí tiene
      `warnings`.
- [X] **T1.3** `GET /health` que reporta estado del servicio y de la conexión a
      PostgreSQL.
      *Verificable:* responde `200` en ambos casos; con la base caída dice
      `"database": "disconnected"`. → CA-23

---

## Fase 2 — Captura

- [X] **T2.1** `POST /api/v1/invoices/scan`: valida content-type, tamaño (10 MB), y
      que Pillow pueda abrir la imagen. Solo valida y delega.
      *Verificable:* `415` con un PDF, `413` con un archivo enorme, `422` con una
      imagen corrupta, y **ninguno de los tres toca la base**. → CA-02, CA-03, CA-04
- [X] **T2.2** **HEIC**: registrar el plugin de `pillow-heif` al arrancar, aceptar
      `image/heic`, y guardar **las dos** imágenes en `original_path` y
      `converted_path`. La que va al OCR es la convertida.
      *Verificable:* una foto de iPhone en HEIC responde `201` y quedan las dos
      rutas. → CA-57
- [X] **T2.3** Llama a la 002, persiste con las queries de la 001, y escribe la
      fila de `ocr_runs`.
      *Verificable:* responde `201` con `invoice_id` y `review_status`.
- [X] **T2.4** Traduce cada excepción a su código HTTP, con la tabla de
      `design.md` § Guardas obligatorias.
      *Verificable:* un mensaje no contiene ruta del sistema, SQL ni excepción
      cruda.
- [X] **T2.5** `ON CONFLICT (dedupe_key) DO NOTHING` en el INSERT de la 001.
      *Verificable:* mandar la misma foto dos veces **nunca** deja dos filas en
      `invoices`, y la segunda responde `409` con el `invoice_id` de la primera.
      → CA-68
- [X] **T2.6** Sin RapidOCR disponible, responde `503` con un mensaje claro.
      *Verificable:* si el motor no carga, no responde `500`. → CA-22
- [X] **T2.7** `raw_text` **solo si hizo falta**: si hay `no_match`, `ambiguous` o
      `low_confidence`, se guarda; si no, queda en `NULL`.
      *Verificable:* con todo en verde, `ocr_runs.raw_text` es `NULL`. Con una
      columna vacía, está lleno. → CA-58, CA-59

---

## Fase 3 — Consulta

- [X] **T3.1** `GET /api/v1/invoices` con filtros por `supplier_rif`,
      `issue_date` y `review_status`, más `limit` y `offset`.
      *Verificable:* los tres filtros devuelven solo lo que corresponde.
- [X] **T3.2** `GET /api/v1/invoices/{id}` con items y taxes, `404` si no existe.
      *Verificable:* la respuesta no tiene `raw_text`, y un importe entero se
      devuelve exacto. → CA-69, CA-70

---

## Fase 4 — Pruebas

- [X] **T4.1** `tests/test_api.py` con `TestClient`, motor y base mockeados: las
      cuatro rutas y los seis códigos de error.
      *Verificable:* pasa **sin base real ni RapidOCR real**. → CA-01, CA-02,
      CA-03, CA-04, CA-23
- [X] **T4.2** Test con una **foto en HEIC**.
      *Verificable:* responde `201`, y quedan las dos rutas en `ocr_runs`.
      → CA-57
- [X] **T4.3** Test de concurrencia: dos peticiones de la misma foto simultáneas.
      *Verificable:* queda una sola fila en `invoices`, y la segunda es `409`.
      → CA-68
- [X] **T4.4** Test que recorra **todas** las respuestas de la API buscando
      `raw_text`, `image_path` y rutas del sistema.
      *Verificable:* el test falla si alguien agrega cualquiera de esos campos.
      → CA-69
- [X] **T4.5** Test de que **ninguna respuesta exige token**: las cuatro rutas
      funcionan sin cabecera `Authorization`.
      *Verificable:* pasa. Confirma que A-02 quedó aplicado.
- [X] **T4.6** `ruff check .` sin hallazgos y `pytest` en verde.
- [ ] **T4.7** Pruebo manual con el Atajo real del iPhone sobre la red Wi-Fi.
      *Verificable:* llega la petición y la respuesta. Si no llega, casi siempre es
      el firewall de Windows bloqueando el puerto 8000: *Configuración de Windows →
      Seguridad de Windows → Firewall y protección de la red → Permitir una
      aplicación a través del Firewall*, marcando Python en redes privadas. → CA-21
