"""Modelos de la extracción de factura.

`Columna` la arma la 004 y la consume la 002; el resto son la salida de la 002 y
viajan a la 003. Ver `specs/002-ocr-factura/design.md` y `SCHEMAS.md` §1, §3.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Columna:
    """Un par del archivo del contador: qué buscar y qué título poner.

    `frase` es el primer texto (lo que se busca en la foto), `encabezado` es el
    segundo texto (el título de la columna) y `linea` es la línea del archivo,
    para señalar errores. Es inmutable: si alguien cambia el segundo texto por el
    camino, el Excel y el valor dejan de corresponder.
    """

    frase: str
    encabezado: str
    linea: int


@dataclass(frozen=True)
class Formato:
    """Cómo leer los números y si se ignoran las tildes al buscar.

    Lo arma la 004 desde las líneas `#` de `plantilla.csv` (`SCHEMAS.md` §4.4).
    `acentos=True` significa que se ignoran las tildes al comparar.
    """

    miles: str = ","
    decimal: str = "."
    acentos: bool = True


@dataclass
class ExtractedValue:
    """Un valor extraído. No lleva el primer texto: la 004 ya tiene las columnas."""

    encabezado: str
    value: str | None
    confidence: float
    engine: str


@dataclass
class ControlFields:
    """Los 4 campos internos de deduplicación (`SCHEMAS.md` §2)."""

    supplier_rif: str | None = None
    serie: str | None = None
    numero: str | None = None
    issue_date: str | None = None


@dataclass
class ExtractionResult:
    """Lo que la 002 entrega a la 003, en el orden de las columnas recibidas."""

    values: list[ExtractedValue] = field(default_factory=list)
    control: ControlFields = field(default_factory=ControlFields)
    items: list[dict[str, Any]] = field(default_factory=list)
    raw_text: str = ""
    engines_used: list[str] = field(default_factory=list)
    review_status: str = "ok"
    review_reason: str | None = None


__all__ = [
    "Columna",
    "ControlFields",
    "ExtractedValue",
    "ExtractionResult",
    "Formato",
]
