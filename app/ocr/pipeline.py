"""Orquestación: imagen → preprocesado → motores → extracción.

La 002 no escribe en PostgreSQL: devuelve el `ExtractionResult` a la 003
(`AGENTS.md` § Roles).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image

from app.models.invoice import Columna, ExtractionResult, Formato
from app.ocr import preprocess, rapidocr_engine
from app.ocr.extract import _resolver, extraer
from app.ocr.rapidocr_engine import Lectura


@dataclass(frozen=True)
class _Candidato:
    lectura: Lectura
    resultado: ExtractionResult
    misma_linea: int


def _misma_linea(
    lectura: Lectura,
    columnas: Sequence[Columna],
    formato: Formato,
) -> int:
    return sum(
        1
        for columna in columnas
        if (hallazgo := _resolver(lectura, columna, formato)).estado == "ok"
        and hallazgo.misma_linea
    )


def _consenso(candidatos: Sequence[_Candidato], total: int) -> list[Counter]:
    votos: list[Counter] = [Counter() for _ in range(total)]
    for candidato in candidatos:
        for indice, valor in enumerate(candidato.resultado.values[:total]):
            if valor.value is not None:
                votos[indice][valor.value] += 1
    return votos


def _puntaje(
    candidato: _Candidato,
    votos: Sequence[Counter],
) -> tuple[int, int, int, int, float]:
    encontrados = 0
    coincidencias = 0
    numericos = 0
    confianza = 0.0

    for indice, valor in enumerate(candidato.resultado.values[: len(votos)]):
        if valor.value is None:
            continue
        encontrados += 1
        confianza += valor.confidence
        if isinstance(valor.value, (int, float)) and not isinstance(valor.value, bool):
            numericos += 1
        comunes = votos[indice].most_common(1)
        if comunes and valor.value == comunes[0][0]:
            coincidencias += 1

    return encontrados, candidato.misma_linea, numericos, coincidencias, confianza


def _mejor_candidato(candidatos: Sequence[_Candidato], total: int) -> _Candidato:
    votos = _consenso(candidatos, total)
    return max(candidatos, key=lambda candidato: _puntaje(candidato, votos))


def _leer_variante(
    preparada: Image.Image,
    columnas: Sequence[Columna],
    formato: Formato,
    umbral: float,
) -> _Candidato:
    lectura = rapidocr_engine.leer(preparada)
    resultado = extraer(lectura, columnas, formato, umbral)
    return _Candidato(
        lectura,
        resultado,
        _misma_linea(lectura, columnas, formato),
    )


def leer_factura(
    imagen: Image.Image,
    columnas: Sequence[Columna],
    formato: Formato,
    umbral: float,
) -> ExtractionResult:
    """Lee una factura completa y devuelve los valores pedidos por el contador."""
    candidatos: list[_Candidato] = []
    for _, preparada in preprocess.variantes(imagen):
        candidatos.append(_leer_variante(preparada, columnas, formato, umbral))

    sin_valores = not any(
        valor.value is not None
        for candidato in candidatos
        for valor in candidato.resultado.values
    )
    if sin_valores:
        preparada = preprocess.preprocesar(imagen)
        candidatos.append(_leer_variante(preparada, columnas, formato, umbral))

    mejor = _mejor_candidato(candidatos, len(columnas))
    return extraer(mejor.lectura, columnas, formato, umbral)


__all__ = ["leer_factura"]
