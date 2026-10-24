"""Tests de la extracción. Ver `specs/002-ocr-factura/tasks.md` Fase 4.

Todo corre con texto simulado: sin Tesseract real y sin EasyOCR.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.models.invoice import Columna, Formato
from app.ocr.extract import extraer
from app.ocr.normalize import numero
from app.ocr.tesseract_engine import Lectura, Palabra

VENEZOLANO = Formato(miles=".", decimal=",")
UMBRAL = 60.0


def _lectura(texto: str, confianza: float = 95.0, motor: str = "tesseract") -> Lectura:
    """Arma una lectura simulada a partir de un texto, una línea por renglón."""
    palabras = [
        Palabra(texto=palabra, confianza=confianza, linea=linea)
        for linea, contenido in enumerate(texto.split("\n"))
        for palabra in contenido.split()
    ]
    return Lectura(texto=texto, palabras=palabras, motor=motor)


def _columna(frase: str, encabezado: str | None = None, linea: int = 1) -> Columna:
    titulo = encabezado if encabezado is not None else frase
    return Columna(frase=frase, encabezado=titulo, linea=linea)


class TestNormalizacion:
    """T2.9 a T2.12: números, signo, NaN/inf y valores que no parsean."""

    def test_formato_por_defecto(self):
        assert numero("1,234.56", Formato()) == pytest.approx(1234.56)

    def test_formato_venezolano(self):
        assert numero("1.234,56", VENEZOLANO) == pytest.approx(1234.56)

    def test_separador_invertido_no_se_adivina(self):
        assert numero("1.234,56", Formato()) is None

    def test_comma_decimal_con_default_no_se_reinterpreta(self):
        assert numero("116,00", Formato()) is None

    def test_numero_pegado_a_letras(self):
        assert numero("100.00Bs", Formato()) == pytest.approx(100.0)

    def test_porcentaje(self):
        assert numero("16%", Formato()) == pytest.approx(16.0)

    def test_signo_se_conserva(self):
        assert numero("-45,00", VENEZOLANO) == pytest.approx(-45.0)

    def test_signo_no_se_inventa(self):
        assert numero("45,00", VENEZOLANO) == pytest.approx(45.0)

    def test_nan_e_inf_no_parsean(self):
        assert numero("nan", Formato()) is None
        assert numero("inf", Formato()) is None

    def test_texto_que_no_es_numero(self):
        assert numero("Verificable", Formato()) is None


class TestBusqueda:
    """T2.2 a T2.8: búsqueda del primer texto y avisos."""

    def test_encuentra_el_valor_que_sigue(self):
        lectura = _lectura("RIF: J-31245678-7\nTOTAL A PAGAR 116,00")
        columnas = [_columna("Total a pagar", "Base imponible")]
        resultado = extraer(lectura, columnas, VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == 116.0
        assert resultado.review_status == "ok"

    def test_no_coincide_dentro_de_subtotal(self):
        lectura = _lectura("SUBTOTAL 100,00 IVA 16,00 TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == 116.0

    def test_sin_coincidencia_no_inventa(self):
        lectura = _lectura("SUBTOTAL 100,00")
        resultado = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value is None
        assert resultado.review_status == "needs_review"
        assert 'no_match:Total (columna "Base imponible")' in resultado.review_reason

    def test_varias_coincidencias_es_ambiguo(self):
        lectura = _lectura("TOTAL 100,00 TOTAL 200,00")
        resultado = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value is None
        assert 'ambiguous:Total (columna "Base imponible")' in resultado.review_reason

    def test_dos_pares_distintos_mismo_valor(self):
        lectura = _lectura("Neto 116,00 Total general 116,00")
        columnas = [_columna("Neto", "Total a pagar"), _columna("Total general", "Neto")]
        resultado = extraer(lectura, columnas, VENEZOLANO, UMBRAL)

        assert [valor.value for valor in resultado.values] == [116.0, 116.0]

    def test_mayusculas_no_importan(self):
        lectura = _lectura("TOTAL A PAGAR 116,00")
        resultado = extraer(lectura, [_columna("total a pagar")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == 116.0

    def test_tildes_se_ignoran_por_defecto(self):
        lectura = _lectura("RAZÓN SOCIAL 100")
        resultado = extraer(lectura, [_columna("Razon social")], Formato(), UMBRAL)

        assert resultado.values[0].value == 100.0

    def test_acentos_apagados_exige_la_tilde(self):
        lectura = _lectura("RAZÓN SOCIAL 100")
        formato = Formato(acentos=False)
        resultado = extraer(lectura, [_columna("Razon social")], formato, UMBRAL)

        assert resultado.values[0].value is None

    def test_valor_en_la_linea_siguiente(self):
        lectura = _lectura("TOTAL\n116,00")
        resultado = extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == 116.0

    def test_primer_texto_mal_escrito_avisa(self):
        lectura = _lectura("TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Ttal", "Base imponible")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value is None
        assert "no_match:Ttal" in resultado.review_reason


class TestObjetoDeSalida:
    """T3.1 a T3.3 y T2.3: forma del resultado."""

    def test_encabezado_sale_intacto(self):
        lectura = _lectura("TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Total", "Base Imponible (Bs)")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].encabezado == "Base Imponible (Bs)"

    def test_encabezado_intacto_aunque_no_haya_valor(self):
        lectura = _lectura("otra cosa")
        resultado = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].encabezado == "Base imponible"
        assert resultado.values[0].value is None

    def test_encabezado_no_influye_en_la_busqueda(self):
        lectura = _lectura("TOTAL 116,00")
        uno = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)
        otro = extraer(lectura, [_columna("Total", "Neto")], VENEZOLANO, UMBRAL)

        assert uno.values[0].value == otro.values[0].value == 116.0

    def test_orden_de_los_valores(self):
        lectura = _lectura("IVA 16,00 TOTAL 116,00 NETO 100,00")
        columnas = [_columna("IVA"), _columna("TOTAL"), _columna("NETO")]
        resultado = extraer(lectura, columnas, VENEZOLANO, UMBRAL)

        assert [valor.encabezado for valor in resultado.values] == ["IVA", "TOTAL", "NETO"]

    def test_extracted_value_no_lleva_el_primer_texto(self):
        lectura = _lectura("TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Total", "Base imponible")], VENEZOLANO, UMBRAL)

        assert not hasattr(resultado.values[0], "frase")

    def test_raw_text_viaja_en_el_objeto(self):
        lectura = _lectura("TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL)

        assert resultado.raw_text == "TOTAL 116,00"

    def test_no_existe_unbalanced_total(self):
        lectura = _lectura("TOTAL 116,00")
        resultado = extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL)

        assert "unbalanced_total" not in (resultado.review_reason or "")

    def test_columna_es_inmutable(self):
        columna = _columna("Total", "Base imponible")

        with pytest.raises(FrozenInstanceError):
            columna.encabezado = "Neto"  # type: ignore[misc]


class TestColumnasDeTexto:
    """Solo se extrae lo que el contador pidió en plantilla.csv."""

    def test_rif_pedido_se_guarda_como_texto(self):
        lectura = _lectura("RIF: J-31245678-7\nTotal 116,00")
        columnas = [_columna("RIF", "RIF del proveedor"), _columna("Total")]
        resultado = extraer(lectura, columnas, VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == "J-31245678-7"
        assert resultado.values[1].value == 116.0

    def test_fecha_pedida_se_guarda_tal_cual(self):
        lectura = _lectura("Fecha 12/10/2026")
        resultado = extraer(lectura, [_columna("Fecha")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == "12/10/2026"

    def test_no_se_buscan_campos_de_control(self):
        lectura = _lectura("RIF: J-31245678-7\nFactura N° 001-00001234\nTotal 116,00")
        resultado = extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL)

        assert not hasattr(resultado, "control")
        assert resultado.review_reason is None


class TestCombinacionDeMotores:
    """T1.4: EasyOCR entra solo donde Tesseract falló o quedó bajo el umbral."""

    def test_no_se_llama_si_tesseract_leyo_bien(self):
        llamadas = []

        def easyocr() -> Lectura:
            llamadas.append(1)
            return _lectura("TOTAL 116,00", motor="easyocr")

        lectura = _lectura("TOTAL 116,00")
        extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL, easyocr)

        assert llamadas == []

    def test_entra_si_tesseract_no_encontro(self):
        lectura = _lectura("texto ilegible")
        resultado = extraer(
            lectura,
            [_columna("Total", "Base imponible")],
            VENEZOLANO,
            UMBRAL,
            lambda: _lectura("TOTAL 116,00", motor="easyocr"),
        )

        assert resultado.values[0].value == 116.0
        assert "easyocr" in resultado.engines_used

    def test_entra_una_sola_vez_para_varias_columnas(self):
        llamadas = []

        def easyocr() -> Lectura:
            llamadas.append(1)
            return _lectura("", motor="easyocr")

        lectura = _lectura("texto ilegible")
        columnas = [_columna("Total"), _columna("IVA")]
        extraer(lectura, columnas, VENEZOLANO, UMBRAL, easyocr)

        assert len(llamadas) == 1

    def test_dos_columnas_pueden_usar_motores_distintos(self):
        lectura = _lectura("IVA 16,00")
        columnas = [_columna("IVA", "Monto del IVA"), _columna("Total", "Base imponible")]
        resultado = extraer(
            lectura,
            columnas,
            VENEZOLANO,
            UMBRAL,
            lambda: _lectura("TOTAL 116,00", motor="easyocr"),
        )

        assert resultado.values[0].value == 16.0
        assert resultado.values[1].value == 116.0
        assert resultado.engines_used == ["tesseract", "easyocr"]

    def test_confianza_baja_se_marca(self):
        lectura = _lectura("TOTAL 116,00", confianza=40.0)
        resultado = extraer(lectura, [_columna("Total")], VENEZOLANO, UMBRAL)

        assert resultado.values[0].value == 116.0
        assert "low_confidence" in resultado.review_reason

    def test_otros_idiomas(self):
        lectura = _lectura("注文番号 12345")
        resultado = extraer(lectura, [_columna("注文番号", "Referencia")], Formato(), UMBRAL)

        assert resultado.values[0].encabezado == "Referencia"
        assert resultado.values[0].value == 12345.0
