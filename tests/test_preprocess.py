"""Tests del preprocesado de imagen."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from app.ocr.preprocess import LADO_MINIMO, preprocesar, variantes


def _imagen() -> Image.Image:
    imagen = Image.new("RGB", (400, 200), "white")
    dibujo = ImageDraw.Draw(imagen)
    dibujo.text((20, 80), "TOTAL 116,00", fill="black")
    return imagen


def test_devuelve_imagen_binaria():
    salida = preprocesar(_imagen())

    assert salida.mode == "L"
    assert set(np.unique(np.array(salida)).tolist()) <= {0, 255}


def test_escala_las_imagenes_chicas():
    salida = preprocesar(_imagen())

    assert max(salida.size) >= LADO_MINIMO


def test_no_falla_con_imagen_uniforme():
    salida = preprocesar(Image.new("RGB", (100, 100), "white"))

    assert salida.mode == "L"


def test_variantes_recortan_y_escalan_el_documento():
    nombres = [nombre for nombre, _ in variantes(_imagen())]

    assert nombres == [
        "original",
        "documento_2x",
        "documento_2x_clahe",
        "documento_amplio_3x_clahe",
    ]
