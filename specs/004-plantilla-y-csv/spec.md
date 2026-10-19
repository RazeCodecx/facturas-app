# Spec 004 — Plantilla y CSV

**Estado:** borrador · **Feature:** `004-plantilla-y-csv` · **Rol:** Agente 1

El contexto del proyecto está en `AGENTS.md`. El formato del archivo y del CSV salen
de `SCHEMAS.md` §4 y §6, y este documento **no los redefine**.

## Necesidad

Como contador, quiero escribir a mano, en mi propio archivo, **qué se busca en la
foto** y **cómo quiero que se llame cada columna de mi Excel**, en el orden que yo
quiera. Sin catálogos, sin sinónimos, sin ejemplos que me party's el criterio, y sin
que nadie me imponga nombres.

El archivo **me lo entregan vacío**. Nadie me pone referencias adentro: si la app me
dejara ejemplos, yo los editaría sin querer y cada ejemplo se volvería una columna
que no pedí.

## Por qué esta feature absorbió a `005-campos-propios`

Cada línea pasó a ser un par `primer texto = segundo texto`. Eso eliminó las tablas
`custom_fields` e `invoice_custom_values`, y con ellas los cuatro endpoints que las
manipulaban. Y después, al separar el primer texto del segundo texto, también
eliminó el supuesto de que **una línea produce un texto** que va al Excel: ahora
produce dos.

## Los referentes no están en el archivo

Están en `app/export/plantilla.py`, como `COLUMNAS_POR_DEFECTO`. Se usan **solo**
cuando el contador no escribió nada. En cuanto escribe una línea, lo suyo es lo único
que existe.

El archivo se entrega vacío. La app **solo** escribe una vez: si lo encuentra
**completamente vacío**, le pone la línea de formato con su mensaje, para que el
contador sepa qué acepta. Después de eso **nunca más lo toca**
(`CONSTITUTION.md` § Convenciones).

## Alcance

Leer `plantilla.csv`, **parsear los pares y las líneas de formato**, pasarle la lista
de columnas a la 002, **emparejar por primer texto**, generar el CSV de facturas y el
de avisos, y servirlos por HTTP.

**`plantilla.csv` se lee y nunca se escribe**, con la única excepción de arriba.

## Criterios de aceptación

- **CA-15.** Dado `plantilla.csv` con tres pares y un conjunto de facturas, cuando
  pido `GET /api/v1/export/invoices.csv`, entonces la **fila 1** lleva los tres
  **segundos textos**, en el orden de las líneas, y no hay fila de
  variables debajo.
- **CA-16.** Dado el mismo archivo, cuando lo abro en Excel, entonces los acentos y
  la `ñ` se ven correctos, gracias al BOM.
- **CA-17.** Dado un conjunto de facturas, cuando exporto, entonces se exportan
  **todas**, incluidas las `needs_review`.
- **CA-18.** Dado un filtro por `review_status` o `issue_date`, cuando lo aplico,
  entonces el CSV sale filtrado con ese criterio.
- **CA-19.** Dado `plantilla.csv`, cuando exporto, entonces el CSV tiene **una columna
  por línea del archivo**, en ese orden, y ni una más.
- **CA-20.** Dado un CSV exportado, cuando lo inspecciono, entonces **no contiene**
  el texto crudo del OCR, ni las rutas de las imágenes, ni el estado de revisión, ni
  **los primeros textos buscados**.
- **CA-28.** Como contador, cuando escribo `Total = Base imponible`, entonces la
  columna que se titula **`Base imponible`** en el CSV lleva el valor que la app
  encontró buscando `Total`.
- **CA-29.** Como contador, cuando reordeno las líneas de `plantilla.csv`, entonces
  el CSV sale con las columnas en ese orden.
- **CA-30.** Como contador, cuando borro una línea de `plantilla.csv`, entonces esa
  columna desaparece del CSV.
- **CA-31.** Como contador, cuando una línea está mal formada, entonces el error me
  dice **qué línea** y **qué escribir**, y no se genera un CSV a medias.
- **CA-32.** Como contador, cuando exporto, entonces mi `plantilla.csv` queda igual
  como estaba: la app no lo modifica.
- **CA-35.** Como contador, cuando un primer texto no encontró nada en la foto, entonces
  su columna sale **vacía** en el CSV, y el motivo llega en la respuesta del
  escaneo, no en el archivo.
- **CA-40.** Como contador, cuando escribo `Total =` sin nada en el segundo texto,
  entonces la columna se titula `Total`.
- **CA-41.** Como contador, cuando escribo el mismo primer texto en dos líneas, entonces
  la app me avisa de que está repetido, diciendo **las dos líneas**, y no exporta nada.
- **CA-42.** Como contador, cuando escribo `Total = Base imponible`, entonces el
  CSV **no** muestra la palabra `Total` en ninguna parte. Solo `Base imponible`.
- **CA-44.** Como contador, cuando abro `plantilla.csv` por primera vez, entonces
  está **vacío**. Sin ejemplos, sin comentarios, sin columnas de la app.
- **CA-45.** Como contador, cuando **no escribo nada** en `plantilla.csv`, entonces la
  app usa su juego de columnas por defecto y el escaneo funciona igual. No me
  avisa de que el archivo está vacío.
- **CA-46.** Como contador, cuando escribo **una sola línea** en `plantilla.csv`,
  entonces el CSV sale con **una sola columna**. No se le suman las columnas de la
  app. Lo que no escribí, no existe.
- **CA-47.** Como contador, cuando escribo `Total = Base imponible` y dejo el resto
  vacío, entonces la app **no me completa** las columnas que me faltan. No adivina.
- **CA-48.** Como contador, cuando busco en `plantilla.csv` los referentes de la
  app, entonces **no están**. Viven en el código y no se me ofrecen en ninguna
  parte.
- **CA-60.** Como contador, cuando escaneo con `Total = Base imponible` y después
  cambio el archivo a `Total = Total factura`, entonces el CSV sale con una columna
  **`Total factura`** y el mismo valor. **El valor no se corre de columna.**
- **CA-61.** Como contador, cuando escaneo y después **borro** una línea del
  archivo, entonces esa columna desaparece del CSV y el valor no aparece en ninguna
  otra. No se corre a la columna vecina.
- **CA-62.** Como contador, cuando abro el archivo por primera vez, entonces
  encontré **una línea que empieza con `#`** que explica qué hace, en español e
  inglés, y los valores por defecto.
- **CA-63.** Como contador, cuando exporto un lote donde algo no coincidió, entonces
  junto al CSV de facturas hay un **`avisos.csv`** que dice qué se buscó, en qué
  columna y por qué falló. **El Excel de facturas no lleva esa información.**
- **CA-64.** Como contador, cuando pongo `#miles=. #decimal=,` en el archivo,
  entonces los números se leen al revés: `1.234,56` produce `1234.56`. Sin esa línea,
  el default es `1,234.56`.
- **CA-65.** Como contador, cuando escribo `#acentos=0`, entonces un primer texto **con
  tilde** solo encuentra el texto con la misma tilde. Con el default, las ignora.
- **CA-66.** Como contador, cuando la línea de formato está **mal escrita**, entonces
  los números salen con el valor por defecto y **la app sigue trabajando**. No se
  para.
- **CA-67.** Como contador, cuando exporto una factura que tuvo una columna vacía,
  entonces la factura **sale igual**, con esa columna en blanco. No desaparece.

## Fuera de alcance

- **Que el contador lo edite y lo reimporte.** El contador es el actor final; la
  app no vuelve a leer lo que escribió (`AGENTS.md`).
- **`.xlsx`.** Habría que agregar `openpyxl`, que no está autorizada.
- **Normalizar los números.** Eso es la 002, no la 004. La 004 solo escribe.
- **Una pantalla web para editar la plantilla.** Se edita en Excel.

## Decisiones tomadas

| # | Decisión | Por qué |
|---|---|---|
| **E-01** | Se exportan **todas** las facturas, incluidas las `needs_review` | Exportar solo las `ok` haría que el contador **pierda datos sin enterarse**. Una factura con una columna dudosa es justo la que él quiere revisar |
| **E-02** | Las líneas y los impuestos **no** llegan al CSV | Una factura con observación llega con su descripción en la columna que el contador pidió. Si necesita el desglose por línea, es una feature aparte |
| **E-03** | **Por HTTP.** El CSV se sirve en `GET /api/v1/export/invoices.csv` | El contador lo abre desde el navegador o lo baja con el Atajo. Es lo que ya está en el contrato de `SCHEMAS.md` §7 |
| **E-04** | **Sí, hay `avisos.csv`**, en `GET /api/v1/export/avisos.csv` | Los avisos no pueden ir en el Excel (`CONSTITUTION.md` regla 4), y en un lote se pierden al cerrar la app. Sin ellos, el contador ve columnas vacías sin saber qué se buscó |

Ninguna se implementa por inventada.