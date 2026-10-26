"""Preprocesado de la imagen antes del OCR.

El orden es fijo y no negociable (`CONSTITUTION.md` § Convenciones): gris, ruido,
inclinación, umbral, escalado. Umbralizar antes de quitar el ruido o de enderezar
rompe los bordes de las letras, que es justo lo que el OCR necesita leer.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

LADO_MINIMO = 1800
INCLINACION_MAXIMA = 15.0
MARGEN_LATERAL = 0.22
MARGEN_AMPLIO = 0.15


def _a_gris(imagen: Image.Image) -> np.ndarray:
    """Paso 1: deja la imagen en un solo canal, sin color."""
    return np.array(imagen.convert("L"))


def _quitar_ruido(gris: np.ndarray) -> np.ndarray:
    """Paso 2: suaviza el grano de la foto sin borrar los bordes de las letras."""
    return cv2.fastNlMeansDenoising(gris, None, h=10, templateWindowSize=7, searchWindowSize=21)


def _detectar_inclinacion(gris: np.ndarray) -> float:
    """Estima cuántos grados está torcida la imagen, mirando el bloque de texto.

    Solo se corrige una inclinación pequeña: si la estimación da más de
    `INCLINACION_MAXIMA` es casi seguro que confundió una tabla con el texto, y
    enderezar por eso empeora la lectura.
    """
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    coordenadas = cv2.findNonZero(binaria)
    if coordenadas is None or coordenadas.shape[0] < 100:
        return 0.0

    (_, _), (ancho, alto), angulo = cv2.minAreaRect(coordenadas)
    if ancho < alto:
        angulo -= 90.0
    if angulo < -45.0:
        angulo += 90.0
    if angulo > 45.0:
        angulo -= 90.0
    if abs(angulo) > INCLINACION_MAXIMA:
        return 0.0
    return angulo


def _enderezar(gris: np.ndarray, angulo: float) -> np.ndarray:
    """Paso 3: gira la imagen para dejar las líneas de texto horizontales."""
    if abs(angulo) < 0.5:
        return gris

    alto, ancho = gris.shape[:2]
    matriz = cv2.getRotationMatrix2D((ancho / 2.0, alto / 2.0), angulo, 1.0)
    return cv2.warpAffine(
        gris,
        matriz,
        (ancho, alto),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def _umbralizar(gris: np.ndarray) -> np.ndarray:
    """Paso 4: deja cada píxel en blanco o negro, sin grises intermedios."""
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return binaria


def _escalar(binaria: np.ndarray) -> np.ndarray:
    """Paso 5: agranda la imagen si es chica, para que el OCR distinga las letras.

    Se usa vecino más cercano para que la imagen siga siendo binaria.
    """
    alto, ancho = binaria.shape[:2]
    lado = max(alto, ancho)
    if lado <= 0 or lado >= LADO_MINIMO:
        return binaria

    factor = LADO_MINIMO / lado
    return cv2.resize(
        binaria,
        (int(round(ancho * factor)), int(round(alto * factor))),
        interpolation=cv2.INTER_NEAREST,
    )


def preprocesar(imagen: Image.Image) -> Image.Image:
    """Aplica los 5 pasos en el orden fijo y devuelve la imagen lista para OCR."""
    gris = _a_gris(imagen)
    sin_ruido = _quitar_ruido(gris)
    angulo = _detectar_inclinacion(sin_ruido)
    enderezada = _enderezar(sin_ruido, angulo)
    binaria = _umbralizar(enderezada)
    escalada = _escalar(binaria)
    return Image.fromarray(escalada)


def recortar_documento(imagen: Image.Image, margen: float = MARGEN_LATERAL) -> Image.Image:
    """Quita las franjas laterales de fondo y deja el papel centrado."""
    ancho, alto = imagen.size
    recorte = int(round(ancho * margen))
    return imagen.crop((recorte, 0, ancho - recorte, alto))


def _realzar(imagen: Image.Image) -> Image.Image:
    """Sube el contraste local del papel sin convertirlo en blanco y negro."""
    gris = np.array(imagen.convert("L"))
    return Image.fromarray(
        cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gris)
    )


def _escalar_color(imagen: Image.Image, factor: int) -> Image.Image:
    return imagen.resize(
        (imagen.width * factor, imagen.height * factor),
        Image.LANCZOS,
    )


def variantes(imagen: Image.Image) -> list[tuple[str, Image.Image]]:
    """Entrega lecturas alternativas del mismo papel para que el pipeline elija.

    La foto completa incluye mucho fondo; el recorte central y las escalas con
    contraste local recuperan los recibos torcidos o arrugados que el
    preprocesado binario fijo degrada.
    """
    documento = recortar_documento(imagen)
    documento_amplio = recortar_documento(imagen, MARGEN_AMPLIO)
    documento_realzado = _realzar(documento)
    documento_amplio_realzado = _realzar(documento_amplio)
    return [
        ("original", imagen),
        ("documento_2x", _escalar_color(documento, 2)),
        ("documento_2x_clahe", _escalar_color(documento_realzado, 2)),
        ("documento_amplio_3x_clahe", _escalar_color(documento_amplio_realzado, 3)),
    ]


__all__ = ["preprocesar", "recortar_documento", "variantes"]
