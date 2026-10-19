"""Orquestación: imagen → preprocesado → motores → extracción.

La 002 no escribe en PostgreSQL: devuelve el `ExtractionResult` a la 003
(`AGENTS.md` § Roles).
"""

from __future__ import annotations

from collections.abc import Sequence

from PIL import Image

from app.models.invoice import Columna, ExtractionResult, Formato
from app.ocr import easyocr_engine, preprocess, tesseract_engine
from app.ocr.extract import extraer


def leer_factura(
    imagen: Image.Image,
    columnas: Sequence[Columna],
    formato: Formato,
    umbral: float,
) -> ExtractionResult:
    """Lee una factura completa y devuelve los valores pedidos y los 4 de control."""
    preparada = preprocess.preprocesar(imagen)
    lectura = tesseract_engine.leer(preparada)
    return extraer(
        lectura,
        columnas,
        formato,
        umbral,
        obtener_easyocr=lambda: easyocr_engine.leer(preparada),
    )


__all__ = ["leer_factura"]
