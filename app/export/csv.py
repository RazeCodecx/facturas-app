"""Generación del CSV de facturas. **Único** punto que lo emite.

La fila 1 son los segundos textos del archivo de hoy. Los valores se emparejan
por **primer texto**, no por posición, para que reordenar o borrar líneas después
de escanear no corra un número a la columna vecina.

Ver `specs/004-plantilla-y-csv/design.md`.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from typing import Any

from app.models.invoice import Columna, Formato
from app.ocr.extract import normalizar_frase


def _celda(valor: Any) -> str:
    """Un `None` es celda vacía; los números salen con 2 decimales al escribir."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, int | float):
        return f"{float(valor):.2f}"
    return str(valor)


def _valores_por_frase(
    valores: Sequence[dict[str, Any]], acentos: bool
) -> dict[str, Any]:
    """Indexa el JSONB por primer texto, con la normalización de la búsqueda."""
    indice: dict[str, Any] = {}
    for objeto in valores:
        if not isinstance(objeto, dict):
            continue
        frase = str(objeto.get("frase") or "")
        clave = normalizar_frase(frase, acentos)
        if clave and clave not in indice:
            indice[clave] = objeto.get("value")
    return indice


def generar_csv(
    facturas: Sequence[dict[str, Any]],
    columnas: Sequence[Columna],
    formato: Formato,
) -> bytes:
    """Devuelve el CSV con una sola cabecera y una fila por factura."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=",")
    escritor.writerow([columna.encabezado for columna in columnas])

    claves = [
        normalizar_frase(columna.frase, formato.acentos) for columna in columnas
    ]
    for factura in facturas:
        guardados = _valores_por_frase(factura.get("values") or [], formato.acentos)
        escritor.writerow([_celda(guardados.get(clave)) for clave in claves])

    return salida.getvalue().encode("utf-8-sig")


__all__ = ["generar_csv"]
