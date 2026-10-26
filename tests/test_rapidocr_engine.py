"""Tests del motor RapidOCR sin cargar modelos reales."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.ocr import rapidocr_engine
from app.ocr.rapidocr_engine import (
    RapidOCRNoDisponible,
    _agrupar_lineas,
    leer,
)


def _caja(izquierda: int, arriba: int, derecha: int, abajo: int) -> list[list[int]]:
    return [
        [izquierda, arriba],
        [derecha, arriba],
        [derecha, abajo],
        [izquierda, abajo],
    ]


def test_agrupa_cajas_en_lineas_y_normaliza_confianza():
    cajas = np.array(
        [
            _caja(10, 10, 100, 30),
            _caja(110, 10, 180, 30),
            _caja(10, 40, 100, 60),
        ]
    )

    lectura = _agrupar_lineas(
        cajas,
        ("TOTAL", "116,00", "OTRA"),
        (0.90, 0.80, 0.70),
    )

    assert lectura.texto == "TOTAL 116,00\nOTRA"
    assert [palabra.linea for palabra in lectura.palabras] == [0, 0, 1]
    assert lectura.confianza_linea(0) == pytest.approx(85.0)
    assert lectura.confianza_linea(1) == pytest.approx(70.0)


def test_ignora_textos_vacios():
    lectura = _agrupar_lineas(
        np.array([_caja(10, 10, 100, 30)]),
        ("  ",),
        (0.90,),
    )

    assert lectura.texto == ""
    assert lectura.palabras == []


def test_leer_devuelve_lectura_vacia_sin_detecciones(monkeypatch):
    class MotorVacio:
        def __call__(self, imagen):
            return SimpleNamespace(boxes=None, txts=None, scores=None)

    monkeypatch.setattr(rapidocr_engine, "_obtener_motor", lambda: MotorVacio())

    lectura = leer(Image.new("RGB", (20, 20), "white"))

    assert lectura.texto == ""
    assert lectura.palabras == []
    assert lectura.motor == "rapidocr"


def test_leer_propaga_motor_no_disponible(monkeypatch):
    def _sin_motor():
        raise RapidOCRNoDisponible("sin motor")

    monkeypatch.setattr(rapidocr_engine, "_obtener_motor", _sin_motor)

    with pytest.raises(RapidOCRNoDisponible):
        leer(Image.new("RGB", (20, 20), "white"))
