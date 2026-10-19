"""Normalización de números y fechas leídos por el OCR.

El formato numérico lo pone el contador en la línea de configuración de
`plantilla.csv` y llega acá desde la 004 (`SCHEMAS.md` §4.4, §5.4).

Ante la duda, la columna queda vacía: un número equivocado es peor que uno
faltante. Por eso un separador que no encaja con el formato configurado se
rechaza en vez de reinterpretarse.
"""

from __future__ import annotations

import math
import re
from datetime import date

from app.models.invoice import Formato

_PATRON_NUMERO = re.compile(r"\d[\d.,]*")
_PATRON_FECHA = re.compile(r"\b(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})\b")
_SIGNOS = "-−–"
_FORMATO_POR_DEFECTO = Formato()


def _quitar_miles(entero: str, miles: str) -> str | None:
    """Valida el agrupamiento de miles y devuelve solo los dígitos."""
    if miles not in entero:
        return entero if entero.isdigit() else None

    grupos = entero.split(miles)
    if not (1 <= len(grupos[0]) <= 3 and grupos[0].isdigit()):
        return None
    if any(len(grupo) != 3 or not grupo.isdigit() for grupo in grupos[1:]):
        return None
    return "".join(grupos)


def _parsear(crudo: str, formato: Formato) -> float | None:
    """Convierte el texto de un número al formato interno, o `None` si no encaja."""
    miles = formato.miles
    decimal = formato.decimal
    if miles == decimal:
        miles = _FORMATO_POR_DEFECTO.miles
        decimal = _FORMATO_POR_DEFECTO.decimal

    tiene_decimal = decimal in crudo
    tiene_miles = miles in crudo

    if tiene_decimal and tiene_miles:
        if crudo.rfind(decimal) < crudo.rfind(miles):
            return None
        entero, _, fraccion = crudo.rpartition(decimal)
        digitos = _quitar_miles(entero, miles)
        if digitos is None or not fraccion.isdigit():
            return None
        normalizado = f"{digitos}.{fraccion}"
    elif tiene_decimal:
        if crudo.count(decimal) != 1:
            return None
        entero, _, fraccion = crudo.partition(decimal)
        if not entero.isdigit() or not fraccion.isdigit():
            return None
        normalizado = f"{entero}.{fraccion}"
    elif tiene_miles:
        digitos = _quitar_miles(crudo, miles)
        if digitos is None:
            return None
        normalizado = digitos
    else:
        if not crudo.isdigit():
            return None
        normalizado = crudo

    try:
        valor = float(normalizado)
    except ValueError:
        return None
    if not math.isfinite(valor):
        return None
    return valor


def numero(token: str, formato: Formato) -> float | None:
    """Devuelve el número que hay en el token, con su signo, o `None`.

    El signo se conserva tal cual: la app no le quita el menos a una retención ni
    se lo agrega a nada (`SCHEMAS.md` §4.1).
    """
    texto = token.strip()
    if not texto:
        return None

    if re.search(r"\d[/\-]\d", texto):
        return None

    negativo = texto[0] in _SIGNOS
    if negativo:
        texto = texto[1:]

    coincidencia = _PATRON_NUMERO.search(texto)
    if coincidencia is None:
        return None

    crudo = coincidencia.group(0).rstrip(".,")
    valor = _parsear(crudo, formato)
    if valor is None:
        return None
    if valor == 0:
        return 0.0
    return -valor if negativo else valor


def formatear_numero(valor: float) -> str:
    """Devuelve el número con punto decimal y 2 decimales, listo para el CSV."""
    return f"{valor:.2f}"


def fecha(token: str) -> str | None:
    """Devuelve la fecha del token en ISO (`YYYY-MM-DD`), o `None`.

    Se acepta día primero (`DD/MM/AAAA`), que es la convención de Venezuela, y
    también `AAAA-MM-DD`.
    """
    coincidencia = _PATRON_FECHA.search(token.strip())
    if coincidencia is None:
        return None

    primero, segundo, tercero = coincidencia.groups()
    if len(primero) == 4:
        anio, mes, dia = int(primero), int(segundo), int(tercero)
    else:
        dia, mes, anio = int(primero), int(segundo), int(tercero)
        if len(tercero) == 2:
            anio += 2000

    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


__all__ = ["fecha", "formatear_numero", "numero"]
