# Spec 001 — Base de datos

**Estado:** implementada · **Feature:** `001-base-datos` · **Rol:** Agente 1

El contexto del proyecto está en `AGENTS.md`. Los campos y las tablas salen de
`SCHEMAS.md`; este documento no los redefine.

## Necesidad

Como sistema, necesito guardar una foto de factura ya procesada con **las columnas
que pidió el contador** en `plantilla.csv`, para que la exportación pueda devolver
esos valores al Excel. La app no modela líneas de factura ni impuestos: el
contador decide qué buscar y la app solo guarda eso.

## Alcance

- El esquema de `invoices` y `ocr_runs`.
- La migración inicial.
- El pool de conexiones.
- Las queries de escritura y lectura.
- Las dos rutas de imagen: original y convertida.

## Criterios de aceptación

- **CA-12.** Dada una foto con una o varias líneas de factura, cuando se escanea,
  entonces se guarda **un registro de factura** con los valores de las columnas
  pedidas. La app **no separa las líneas** ni crea ítems. Enviar la misma foto dos
  veces crea dos registros.
- **CA-13.** Dada una factura persistida, cuando se consulta por su `id`, entonces
  devuelve `id`, `review_status`, `review_reason`, `values` y `created_at`. No
  devuelve `raw_text`, rutas de imagen, líneas ni impuestos.
- **CA-14.** Dada cualquier factura guardada, cuando se lee de la base, entonces
  los importes numéricos conservan su valor exacto. Ver `CONSTITUTION.md`
  § Convenciones.
- **CA-51.** Dada una factura escaneada, cuando leo `invoices.values`, entonces
  cada objeto trae `frase`, `encabezado`, `value` y `confidence`. **No trae
  `engine`.** El primer texto (`frase`) es la clave del emparejamiento del export.
- **CA-52.** Dada una columna de `plantilla.csv` que no encontró su primer texto,
  cuando se guarda la factura, entonces se guarda igual, con `value` en `NULL`,
  `review_status` en `needs_review` y el motivo `no_match`/`ambiguous`.
- **CA-53.** Dada una foto en HEIC, cuando se guarda, entonces quedan guardadas
  **las dos** rutas: la original y la convertida.

### Para qué existen `review_status` y `review_reason`

Son datos de revisión, no campos de negocio:

- `review_status` dice si todos los valores pedidos encontraron su texto (`ok`) o
  si algo necesita atención (`needs_review`). Permite filtrar la lista.
- `review_reason` dice **qué columna** falló y por qué (`no_match`, `ambiguous`,
  `low_confidence`). Es la fuente de `avisos.csv`.

Se exponen en la API para que el contador vea el estado, pero **nunca se exportan
al Excel**.

## Fuera de alcance

- **Disparar el OCR.** Eso es la 002.
- **Servir las facturas por HTTP.** Eso es la 003.
- **Generar el CSV.** Eso es la 004.
- **La plantilla de pares.** Vive en `plantilla.csv`, no en una tabla.
- **Modelar líneas, impuestos o perfiles por país.** La app no los necesita.
- **Deduplicar facturas.** Cada foto crea su propio registro.
- **Migraciones posteriores a la inicial.** Se numeran aparte y nunca se
  reescriben (`CONSTITUTION.md` regla 1).

## Decisiones tomadas

| # | Decisión | Resultado |
|---|---|---|
| **D-00** | ¿Cómo se guardan los valores que pidió el contador? | `values JSONB`: un objeto por valor con `frase`, `encabezado`, `value` y `confidence` |
| **D-01** | ¿Dónde se guarda el motor de OCR? | Solo en `ocr_runs.engine_version`, como dato interno. **No** se guarda dentro de `values` |
| **D-02** | ¿La imagen en disco o en la base? | En disco. `original_path` y `converted_path` |
| **D-03** | ¿`operator` se llena o queda en `NULL`? | **La columna no existe.** Sin autenticación no hay operador |

## Retención de `raw_text`

`ocr_runs.raw_text` solo se guarda cuando hubo `no_match`, `ambiguous` o
`low_confidence`; si todo salió bien, queda en `NULL`. Es dato interno y no sale
por la API ni por el CSV. No hay purga automática ni pantalla de mantenimiento.
