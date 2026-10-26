"""Búsqueda del primer texto de cada columna, valores y avisos.

Es el corazón de la 002. Recibe texto ya reconocido, no imágenes: por eso se
prueba sin RapidOCR real (`specs/002-ocr-factura/tasks.md` T4.1).

Reglas (`SCHEMAS.md` §5): coincidencia completa, sin distinguir mayúsculas, sin
distinguir tildes salvo `#acentos=0`, sin coincidencias parciales, y **nunca se
adivina**.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.invoice import (
    Columna,
    ExtractedValue,
    ExtractionResult,
    Formato,
)
from app.ocr.normalize import numero
from app.ocr.rapidocr_engine import Lectura

_ESTADO_OK = "ok"
_ESTADO_SIN_COINCIDENCIA = "no_match"
_ESTADO_AMBIGUO = "ambiguous"
_PATRON_SOLO_NUMERO = re.compile(r"^[+\-−–]?\d[\d.,]*%?$")


@dataclass(frozen=True)
class _Hallazgo:
    """Resultado interno de buscar una columna en una lectura."""

    estado: str
    valor: float | str | None = None
    linea: int | None = None
    misma_linea: bool = False


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


def _parece_numero(token: str) -> bool:
    return bool(_PATRON_SOLO_NUMERO.match(token.strip(".,;:()[]")))


def _linea_de_valor(segmento: str) -> bool:
    """Acepta una línea siguiente solo si parece contener el valor y nada más."""
    tokens = [token for token in re.split(r"\s+", segmento) if token]
    if not tokens or len(tokens) > 2:
        return False

    numeros = sum(_parece_numero(token) for token in tokens)
    letras = [
        token
        for token in tokens
        if not _parece_numero(token) and any(caracter.isalpha() for caracter in token)
    ]
    return numeros == 1 and all(
        sum(caracter.isalpha() for caracter in token) <= 3 for token in letras
    )


def _primer_valor(segmento: str, formato: Formato) -> float | str | None:
    """Devuelve el primer número del segmento; si no hay, el primer texto.

    El número se normaliza con el formato del contador. El texto se conserva tal
    cual, para las columnas que el contador pidió explícitamente y que no son
    numéricas (por ejemplo, un RIF o una moneda). Los tokens puramente
    numéricos tienen prioridad para que un `Bs` leído como `8s` no se guarde
    como el número 8.
    """
    tokens = [token for token in re.split(r"\s+", segmento) if token]

    for token in tokens:
        if _parece_numero(token):
            valor = numero(token, formato)
            if valor is not None:
                return valor

    for token in tokens:
        if _parece_numero(token):
            continue
        if sum(caracter.isalpha() for caracter in token) < 2:
            continue
        valor = numero(token, formato)
        if valor is not None:
            return valor

    for token in tokens:
        if _parece_numero(token):
            return token.strip(".,;:()[]")

    for token in tokens:
        limpio = token.strip(".,;:()[]")
        if any(caracter.isalnum() for caracter in limpio):
            return limpio
    return None


def _valor_despues(
    texto: str, fin: int, formato: Formato
) -> tuple[float | str, int, bool] | None:
    """Busca el valor en la misma línea de la coincidencia y, si no hay, en la siguiente."""
    linea = texto.count("\n", 0, fin)
    segmentos = texto[fin:].split("\n")

    valor = _primer_valor(segmentos[0], formato)
    if valor is not None:
        return valor, linea, True

    if len(segmentos) > 1 and _linea_de_valor(segmentos[1]):
        valor = _primer_valor(segmentos[1], formato)
        if valor is not None:
            return valor, linea + 1, False
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

    valor, linea, misma_linea = encontrado
    return _Hallazgo(_ESTADO_OK, valor, linea, misma_linea)


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
) -> ExtractionResult:
    """Extrae un valor por columna, en el orden recibido, y arma los avisos."""
    valores: list[ExtractedValue] = []
    motivos: list[str] = []

    for columna in columnas:
        hallazgo = _resolver(lectura, columna, formato)
        confianza = lectura.confianza_linea(hallazgo.linea) if hallazgo.linea is not None else 0.0

        if hallazgo.estado == _ESTADO_AMBIGUO:
            motivos.append(_aviso(_ESTADO_AMBIGUO, columna))
            valores.append(ExtractedValue(columna.encabezado, None, 0.0))
            continue

        if hallazgo.estado != _ESTADO_OK:
            motivos.append(_aviso(_ESTADO_SIN_COINCIDENCIA, columna))
            valores.append(ExtractedValue(columna.encabezado, None, 0.0))
            continue

        if confianza < umbral:
            motivos.append("low_confidence")
        valores.append(ExtractedValue(columna.encabezado, hallazgo.valor, confianza))

    motivo = _unir_motivos(motivos)
    return ExtractionResult(
        values=valores,
        raw_text=lectura.texto,
        engines_used=[lectura.motor],
        review_status="needs_review" if motivo is not None else "ok",
        review_reason=motivo,
    )


__all__ = ["extraer", "normalizar_frase"]
