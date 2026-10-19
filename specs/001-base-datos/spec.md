# Spec 001 — Base de datos

**Estado:** borrador · **Feature:** `001-base-datos` · **Rol:** Agente 1

El contexto del proyecto está en `AGENTS.md`. Los campos y las tablas salen de
`SCHEMAS.md`; este documento no los redefine.

## Necesidad

Como sistema, necesito un esquema donde guardar las facturas y sus líneas sin
duplicar registros contables, para que la 002 pueda persistir lo que el OCR lea y
la 004 pueda exportarlo.

## Alcance

El esquema completo de `SCHEMAS.md` §3, la migración inicial, el pool de
conexiones, y las queries de escritura y lectura. Incluye `ocr_runs`, que es la
comunicación entre la 002 y la 003.

## Criterios de aceptación

- **CA-12.** Dada una clave `dedupe_key` ya existente, cuando se intenta insertar
  otra factura con la misma, entonces la base la rechaza. Nunca hay dos registros
  contables para la misma factura.
- **CA-13.** Dada una factura persistida, cuando se consulta por su `id`, entonces
  devuelve sus items y sus impuestos, sin el texto crudo del OCR.
- **CA-14.** Dada cualquier factura guardada, cuando se lee de la base, entonces
  los importes conservan su valor exacto. Ver `CONSTITUTION.md` § Convenciones.
- **CA-51.** Dada una factura escaneada, cuando leo `invoices.values`, entonces cada
  objeto trae `frase`, `encabezado`, `value`, `confidence` y `engine`. El primer
  texto es el que permite el emparejamiento del export (`SCHEMAS.md` §1.3).
- **CA-52.** Dada una factura cuyo RIF no se pudo leer, cuando se guarda, entonces
  **se guarda igual**, con `supplier_rif` en `NULL`, `review_status` en
  `needs_review` y `unreadable_rif` en el motivo.
- **CA-53.** Dada una foto en HEIC, cuando se guarda, entonces quedan guardadas
  **las dos** rutas: la original y la convertida.

## Fuera de alcance

- **Disparar el OCR.** Eso es la 002.
- **Servir las facturas por HTTP.** Eso es la 003.
- **Generar el CSV.** Eso es la 004.
- **La plantilla de pares.** Eso es la 004, y vive en `plantilla.csv`, no en una
  tabla.
- **Migraciones posteriores a la inicial.** Esta feature solo crea el esquema; las
  que vengan después se numeran aparte y **nunca se reescriben** (`CONSTITUTION.md`
  regla 1).

## Decisiones tomadas

Estas cuatro tocaban columnas del esquema y cambiar las después está prohibido por
`CONSTITUTION.md` regla 1. **Están resueltas** y escritas en `design.md`:

| # | Decisión | Resultado |
|---|---|---|
| **D-00** | ¿Cómo se guardan los valores que pidió el contador? | `values JSONB`, un objeto por valor con `frase`, `encabezado`, `value`, `confidence`, `engine` |
| **D-01** | ¿Qué motor produjo cada campo? | El motor va **dentro** de cada objeto del JSONB. `ocr_runs.engine_version` guarda el motor principal |
| **D-02** | ¿La imagen en disco o en la base? | En disco. `original_path` y `converted_path` |
| **D-03** | ¿`operator` se llena o queda en `NULL`? | **La columna no existe.** Sin autenticación no hay operador |

Ninguna se implementa por inventada.

## Decisiones pendientes

| # | Pregunta | Por qué está abierta |
|---|---|---|
| **D-04** | ¿Cómo se purga el texto reconocido? | `ocr_runs.raw_text` guarda el texto de la foto: RIF, razones sociales, importes. Una auditoría puede exigir conservar la imagen y **no** el texto. La respuesta es una sentencia `UPDATE ocr_runs SET raw_text = NULL`, pero falta decidir **quién** la ejecuta y **cuándo**: un comando manual, una tarea programada, o una pantalla. **No se creó carpeta `scripts/`** para esto: sería una estructura vacía كمando único. Cuando se decida, se documenta donde corresponda |
