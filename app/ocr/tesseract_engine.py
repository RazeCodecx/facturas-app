"""Lectura con Tesseract: texto en orden de lectura y confianza por palabra.

`--psm 6` asume un bloque uniforme de texto, que es lo que se pidió en
`specs/002-ocr-factura/design.md`. La confianza la devuelve Tesseract en 0-100.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytesseract
from PIL import Image

from app.config import config

CONFIGURACION = "--psm 6 --oem 3 -l eng+spa"
MOTOR = "tesseract"


@dataclass(frozen=True)
class Palabra:
    """Una palabra reconocida, con su confianza y la línea a la que pertenece."""

    texto: str
    confianza: float
    linea: int


@dataclass
class Lectura:
    """Texto reconocido, sus palabras y el motor que lo produjo."""

    texto: str
    palabras: list[Palabra] = field(default_factory=list)
    motor: str = MOTOR

    def confianza_linea(self, linea: int) -> float:
        """Promedio de confianza de las palabras de una línea, o 0 si no hay."""
        valores = [palabra.confianza for palabra in self.palabras if palabra.linea == linea]
        if not valores:
            return 0.0
        return sum(valores) / len(valores)


def leer(imagen: Image.Image) -> Lectura:
    """Reconoce la imagen y devuelve el texto de izquierda a derecha y arriba abajo."""
    pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd
    datos = pytesseract.image_to_data(
        imagen,
        config=CONFIGURACION,
        output_type=pytesseract.Output.DICT,
    )

    palabras: list[Palabra] = []
    lineas: dict[int, list[str]] = {}
    indice_linea: dict[tuple[int, int, int], int] = {}

    for posicion, texto in enumerate(datos["text"]):
        texto = texto.strip()
        confianza = float(datos["conf"][posicion])
        if not texto or confianza < 0:
            continue

        clave = (
            int(datos["block_num"][posicion]),
            int(datos["par_num"][posicion]),
            int(datos["line_num"][posicion]),
        )
        linea = indice_linea.setdefault(clave, len(indice_linea))
        palabras.append(Palabra(texto=texto, confianza=confianza, linea=linea))
        lineas.setdefault(linea, []).append(texto)

    texto_completo = "\n".join(" ".join(lineas[numero]) for numero in sorted(lineas))
    return Lectura(texto=texto_completo, palabras=palabras, motor=MOTOR)


__all__ = ["Lectura", "Palabra", "leer"]
