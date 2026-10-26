# Tasks 002 — Extracción de factura

**Spec:** [`spec.md`](./spec.md) · **Design:** [`design.md`](./design.md)

> Checklist en orden. Cada tarea dice cómo se comprueba. **Una tarea a la vez**
> (`AGENTS.md` § No hagas).
>
> **La 002 no escribe en PostgreSQL.** Entrega el resultado a la 003
> (`AGENTS.md` § Roles).

**Las cinco decisiones (O-01 a O-05) están resueltas** y escritas en `design.md`.
Esta feature no tiene bloqueos.

**Precondición:** la 004 pasa la lista de columnas como `list[Columna]` y, con ella,
el formato numérico y si se ignoran tildes.

---

## Fase 1 — Preprocesado y motores

- [x] **T1.1** `app/ocr/preprocess.py` con los 5 pasos, **en el orden fijo de
      `CONSTITUTION.md` § Convenciones**: gris, ruido, inclinación, umbral,
      escalado.
      *Verificable:* recibe una imagen de prueba y devuelve una umbralizada.
- [x] **T1.2** `app/ocr/rapidocr_engine.py`: arranque **perezoso**, modelos
      PP-OCRv6 en español sobre ONNX Runtime, texto **en orden de lectura** y
      confianza normalizada de 0-1 a **0-100**.
      *Verificable:* el texto sale en el mismo orden en que se lee la factura.
      El servidor no carga los modelos al arrancar.
- [x] **T1.3** `app/ocr/pipeline.py` prueba varias variantes de la misma imagen y
      elige la lectura con más valores, en la línea correcta y con mayor confianza.
      *Verificable:* una foto difícil no depende de una sola lectura.

---

## Fase 2 — La búsqueda

Es el corazón de la feature.

- [x] **T2.1** `Columna` en `app/models/invoice.py`, **inmutable**, con `frase`,
      `encabezado` y `linea`. La recibe la 004; la 002 no la arma.
      *Verificable:* no se le puede cambiar el `encabezado` después de creada.
- [x] **T2.2** `app/ocr/extract.py`: recibe `list[Columna]` y devuelve un
      `ExtractedValue` por columna, **en el mismo orden**.
      *Verificable:* con texto de muestra, cada primer texto recibe el valor que va
      después de él. → CA-05
- [x] **T2.3** El `encabezado` viaja **intacto**: con sus tildes, sus espacios y su
      idioma, y **sin tocar la búsqueda**.
      *Verificable:* `Columna(frase="Total", encabezado="Base imponible")` devuelve
      `encabezado="Base imponible"` aunque el primer texto salga vacío. → CA-36
- [x] **T2.4** Búsqueda del primer texto completo, sin distinguir **mayúsculas**.
      *Verificable:* `Total a pagar` encuentra `TOTAL A PAGAR`.
- [x] **T2.5** Las **tildes se ignoran por defecto** y se dejan de ignorar con
      `#acentos=0`. Los espacios interiores no se colapsan y la puntuación no se
      quita.
      *Verificable:* `Razon social` encuentra `RAZÓN SOCIAL` con `acentos=1`, y no
      la encuentra con `acentos=0`. → CA-55
- [x] **T2.6** **Saltar coincidencias parciales**: una coincidencia pegada a otras
      letras no cuenta.
      *Verificable:* con el texto `SUBTOTAL 100,00 IVA 16,00 TOTAL 116,00`, la
      columna `Total = Base imponible` devuelve `116,00`, no `100,00`. → CA-07
- [x] **T2.7** **Nunca adivinar**: sin coincidencia, valor vacío; con varias
      coincidencias válidas, valor vacío y `ambiguous:<primer texto> (columna "<segundo texto>")`.
      *Verificable:* no hay ningún camino del código que elija una coincidencia al
      azar. → CA-06, CA-34
- [x] **T2.8** **Los avisos se arman aquí**, en `extract.py`. No hay `validate.py`.
      *Verificable:* no existe el archivo, y `extract.py` devuelve `review_status` y
      `review_reason`. → CA-06, CA-56
- [x] **T2.9** `app/ocr/normalize.py` con los separadores que llegan de la 004:
      por defecto `,` de miles y `.` decimal, y `1.234,56` → `1234.56` si el
      contador puso lo contrario.
      *Verificable:* `1,234.56` da `1234.56` con el default, y `1.234,56` también
      con `#miles=. #decimal=,`. → CA-33
- [x] **T2.10** **El signo se queda tal cual.** `-45,00` devuelve `-45,00`.
      *Verificable:* una retención negativa sale negativa, y la app no le quita el
      menos a nada ni se lo pone. → CA-54
- [x] **T2.11** Un `NaN` o un `inf` **no llegan al CSV**: la columna sale vacía.
      *Verificable:* un token raro deja la celda vacía, no `#N/A`.
- [x] **T2.12** Un valor que no parsea queda vacío, nunca aproximado.
      *Verificable:* `Verificable` sale vacío, no `0`.
- [x] **T2.13** Los 4 campos de control con los alias fijos de `design.md`, y
      separación de `serie` y `numero`. **Sin par y sin ocupar columna.**
      *Verificable:* sin que el contador los pida, aparecen en
      `ExtractionResult.control` y **no** aparecen en `.values`. → CA-52
- [x] **T2.14** Dos pares con **primeros textos distintos** que caen en el mismo valor:
      ambos lo reciben.
      *Verificable:* `Total = Total a pagar` y `Importe total = Neto` sobre el mismo
      `116,00` dan las dos columnas con `116.00`. → CA-34

---

## Fase 3 — El objeto de salida

- [x] **T3.1** `ExtractionResult`, `ExtractedValue` y `ControlFields`, como en
      `design.md`. **`ExtractedValue` no lleva el primer texto.**
      *Verificable:* el dataclass no tiene atributo `frase`.
- [x] **T3.2** `raw_text` viaja en el objeto, y **solo** la 003 decide si lo guarda.
      *Verificable:* la 002 lo devuelve siempre, y no escribe nada.
      → CA-09
- [x] **T3.3** Parseo de `invoice_items`.
      *Verificable:* con una factura de dos líneas las extrae. Si el diseño decide
      no hacerlo todavía, queda en `[]` y se anota en el CHANGELOG.

---

## Fase 4 — Pruebas

- [x] **T4.1** `tests/test_extract.py` con `mocks` de texto: primer texto que coincide,
      que no coincide, que coincide dentro de `SUBTOTAL`, que tiene varias
      coincidencias, dos primeros textos distintos sobre el mismo valor, número con
      los dos formatos numéricos, número con signo y valores de texto.
      *Verificable:* pasa **sin RapidOCR real**.
      → CA-05 a CA-09, CA-33 a CA-34, CA-54, CA-55
- [x] **T4.2** Test de que el resultado **nunca** lleva un valor inventado: sin
      coincidencia es `None`, no `""`, ni `0`, ni el valor de otra columna.
- [x] **T4.3** Test de que el orden de `values` coincide con el de las columnas.
      *Verificable:* con 3 columnas, `values` viene en el mismo orden. → CA-36
- [x] **T4.4** Test de que el `encabezado` sale **intacto** y que **no influye en la
      búsqueda**.
      *Verificable:* cambiar `Base imponible` por `Neto` no cambia el valor.
- [x] **T4.5** `tests/test_extract.py` con primeros textos en otro idioma.
      *Verificable:* `注文番号 = Referencia` busca `注文番号` y devuelve el
      segundo texto `Referencia` intacto.
- [x] **T4.6** Test de que **no existe cuadre contable**: `review_reason` nunca
      trae `unbalanced_total`.
      *Verificable:* el test falla si alguien lo agrega. → CA-56
- [ ] **T4.7** Probar con fotos que desestabilizan el preprocesado: fondo de
      color (amarillo, azul), sombra de la mano en una esquina, dobladura o grapa
      sobre el total, y recibo térmico desvanecido.
      *Verificable:* cada caso o extrae bien o deja la columna vacía y avisa.
- [x] **T4.8** `ruff check .` sin hallazgos y `pytest` en verde.
- [x] **T4.9** Medir RapidOCR con fotos reales de factura.
      *Verificable:* cada valor esperado coincide y el tiempo por imagen es
      aceptable para un lote.
- [x] **T4.10** Probar primeros textos mal escritos a propósito, con tildes cambiadas
      y en minúsculas.
      *Verificable:* el contador ve la columna vacía y el aviso, no un valor
      equivocado.