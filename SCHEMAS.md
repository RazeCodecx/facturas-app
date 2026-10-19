# SCHEMAS.md — Contrato de datos

> Leer junto con `AGENTS.md` (roles) y `CONSTITUTION.md` (reglas).

---

## 1. Cómo funciona la extracción

Cada línea de `plantilla.csv` describe una columna del Excel mediante **tres
cosas**. Los nombres de esta sección valen para todo el proyecto:

| | |
|---|---|
| **Primer texto** | Lo que se busca en la foto. Lo escribe el contador |
| **Valor** | Lo que se lee en la foto a continuación del primer texto |
| **Segundo texto** | El título de la columna en el Excel. Lo escribe el contador |

El `=` separa el primer texto del segundo texto, y **solo marca dónde termina el
primer texto**. No se busca, no se muestra y no significa nada. Si el segundo texto
queda vacío, se usa el primer texto como título.

El contador escribe el primer texto como cree que aparece impreso en la factura, y
el segundo texto como quiere verlo en su Excel: puede ser distinto, más corto o más
largo. **No hay lista de variables conocidas, ni sinónimos, ni sugerencias.**

```
Lo que escribe              Lo que la app                  Lo que recibe
el contador                 hace con la foto               el contador

primer texto                busca "Total a pagar"   ──▶    segundo texto
= segundo texto             toma el valor que sigue  ──▶    |
   Total a pagar =          y lo coloca bajo el             | Base imponible |
   Base imponible           título indicado                 |   1234,56     |
```

**El valor es lo que viaja.** Nunca se escribe a mano, nunca se adivina: o sale de
la foto, o la columna queda vacía y con aviso (§5.3).

En la base, el primer texto se guarda en el campo `frase` y el segundo texto en el
campo `encabezado` de cada objeto de `invoices.values` (§3.1). Los nombres de los
campos son los de siempre; este documento usa primer y segundo texto porque
describen el papel que cumplen, no su posición en la línea.

### 1.1 Quién traduce

**El contador no traduce nada. Traducen los módulos internos.**

| | Qué hace |
|---|---|
| `plantilla.csv` | Solo lo que el contador escribió. Los dos textos, tal cual |
| `app/ocr/extract.py` | Busca cada primer texto en la foto y saca el valor |
| `app/export/csv.py` | Coloca el valor bajo el segundo texto que le corresponde |

**Los referentes no están en `plantilla.csv`.** El archivo se entrega vacío y el
juego de columnas por defecto vive en el código (§4.3).

### 1.2 Lo que va al Excel y lo que no

| | Visible en el Excel |
|---|---|
| **Primer texto** | **No.** Solo se busca |
| **Valor** | **Sí.** Es el contenido de la columna |
| **Segundo texto** | **Sí.** Es el título de la columna |
| **Los 4 campos de control** | **No** (§2) |

La fila 1 del CSV lleva **solo los segundos textos**. Si un primer texto no
coincide, su columna sale vacía y el motivo llega en el aviso (§7), donde sí se
nombra el primer texto.

### 1.3 El emparejamiento es por primer texto

Cada factura guarda, junto a su valor, **el primer texto que lo produjo** (§3). Al
exportar, la app no usa la posición que tenía el valor en el archivo, sino el primer
texto. Por eso el contador puede renombrar, reordenar o agregar columnas después de
escanear sin que los valores se corran de columna. Si **borra** una línea, esa
columna desaparece del CSV y el valor queda guardado sin usarse.

---

## 2. Campos de control internos

Cuatro, y solo para deduplicación. El contador no los ve, no los pide y no puede
cambiarlos. **Son fijos**, con palabras internas que la app busca por su cuenta.

| Campo | Qué busca la app por dentro |
|---|---|
| `supplier_rif` | `RIF` |
| `serie` | Se separa de `numero` si viene `001-00001234` |
| `numero` | `N° factura`, `Nº factura`, `No. factura`, `Factura N°` |
| `issue_date` | `Fecha` |

Son palabras internas, **no sugerencias**: no se le muestran al contador, no
aparecen en su Excel, y no se registran en `plantilla.csv`. **No ocupan columna**,
vuelven en `ExtractionResult.control`.

### 2.1 Deduplicación

`invoice_number` se repite entre proveedores y entre años, así que no sirve como
clave única:

```
dedupe_key = supplier_rif + "|" + serie + "|" + numero + "|" + issue_date
```

**Si la app no logra leer el RIF, guarda la factura igual, con el RIF vacío** y
avisa con `unreadable_rif`. Esos registros no están protegidos contra duplicados, y
el contador debe saberlo al ver el aviso.

---

## 3. Tablas

| Tabla | Contenido |
|---|---|
| `invoices` | Los 4 campos de control (§2) + `dedupe_key` UNIQUE + `review_status` + `review_reason` + **`values JSONB`**, los valores que pidió el contador |
| `invoice_items` | Una fila por línea: código, descripción, cantidad, precio, importe, FK a `invoices` |
| `taxes` | Desglose de impuestos y retenciones, por factura o por línea |
| `fiscal_profiles` | Catálogos por país. Venezuela primero |
| `ocr_runs` | Rutas de imagen, texto crudo **condicional**, confianza, operador, fecha. **Interno** |

### 3.1 `invoices.values` — el JSONB

Es la decisión que sostiene todo lo demás. Un objeto por valor extraído, **con el
primer texto adentro**:

```json
[
  { "frase": "Total",       "encabezado": "Total a pagar",  "value": "116.00",
    "confidence": 92.0, "engine": "tesseract" },
  { "frase": "IVA",         "encabezado": "Monto del IVA",  "value": "16.00",
    "confidence": 88.5, "engine": "easyocr" }
]
```

- **El primer texto (`frase`) es la clave de emparejamiento** (§1.3). Por eso está
  guardado, y no solo el valor.
- El segundo texto (`encabezado`) se guarda como estaba **en el momento del
  escaneo**, para poder reconstruir el CSV aunque el archivo ya no exista.
- `engine` va por valor, porque EasyOCR interviene **por primer texto** (§5.5).

**El JSONB nunca se purga.** El contador puede volver a exportar cuando quiera.

### 3.2 Tipos numéricos

`float` en Python y `DOUBLE PRECISION` en PostgreSQL, para que los importes enteros
se conserven exactos. Redondeo a 2 decimales solo al exportar, nunca dentro de la
base.

### 3.3 `review_status`

| Valor | Significado |
|---|---|
| `ok` | Todos los valores solicitados encontraron su primer texto en la foto |
| `needs_review` | Algo requiere atención del contador antes de usar el dato |

Motivos (`review_reason`, texto corto, separados por `;`):

| Motivo | Condición |
|---|---|
| `no_match:<primer texto>` | Un primer texto no encontró nada en la foto |
| `ambiguous:<primer texto>` | Encontró varias coincidencias y no sabía cuál tomar |
| `low_confidence` | La confianza del OCR sobre la zona fue baja |
| `unreadable_rif` | No se pudo leer el RIF del proveedor, así que no hay dedupe |

Los avisos de `no_match` y `ambiguous` llevan **las dos mitades del par**:

```
no_match:Total a pagar (columna "Base imponible")
```

**No existe `unbalanced_total`.** Con columnas arbitrarias la app no puede saber
cuál valor es la base y cuál el IVA. El cuadre contable lo hace el contador en su
Excel, que es donde va a corregirlo igual.

**Ninguno de estos motivos aparece en el Excel del contador.** Van por el canal de
avisos (§7).

---

## 4. `plantilla.csv` — el archivo del contador

Vive en la raíz del proyecto. Es el **único archivo que el contador modifica**.

### 4.1 Formato

Una sola columna. Un par por línea, separado por `=`. **Sin fila de título y sin
ninguna sugerencia de la app.**

```
Total a pagar = Base imponible
RIF del proveedor = RIF
Moneda =
Total =
```

- **Una línea, una columna del Excel.**
- **El `=` solo marca dónde termina el primer texto.** No se busca, no se muestra, no
  significa nada.
- Se parte por el **primer** `=`, así que el segundo texto puede llevar espacios.
- **El primer texto es lo que se busca**, escrito tal como el contador lo espera
  impreso en la factura.
- **El segundo texto es el título del Excel.** Texto libre.
- **Si el segundo texto está vacío**, se usa el primer texto como título.
- **El orden de las líneas es el orden de las columnas** del Excel.
- **Para quitar una columna, se borra la línea.**
- **Líneas vacías se ignoran**, para que el contador pueda separar bloques.
- **El primer texto no puede repetirse.** Dos columnas no pueden salir del mismo
  valor de la foto. Si se repite, es error (§4.5).
- **Codificación `UTF-8` con BOM.**
- **El signo de los importes se queda tal cual.** Una retención escrita
  `-45,00` sale `-45,00`. La app no le quita el signo a nada.

### 4.2 El archivo se entrega vacío

`plantilla.csv`, en la raíz del proyecto, es **el único archivo que el contador
modifica**. Se entrega **vacío**, y la app tiene una **excepción única**: si lo
encuentra completamente vacío, escribe la línea de formato con su mensaje para que
el contador sepa qué acepta el archivo. Después de eso **nunca más lo toca**.

Mientras esté vacío, la app usa `COLUMNAS_POR_DEFECTO` (§4.3). En cuanto el
contador escriba una línea, la suya es la única que existe: no se le agregan
columnas, no se le completan las que le faltan y no se le avisa de que le faltan.

Lo que **no** es flexible: los 4 campos de control (§2), el orden de lectura del
OCR, y las reglas de extracción. El contador decide qué busca, cómo lo nombra y en
qué orden lo ve; no qué reglas sigue la app.


### 4.3 Los referentes viven en el código

El juego por defecto está en `app/export/plantilla.py`, como
`COLUMNAS_POR_DEFECTO`, y es interno. Se usa **solo** cuando el contador no escribió
ninguna línea.

No está en `plantilla.csv` porque ese archivo es del contador: si la app le deja
ejemplos ahí, los editaría sin querer y cada ejemplo se volvería una columna que no
pidió.

### 4.4 Las líneas que empiezan con `#`

Cualquier línea que empiece con `#` es de **configuración**, esté donde esté. Son
las únicas líneas que no producen columnas.

| Opción | Qué hace | Por defecto |
|---|---|---|
| `miles` | Separador de miles | `,` |
| `decimal` | Separador decimal | `.` |
| `acentos` | `1` ignora tildes al buscar, `0` no las ignora | `1` |

Ejemplo, con el mensaje que la app escribe:

```
# Formato de numeros / Number format: miles=coma, decimal=punto / comma, point
#miles=, #decimal=. #acentos=1
```

Una sola línea con las tres opciones, o varias, da igual: se leen todas y la última
que aparece gana.

### 4.5 Casos de error

**Los del contador se paran antes de procesar nada**, y el mensaje dice **qué línea**
y **qué escribir**.

| Situación | Qué hace la app |
|---|---|
| Archivo ausente | Error diciendo que falta `plantilla.csv` |
| **Archivo vacío** | **No es error.** Usa `COLUMNAS_POR_DEFECTO` (§4.3) |
| Línea sin `=` | Error: *falta el `=`* |
| Línea con dos `=` o más | Error: *solo un `=` por línea* |
| Primer texto repetido en dos líneas | Error, nombrando **las dos** líneas |
| Primer texto vacío | Error: *no dice qué buscar* |
| **Línea de formato mal escrita** | **No es error.** Usa el valor por defecto |

**La diferencia entre los dos tipos de error es si corrompen datos.** Una línea de
formato mal escrita solo hace que los números salgan raros, y el contador lo ve en
el Excel. Un `=` faltante cambia qué se busca y qué se muestra, y eso no se ve. Por
eso una para y la otra pasa.

Un segundo texto que **no coincide** con la foto tampoco es un error del archivo: la
columna sale vacía, la factura queda `needs_review` y la app avisa (§3.3, §5.3).

### 4.6 Un primer texto específico coincide menos

En una factura, `Total` aparece en `SUBTOTAL`, en `TOTAL` y en `TOTAL IVA`. Quien
escribe `Total` va a obtener resultados ambiguos. Quien escribe `TOTAL A PAGAR`
obtiene exactamente lo que pidió.

La app salta las coincidencias que son parte de una palabra más larga (§5.2), así
que `Total` no se confunde con `SUBTOTAL`. Aun así, **escribir el primer texto tal
como aparece impreso en la factura es la forma más segura de acertar.**

---

## 5. Reglas de extracción

### 5.1 Orden de lectura

El OCR lee la factura **de izquierda a derecha y de arriba abajo**. No se configura.

### 5.2 Qué cuenta como coincidencia

El **primer texto** tiene que aparecer **completa** en el texto reconocido. El
segundo texto no participa de la coincidencia: es un título, no algo que se busque.

- **No distingue mayúsculas.** `TOTAL A PAGAR` encuentra `Total a pagar`.
- **No distingue tildes**, salvo que el contador lo apague con `#acentos=0`.
- **Salta las coincidencias que son parte de una palabra más larga.** `Total` no
  coincide con `SUBTOTAL` porque está pegado a otras letras. Sí coincide con
  `TOTAL IVA`, que es una palabra aparte: por eso `Total` puede quedar ambiguo, y
  conviene escribir el primer texto completo (§4.6).

### 5.3 Qué valor se queda

**El que viene a continuación de la coincidencia, en el orden de lectura.**

```
... SUBTOTAL 100,00 IVA 16,00 TOTAL 116,00 ...
                            ▲
   primer texto "Total"  +  valor "116,00"  +  segundo texto "Base imponible"
```

El espacio en blanco de la línea de arriba es de ejemplo: el valor es lo que el OCR
leyó después del primer texto, y ese valor es el que se coloca bajo el segundo
texto.

- **Si no encuentra nada**, el valor queda vacío. Nunca se inventa uno.
- **Si quedan varias coincidencias válidas**, la app **no adivina**: deja la columna
  vacía y marca `ambiguous:<primer texto>`.
- **Una factura con columnas vacías se exporta igual.** Sale con lo que encontró y
  lo demás en blanco, con su aviso (§7). Perder datos sin avisar sería peor.

### 5.4 Los números

**Por defecto, coma de miles y punto decimal**: `1,234.56` → `1234.56`. Es el formato
con el que Excel en español guarda los números, y el contador va a usarlos en
fórmulas.

El contador puede cambiarlo en la línea de formato (§4.4) si trabaja con facturas de
otro país. Con `#miles=. #decimal=,` el `1.234,56` se lee como `1234.56`.

Se normaliza porque si el texto queda crudo, Excel lo interpreta como texto y las
fórmulas no suman.

### 5.5 EasyOCR

Tesseract siempre primero. **EasyOCR entra solo por primer texto**, para los que
salieron vacíos o con confianza bajo el umbral. Es mucho más lento en CPU, y en
facturas impresas y nítidas suele rendir peor que Tesseract.

**Arranque perezoso**: los modelos se cargan la primera vez que un primer texto lo
necesita. Si los pesos no están descargados, se avisa y el escaneo sigue solo con
Tesseract.

---

## 6. El CSV de exportación

- **Formato:** CSV (`.csv`), una factura por fila.
- **Separador:** `,`. **Codificación:** `UTF-8` con BOM (`utf-8-sig`).
- **Una sola fila de cabecera**, con los segundos textos de `plantilla.csv`, en su
  orden.

```
fila 1:   los segundos textos, en el orden de plantilla.csv
fila 2+:  una factura por fila
```

- **El primer texto no aparece en el CSV.** Si no coincidió, su columna sale vacía.
- **El emparejamiento es por primer texto** (§1.3): el valor guardado se coloca en
  la columna cuyo primer texto coincide con el suyo, sin importar el orden ni el
  título.
- **Los `NULL` se escriben como celda vacía.** Nunca `None`, ni `NaN`, ni `nan`.
- Importes **normalizados** (§5.4) y redondeados a 2 decimales al escribir.
- **El texto crudo del OCR nunca aparece** (`CONSTITUTION.md` regla 4). Tampoco las
  rutas de imagen, ni la confianza, ni el estado de revisión, ni los primeros
  textos.

### 6.1 `avisos.csv`

Un archivo aparte, junto al CSV de facturas, porque **los avisos no pueden ir en el
Excel** (`CONSTITUTION.md` regla 4). Sin él, el contador escanea 20 facturas, cierra
la app, y se queda con columnas vacías sin saber qué se buscó en ninguna.

Una fila por aviso, con los dos textos de la línea que la originó:

```csv
invoice_id,frase,columna,motivo
142,Total a pagar,Base imponible,no_match
142,IVA,Monto del IVA,low_confidence
```

El Excel de facturas **no se toca**: los avisos van aparte, siempre.

---

## 7. Contrato de API (resumen)

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/health` | Estado del servicio y de la conexión a la base |
| `POST` | `/api/v1/invoices/scan` | Recibe la imagen, dispara la extracción y persiste. Devuelve el `invoice_id`, el `review_status` y los avisos |
| `GET` | `/api/v1/invoices` | Lista paginada con filtros por `review_status` y `issue_date` |
| `GET` | `/api/v1/invoices/{id}` | Detalle de una factura, con sus items e impuestos |
| `GET` | `/api/v1/export/invoices.csv` | Devuelve el CSV con los filtros aplicados |
| `GET` | `/api/v1/export/avisos.csv` | Devuelve los avisos del mismo lote |

**Sin autenticación.** El servidor escucha en `0.0.0.0` y toda la red Wi-Fi puede
exportar datos fiscales. Es una decisión consciente de una app local.

Los avisos viajan **también** en la respuesta del escaneo, con las dos mitades del
par:

```json
{
  "invoice_id": 1,
  "review_status": "needs_review",
  "warnings": ["no_match:Total a pagar (columna \"Base imponible\")"]
}
```

La foto del iPhone puede llegar en **HEIC**: se acepta y se convierte. La app
acepta `image/jpeg`, `image/png` y `image/heic`, y guarda **las dos imágenes**: la
original y la convertida.

Ningún endpoint expone el texto crudo del OCR (`CONSTITUTION.md` regla 4).