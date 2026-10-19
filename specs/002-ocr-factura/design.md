# Design 002 — Extracción de factura

**Spec:** [`spec.md`](./spec.md) · **Rol:** Agente 2

> No hay decisiones abiertas. Las cinco (O-01 a O-05) están resueltas y van
> escritas acá, sin `[PENDIENTE]`.

## Flujo

El contexto global del proyecto está en `AGENTS.md`. Esto es dónde vive cada paso.
La lista de columnas la lee la 004 y la pasa ya en memoria.

```
imagen ya convertida
   │
   ├─▶ preprocess     app/ocr/preprocess.py   5 pasos, orden fijo
   │
   ├─▶ tesseract      app/ocr/tesseract_engine.py   texto en orden de lectura
   │      │                                        + confianza 0-100
│      └─ primeros textos vacíos o bajo el umbral de .env
    │             │
    │             └─▶ easyocr  app/ocr/easyocr_engine.py   solo esos
    │
    ├─▶ extract        app/ocr/extract.py
    │      • por cada columna del contador:
    │          buscar SU PRIMER TEXTO, saltar coincidencias parciales,
    │          tomar el valor que sigue, normalizar el número
    │      • devolver el segundo texto intacto junto al valor
   │      • los 4 campos de control, con sus alias internos fijos
   │
   └─▶ ExtractionResult  (dataclass, va a la 003)
```

**No hay paso de validación contable.** Antes había `validate.py`, que armaba
`review_status` comparando base + impuestos contra el total. Eso **ya no existe**:
con columnas arbitrarias la app no sabe cuál valor es la base y cuál el IVA
(`SCHEMAS.md` §3.3). Los motivos que quedan se arman en `extract.py`, que es donde
se sabe qué pasó.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `app/ocr/preprocess.py` | Gris, ruido, inclinación, umbral, escalado |
| `app/ocr/tesseract_engine.py` | Texto en orden de lectura y confianza. `--psm 6 --oem 3 -l eng+spa` |
| `app/ocr/easyocr_engine.py` | Igual, arranque perezoso, `gpu=False`, `['es','en']` |
| `app/ocr/extract.py` | **Búsqueda del primer texto de cada columna, valores y avisos** |
| `app/ocr/normalize.py` | Separadores de miles y decimal, fechas a ISO |
| `app/models/invoice.py` | `Columna`, `ExtractionResult`, `ExtractedValue`, `ControlFields` |

`extract.py` es el corazón de la feature. Antes hacía un parseo que conocía 13 campos
fijos; después solo buscaba una lista de cadenas; ahora busca **pares** y devuelve
los dos lados intactos.

## `app/models/invoice.py`

```python
@dataclass(frozen=True)
class Columna:
    frase: str      # primer texto: lo que se busca en la foto
    encabezado: str # segundo texto: lo que va en la fila 1 del Excel
    linea: int      # número de línea en el archivo del contador, para señalar
                    # errores. En COLUMNAS_POR_DEFECTO es un número sin
                    # correspondencia real, y nunca se muestra
```

Los dos primeros campos se llaman `frase` y `encabezado` porque son los nombres que
usa el `JSONB` de `invoices.values` (`SCHEMAS.md` §3.1). Los nombres de campo no se
cambian; en la documentación el primero es el **primer texto** y el segundo el
**segundo texto**.

`Columna` es **inmutable**: los dos textos no se tocan una vez parseados.
`frozen=True` porque si alguien modifica el segundo texto por el camino, el Excel y el
valor dejan de corresponder.

La construye la 004. La 002 no la arma: recibe la lista.

**El `=` solo marca dónde termina el primer texto.** Nunca se busca, nunca se muestra,
nunca significa nada. Es el separador entre las dos mitades, y quien lo decide es el
`split("=", 1)` de la 004.

**La lista puede venir del archivo del contador o de `COLUMNAS_POR_DEFECTO`, y a la
002 le da igual.** No lee el archivo, no sabe si el contador escribió algo y no tiene
ningún default propio. Solo recibe columnas y devuelve columnas. Por eso una factura
con el archivo vacío y otra con una línea del contador se procesan con el mismo
código.

## `app/ocr/extract.py`

### Buscar el primer texto

```
texto OCR:  "RIF: J-31245678-7   SUBTOTAL 100,00   TOTAL 116,00"
columna:    Columna(frase="Total", encabezado="Base imponible", linea=10)
```

1. **Normalizar para comparar**: minúsculas siempre. Las tildes **salvo que el
   contador haya puesto `#acentos=0`** (`SCHEMAS.md` §4.4). Los espacios
   interiores **no** se colapsan y la puntuación **no** se quita, para que
   `Total (Bs)` siga siendo `Total (Bs)`.
2. **Buscar el primer texto completo**, como palabra completa y no como fragmento.
3. **Saltar coincidencias parciales**: si la coincidencia está pegada a letras
   anteriores o posteriores, no cuenta. Así `Total` no coincide con `SUBTOTAL` ni
   con `Subtotal`, porque están pegadas. Sí coincide con `TOTAL IVA`, que es una
   palabra aparte: por eso puede quedar ambiguo (`SCHEMAS.md` §4.6). → CA-07
4. **Quedarse con el valor que sigue**: el primer token numérico o fecha que
   aparece después de la coincidencia, en el orden de lectura.
5. **Si hay varias coincidencias válidas, no adivinar.** Dejar vacío y marcar
   `ambiguous:Total (columna "Base imponible")`. → `SCHEMAS.md` §5.3, CA-34

**El segundo texto no entra en ninguno de estos pasos.** Se copia tal cual al
resultado. La 004 es la que lo escribe en el CSV, y solo ella.

### Normalizar el número

El formato lo pone el contador en la línea de configuración, y llega a `normalize`
desde la 004. Por defecto **coma de miles y punto decimal** (`SCHEMAS.md` §5.4).

```
#miles=, #decimal=.      1,234.56   → 1234.56
#miles=. #decimal=,      1.234,56   → 1234.56
```

- Separador de miles + separador decimal → `1234.56`
- Sin separador de miles → `100.00` → `100.0`
- Un número pegado a una letra (`100.00Bs`) → se separa
- Un porcentaje (`16%`) → se queda el `16`
- **El signo se queda.** `-45,00` devuelve `-45,00`. La app **no le quita el menos
  a nada** ni se lo pone. → CA-54

Se normaliza porque si el texto queda crudo, Excel lo interpreta como texto y las
fórmulas del contador no suman.

**Riesgo asumido:** un valor que no sea un número puro puede no parsearse y quedar
vacío. Es preferible una columna vacía a un número incorrecto.

**Un `NaN` o un `inf` no llegan al CSV.** Si un token raro produce uno, la columna
sale vacía, no `#N/A`.

### Los 4 campos de control

Se buscan con alias internos **fijos**, sin que el contador los pida y **sin par**
(`SCHEMAS.md` §2):

| Campo | Alias internos |
|---|---|
| `supplier_rif` | `RIF` |
| `numero` | `N° factura`, `Nº factura`, `No. factura`, `Factura N°` |
| `issue_date` | `Fecha` |
| `serie` | Se separa de `numero` si viene `001-00001234` |

Son palabras internas, **no sugerencias**: no se le muestran al contador, no
aparecen en su Excel, y no se registran en `plantilla.csv`.

**No ocupan columna.** Vuelven en `ExtractionResult.control`, no en `.values`. Si el
contador escribe `RIF = RIF del proveedor`, esa es su columna y es otra cosa; los
dos RIF pueden coincidir y no se mezclan.

**Si `supplier_rif` no se puede leer, se devuelve `None` y la 003 guarda la
factura igual.** La 002 no lanza ni descarta nada; solo avisa con
`unreadable_rif`, y el riesgo lo acepta el contador al ver el aviso. → CA-52

## El objeto de salida

```python
@dataclass
class ExtractedValue:
    encabezado: str       # segundo texto: el nombre de la columna, intacto
    value: str | None     # None cuando no se encontró. Nunca inventado
    confidence: float     # 0-100
    engine: str           # "tesseract" | "easyocr"

@dataclass
class ControlFields:
    supplier_rif: str | None
    serie: str | None
    numero: str | None
    issue_date: str | None

@dataclass
class ExtractionResult:
    values: list[ExtractedValue]   # uno por columna, en el orden de la lista
    control: ControlFields         # los 4, nunca exportados
    items: list[InvoiceLine]
    raw_text: str                  # NUNCA sale por la API. Va a ocr_runs solo
                                   # si algún valor salió dudoso
    engines_used: list[str]
```

`ExtractedValue` **no lleva el primer texto**. La 004 ya tiene la lista de columnas y
solo necesita el segundo texto para la fila 1 y el valor para la fila de la factura.
Llevar el primer texto sería duplicar datos que ya están en `plantilla.csv`.

**El primer texto no se pierde igual.** La 003 lo recupera de la lista de columnas
que ya tiene y lo arma con el valor al escribir el `JSONB` de `invoices`, que es
donde sí se guarda, porque es la clave del emparejamiento (`SCHEMAS.md` §3.1).

`values` viene en el mismo orden que las columnas, para que la 004 no tenga que
reordenar nada. → CA-36

`raw_text` viaja porque la 003 lo guarda en `ocr_runs`, pero ningún endpoint lo
devuelve (`CONSTITUTION.md` regla 4).

## Los avisos

Se arman en `extract.py`, que es donde se sabe qué pasó. Los que dependen de la
búsqueda llevan **las dos mitades del par**, porque el Excel del contador no muestra
el primer texto (`SCHEMAS.md` §1.2):

```
no_match:Total a pagar (columna "Base imponible")
ambiguous:Total (columna "Total a pagar")
low_confidence
unreadable_rif
```

Múltiplos motivos van separados por `;`.

**`unbalanced_total` ya no existe.** La app no intenta cuadrar nada, y no tiene con
qué: entre las columnas del contador puede no haber ninguna base ni ningún IVA. → CA-56

## Umbral de confianza

Vive en `.env`, como `OCR_CONFIDENCE_THRESHOLD`. EasyOCR devuelve confianza en 0-1 y
Tesseract en 0-100, así que hay que **normalizar a 0-100 antes de comparar**.

Un valor por debajo del umbral marca `low_confidence`, **y es la razón por la que
`raw_text` se guarda**: si algo salió dudoso, el texto reconocido es lo único que
permite saber por qué.

## EasyOCR

**Arranque perezoso.** Los modelos ocupan cientos de MB en memoria. Se cargan la
primera vez que un primer texto lo necesita, y `EASYOCR_MODEL_DIR` dice dónde viven los
pesos ya descargados.

**Si los pesos no están descargados, se avisa y se devuelve `None`.** La 003
responde igual y el escaneo sigue con Tesseract solamente.

## Configuración

| Variable | Para qué | Estado |
|---|---|---|
| `TESSERACT_CMD` | Ruta del binario | Conocida |
| `EASYOCR_MODEL_DIR` | Dónde viven los pesos descargados | Por defecto en la carpeta de la app |
| `OCR_CONFIDENCE_THRESHOLD` | Umbral de `low_confidence` | En `.env`, por defecto `60` |

El formato numérico y el manejo de tildes **no vienen de `.env`**: vienen de la
línea de configuración de `plantilla.csv`, que es del contador
(`SCHEMAS.md` §4.4).