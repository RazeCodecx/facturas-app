"""Tests del preprocesado y del arranque perezoso de EasyOCR."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from app.ocr import easyocr_engine
from app.ocr.preprocess import LADO_MINIMO, preprocesar


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


def test_easyocr_sin_lector_devuelve_none(monkeypatch):
    monkeypatch.setattr(easyocr_engine, "_resuelto", True)
    monkeypatch.setattr(easyocr_engine, "_lector", None)

    assert easyocr_engine.leer(_imagen()) is None
