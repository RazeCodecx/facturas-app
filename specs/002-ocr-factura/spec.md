# Spec 002 — Extracción de factura

**Estado:** borrador · **Feature:** `002-ocr-factura` · **Rol:** Agente 2

El contexto del proyecto está en `AGENTS.md`. Las reglas de extracción y de
búsqueda salen de `SCHEMAS.md` §5, y este documento **no las redefine**.

## Necesidad

Como sistema, necesito leer una foto, encontrar lo que el contador pidió y devolver
los valores con la confianza de cada uno, para que la 003 los guarde y la 004 los
escriba. Un valor que no sé leer vale menos que uno vacío: no se inventa.

## Qué cambió respecto al modelo anterior

El contador no pide campos de un catálogo. Pide **pares**. Si escribe
`Total = Base imponible`, la app busca `Total` en la foto, se queda con el valor que
viene después, y devuelve ese valor para una columna que se titula
`Base imponible`. El primer texto y el segundo texto son
cosas distintas (`SCHEMAS.md` §1).

Antes una sola línea cumplía los dos papeles. Ahora los cumple separados por `=`, y
esta feature tiene que respetar los dos: **busca** el primer texto y **devuelve** el
segundo texto intacto.

**El `=` no se busca y no se muestra.** Solo marca dónde termina el primer texto: el
primer texto es lo que se busca en la foto, y el segundo texto es el nombre de la
columna.

## Alcance

Limpieza de la imagen, los dos motores de OCR, la **búsqueda del primer texto de cada
par** en el texto reconocido, la normalización de números, y la extracción interna
de los 4 campos de control.

**La 002 no cuadra importes.** No existe `unbalanced_total` (`SCHEMAS.md` §3.3).

**La 002 no escribe en PostgreSQL.** Entrega un objeto al Agente 1
(`AGENTS.md` § Roles).

## Criterios de aceptación

- **CA-05.** Dada una foto de factura y una lista de columnas con
  `Total a pagar = Base imponible` y `RIF = RIF del proveedor`, cuando proceso la
  foto, entonces **busco `Total a pagar` y `RIF`**, devuelvo el valor que sigue a
  cada una, y devuelvo los segundos textos `Base imponible` y `RIF del proveedor`
  intactos. Que venga de un archivo o de los defaults internos no cambia nada.
- **CA-06.** Dado un primer texto que no aparece en la foto, cuando proceso, entonces su
  valor queda vacío, la factura queda `needs_review` y el motivo es
  `no_match:<primer texto> (columna "<segundo texto>")`. **Nunca un valor inventado.**
- **CA-07.** Dado un primer texto que coincide dentro de una palabra más larga, cuando
  proceso, entonces esa coincidencia se descarta. `Total` no coincide con `SUBTOTAL`.
- **CA-08.** Dados dos motores disponibles, cuando un primer texto sale mal con el
  primero, entonces el segundo interviene.
- **CA-09.** Dada una foto procesada, cuando termina, entonces el resultado incluye
  la confianza y el motor **por valor**, y el texto crudo viaja en el objeto pero
  **nunca sale por la API**.
- **CA-33.** Dado un número escrito con el formato por defecto (`1,234.56`), cuando
  lo extraigo, entonces devuelvo `1234.56`, con punto decimal y sin coma de miles.
  Y si el contador puso `#miles=. #decimal=,`, entonces `1.234,56` da `1234.56`.
- **CA-34.** Dados dos pares con **primeros textos distintos** que coinciden en el mismo
  valor, cuando proceso, entonces ambos reciben ese valor. Y si un primer texto tiene
  varias coincidencias válidas, su columna queda vacía y se marca
  `ambiguous:<primer texto> (columna "<segundo texto>")`.
- **CA-36.** Dada una lista de columnas, cuando proceso, entonces devuelvo un valor
  por columna, **en el mismo orden**, y el segundo texto de cada una sale **exacto**
  como lo escribió el contador, con sus tildes, sus espacios y su idioma.
- **CA-37.** Dados dos pares con el mismo primer texto, cuando los recibo, entonces es
  error y nombro las dos líneas. Dos columnas no pueden salir del mismo valor de la
  foto.
- **CA-39.** Dado un par con el segundo texto vacío, como `Total =`, cuando lo recibo,
  entonces busco `Total` y devuelvo el segundo texto `Total`.
- **CA-54.** Dado un número de retención escrito `-45,00`, cuando lo extraigo, entonces
  devuelve `-45,00`, con el signo. La app **no le quita el signo a nada**.
- **CA-55.** Dado `#acentos=1` (por defecto), un primer texto sin tildes encuentra el texto
  con tildes. Dado `#acentos=0`, entonces **solo** encuentra el texto idéntico,
  tildes incluidas.
- **CA-56.** Dada una factura con columnas vacías, entonces la app **no intenta
  cuadrar nada**. No existe `unbalanced_total`: con columnas arbitrarias no puede
  saber cuál es la base y cuál el IVA (`SCHEMAS.md` §3.3).

## Los 4 campos de control

Se extraen **sin que el contador los pida** y no aparecen en su Excel
(`SCHEMAS.md` §2). Son fijos, con palabras internas:

| Campo | Qué busca la app por dentro |
|---|---|
| `supplier_rif` | `RIF` |
| `serie` | Se separa de `numero` si viene `001-00001234` |
| `numero` | `N° factura`, `Nº factura`, `No. factura`, `Factura N°` |
| `issue_date` | `Fecha` |

Son palabras internas, **no sugerencias**: no se le muestran, no aparecen en su
Excel, y no se registran en `plantilla.csv`. **No ocupan columna**: van en
`ExtractionResult.control`.

**Si no se puede leer el RIF, la factura se guarda igual** con el RIF vacío, y el
motivo es `unreadable_rif`. La 002 no decide si se guarda: devuelve el campo en
`None` y la 003 lo persiste con `NULL`.

## Fuera de alcance

- **Recibir el archivo.** Eso es la 003, que valida content-type y tamaño antes de
  llamar a la 002.
- **Escribir en la base.** Eso es la 001 y la 003.
- **Generar el CSV.** Eso es la 004.
- **Leer `plantilla.csv`.** Eso es la 004, que le pasa a la 002 la lista de columnas
  ya leída. La 002 recibe `list[Columna]` y **no sabe de dónde salió**: del archivo
  del contador o de `COLUMNAS_POR_DEFECTO`. Las dos le llegan igual.
- **Escribir la fila 1 del Excel.** También es la 004. La 002 devuelve el segundo texto
  en cada valor y no lo emite.
- **HEIC.** La 003 convierte antes de llamar a la 002, con `pillow-heif`.

## Decisiones tomadas

Ninguna. Las cinco quedaron resueltas:

| # | Decisión |
|---|---|
| **O-01** | **Eliminado.** La app no cuadra totales. Con columnas arbitrarias no puede saber cuál es la base y cuál el IVA. No existe `unbalanced_total` |
| **O-02** | **EasyOCR entra por primer texto**, solo donde Tesseract devolvió vacío o confianza bajo el umbral |
| **O-03** | El umbral vive en `.env`, como `OCR_CONFIDENCE_THRESHOLD` |
| **O-04** | Alias internos fijos: `RIF`, `N° factura`/`Nº factura`/`No. factura`/`Factura N°`, `Fecha`. Ver la tabla de arriba |
| **O-05** | Se ignoran mayúsculas siempre. Las tildes se ignoran por defecto y se apagan con `#acentos=0`. Los espacios interiores no se colapsan y la puntuación no se quita |