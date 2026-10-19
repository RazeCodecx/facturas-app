"""Tests de `app/export/plantilla.py` (004 T2.9, T2.10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.export import csv as modulo_csv
from app.export.plantilla import (
    COLUMNAS_POR_DEFECTO,
    MENSAJE_FORMATO,
    PlantillaError,
    leer_columnas,
    leer_plantilla,
)
from app.models.invoice import Formato

BOM = b"\xef\xbb\xbf"


def _escribir(tmp_path: Path, texto: str, *, bom: bool = True) -> Path:
    ruta = tmp_path / "plantilla.csv"
    datos = texto.encode("utf-8")
    ruta.write_bytes((BOM if bom else b"") + datos)
    return ruta


def _leer(tmp_path: Path, texto: str, *, bom: bool = True):
    ruta = _escribir(tmp_path, texto, bom=bom)
    return leer_plantilla(ruta, tmp_path / ".marcador")


def test_archivo_vacio_devuelve_defaults_y_escribe_mensaje(tmp_path: Path) -> None:
    ruta = tmp_path / "plantilla.csv"
    ruta.write_bytes(BOM)

    plantilla = leer_plantilla(ruta, tmp_path / ".marcador")

    assert plantilla.columnas == COLUMNAS_POR_DEFECTO
    assert plantilla.columnas == leer_plantilla(ruta, tmp_path / ".marcador").columnas
    escrito = ruta.read_bytes()
    assert escrito.startswith(BOM)
    assert MENSAJE_FORMATO.encode("utf-8") in escrito


def test_solo_lineas_vacias_es_vacio(tmp_path: Path) -> None:
    ruta = tmp_path / "plantilla.csv"
    ruta.write_bytes(BOM + b"\n\n   \n")

    assert leer_columnas(ruta) == COLUMNAS_POR_DEFECTO


def test_una_sola_linea_devuelve_una_columna(tmp_path: Path) -> None:
    columnas = _leer(tmp_path, "Total = Base imponible\n").columnas

    assert len(columnas) == 1
    assert columnas[0].frase == "Total"
    assert columnas[0].encabezado == "Base imponible"
    assert columnas[0].linea == 1


def test_falta_el_igual(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError) as error:
        _leer(tmp_path, "A = B\nC = D\nE = F\nTotal Base imponible\n")

    mensaje = str(error.value)
    assert "línea 4" in mensaje
    assert 'primer texto = segundo texto' in mensaje


def test_dos_iguales(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError) as error:
        _leer(tmp_path, "Total = Base = Imponible\n")

    assert "línea 1" in str(error.value)
    assert "más de un" in str(error.value)


def test_primer_texto_vacio(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError) as error:
        _leer(tmp_path, "  = Base imponible\n")

    assert "línea 1" in str(error.value)
    assert "no dice qué buscar" in str(error.value)


def test_primer_texto_repetido_nombra_las_dos_lineas(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError) as error:
        _leer(tmp_path, "A = Uno\nB = Dos\nTotal = Base\nC = Tres\nTotal = Otra\n")

    mensaje = str(error.value)
    assert "líneas 3 y 5" in mensaje
    assert '"Total"' in mensaje


def test_primer_texto_repetido_ignora_mayusculas(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError):
        _leer(tmp_path, "Total = Base\nTOTAL = Otra\n")


def test_segundo_texto_puede_repetirse(tmp_path: Path) -> None:
    columnas = _leer(tmp_path, "Total = Base imponible\nBase = Base imponible\n").columnas

    assert [columna.frase for columna in columnas] == ["Total", "Base"]


def test_conserva_idioma_y_espacios_interiores(tmp_path: Path) -> None:
    columnas = _leer(tmp_path, "  Total   a   pagar  =  合計  金額  \n").columnas

    assert columnas[0].frase == "Total   a   pagar"
    assert columnas[0].encabezado == "合計  金額"


def test_archivo_inexistente(tmp_path: Path) -> None:
    with pytest.raises(PlantillaError) as error:
        leer_columnas(tmp_path / "no-existe.csv")

    assert "plantilla.csv" in str(error.value)


def test_archivo_sin_bom(tmp_path: Path) -> None:
    columnas = _leer(tmp_path, "Total = Base imponible\n", bom=False).columnas

    assert columnas[0].encabezado == "Base imponible"


def test_segundo_texto_vacio_usa_el_primero(tmp_path: Path) -> None:
    columna = _leer(tmp_path, "Moneda =\n").columnas[0]

    assert (columna.frase, columna.encabezado) == ("Moneda", "Moneda")


def test_formato_completo(tmp_path: Path) -> None:
    formato = _leer(
        tmp_path, "#miles=. #decimal=, #acentos=0\nTotal = Base\n"
    ).formato

    assert formato == Formato(miles=".", decimal=",", acentos=False)


def test_gana_la_ultima_opcion(tmp_path: Path) -> None:
    formato = _leer(
        tmp_path, "#miles=, #decimal=.\n#decimal=,\nTotal = Base\n"
    ).formato

    assert formato == Formato(miles=",", decimal=",", acentos=True)


def test_defaults_del_formato(tmp_path: Path) -> None:
    formato = _leer(tmp_path, "Total = Base\n").formato

    assert formato == Formato(miles=",", decimal=".", acentos=True)


def test_formato_mal_escrito_no_es_error(tmp_path: Path) -> None:
    plantilla = _leer(
        tmp_path, "#cualquier cosa\n#miles=ab\n#acentos=si\nTotal = Base\n"
    )

    assert plantilla.columnas[0].encabezado == "Base"
    assert plantilla.formato == Formato()


def test_lineas_numeral_en_distintas_posiciones(tmp_path: Path) -> None:
    columnas = _leer(
        tmp_path,
        "# primero\nTotal = Base\n# en medio\n#miles=.\nIVA = Monto\n# último\n",
    ).columnas

    assert [columna.frase for columna in columnas] == ["Total", "IVA"]
    assert [columna.linea for columna in columnas] == [2, 5]


def test_mensaje_explica_las_tres_opciones_en_dos_idiomas(tmp_path: Path) -> None:
    ruta = tmp_path / "plantilla.csv"
    ruta.write_bytes(BOM)

    leer_plantilla(ruta, tmp_path / ".marcador")
    mensaje = ruta.read_text(encoding="utf-8-sig")

    for palabra in ("miles", "decimal", "acentos", "thousands", "separator", "default"):
        assert palabra in mensaje


def test_el_mensaje_se_escribe_una_sola_vez(tmp_path: Path) -> None:
    ruta = tmp_path / "plantilla.csv"
    marcador = tmp_path / ".marcador"
    ruta.write_bytes(BOM)

    leer_plantilla(ruta, marcador)
    assert marcador.exists()

    ruta.write_bytes(BOM)
    leer_plantilla(ruta, marcador)

    assert ruta.read_bytes() == BOM


def test_el_export_no_modifica_la_plantilla(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "Total = Base imponible\n")
    antes = ruta.read_bytes()
    plantilla = leer_plantilla(ruta, tmp_path / ".marcador")

    modulo_csv.generar_csv([], plantilla.columnas, plantilla.formato)

    assert ruta.read_bytes() == antes
