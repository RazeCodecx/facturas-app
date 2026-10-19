# Design 004 — Plantilla y CSV

**Spec:** [`spec.md`](./spec.md)

> Las cuatro decisiones (E-01 a E-04) están resueltas. No hay `[PENDIENTE]`.
> Lo que gobierna esta feature es **el emparejamiento por primer texto** y **una excepción
> acotada** a la regla de no escribir el archivo.

## Módulos

| Archivo | Responsabilidad |
|---|---|
| `app/export/plantilla.py` | Lee `plantilla.csv`, **parsea los pares y las líneas `#`**. Escribe **solo** si el archivo está vacío |
| `app/export/csv.py` | **Único** punto que emite el CSV de facturas. **Empareja por primer texto** |
| `app/export/avisos.py` | Emite `avisos.csv` |
| `app/api/export.py` | `GET /api/v1/export/invoices.csv` y `.../avisos.csv` |

`plantilla.py` sabe del archivo y del formato del par. `csv.py` sabe del formato de
salida y **no abre el archivo**.

## `app/export/plantilla.py`

Devuelve `list[Columna]`, en el orden de las líneas.

```python
def leer_columnas() -> list[Columna]: ...
```

`Columna` está definida en `app/models/invoice.py` y la construyen las dos features:
la 004 la arma del archivo y la 002 la consume. No se duplica el tipo.

### `COLUMNAS_POR_DEFECTO`

```python
COLUMNAS_POR_DEFECTO: list[Columna] = [
    Columna("RIF", "RIF del proveedor", 1),
    Columna("Numero de factura", "Numero", 2),
    Columna("Fecha", "Fecha de emision", 3),
    Columna("Fecha vencimiento", "Fecha de vencimiento", 4),
    Columna("Base", "Base imponible", 5),
    Columna("Monto exento", "Monto exento", 6),
    Columna("IVA", "Monto del IVA", 7),
    Columna("Monto IFA", "Monto IFA", 8),
    Columna("Retenciones", "Retenciones de IVA", 9),
    Columna("Total", "Total a pagar", 10),
    Columna("Moneda", "Moneda", 11),
]
```

**Estos son los referentes, y viven aquí y no en `plantilla.csv`.**

El archivo se entrega vacío a propósito. Si la app dejara ejemplos ahí, el contador
los editaría sin querer y cada ejemplo se convertiría en una columna que no pidió. Un
archivo vacío no se puede editar por error.

Se usan **solo** si el contador no escribió ninguna línea. El `linea` de los defaults
es un número inventado que no corresponde a nada del archivo: **no se muestra en
ningún mensaje de error**, porque esos mensajes hablan del archivo del contador y
allí no existen esas líneas.

### Cuál de los dos juegos gana

```
plantilla.csv tiene líneas   →  las del contador.  Punto.
plantilla.csv está vacío     →  COLUMNAS_POR_DEFECTO
plantilla.csv no existe      →  error
```

No hay mezcla. **Si el contador escribió una línea, esa es la única columna que
existe.** La app no le agrega las suyas, no le completa las que le faltan y no le
avisa que le faltan. → CA-46, CA-47

Que el contador escriba **una sola línea** es un archivo válido: es una app para un
contador que puede querer una sola columna, y una sola columna es un resultado
correcto.

### Parsear una línea

```
"RIF del proveedor = "          → Columna("RIF del proveedor", "RIF del proveedor", 1)
"RIF = RIF del proveedor"       → Columna("RIF", "RIF del proveedor", 1)
"Total = Base imponible"        → Columna("Total", "Base imponible", 10)
"Moneda ="                      → Columna("Moneda", "Moneda", 11)
```

1. **Partir por el primer `=`.** `linea.split("=", 1)`. El `=` **solo marca dónde
   termina el primer texto**: no se busca, no se muestra, no significa nada. Por eso
   el segundo texto puede llevar espacios: `Total = Base imponible`.
2. **El primer texto es la `frase`.** Se recorta el espacio de los dos lados. Si
   queda vacío, error.
3. **El segundo texto es el `encabezado`.** Se recorta. Si queda vacío, **se usa el
   primer texto**. Es el atajo de `SCHEMAS.md` §4.1. → CA-40
4. **Líneas vacías se ignoran**, para que el contador pueda separar bloques.
5. El texto se conserva **tal cual**, con sus tildes y su idioma. No se quita ni se
   agrega nada. Solo se recorta el espacio de los bordes.

### Cuándo entra el juego por defecto

Después de parsear, **antes de devolver**:

```
columnas = parseadas_del_archivo()
if columnas == []:
    return COLUMNAS_POR_DEFECTO
return columnas
```

Solo cuando no quedó **ninguna** línea de columnas. Un archivo con dos líneas
válidas devuelve dos columnas, aunque el default tenga once. → CA-45, CA-46

### La excepción: la línea de formato

`plantilla.csv` se lee y **nunca se escribe**, con **una única excepción** que el
usuario autorizó: si el archivo está **completamente vacío**, la app le escribe la
línea de formato con su mensaje, para que el contador sepa qué acepta.

```
completamente vacío  →  escribe la línea de formato, una sola vez
tiene algo           →  no escribe NADA, jamás
```

**Después de escribirla, la app se olvida.** No vuelve a mirar si el archivo quedó
vacío otra vez, y no actualiza la línea si el contador la borró. Escribir el
archivo es una cortesía de instalación, no una función del sistema.

```python
MENSAJE_FORMATO = (
    "# Formato de numeros / Number format\n"
    "# miles   separador de miles / thousands separator   por defecto / default ,\n"
    "# decimal separador decimal / decimal separator     por defecto / default .\n"
    "# acentos 1 ignora tildes al buscar / ignore accents 0 no las ignora / keep them\n"
)
```

Sin esas tres líneas, el contador abre el archivo y ve tres columnas vacías, sin
saber que escribe `primer texto = segundo texto` ni que el `=` es un separador. Un
archivo vacío es correcto pero inútil, y esto es lo que lo hace útil **una vez**. → CA-62

### Las líneas de configuración

Cualquier línea que empiece con `#` es configuración, **esté donde esté**. No
produce columna.

```
#miles=. #decimal=, #acentos=1
```

Se leen **todas**, y la última que aparece de cada opción gana, para que el contador
pueda cambiar una sin borrar la otra.

| Opción | Valores | Por defecto |
|---|---|---|
| `miles` | Un carácter | `,` |
| `decimal` | Un carácter | `.` |
| `acentos` | `1` o `0` | `1` |

**Una línea de configuración mal escrita no es error.** Se usa el valor por defecto
y la app sigue. La diferencia con los errores de columna es que **una línea de
formato no cambia qué se busca ni qué se muestra**, solo cómo se lee un número, y eso
el contador lo ve en su Excel. Un `=` faltante sí cambia el resultado, y en
silencio. → CA-66

Los valores por defecto salen de esta tabla, **no de `.env`**: son del contador.
`OCR_CONFIDENCE_THRESHOLD` sí vive en `.env`, porque es cosa de la 002, no del
archivo.

### Los cuatro errores de columna

Todos son culpa del contador. Todos se paran **antes de procesar nada**, y el
mensaje dice **qué línea** y **qué escribir**.

| Situación | Mensaje al contador |
|---|---|
| Sin `=` | `plantilla.csv línea 4: falta el "=". Escriba "primer texto = segundo texto".` |
| Dos `=` o más | `plantilla.csv línea 4: hay más de un "=". Solo uno por línea.` |
| Primer texto repetido | `plantilla.csv: "Total" está en las líneas 3 y 10. Un primer texto no se repite.` |
| Primer texto vacío | `plantilla.csv línea 4: no dice qué buscar antes del "=".` |

Que el error diga la línea exacta no es un detalle: el contador va a tener un archivo
de diez u once líneas y no va a contar líneas para encontrar el problema.

**Estos mensajes nunca mencionan `COLUMNAS_POR_DEFECTO`.** Hablan del archivo del
contador, y los defaults no tienen líneas ahí. Si el contador deja el archivo vacío
y escanea, no recibe ningún aviso: funciona.

**Las líneas `#` no producen columna, así que no pueden dar ninguno de estos cuatro
errores.** Una línea `#cualquier cosa` es configuración mal escrita: se ignora y se
usa el default.

**Un primer texto repetido es error**, no aviso. → CA-41 Dos columnas con el mismo
valor de origen no le aportan nada al contador y hacen el Excel más difícil de leer.
Para dejar el nombre tal cual, `Total =`, que no repite el primer texto.

**El segundo texto sí puede repetirse**, porque lo que no puede repetirse es el
primer texto. `Total = Base imponible` y `Base = Base imponible` son dos columnas
válidas con dos primeros textos distintos.

### Codificación

Se lee con BOM. Si el contador lo editó en Excel, el BOM sigue ahí; si lo editó en
otro editor puede no estar, y sin él los acentos se rompen.

**La app no escribe el archivo, salvo la excepción de arriba.** → `CA-32`

## `app/export/csv.py`

```
fila 1:   los segundos textos, en el orden de las líneas del archivo
fila 2+:  una factura por fila
```

### El emparejamiento es por primer texto

Esta es la parte que hace que todo lo demás sea seguro. **El valor no se coloca por
posición, se coloca por primer texto.**

Cada valor viene guardado en `invoices.values` con el primer texto que lo produjo
(`SCHEMAS.md` §3.1). Al exportar:

```
para cada columna del archivo de HOY:
    busca en values el objeto cuyo primer texto coincide
    si está, escribe su value en esa columna
    si no, escribe celda vacía
```

**Por qué no por posición.** El contador puede editar `plantilla.csv` después de
escanear. Si el valor fuera por posición, esto pasaría:

```
Escaneó con    Total = Base imponible
               IVA   = Monto del IVA
Editó a        IVA   = Monto del IVA      ← movió una línea de lugar
               Total = Base imponible
Exportaría     | Base imponible | Monto del IVA |
               | 116,00         | 16,00         |
```

El 116,00 y el 16,00 quedan intercambiados, con la factura guardada como
correcta, y **sin un solo aviso**. Con emparejamiento por primer texto, cada valor
encuentra su columna por el primer texto que lo produjo y el orden no importa.
→ CA-60

Si el contador **borra** una línea, la columna desaparece y el valor se queda
guardado sin usarse. Nunca se corre a la columna vecina. → CA-61

La comparación de primeros textos usa la **misma normalización** que la búsqueda:
sin mayúsculas, y sin tildes si `acentos=1`. Si el contador apaga los acentos en el
archivo, el emparejamiento también los apaga.

- **Una sola fila de cabecera**, con los segundos textos. Ya no hay fila
  de variables. → `SCHEMAS.md` §6
- **El primer texto no aparece.** Ni en la fila 1, ni en ninguna celda. → CA-42
- `csv.writer` de la biblioteca estándar, separador `,`. Sin `pandas`.
- Encoding **`utf-8-sig`**. Sin el BOM, Excel abre los acentos y la `ñ` como
  caracteres raros. → CA-16
- `Content-Type: text/csv; charset=utf-8`.
- Los valores salen en **el orden de las líneas del archivo de hoy**, no en el
  orden en que se escaneó. → CA-19
- Los `None` se escriben como celda vacía. **Nunca** `None`, ni `NaN`, ni `nan`.
  → CA-35, CA-67
- **Una factura con columnas vacías se exporta igual.** Sale con lo que encontró y
  lo demás en blanco. Perderla sería peor que dejarla incompleta. → CA-67
- Redondeo a 2 decimales **solo al escribir**, nunca en la base.
- `csv.py` **no importa** `ocr_runs` ni escribe `plantilla`. → CA-20

### Se exportan todas las facturas

**Incluidas las `needs_review`.** Exportar solo las `ok` haría que el contador
perdiera datos sin enterarse, y una factura dudosa es justo la que él quiere
revisar. → CA-17

**El archivo de salida ya no sirve como plantilla.** Antes el contador podía copiar
la fila de variables de un CSV viejo sobre su archivo. Ahora no: la fila 1 del CSV
sale de los segundos textos de su propio archivo, y no hay fila de variables que copiar.

## `app/export/avisos.py` — el archivo de avisos

```
GET /api/v1/export/avisos.csv
```

Un archivo **aparte**, con los mismos filtros que el de facturas, y **con el mismo
BOM**. `CONSTITUTION.md` regla 4 prohíbe poner avisos en el Excel, y sin este archivo
el contador escanea 20 facturas, cierra la app, y se queda con columnas vacías sin
saber **qué se buscó en ninguna**. → CA-63

```csv
invoice_id,frase,columna,motivo
142,Total a pagar,Base imponible,no_match
142,IVA,Monto del IVA,low_confidence
```

La fila 1 son palabras fijas de la app, **no columnas del contador**: es una tabla
de diagnóstico, no el archivo que él edita. El primer texto sí va aquí, porque este
archivo no lo edita nadie.

Sale **siempre**, aunque no haya avisos: cabecera y nada más. Un contador que abre
un archivo vacío no sabe si falló la app o si todo salió bien.

## Qué no va nunca

- **El primer texto buscado**, ni en la fila 1 ni en ninguna celda.
- **`raw_text` de `ocr_runs`.**
- **Rutas de imagen.** `original_path` y `converted_path` son internas.
- **Confianza por valor.** Es dato técnico de la 002.
- **`review_status` y `review_reason`.** El contador ve las columnas vacías y
  consulta los avisos por separado (`SCHEMAS.md` §3.2, §6).

`CONSTITUTION.md` regla 4.

## Filtros

Los mismos que `GET /api/v1/invoices`: `review_status`, `issue_date`. Se aplican
en el SELECT de la 001, nunca leyendo todo y filtrando en Python. → `CA-18`

## Orden de implementación

`plantilla.py` va primero, con sus tests, antes que `csv.py`. Si el CSV se escribe
sin el archivo leído, un error del contador se descubre tarde y se manifiesta como
una columna corrida, con el nombre equivocado o sin nombre. Que es el peor síntoma
posible, porque el contador no sabe si la app falló o si él escribió mal.

## Configuración

| Variable | Para qué | Estado |
|---|---|---|
| `PLANTILLA_PATH` | Ruta de `plantilla.csv` | Fija: raíz del proyecto. **No configurable** |

**El formato numérico y el manejo de tildes no vienen de `.env`.** Vienen de las
líneas `#` del archivo, que son del contador (`SCHEMAS.md` §4.4).
