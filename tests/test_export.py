"""Tests del CSV de facturas y del archivo de avisos (004 T7.1-T7.4)."""

from __future__ import annotations

import csv
import io

from app.export.avisos import CABECERA, generar_avisos
from app.export.csv import generar_csv
from app.models.invoice import Columna, Formato


def _columna(frase: str, encabezado: str, linea: int = 1) -> Columna:
    return Columna(frase, encabezado, linea)


def _valor(frase: str, value) -> dict[str, object]:
    return {
        "frase": frase,
        "encabezado": frase.title(),
        "value": value,
        "confidence": 90.0,
    }


def _factura(invoice_id: int, valores: list[dict[str, object]], motivo: str | None = None):
    return {
        "id": invoice_id,
        "review_status": "needs_review" if motivo else "ok",
        "review_reason": motivo,
        "values": valores,
        "created_at": "2026-10-12T10:00:00Z",
    }


def _filas(contenido: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(contenido.decode("utf-8-sig"))))


def test_una_cabecera_y_una_fila_por_factura() -> None:
    columnas = [_columna("Total", "Base imponible"), _columna("IVA", "Monto del IVA")]
    facturas = [
        _factura(1, [_valor("Total", "116.00"), _valor("IVA", "16.00")]),
        _factura(2, [_valor("Total", None), _valor("IVA", "8.00")]),
    ]

    filas = _filas(generar_csv(facturas, columnas, Formato()))

    assert filas[0] == ["Base imponible", "Monto del IVA"]
    assert filas[1] == ["116.00", "16.00"]
    assert filas[2] == ["", "8.00"]
    assert len(filas) == 3


def test_empieza_con_bom_y_no_hay_segunda_cabecera() -> None:
    contenido = generar_csv(
        [_factura(1, [_valor("Total", "116.00")])],
        [_columna("Total", "Base imponible")],
        Formato(),
    )

    assert contenido.startswith(b"\xef\xbb\xbf")
    filas = _filas(contenido)
    assert len(filas) == 2
    assert filas[0] == ["Base imponible"]


def test_empareja_por_primer_texto_sin_importar_el_orden() -> None:
    columnas = [_columna("Total", "Base imponible"), _columna("IVA", "Monto del IVA")]
    factura = _factura(1, [_valor("IVA", "16.00"), _valor("Total", "116.00")])

    filas = _filas(generar_csv([factura], columnas, Formato()))

    assert filas[1] == ["116.00", "16.00"]


def test_reordenar_y_renombrar_columnas_conserva_los_valores() -> None:
    factura = _factura(1, [_valor("Total", "116.00"), _valor("IVA", "16.00")])

    antes = _filas(
        generar_csv(
            [factura],
            [_columna("Total", "Base imponible"), _columna("IVA", "Monto del IVA")],
            Formato(),
        )
    )
    despues = _filas(
        generar_csv(
            [factura],
            [_columna("IVA", "Impuesto"), _columna("Total", "Total a pagar")],
            Formato(),
        )
    )

    assert antes[1] == ["116.00", "16.00"]
    assert despues[1] == ["16.00", "116.00"]
    assert despues[0] == ["Impuesto", "Total a pagar"]


def test_borrar_una_linea_no_corre_el_valor_a_la_vecina() -> None:
    factura = _factura(1, [_valor("Total", "116.00"), _valor("IVA", "16.00")])

    filas = _filas(
        generar_csv([factura], [_columna("Total", "Base imponible")], Formato())
    )

    assert filas[0] == ["Base imponible"]
    assert filas[1] == ["116.00"]


def test_comparacion_sin_tildes_y_sin_mayusculas() -> None:
    columnas = [_columna("Razón social", "Proveedor")]
    factura = _factura(1, [_valor("RAZON SOCIAL", "ACME")])

    assert _filas(generar_csv([factura], columnas, Formato(acentos=True)))[1] == ["ACME"]
    assert _filas(generar_csv([factura], columnas, Formato(acentos=False)))[1] == [""]


def test_factura_con_columnas_vacias_se_exporta() -> None:
    facturas = [_factura(1, [_valor("Total", None)], motivo="no_match")]

    filas = _filas(generar_csv(facturas, [_columna("Total", "Base imponible")], Formato()))

    assert len(filas) == 2
    assert filas[1] == [""]


def test_numeros_con_dos_decimales_al_escribir() -> None:
    facturas = [_factura(1, [_valor("Total", 116)])]

    filas = _filas(generar_csv(facturas, [_columna("Total", "Base")], Formato()))

    assert filas[1] == ["116.00"]


def test_no_escribe_primer_texto_ni_datos_internos() -> None:
    factura = _factura(
        1,
        [_valor("Total", "116.00")],
        motivo='no_match:Total (columna "Base imponible")',
    )
    contenido = generar_csv(
        [_factura(1, [_valor("Total", "116.00")])],
        [_columna("Total", "Base imponible")],
        Formato(),
    ).decode("utf-8-sig")

    for prohibido in ("Total", "raw_text", "review_status", "review_reason", "ocr_runs"):
        assert prohibido not in contenido
    assert factura["review_reason"] not in contenido


def test_avisos_siempre_trae_cabecera() -> None:
    contenido = generar_avisos([])

    assert contenido.startswith(b"\xef\xbb\xbf")
    assert _filas(contenido) == [list(CABECERA)]


def test_avisos_parsea_frase_columna_y_motivo() -> None:
    factura = _factura(
        142,
        [_valor("Total a pagar", None)],
        motivo='no_match:Total a pagar (columna "Base imponible");low_confidence',
    )

    filas = _filas(generar_avisos([factura]))

    assert filas[0] == list(CABECERA)
    assert filas[1] == ["142", "Total a pagar", "Base imponible", "no_match"]
    assert filas[2] == ["142", "", "", "low_confidence"]


def test_avisos_sin_motivo_solo_cabecera() -> None:
    filas = _filas(generar_avisos([_factura(7, [], motivo=None)]))

    assert filas == [list(CABECERA)]
