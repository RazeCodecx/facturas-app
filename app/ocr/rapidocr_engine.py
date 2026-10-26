"""Lectura con RapidOCR: texto en orden de lectura y confianza por detección.

RapidOCR carga sus modelos de forma perezosa y devuelve confianza en 0-1. El
pipeline prueba varias variantes de la misma imagen, así que el motor se crea una
sola vez y se reutiliza entre escaneos.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

LOGGER = logging.getLogger(__name__)
MOTOR = "rapidocr"
_PARAMETROS = {
    "Det.lang_type": "es",
    "Rec.lang_type": "es",
    "Global.text_score": 0.0,
}

_motor: Any | None = None
_cerrojo = threading.Lock()


class RapidOCRNoDisponible(RuntimeError):
    """RapidOCR no está instalado o no pudo cargar sus modelos."""


@dataclass(frozen=True)
class Palabra:
    """Una detección reconocida, con su confianza y la línea a la que pertenece."""

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


def _obtener_motor() -> Any:
    """Crea RapidOCR una sola vez. Lanza `RapidOCRNoDisponible` si falla."""
    global _motor
    if _motor is not None:
        return _motor

    with _cerrojo:
        if _motor is not None:
            return _motor
        try:
            from rapidocr import RapidOCR

            _motor = RapidOCR(params=_PARAMETROS)
        except Exception as error:
            raise RapidOCRNoDisponible("RapidOCR no está disponible.") from error
    return _motor


def _agrupar_lineas(
    cajas: Any,
    textos: Any,
    confianzas: Any,
) -> Lectura:
    """Ordena las detecciones por posición y las agrupa en líneas de lectura."""
    elementos: list[tuple[float, float, float, str, float]] = []
    for caja, texto, confianza in zip(cajas, textos, confianzas, strict=False):
        texto = texto.strip()
        if not texto:
            continue
        alturas = [punto[1] for punto in caja]
        anchos = [punto[0] for punto in caja]
        arriba = min(alturas)
        alto = max(alturas) - arriba
        elementos.append(
            (arriba, min(anchos), alto, texto, float(confianza) * 100.0)
        )

    elementos.sort(key=lambda elemento: (elemento[0], elemento[1]))

    palabras: list[Palabra] = []
    lineas: list[str] = []
    actual: list[tuple[str, float]] = []
    centro_actual = 0.0
    alto_actual = 0.0

    def cerrar_linea() -> None:
        if not actual:
            return
        numero = len(lineas)
        lineas.append(" ".join(texto for texto, _ in actual))
        for texto, confianza in actual:
            palabras.append(Palabra(texto=texto, confianza=confianza, linea=numero))

    for arriba, _, alto, texto, confianza in elementos:
        centro = arriba + alto / 2.0
        if actual and abs(centro - centro_actual) <= max(8.0, alto_actual * 0.6):
            actual.append((texto, confianza))
            continue
        cerrar_linea()
        actual = [(texto, confianza)]
        centro_actual = centro
        alto_actual = alto

    cerrar_linea()
    return Lectura(texto="\n".join(lineas), palabras=palabras, motor=MOTOR)


def leer(imagen: Image.Image) -> Lectura:
    """Reconoce la imagen y devuelve el texto de izquierda a derecha y arriba abajo."""
    motor = _obtener_motor()

    try:
        resultado = motor(imagen)
    except Exception as error:
        LOGGER.exception("RapidOCR no pudo procesar la imagen.")
        raise RapidOCRNoDisponible("RapidOCR no pudo procesar la imagen.") from error

    cajas = getattr(resultado, "boxes", None)
    textos = getattr(resultado, "txts", None)
    confianzas = getattr(resultado, "scores", None)
    if cajas is None or textos is None or confianzas is None:
        return Lectura(texto="", palabras=[], motor=MOTOR)

    return _agrupar_lineas(cajas, textos, confianzas)


__all__ = ["Lectura", "Palabra", "RapidOCRNoDisponible", "leer"]
