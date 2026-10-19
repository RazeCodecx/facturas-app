"""Tests de la capa de base de datos. Ver `specs/001-base-datos/tasks.md`."""

from __future__ import annotations

from tests.conftest import _valores


def _insertar(db, **cambios) -> int | None:
    """Inserta una factura completa con los valores por defecto."""
    datos = {
        "supplier_rif": "J-31245678-7",
        "serie": "001",
        "numero": "00001234",
        "issue_date": "2026-10-01",
        "fiscal_profile_id": None,
        "review_status": "ok",
        "review_reason": None,
        "values": _valores(),
        "items": [
            {
                "line_number": 1,
                "code": "A1",
                "description": "Servicio",
                "quantity": 1.0,
                "unit_price": 1000.0,
                "amount": 1000.0,
            }
        ],
        "taxes": [{"tax_type": "IVA", "rate": 16.0, "base_amount": 1000.0, "amount": 160.0}],
    }
    datos.update(cambios)
    return db.insertar_factura(**datos)


class TestEsquema:
    """La migracion crea las 5 tablas de SCHEMAS.md 3."""

    def test_cinco_tablas(self, db):
        from app.db.pool import conexion

        with conexion() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tablas = {f["table_name"] for f in cur.fetchall()}

        for esperada in (
            "invoices",
            "invoice_items",
            "taxes",
            "fiscal_profiles",
            "ocr_runs",
        ):
            assert esperada in tablas, f"falta la tabla {esperada}"

    def test_dedupe_key_es_unico(self, db):
        primero = _insertar(db)
        segundo = _insertar(db)

        assert primero is not None
        assert segundo is None, "la segunda insercion deberia rebotar por dedupe_key"

    def test_dedupe_rechaza_y_devuelve_none(self, db):
        """CA-12: nunca hay dos registros contables para la misma factura."""
        _insertar(db)
        repetida = _insertar(db)
        assert repetida is None

    def test_una_factura_sin_rif_se_guarda(self, db):
        """CA-52: sin RIF se guarda igual, con el RIF en NULL."""
        invoice_id = _insertar(
            db,
            supplier_rif=None,
            review_status="needs_review",
            review_reason="unreadable_rif",
        )
        assert invoice_id is not None

        factura = db.obtener_factura(invoice_id)
        assert factura is not None
        assert factura["supplier_rif"] is None
        assert factura["review_reason"] == "unreadable_rif"

    def test_review_status_por_defecto_es_needs_review(self, db):
        """Una factura insertada sin validar queda pendiente, nunca en ok."""
        invoice_id = _insertar(db, review_status="needs_review", review_reason=None)
        factura = db.obtener_factura(invoice_id)
        assert factura["review_status"] == "needs_review"


class TestValoresDelContador:
    """CA-51: los valores guardan la FRASE, que es la clave del emparejamiento."""

    def test_values_conserva_la_frase(self, db):
        invoice_id = _insertar(db)
        factura = db.obtener_factura(invoice_id)
        valores = factura["values"]

        assert len(valores) == 2
        assert valores[0]["frase"] == "Total a pagar"
        assert valores[0]["encabezado"] == "Total factura"
        assert valores[0]["engine"] == "tesseract"

    def test_values_conserva_el_motor_por_valor(self, db):
        """D-01: EasyOCR entra por frase, asi que conviven los dos motores."""
        factura = db.obtener_factura(_insertar(db))
        motores = {v["frase"]: v["engine"] for v in factura["values"]}
        assert motores["Total a pagar"] == "tesseract"
        assert motores["IVA"] == "easyocr"

    def test_values_acepta_encabezado_con_acentos(self, db):
        invoice_id = _insertar(
            db,
            values=[
                {
                    "frase": "Razon social",
                    "encabezado": "Razón Social",
                    "value": "ACME",
                    "confidence": 99.0,
                    "engine": "tesseract",
                }
            ],
        )
        factura = db.obtener_factura(invoice_id)
        assert factura["values"][0]["encabezado"] == "Razón Social"


class TestExactitud:
    """CA-14: los importes conservan su valor exacto."""

    def test_importe_entero_exacto(self, db):
        invoice_id = _insertar(
            db,
            items=[
                {
                    "line_number": 1,
                    "code": None,
                    "description": "Algo",
                    "quantity": 1.0,
                    "unit_price": 1234567890123.0,
                    "amount": 1234567890123.0,
                }
            ],
            taxes=[],
        )
        factura = db.obtener_factura(invoice_id)
        assert factura["items"][0]["amount"] == 1234567890123.0

    def test_importe_con_decimales(self, db):
        invoice_id = _insertar(
            db,
            items=[
                {
                    "line_number": 1,
                    "code": None,
                    "description": "Algo",
                    "quantity": 2.5,
                    "unit_price": 19.99,
                    "amount": 49.975,
                }
            ],
            taxes=[],
        )
        factura = db.obtener_factura(invoice_id)
        assert factura["items"][0]["amount"] == 49.975


class TestDetalle:
    """CA-13: el detalle trae items e impuestos, nunca el texto del OCR."""

    def test_detalle_trae_items_y_taxes(self, db):
        factura = db.obtener_factura(_insertar(db))
        assert len(factura["items"]) == 1
        assert len(factura["taxes"]) == 1
        assert factura["items"][0]["description"] == "Servicio"
        assert factura["taxes"][0]["tax_type"] == "IVA"

    def test_detalle_no_trae_raw_text(self, db):
        """CA-13: el texto reconocido nunca sale."""
        invoice_id = _insertar(db)
        db.registrar_ocr_run(
            invoice_id=invoice_id,
            original_path="imagenes/a.heic",
            converted_path="imagenes/a.png",
            raw_text="TEXTO SECRETO DEL OCR",
            engine_version="tesseract-5.4.0",
            confidence=90.0,
        )
        factura = db.obtener_factura(invoice_id)
        assert "raw_text" not in factura
        assert "TEXTO SECRETO" not in str(factura)


class TestOcrRuns:
    """CA-58 y CA-59: raw_text se guarda solo cuando hizo falta."""

    def test_raw_text_se_guarda_cuando_hubo_dudas(self, db):
        invoice_id = _insertar(db, review_status="needs_review", review_reason="no_match")
        run_id = db.registrar_ocr_run(
            invoice_id=invoice_id,
            original_path="imagenes/a.heic",
            converted_path="imagenes/a.png",
            raw_text="texto reconocido",
            engine_version="tesseract-5.4.0",
            confidence=41.0,
        )
        assert run_id > 0

        from app.db.pool import conexion

        with conexion() as conn, conn.cursor() as cur:
            cur.execute("SELECT raw_text FROM ocr_runs WHERE id = %s", (run_id,))
            assert cur.fetchone()["raw_text"] == "texto reconocido"

    def test_raw_text_queda_null_cuando_todo_salio_bien(self, db):
        invoice_id = _insertar(db)
        run_id = db.registrar_ocr_run(
            invoice_id=invoice_id,
            original_path="imagenes/b.heic",
            converted_path="imagenes/b.png",
            raw_text=None,
            engine_version="tesseract-5.4.0",
            confidence=97.0,
        )

        from app.db.pool import conexion

        with conexion() as conn, conn.cursor() as cur:
            cur.execute("SELECT raw_text FROM ocr_runs WHERE id = %s", (run_id,))
            assert cur.fetchone()["raw_text"] is None

    def test_una_factura_sin_rif_igual_registra_la_corrida(self, db):
        invoice_id = _insertar(
            db, supplier_rif=None, review_status="needs_review", review_reason="unreadable_rif"
        )
        run_id = db.registrar_ocr_run(
            invoice_id=invoice_id,
            original_path="imagenes/c.heic",
            converted_path=None,
            raw_text=None,
            engine_version="tesseract-5.4.0",
            confidence=80.0,
        )
        assert run_id > 0


class TestFiltros:
    """Los filtros van en el SELECT, no en Python."""

    def test_filtro_por_review_status(self, db):
        _insertar(db, review_status="ok")
        _insertar(
            db,
            numero="00009999",
            review_status="needs_review",
            review_reason="no_match",
        )

        solo_ok = db.listar_facturas(review_status="ok")
        assert len(solo_ok) == 1
        assert solo_ok[0]["review_status"] == "ok"

        pendientes = db.listar_facturas(review_status="needs_review")
        assert len(pendientes) == 1

    def test_filtro_por_issue_date(self, db):
        _insertar(db, issue_date="2026-01-15")
        _insertar(db, numero="00002222", issue_date="2026-10-01")

        resultado = db.listar_facturas(issue_date="2026-01-15")
        assert len(resultado) == 1
        assert str(resultado[0]["issue_date"]) == "2026-01-15"

    def test_filtro_por_supplier_rif(self, db):
        _insertar(db)
        _insertar(db, supplier_rif="J-99999999-9", numero="00005555")

        resultado = db.listar_facturas(supplier_rif="J-99999999-9")
        assert len(resultado) == 1

    def test_contar_respeta_los_filtros(self, db):
        _insertar(db, review_status="ok")
        _insertar(db, numero="00003333", review_status="needs_review")

        assert db.contar_facturas() == 2
        assert db.contar_facturas(review_status="ok") == 1

    def test_sin_filtros_trae_todas(self, db):
        for n in range(3):
            _insertar(db, numero=f"0001000{n}")
        assert db.contar_facturas() == 3


class TestDedupeKey:
    """La clave se arma con las cuatro partes de SCHEMAS.md 2.1."""

    def test_partes_vacias_no_revientan(self, db):
        """Sin RIF la clave queda con huecos, pero la factura entra."""
        invoice_id = _insertar(
            db, supplier_rif=None, serie=None, numero=None, issue_date=None
        )
        assert invoice_id is not None

    def test_misma_clave_no_crea_dos(self, db):
        """Dos facturas con las mismas cuatro partes son la misma factura."""
        _insertar(db)
        _insertar(db, review_status="needs_review", review_reason="no_match")
        assert db.contar_facturas() == 1

    def test_una_parte_vacia_cambia_la_clave(self, db):
        """Sin serie la clave es distinta, y eso es una factura distinta.

        Por eso el RIF es lo unico que evita el choque entre proveedores.
        """
        _insertar(db)
        _insertar(db, serie=None)
        assert db.contar_facturas() == 2

    def test_existe_dedupe_key_devuelve_el_id(self, db):
        invoice_id = _insertar(db)
        clave = "J-31245678-7|001|00001234|2026-10-01"
        assert db.existe_dedupe_key(clave) == invoice_id
        assert db.existe_dedupe_key("no-existe") is None