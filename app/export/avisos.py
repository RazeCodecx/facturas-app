"""Generación de `avisos.csv`: qué se buscó, dónde, y qué salió mal.

Va en un archivo aparte del CSV de facturas (`CONSTITUTION.md` regla 4). Sale
siempre, aunque no haya avisos: una cabecera sin filas significa "todo bien".

Ver `specs/004-plantilla-y-csv/design.md`.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
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


def generar_avisos(facturas: Sequence[dict[str, Any]]) -> bytes:
    """Un renglón por aviso, en el mismo orden en que se exportan las facturas."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=",")
    escritor.writerow(CABECERA)

    for factura in facturas:
        motivo_crudo = factura.get("review_reason") or ""
        for aviso in (parte.strip() for parte in motivo_crudo.split(";")):
            if not aviso:
                continue
            frase, columna, motivo = _partir_aviso(aviso)
            escritor.writerow([factura.get("id", ""), frase, columna, motivo])

    return salida.getvalue().encode("utf-8-sig")


__all__ = ["CABECERA", "generar_avisos"]
