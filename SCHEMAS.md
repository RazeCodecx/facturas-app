# SCHEMAS.md — Contrato de datos

> Leer junto con `AGENTS.md` (roles) y `CONSTITUTION.md` (reglas).

---

## 1. Cómo funciona la extracción

Cada línea de `plantilla.csv` describe una columna del Excel mediante **tres
cosas**:

| | |
|---|---|
| **Primer texto** | Lo que se busca en la foto. Lo escribe el contador |
| **Valor** | Lo que se lee a continuación del primer texto |
| **Segundo texto** | El título de la columna en el Excel. Lo escribe el contador |

El `=` separa el primer texto del segundo texto y **solo marca dónde termina el
primer texto**. No se busca, no se muestra y no significa nada. Si el segundo texto
queda vacío, se usa el primer texto como título.

**No hay columnas de fábrica.** La app no busca RIF, fecha, número de factura,
serie ni ningún otro dato por su cuenta. Solo busca los primeros textos que el
contador escribió en `plantilla.csv`.

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
campo `encabezado` de cada objeto de `invoices.values` (§3.1).

### 1.1 Quién traduce

**El contador no traduce nada. Traducen los módulos internos.**

| | Qué hace |
|---|---|
| `plantilla.csv` | Solo lo que el contador escribió. Los dos textos, tal cual |
| `app/ocr/extract.py` | Busca cada primer texto en la foto y saca el valor |
| `app/export/csv.py` | Coloca el valor bajo el segundo texto que le corresponde |

### 1.2 Lo que va al Excel y lo que no

| | Visible en el Excel |
|---|---|
| **Primer texto** | **No.** Solo se busca |
| **Valor** | **Sí.** Es el contenido de la columna |
| **Segundo texto** | **Sí.** Es el título de la columna |
| **Estado de revisión y avisos** | **No** (§7) |

La fila 1 del CSV lleva **solo los segundos textos**. Si un primer texto no
coincide, su columna sale vacía y el motivo llega en el aviso (§6.1), donde sí se
nombra el primer texto.

### 1.3 El emparejamiento es por primer texto

Cada factura guarda, junto a su valor, **el primer texto que lo produjo** (§3). Al
exportar, la app no usa la posición que tenía el valor en el archivo, sino el primer
texto. Por eso el contador puede renombrar, reordenar o agregar columnas después de
escanear sin que los valores se corran de columna. Si **borra** una línea, esa
columna desaparece del CSV y el valor queda guardado sin usarse.

---

## 2. Sin campos de control

La app **no** extrae RIF, serie, número de factura ni fecha de emisión por su
cuenta. Si el contador los quiere, los pide como cualquier otra columna:

```
RIF = RIF del proveedor
Fecha = Fecha de emisión
```

En ese caso el valor se guarda tal como se leyó, porque el contador lo pidió de
forma explícita.

### 2.1 Sin deduplicación

Cada foto crea una fila. Si la misma foto se envía dos veces, se registra dos
veces. La app no compara imágenes, textos ni datos de la factura.

---

## 3. Tablas

| Tabla | Contenido |
|---|---|
| `invoices` | `id`, `review_status`, `review_reason`, **`values JSONB`** y `created_at` |
| `ocr_runs` | Rutas de imagen, texto crudo **condicional**, confianza, operador, fecha. **Interno** |

No existen `invoice_items`, `taxes` ni `fiscal_profiles`. No hay catálogos por
país ni datos prefabricados.

### 3.1 `invoices.values` — el JSONB

Un objeto por valor extraído, **con el primer texto adentro**:

```json
[
  { "frase": "Total", "encabezado": "Total a pagar", "value": 116.0,
    "confidence": 92.0 },
  { "frase": "RIF",   "encabezado": "RIF del proveedor", "value": "J-31245678-7",
    "confidence": 88.5 }
]
```

- **El primer texto (`frase`) es la clave de emparejamiento** (§1.3).
- El segundo texto (`encabezado`) se guarda como estaba **en el momento del
  escaneo**, para poder reconstruir el CSV aunque el archivo ya no exista.
- El motor **no se guarda por valor**. `ocr_runs.engine_version` conserva el motor
  principal de la corrida, como dato interno.
- `value` es un **número** cuando el valor leído es numérico. Es **texto** solo
  cuando el contador pidió explícitamente una columna no numérica (RIF, moneda,
  fecha escrita).

**El JSONB nunca se purga.** El contador puede volver a exportar cuando quiera.

### 3.2 Tipos numéricos

`float` en Python y JSONB en PostgreSQL, para que los importes enteros se conserven
exactos. Redondeo a 2 decimales solo al exportar, nunca dentro de la base.

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

Los avisos de `no_match` y `ambiguous` llevan **las dos mitades del par**:

```
no_match:Total a pagar (columna "Base imponible")
```

**No existe `unbalanced_total`.** Con columnas arbitrarias la app no puede saber
cuál valor es la base y cuál el IVA. El cuadre contable lo hace el contador en su
Excel.

**Ninguno de estos motivos aparece en el Excel del contador.** Van por el canal de
avisos (§6.1).

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
- **El `=` solo marca dónde termina el primer texto.**
- Se parte por el **primer** `=`, así que el segundo texto puede llevar espacios.
- **El primer texto es lo que se busca**, escrito tal como el contador lo espera
  impreso en la factura.
- **El segundo texto es el título del Excel.** Texto libre.
- **Si el segundo texto está vacío**, se usa el primer texto como título.
- **El orden de las líneas es el orden de las columnas** del Excel.
- **Para quitar una columna, se borra la línea.**
- **Líneas vacías se ignoran**, para que el contador pueda separar bloques.
- **El primer texto no puede repetirse.** Si se repite, es error (§4.5).
- **Codificación `UTF-8` con BOM.**
- **El signo de los importes se queda tal cual.**

### 4.2 El archivo se entrega vacío

`plantilla.csv` se entrega vacío. La app tiene una **excepción única**: si lo
encuentra completamente vacío, escribe la línea de formato con su mensaje para que
el contador sepa qué acepta el archivo. Después de eso **nunca más lo toca**.

Un archivo sin columnas **es error**: la app no inventa columnas ni usa un juego
por defecto.

### 4.3 Las líneas que empiezan con `#`

Cualquier línea que empiece con `#` es de **configuración**, esté donde esté. Son
las únicas líneas que no producen columnas.

| Opción | Qué hace | Por defecto |
|---|---|---|
| `miles` | Separador de miles | `,` |
| `decimal` | Separador decimal | `.` |
| `acentos` | `1` ignora tildes al buscar, `0` no las ignora | `1` |
| `excel` | Ruta absoluta del `.xlsx` de salida | Sin salida |

Ejemplo:

```
#miles=. #decimal=, #acentos=1
#excel=C:\Contabilidad\facturas.xlsx
```

Una línea de configuración mal escrita **no es error**: la app usa el valor por
defecto y sigue.

### 4.4 Casos de error

| Situación | Qué hace la app |
|---|---|
| Archivo ausente | Error diciendo que falta `plantilla.csv` |
| Archivo vacío o solo con líneas `#` | Error pidiendo al menos una columna |
| Línea sin `=` | Error: *falta el `=`* |
| Línea con dos `=` o más | Error: *solo un `=` por línea* |
| Primer texto repetido en dos líneas | Error, nombrando **las dos** líneas |
| Primer texto vacío | Error: *no dice qué buscar* |
| Línea de formato mal escrita | **No es error.** Usa el valor por defecto |

### 4.5 Un primer texto específico coincide menos

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

El **primer texto** tiene que aparecer **completo** en el texto reconocido. El
segundo texto no participa de la coincidencia: es un título, no algo que se busque.

- **No distingue mayúsculas.**
- **No distingue tildes**, salvo que el contador lo apague con `#acentos=0`.
- **Salta las coincidencias que son parte de una palabra más larga.**

### 5.3 Qué valor se queda

**El primer número que aparezca a continuación de la coincidencia, en la misma
línea o en la siguiente, en el orden de lectura.**

```
... SUBTOTAL 100,00 IVA 16,00 TOTAL 116,00 ...
                            ▲
   primer texto "Total"  +  valor "116,00"  +  segundo texto "Base imponible"
```

Si después de la frase no hay ningún número, la app toma el primer token de texto
y lo guarda tal cual. Eso permite columnas como `RIF = RIF del proveedor`.

- **Si no encuentra nada**, el valor queda vacío. Nunca se inventa uno.
- **Si quedan varias coincidencias válidas**, la app **no adivina**: deja la columna
  vacía y marca `ambiguous:<primer texto>`.
- **Una factura con columnas vacías se exporta igual.**

### 5.4 Los números

**Por defecto, coma de miles y punto decimal**: `1,234.56` → `1234.56`.

El contador puede cambiarlo con `#miles=. #decimal=,` para leer `1.234,56` como
`1234.56`. La app no adivina el separador.

Las fechas **no se convierten**. Si el contador pide una fecha, se guarda el texto
tal como se leyó.

### 5.5 EasyOCR

Tesseract siempre primero. **EasyOCR entra solo por primer texto**, para los que
salieron vacíos o con confianza bajo el umbral. Es mucho más lento en CPU.

**Arranque perezoso**: los modelos se cargan la primera vez que un primer texto lo
necesita. Si los pesos no están descargados, se avisa y el escaneo sigue solo con
Tesseract.

---

## 6. El CSV de exportación

- **Formato:** CSV (`.csv`), una factura por fila.
- **Separador:** `,`. **Codificación:** `UTF-8` con BOM (`utf-8-sig`).
- **Una sola fila de cabecera**, con los segundos textos de `plantilla.csv`, en su
  orden.

- **El primer texto no aparece en el CSV.**
- **El emparejamiento es por primer texto** (§1.3).
- **Los `NULL` se escriben como celda vacía.**
- Importes **normalizados** (§5.4) y redondeados a 2 decimales al escribir.
- Los valores de texto se escriben tal cual.
- **El texto crudo del OCR nunca aparece**, ni las rutas, ni la confianza, ni el
  estado de revisión.

### 6.1 `avisos.csv`

Un archivo aparte, junto al CSV de facturas:

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
| `GET` | `/api/v1/invoices` | Lista paginada con filtro por `review_status` |
| `GET` | `/api/v1/invoices/{id}` | Detalle de una factura |
| `GET` | `/api/v1/export/invoices.csv` | Devuelve el CSV con el filtro aplicado |
| `GET` | `/api/v1/export/avisos.csv` | Devuelve los avisos del mismo lote |

**Sin autenticación.** El servidor escucha en `0.0.0.0` y toda la red Wi-Fi puede
exportar datos fiscales. Es una decisión consciente de una app local.

La foto del iPhone puede llegar en **HEIC**: se acepta y se convierte. La app
acepta `image/jpeg`, `image/png` y `image/heic`, y guarda **las dos imágenes**: la
original y la convertida.

Ningún endpoint expone el texto crudo del OCR (`CONSTITUTION.md` regla 4).
