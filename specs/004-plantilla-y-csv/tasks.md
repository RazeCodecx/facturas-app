# Tasks 004 — Plantilla y CSV

**Spec:** [`spec.md`](./spec.md) · **Design:** [`design.md`](./design.md)

> Checklist en orden. Cada tarea dice cómo se comprueba. **Una tarea a la vez**
> (`AGENTS.md` § No hagas).
>
> `plantilla.csv` se lee y **nunca se escribe**, con **una única excepción**: si
> está completamente vacío, la app le escribe una vez la línea de formato con su
> mensaje. Después, nunca más.

**Las cuatro decisiones (E-01 a E-04) están resueltas** y escritas en `design.md`.
**No hay autenticación**, así que el endpoint no pide token.

**Precondición:** requiere la 001 (queries). T2.1 y T2.2 no dependen de nadie.

---

## Fase 1 — La plantilla

Va antes que el CSV: si el archivo se lee tarde, un error del contador aparece como
una columna corrida o con el nombre equivocado en el Excel.

- [X] **T1.1** `plantilla.csv` en la raíz, **vacío con BOM**: 3 bytes, cero líneas.
      Los referentes **no** van en el archivo.
      *Verificable:* `Get-Content plantilla.csv` no devuelve nada, y los primeros
      tres bytes son `EF BB BF`. → CA-44
- [X] **T1.2** `COLUMNAS_POR_DEFECTO` en `app/export/plantilla.py`, con los 11 pares
      de `design.md`. **Interno.** No se escribe al archivo, no sale por la API y no
      se ofrece como sugerencia.
      *Verificable:* un grep de `RIF del proveedor` en `plantilla.csv` no encuentra
      nada. → CA-48
- [X] **T1.3** `leer_columnas()` devuelve `list[Columna]`. Si el archivo no dejó
      **ninguna** línea de columnas, devuelve `COLUMNAS_POR_DEFECTO`.
      *Verificable:* con el archivo vacío devuelve los 11 defaults. → CA-45
- [X] **T1.4** Con **una o más** líneas escritas, devuelve **solo** las del contador.
      *Verificable:* con una sola línea `Total = Base imponible` devuelve **una**
      columna, no once. → CA-46
- [X] **T1.5** No hay mezcla ni aviso: la app **no completa** las columnas que
      faltan y **no dice** que faltan.
      *Verificable:* con una línea escrita, no hay ningún log ni respuesta que
      mencione `COLUMNAS_POR_DEFECTO`. → CA-47
- [X] **T1.6** Partir por el **primer** `=`, con `split("=", 1)`. El `=` **solo
      marca dónde termina el primer texto**.
      *Verificable:* `Total = Base imponible` da primer texto `Total` y segundo
      texto `Base imponible`, con el espacio del medio. Un `=` en el segundo texto
      no parte la línea.
- [X] **T1.7** Segundo texto vacío: se usa el primer texto como título.
      *Verificable:* `Moneda =` da `Columna("Moneda", "Moneda", ...)`.
      → CA-40
- [X] **T1.8** Ignora líneas vacías y conserva el texto tal cual, con tildes,
      espacios interiores e idioma.
      *Verificable:* un archivo con líneas en blanco y un segundo texto en japonés
      devuelve solo los pares, sin modificaciones.
- [X] **T1.9** **Error** si falta el `=`, con el **número de línea**.
      *Verificable:* el mensaje dice `línea 4` y muestra el ejemplo
      `primer texto = segundo texto`. → CA-31
- [X] **T1.10** **Error** si hay dos `=` o más, con el número de línea.
      *Verificable:* `Total = Base = Imponible` se rechaza y nombra la línea.
- [X] **T1.11** **Error** si el primer texto está vacío, con el número de línea.
      *Verificable:* ` = Base imponible` se rechaza y dice que no dice qué buscar.
- [X] **T1.12** **Error** si un primer texto se repite, nombrando **las dos líneas**.
      *Verificable:* con `Total` en las líneas 3 y 10, el mensaje dice las dos.
      → CA-41
- [X] **T1.13** El segundo texto **sí** puede repetirse, porque lo que no puede
      repetirse es el primer texto.
      *Verificable:* `Total = Base imponible` y `Base = Base imponible` dan dos
      columnas válidas.
- [X] **T1.14** Lectura con BOM, y **error** si el archivo **no existe**. Vacío no
      es error: es el default.
      *Verificable:* con el archivo vacío devuelve los defaults; con el archivo
      borrado, error diciendo que falta `plantilla.csv`.
- [X] **T1.15** Cada mensaje de error dice **el número de línea y qué escribir**, y
      **ninguno** menciona los defaults.
      *Verificable:* los cuatro mensajes de T1.9 a T1.12 tienen los dos, y no
      contienen la palabra `COLUMNAS_POR_DEFECTO` ni `default`.

---

## Fase 2 — Las líneas de formato

- [X] **T2.1** Cualquier línea que empiece con `#` es de configuración y **no
      produce columna**, esté donde esté en el archivo.
      *Verificable:* un archivo con `#` en la línea 1 y pares después devuelve solo
      los pares.
- [X] **T2.2** Se leen `miles`, `decimal` y `acentos`. **La última que aparece de
      cada opción gana.**
      *Verificable:* con `#miles=, #decimal=.` y después `#decimal=,`, el decimal
      final es `,`.
- [X] **T2.3** Por defecto `miles=,`, `decimal=.` y `acentos=1`, y eso se le pasa a
      la 002.
      *Verificable:* la 002 recibe `,` `.` y `True` cuando el archivo no dice nada.
- [X] **T2.4** **Una línea de formato mal escrita NO es error**: se usa el default y
      la app sigue.
      *Verificable:* con `#cualquier cosa`, la app responde `201` y exporta igual,
      con los separadores por defecto. → CA-66
- [X] **T2.5** `#acentos=0` apaga el ignorar tildes, tanto en la búsqueda como en el
      emparejamiento del export.
      *Verificable:* `Razon social` deja de encontrar `RAZÓN SOCIAL`. → CA-65
- [X] **T2.6** **La excepción de escritura**: si el archivo está **completamente
      vacío**, la app escribe `MENSAJE_FORMATO` con BOM. **Una sola vez.**
      *Verificable:* con el archivo vacío, aparece el mensaje; con un archivo que
      tiene algo, **no se escribe nada**. → CA-62
- [X] **T2.7** El mensaje explica `miles`, `decimal` y `acentos`, **en español y en
      inglés**, y trae los valores por defecto.
      *Verificable:* el mensaje contiene las tres palabras y los dos idiomas.
- [X] **T2.8** Después de escribir el mensaje, la app **no vuelve a mirar** si el
      archivo quedó vacío.
      *Verificable:* si el contador borra todo y reinicia, no se escribe otra vez.
- [X] **T2.9** `tests/test_plantilla.py`: archivo vacío, solo líneas vacías, una
      sola línea, `=` ausente, `=` duplicado, primer texto vacío, primer texto
      repetido, segundo texto repetido, par en otro idioma, archivo inexistente,
      archivo sin BOM, cada opción de formato, formato mal escrito, y `#` en
      distintas posiciones.
      *Verificable:* pasa leyendo archivos temporales, no el archivo real.
- [X] **T2.10** Test de que el export **no modifica** `plantilla.csv`.
      *Verificable:* se compara el archivo antes y después. → CA-32

---

## Fase 3 — El emparejamiento

Es lo que hace segura la edición después del escaneo.

- [X] **T3.1** `csv.py` busca cada valor en `invoices.values` **por el primer texto**, no por
      la posición que tenía al escanear.
      *Verificable:* con el JSONB en orden distinto al del archivo, cada columna
      recibe su valor. → CA-60
- [X] **T3.2** La comparación de primeros textos usa la misma normalización que la
      búsqueda: sin mayúsculas, y sin tildes si `acentos=1`.
      *Verificable:* el primer texto `Total` encuentra el valor guardado con `TOTAL`.
- [X] **T3.3** Si el contador **borró** una línea, esa columna desaparece y el valor
      **no se corre** a la columna vecina.
      *Verificable:* el valor no aparece en ninguna otra columna. → CA-61
- [X] **T3.4** Renombrar, reordenar y agregar líneas después de escanear **no cambia
      los valores**.
      *Verificable:* con el mismo `plantilla.csv` reordenado, el CSV trae los mismos
      números en las mismas columnas, solo que en otro orden.
- [X] **T3.5** Una factura con columnas vacías **se exporta igual**, con lo demás en
      blanco.
      *Verificable:* la factura aparece en el CSV, con la columna vacía. → CA-67

---

## Fase 4 — El CSV de facturas

- [X] **T4.1** `app/export/csv.py`: fila 1 con los **segundos textos**, una
      fila por factura.
      *Verificable:* **no existe otra función que escriba el CSV**, y el archivo
      **no tiene segunda fila**. → CA-15
- [X] **T4.2** **El primer texto buscado no aparece en ninguna parte del CSV.**
      *Verificable:* con `Total = Base imponible` exportado, un grep de `Total` en el
      archivo no encuentra nada. → CA-42, CA-20
- [X] **T4.3** Una columna por línea del archivo, en el orden del archivo.
      *Verificable:* con columnas reordenadas sale en ese orden. → CA-19, CA-29
- [X] **T4.4** Encoding `utf-8-sig`, separador coma, `None` como celda vacía, y
      redondeo a 2 decimales **solo al escribir**.
      *Verificable:* el archivo abre en Excel con acentos y `ñ` correctos, y un
      `None` se ve vacío. → CA-16
- [X] **T4.5** `csv.py` **no importa** `ocr_runs` ni escribe `review_status` ni
      `review_reason`.
      *Verificable:* el archivo no contiene texto crudo, rutas de imagen, ni el
      estado de revisión. → CA-20
- [X] **T4.6** Se exportan **todas** las facturas, incluidas las `needs_review`.
      *Verificable:* una `needs_review` también sale. → CA-17

---

## Fase 5 — El archivo de avisos

- [X] **T5.1** `app/export/avisos.py`: una fila por aviso, con `invoice_id`,
      `frase`, `columna` y `motivo`.
      *Verificable:* sale un archivo con esos cuatro campos.
- [X] **T5.2** Sale **siempre**, aunque no haya avisos: cabecera y nada más.
      *Verificable:* con todo en verde, el archivo tiene solo la fila de campos, y
      el contador no ve un error donde no hay nada.
- [X] **T5.3** Encoding `utf-8-sig`, como el CSV de facturas.
      *Verificable:* abre en Excel con acentos correctos.
- [X] **T5.4** Los avisos van **en este archivo y no en el de facturas**.
      *Verificable:* el CSV de facturas no tiene `frase` ni `motivo`.
      → CA-63
- [X] **T5.5** Acepta los mismos filtros que el CSV de facturas.
      *Verificable:* filtrar por `review_status` filtra los dos archivos igual.

---

## Fase 6 — Endpoints

- [X] **T6.1** `GET /api/v1/export/invoices.csv` con los filtros de
      `review_status` e `issue_date`, aplicados en el SELECT de la 001.
      *Verificable:* cada filtro devuelve solo lo que corresponde, y nunca se lee
      todo para filtrar en Python. → CA-18
- [X] **T6.2** `GET /api/v1/export/avisos.csv`, con los mismos filtros.
- [X] **T6.3** **Sin token.** Ninguna de las dos rutas pide autenticación.
      *Verificable:* funcionan sin cabecera `Authorization`. → A-02
- [X] **T6.4** Un error de la plantilla se propaga al cliente con su mensaje y **con
      el número de línea**, sin escribir un CSV a medias.
      *Verificable:* con `plantilla.csv` sin `=` en la línea 4, responde `500` con
      ese mensaje y **no** devuelve un CSV incompleto. → CA-31
- [X] **T6.5** `Content-Type: text/csv; charset=utf-8` en las dos rutas.

---

## Fase 7 — Pruebas

- [X] **T7.1** `tests/test_export.py`: una sola fila de cabecera, una fila por
      factura, `None` vacío, y que el resultado **cambia** según `plantilla.csv`.
      *Verificable:* cambiar una línea del archivo cambia la fila 1 del CSV.
      → CA-15, CA-28
- [X] **T7.2** Test que abre el archivo y verifica que empieza con el BOM y que
      **no hay una segunda fila de variables**.
      *Verificable:* pasa. → CA-16
- [X] **T7.3** Test que busca en todo el contenido del archivo `raw_text`, rutas de
      disco, `ocr_runs`, `review_status`, `review_reason` y **cada primer texto
      buscado**.
      *Verificable:* el test falla si aparece cualquiera. → CA-20, CA-42
- [X] **T7.4** Test del **emparejamiento por primer texto**: escanear, reordenar el
      archivo, exportar, y comparar.
      *Verificable:* los números van en las mismas columnas, solo que en otro orden.
      → CA-60, CA-61
- [X] **T7.5** `ruff check .` sin hallazgos y `pytest` en verde.
- [ ] **T7.6** Prueba real de punta a punta: escribir `Total = Base imponible` en
      `plantilla.csv`, escanear una foto y abrir el CSV en Excel.
      *Verificable:* aparece una columna **`Base imponible`** con el total, y la
      palabra `Total` **no** aparece en el archivo. → CA-28, CA-42
- [ ] **T7.7** Prueba real con los dos formatos numéricos.
      *Verificable:* con `#miles=. #decimal=,`, `1.234,56` sale `1234.56`. Y con el
      default, `1,234.56` sale `1234.56`. → CA-64
- [ ] **T7.8** Prueba real del arranque: abrir el archivo vacío, ver el mensaje,
      escanear una foto y abrir el CSV.
      *Verificable:* el CSV sale con las 11 columnas del default, sin avisos.
      → CA-45, CA-62
- [ ] **T7.9** Prueba real del control del contador: dejar **una sola línea**,
      escanear y abrir el CSV.
      *Verificable:* el CSV sale con **una** columna, y el contador no ve ninguna
      columna de la app. → CA-46, CA-47
- [ ] **T7.10** Prueba real de un archivo con una línea repetida.
      *Verificable:* la app para, dice las dos líneas, y no genera CSV. → CA-41
- [ ] **T7.11** Prueba real de un lote con columnas vacías: exportar y abrir los
      dos archivos.
      *Verificable:* el de facturas sale con las columnas en blanco, y el de avisos
      dice qué se buscó en cada una. → CA-63, CA-67
- [ ] **T7.12** Después de T7.6 a T7.11, **volver a dejar el archivo como estaba**.
      *Verificable:* los tests de punta a punta no dejan basura en el archivo del
      contador.
