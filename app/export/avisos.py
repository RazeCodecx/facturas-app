"""Generación de `avisos.csv`: qué se buscó, dónde, y qué salió mal.

Va en un archivo aparte del CSV de facturas (`CONSTITUTION.md` regla 4). Sale
siempre, aunque no haya avisos: una cabecera sin filas significa "todo bien".

Ver `specs/004-plantilla-y-csv/design.md`.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

CABECERA = ("invoice_id", "frase", "columna", "motivo")

_AVISO_CON_COLUMNA = re.compile(
    r'^(?P<motivo>[a-z_]+):(?P<frase>.*?) \(columna "(?P<columna>.*)"\)$'
)
_MOTIVOS_SIN_COLUMNA = {"low_confidence", "unreadable_rif"}


def _partir_aviso(aviso: str) -> tuple[str, str, str]:
    """Devuelve `(frase, columna, motivo)` de un aviso de `SCHEMAS.md` §3.3."""
    coincidencia = _AVISO_CON_COLUMNA.match(aviso)
    if coincidencia is not None:
        return (
            coincidencia.group("frase"),
            coincidencia.group("columna"),
            coincidencia.group("motivo"),
        )

    motivo = aviso if aviso in _MOTIVOS_SIN_COLUMNA else aviso.split(":", 1)[0]
    return "", "", motivo


def _filas(facturas: Iterable[dict[str, Any]]) -> Iterator[list[Any]]:
    """Genera un renglón por aviso, en el orden de las facturas recibidas."""
    for factura in facturas:
        motivo_crudo = factura.get("review_reason") or ""
        for aviso in (parte.strip() for parte in motivo_crudo.split(";")):
            if not aviso:
                continue
            frase, columna, motivo = _partir_aviso(aviso)
            yield [factura.get("id", ""), frase, columna, motivo]


def generar_avisos(facturas: Sequence[dict[str, Any]]) -> bytes:
    """Un renglón por aviso, en el mismo orden en que se exportan las facturas."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=",")
    escritor.writerow(CABECERA)
    escritor.writerows(_filas(facturas))
    return salida.getvalue().encode("utf-8-sig")


def escribir_avisos(ruta: Path, facturas: Sequence[dict[str, Any]]) -> None:
    """Reescribe el archivo completo, con su cabecera."""
    ruta.write_bytes(generar_avisos(facturas))


def agregar_avisos(ruta: Path, facturas: Sequence[dict[str, Any]]) -> None:
    """Agrega los avisos al final; la cabecera solo va si el archivo es nuevo."""
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    with ruta.open(
        "a", newline="", encoding="utf-8-sig" if nuevo else "utf-8"
    ) as archivo:
        escritor = csv.writer(archivo, delimiter=",")
        if nuevo:
            escritor.writerow(CABECERA)
        escritor.writerows(_filas(facturas))


__all__ = [
    "CABECERA",
    "agregar_avisos",
    "escribir_avisos",
    "generar_avisos",
]
