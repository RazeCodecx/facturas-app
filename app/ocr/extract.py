"""Búsqueda del primer texto de cada columna, valores y avisos.

Es el corazón de la 002. Recibe texto ya reconocido, no imágenes: por eso se
prueba sin Tesseract ni EasyOCR reales (`specs/002-ocr-factura/tasks.md` T4.1).

Reglas (`SCHEMAS.md` §5): coincidencia completa, sin distinguir mayúsculas, sin
distinguir tildes salvo `#acentos=0`, sin coincidencias parciales, y **nunca se
adivina**.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.models.invoice import (
    Columna,
    ControlFields,
    ExtractedValue,
    ExtractionResult,
    Formato,
)
from app.ocr.normalize import fecha, formatear_numero, numero
from app.ocr.tesseract_engine import Lectura

ALIAS_RIF = ("RIF",)
ALIAS_NUMERO = ("N° factura", "Nº factura", "No. factura", "Factura N°")
ALIAS_FECHA = ("Fecha",)

_ESTADO_OK = "ok"
_ESTADO_SIN_COINCIDENCIA = "no_match"
_ESTADO_AMBIGUO = "ambiguous"


@dataclass(frozen=True)
class _Hallazgo:
    """Resultado interno de buscar una columna en una lectura."""

    estado: str
    valor: str | None = None
    linea: int | None = None


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(caracter for caracter in descompuesto if not unicodedata.combining(caracter))


def _normalizar(texto: str, acentos: bool) -> tuple[str, list[int]]:
    """Pasa el texto a minúsculas (y sin tildes) conservando el índice original.

    Devuelve el texto normalizado y un mapa posición normalizada → posición
    original, para poder volver al texto real y leer el valor que sigue.
    """
    partes: list[str] = []
    mapa: list[int] = []
    for indice, caracter in enumerate(texto):
        limpio = caracter.casefold()
        if acentos:
            limpio = _sin_tildes(limpio)
        for normalizado in limpio:
            partes.append(normalizado)
            mapa.append(indice)
    return "".join(partes), mapa


def _normalizar_frase(frase: str, acentos: bool) -> str:
    texto, _ = _normalizar(frase, acentos)
    return texto


def normalizar_frase(frase: str, acentos: bool) -> str:
    """Normaliza un primer texto igual que la búsqueda, para emparejar en el CSV."""
    return _normalizar_frase(frase, acentos)


def _coincidencias(texto: str, frase: str) -> list[tuple[int, int]]:
    """Busca la frase completa, sin que sea parte de una palabra más larga."""
    if not frase:
        return []

    izquierda = r"(?<!\w)" if frase[0].isalnum() or frase[0] == "_" else ""
    derecha = r"(?!\w)" if frase[-1].isalnum() or frase[-1] == "_" else ""
    patron = re.compile(f"{izquierda}{re.escape(frase)}{derecha}")
    return [(coincidencia.start(), coincidencia.end()) for coincidencia in patron.finditer(texto)]


def _primer_valor(segmento: str, formato: Formato) -> str | None:
    """Devuelve el primer número o fecha del segmento, ya normalizado."""
    for token in re.split(r"\s+", segmento):
        if not token:
            continue
        valor_fecha = fecha(token)
        if valor_fecha is not None:
            return valor_fecha
        valor_numero = numero(token, formato)
        if valor_numero is not None:
            return formatear_numero(valor_numero)
    return None


def _valor_despues(texto: str, fin: int, formato: Formato) -> tuple[str, int] | None:
    """Busca el valor en la misma línea de la coincidencia y, si no hay, en la siguiente."""
    linea = texto.count("\n", 0, fin)
    segmentos = texto[fin:].split("\n")
    for desplazamiento, segmento in enumerate(segmentos[:2]):
        valor = _primer_valor(segmento, formato)
        if valor is not None:
            return valor, linea + desplazamiento
    return None


def _resolver(lectura: Lectura, columna: Columna, formato: Formato) -> _Hallazgo:
    """Busca una columna en una lectura. No elige nada si hay varias coincidencias."""
    texto_normalizado, mapa = _normalizar(lectura.texto, formato.acentos)
    frase_normalizada = _normalizar_frase(columna.frase, formato.acentos)
    posiciones = _coincidencias(texto_normalizado, frase_normalizada)

    if not posiciones:
        return _Hallazgo(_ESTADO_SIN_COINCIDENCIA)
    if len(posiciones) > 1:
        return _Hallazgo(_ESTADO_AMBIGUO)

    inicio, fin = posiciones[0]
    if fin <= 0 or fin - 1 >= len(mapa):
        return _Hallazgo(_ESTADO_SIN_COINCIDENCIA)
    fin_original = mapa[fin - 1] + 1

    encontrado = _valor_despues(lectura.texto, fin_original, formato)
    if encontrado is None:
        return _Hallazgo(_ESTADO_SIN_COINCIDENCIA)

    valor, linea = encontrado
    return _Hallazgo(_ESTADO_OK, valor, linea)


def _tokens_despues(lectura: Lectura, frase: str, formato: Formato, limite: int) -> list[str]:
    """Devuelve los primeros tokens que siguen a una frase, para los campos internos."""
    texto_normalizado, mapa = _normalizar(lectura.texto, formato.acentos)
    frase_normalizada = _normalizar_frase(frase, formato.acentos)
    posiciones = _coincidencias(texto_normalizado, frase_normalizada)
    if not posiciones:
        return []

    _, fin = posiciones[0]
    if fin <= 0 or fin - 1 >= len(mapa):
        return []
    fin_original = mapa[fin - 1] + 1

    tokens = [token for token in re.split(r"\s+", lectura.texto[fin_original:]) if token]
    return tokens[:limite]


def _buscar_rif(lecturas: Sequence[Lectura], formato: Formato) -> str | None:
    """Busca el RIF del proveedor y lo devuelve en forma canónica."""
    for lectura in lecturas:
        for alias in ALIAS_RIF:
            for token in _tokens_despues(lectura, alias, formato, limite=5):
                limpio = re.sub(r"[^A-Za-z0-9]", "", token).upper()
                if len(limpio) == 10 and limpio[0] in "VEJPG" and limpio[1:].isdigit():
                    return f"{limpio[0]}-{limpio[1:9]}-{limpio[9]}"
    return None


def _buscar_numero_factura(lecturas: Sequence[Lectura], formato: Formato) -> str | None:
    """Busca el número de factura. Puede traer la serie pegada (`001-00001234`)."""
    for lectura in lecturas:
        for alias in ALIAS_NUMERO:
            for token in _tokens_despues(lectura, alias, formato, limite=4):
                limpio = token.strip(".,;:()[]")
                if re.search(r"\d", limpio) and fecha(limpio) is None:
                    return limpio
    return None


def _buscar_fecha(lecturas: Sequence[Lectura], formato: Formato) -> str | None:
    """Busca la fecha de emisión y la devuelve en ISO."""
    for lectura in lecturas:
        for alias in ALIAS_FECHA:
            for token in _tokens_despues(lectura, alias, formato, limite=4):
                valor = fecha(token)
                if valor is not None:
                    return valor
    return None


def _extraer_control(lecturas: Sequence[Lectura], formato: Formato) -> ControlFields:
    """Extrae los 4 campos internos, separando la serie del número si viene junto."""
    numero_factura = _buscar_numero_factura(lecturas, formato)
    serie = None
    numero = numero_factura
    if numero_factura is not None and re.fullmatch(r"\d+-\d+", numero_factura):
        serie, numero = numero_factura.split("-", 1)

    return ControlFields(
        supplier_rif=_buscar_rif(lecturas, formato),
        serie=serie,
        numero=numero,
        issue_date=_buscar_fecha(lecturas, formato),
    )


def _unir_motivos(motivos: Sequence[str]) -> str | None:
    """Une los motivos sin repetir y separados por `;` (`SCHEMAS.md` §3.3)."""
    unicos: list[str] = []
    for motivo in motivos:
        if motivo not in unicos:
            unicos.append(motivo)
    if not unicos:
        return None
    return ";".join(unicos)


def _aviso(estado: str, columna: Columna) -> str:
    return f'{estado}:{columna.frase} (columna "{columna.encabezado}")'


def extraer(
    lectura: Lectura,
    columnas: Sequence[Columna],
    formato: Formato,
    umbral: float,
    obtener_easyocr: Callable[[], Lectura | None] | None = None,
) -> ExtractionResult:
    """Extrae un valor por columna, en el orden recibido, y arma los avisos.

    `obtener_easyocr` se llama como máximo una vez y solo si alguna columna salió
    vacía o con confianza bajo el umbral (`SCHEMAS.md` §5.5).
    """
    valores: list[ExtractedValue] = []
    motivos: list[str] = []
    motores: list[str] = [lectura.motor]
    cache_alternativa: list[Lectura | None] = []

    def alternativa() -> Lectura | None:
        if not cache_alternativa:
            cache_alternativa.append(obtener_easyocr() if obtener_easyocr is not None else None)
        return cache_alternativa[0]

    for columna in columnas:
        hallazgo = _resolver(lectura, columna, formato)
        motor = lectura.motor
        confianza = lectura.confianza_linea(hallazgo.linea) if hallazgo.linea is not None else 0.0

        necesita_ayuda = hallazgo.estado == _ESTADO_SIN_COINCIDENCIA or (
            hallazgo.estado == _ESTADO_OK and confianza < umbral
        )
        if necesita_ayuda:
            otra_lectura = alternativa()
            if otra_lectura is not None:
                if otra_lectura.motor not in motores:
                    motores.append(otra_lectura.motor)
                otro = _resolver(otra_lectura, columna, formato)
                if otro.estado == _ESTADO_OK:
                    otra_confianza = (
                        otra_lectura.confianza_linea(otro.linea) if otro.linea is not None else 0.0
                    )
                    if hallazgo.estado != _ESTADO_OK or otra_confianza > confianza:
                        hallazgo = otro
                        motor = otra_lectura.motor
                        confianza = otra_confianza

        if hallazgo.estado == _ESTADO_AMBIGUO:
            motivos.append(_aviso(_ESTADO_AMBIGUO, columna))
            valores.append(ExtractedValue(columna.encabezado, None, 0.0, motor))
            continue

        if hallazgo.estado != _ESTADO_OK:
            motivos.append(_aviso(_ESTADO_SIN_COINCIDENCIA, columna))
            valores.append(ExtractedValue(columna.encabezado, None, 0.0, motor))
            continue

        if confianza < umbral:
            motivos.append("low_confidence")
        valores.append(ExtractedValue(columna.encabezado, hallazgo.valor, confianza, motor))

    lecturas_control = [lectura, *(otra for otra in cache_alternativa if otra is not None)]
    control = _extraer_control(lecturas_control, formato)
    if control.supplier_rif is None:
        motivos.append("unreadable_rif")

    motivo = _unir_motivos(motivos)
    return ExtractionResult(
        values=valores,
        control=control,
        items=[],
        raw_text=lectura.texto,
        engines_used=motores,
        review_status="needs_review" if motivo is not None else "ok",
        review_reason=motivo,
    )


__all__ = ["extraer", "normalizar_frase"]
