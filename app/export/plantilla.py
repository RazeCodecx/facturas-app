"""Lectura de `plantilla.csv`: los pares del contador y su formato numérico.

El archivo es del contador y **no se toca**, salvo una excepción de instalación: si
está completamente vacío, se le escribe una vez el mensaje de formato. Para que
"una vez" sobreviva a un reinicio, se deja un archivo centinela al lado.

Ver `specs/004-plantilla-y-csv/design.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import RAIZ
from app.models.invoice import Columna, Formato
from app.ocr.extract import normalizar_frase

RUTA_PLANTILLA = RAIZ / "plantilla.csv"
MARCADOR_FORMATO = RAIZ / ".plantilla_escrita"

MENSAJE_FORMATO = (
    "# Escriba una linea por columna: primer texto = titulo\n"
    "# Formato de numeros / Number format\n"
    "# miles   separador de miles / thousands separator   por defecto / default ,\n"
    "# decimal separador decimal / decimal separator     por defecto / default .\n"
    "# acentos 1 ignora tildes al buscar / ignore accents 0 no las ignora / keep them\n"
    "# excel   ruta absoluta del Excel de salida / output Excel absolute path\n"
    "#         ejemplo / example: #excel=C:\\Contabilidad\\facturas.xlsx\n"
)

_OPCION = re.compile(r"\b(miles|decimal|acentos)\s*=\s*(\S+)")
_EXCEL = re.compile(r"^#\s*excel\s*=\s*(.*)$", re.IGNORECASE)


class PlantillaError(ValueError):
    """El archivo del contador no se puede interpretar. El mensaje es para él."""


@dataclass(frozen=True)
class Plantilla:
    """Los pares del archivo, el formato de los números y el Excel de salida."""

    columnas: list[Columna]
    formato: Formato
    salida: Path | None = None


def _leer_texto(ruta: Path) -> str:
    try:
        datos = ruta.read_bytes()
    except FileNotFoundError as exc:
        raise PlantillaError(
            "No se encuentra plantilla.csv. Escriba una línea por columna con el "
            '"primer texto = segundo texto".'
        ) from exc

    if datos.startswith(b"\xef\xbb\xbf"):
        datos = datos[3:]
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlantillaError(
            "No se pudo leer plantilla.csv: guarde el archivo con codificación UTF-8."
        ) from exc


def _escribir_mensaje(ruta: Path, marcador: Path) -> None:
    """Escribe el mensaje de formato una sola vez en la vida de la instalación."""
    if marcador.exists():
        return
    ruta.write_text(MENSAJE_FORMATO, encoding="utf-8-sig", newline="\n")
    marcador.write_text("", encoding="utf-8")


def _ruta_excel(crudo: str) -> Path | None:
    """Valida la ruta del Excel de salida. Lo que no sirve se ignora."""
    texto = crudo.strip().strip('"').strip("'").strip()
    if not texto:
        return None
    ruta = Path(texto)
    if not ruta.is_absolute() or ruta.suffix.lower() != ".xlsx":
        return None
    return ruta


def _aplicar_formato(linea: str, valores: dict[str, object]) -> None:
    """Lee las opciones de una línea `#`. Lo mal escrito se ignora."""
    for clave, valor in _OPCION.findall(linea):
        if clave in ("miles", "decimal"):
            if len(valor) == 1:
                valores[clave] = valor
        elif valor in ("0", "1"):
            valores["acentos"] = valor == "1"


def _parsear(lineas: list[str]) -> tuple[list[Columna], Formato, Path | None]:
    valores: dict[str, object] = {"miles": ",", "decimal": ".", "acentos": True}
    columnas: list[Columna] = []
    salida: Path | None = None

    for numero, cruda in enumerate(lineas, start=1):
        linea = cruda.strip()
        if not linea:
            continue
        if linea.startswith("#"):
            coincidencia_excel = _EXCEL.match(linea)
            if coincidencia_excel is not None:
                ruta = _ruta_excel(coincidencia_excel.group(1))
                if ruta is not None:
                    salida = ruta
                continue
            _aplicar_formato(linea, valores)
            continue

        if "=" not in linea:
            raise PlantillaError(
                f'plantilla.csv línea {numero}: falta el "=". '
                'Escriba "primer texto = segundo texto".'
            )
        if linea.count("=") > 1:
            raise PlantillaError(
                f'plantilla.csv línea {numero}: hay más de un "=". Solo uno por línea.'
            )

        frase, encabezado = linea.split("=", 1)
        frase = frase.strip()
        encabezado = encabezado.strip()
        if not frase:
            raise PlantillaError(
                f'plantilla.csv línea {numero}: no dice qué buscar antes del "=".'
            )
        columnas.append(Columna(frase, encabezado or frase, numero))

    formato = Formato(
        miles=str(valores["miles"]),
        decimal=str(valores["decimal"]),
        acentos=bool(valores["acentos"]),
    )

    vistos: dict[str, Columna] = {}
    for columna in columnas:
        clave = normalizar_frase(columna.frase, formato.acentos)
        anterior = vistos.get(clave)
        if anterior is not None:
            raise PlantillaError(
                f'plantilla.csv: "{columna.frase}" está en las líneas '
                f"{anterior.linea} y {columna.linea}. Un primer texto no se repite."
            )
        vistos[clave] = columna

    return columnas, formato, salida


def leer_plantilla(
    ruta: Path | None = None,
    marcador: Path | None = None,
) -> Plantilla:
    """Lee el archivo completo. Sin columnas es error: no hay valores por defecto."""
    ruta = RUTA_PLANTILLA if ruta is None else ruta
    marcador = (ruta.with_name(".plantilla_escrita") if marcador is None else marcador)

    texto = _leer_texto(ruta)
    if not texto.strip():
        _escribir_mensaje(ruta, marcador)
        raise PlantillaError(
            "plantilla.csv no tiene columnas. Escriba al menos una línea "
            '"primer texto = título".'
        )

    columnas, formato, salida = _parsear(texto.splitlines())
    if not columnas:
        raise PlantillaError(
            "plantilla.csv no tiene columnas. Escriba al menos una línea "
            '"primer texto = título".'
        )
    return Plantilla(columnas, formato, salida)


def leer_columnas(ruta: Path | None = None) -> list[Columna]:
    """Devuelve las columnas que escribió el contador."""
    return leer_plantilla(ruta).columnas


def leer_formato(ruta: Path | None = None) -> Formato:
    """Devuelve el formato numérico del archivo."""
    return leer_plantilla(ruta).formato


__all__ = [
    "MENSAJE_FORMATO",
    "Plantilla",
    "PlantillaError",
    "leer_columnas",
    "leer_formato",
    "leer_plantilla",
]
