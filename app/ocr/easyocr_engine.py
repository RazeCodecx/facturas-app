"""Lectura con EasyOCR. Arranque perezoso.

Los modelos ocupan cientos de MB y en CPU son lentos, así que no se cargan al
arrancar el servidor: se cargan la primera vez que un primer texto los necesita.
Si los pesos no están descargados se avisa y se devuelve `None`, para que el
escaneo siga solo con Tesseract (`specs/002-ocr-factura/design.md`).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PIL import Image

from app.config import config
from app.ocr.tesseract_engine import Lectura, Palabra

LOGGER = logging.getLogger(__name__)
MOTOR = "easyocr"

_lector: Any | None = None
_resuelto = False


def _obtener_lector() -> Any | None:
    """Carga EasyOCR una sola vez. Devuelve `None` si no está disponible."""
    global _lector, _resuelto
    if _resuelto:
        return _lector

    _resuelto = True
    try:
        import easyocr

        _lector = easyocr.Reader(
            ["es", "en"],
            gpu=False,
            model_storage_directory=config.easyocr_model_dir,
            download_enabled=False,
        )
    except Exception as error:
        LOGGER.warning("EasyOCR no disponible; se sigue solo con Tesseract: %s", error)
        _lector = None
    return _lector


def _agrupar_lineas(detecciones: list[Any]) -> Lectura:
    """Ordena las detecciones por posición y las agrupa en líneas de lectura."""
    elementos: list[tuple[float, float, float, str, float]] = []
    for caja, texto, confianza in detecciones:
        texto = texto.strip()
        if not texto:
            continue
        alturas = [punto[1] for punto in caja]
        anchos = [punto[0] for punto in caja]
        arriba = min(alturas)
        alto = max(alturas) - arriba
        elementos.append((arriba, min(anchos), alto, texto, float(confianza) * 100.0))

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


def leer(imagen: Image.Image) -> Lectura | None:
    """Reconoce la imagen, o devuelve `None` si EasyOCR no está disponible."""
    lector = _obtener_lector()
    if lector is None:
        return None

    try:
        detecciones = lector.readtext(np.array(imagen.convert("RGB")), detail=1)
    except Exception as error:
        LOGGER.warning("EasyOCR falló en esta imagen: %s", error)
        return None

    return _agrupar_lineas(detecciones)


__all__ = ["leer"]
