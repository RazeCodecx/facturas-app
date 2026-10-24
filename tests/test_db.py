"""Tests de la capa de base de datos."""

from __future__ import annotations

from tests.conftest import _valores


def _insertar(db, **cambios) -> int:
    """Inserta una factura con los valores por defecto."""
    datos = {
        "review_status": "ok",
        "review_reason": None,
        "values": _valores(),
    }
    datos.update(cambios)
    return db.insertar_factura(**datos)


class TestEsquema:
    """La migracion crea solo las tablas que la app necesita."""

    def test_tablas(self, db):
        from app.db.pool import conexion

        with conexion() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            tablas = {f["table_name"] for f in cur.fetchall()}

        assert {"invoices", "ocr_runs", "schema_migrations"} <= tablas
        for sobrante in ("invoice_items", "taxes", "fiscal_profiles"):
            assert sobrante not in tablas

    def test_invoices_no_tiene_campos_de_control(self, db):
        from app.db.pool import conexion

        with conexion() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'invoices'"
            )
            columnas = {f["column_name"] for f in cur.fetchall()}

        assert columnas == {
            "id",
            "review_status",
            "review_reason",
            "values",
            "created_at",
        }


class TestValoresDelContador:
    """Los valores guardan la FRASE, que es la clave del emparejamiento."""

    def test_values_conserva_la_frase(self, db):
        invoice_id = _insertar(db)
        factura = db.obtener_factura(invoice_id)
        valores = factura["values"]

        assert len(valores) == 2
        assert valores[0]["frase"] == "Total a pagar"
        assert valores[0]["encabezado"] == "Total factura"

    def test_values_no_guarda_el_motor(self, db):
        factura = db.obtener_factura(_insertar(db))
        assert all("engine" not in valor for valor in factura["values"])

    def test_values_acepta_encabezado_con_acentos(self, db):
        invoice_id = _insertar(
            db,
            values=[
                {
                    "frase": "Razon social",
                    "encabezado": "Razón Social",
                    "value": "ACME",
                    "confidence": 99.0,
                }
            ],
        )
        factura = db.obtener_factura(invoice_id)
        assert factura["values"][0]["encabezado"] == "Razón Social"


class TestSinDeduplicacion:
    """Cada foto crea una fila, aunque sea la misma foto."""

    def test_dos_inserciones_crean_dos_filas(self, db):
        primero = _insertar(db)
        segundo = _insertar(db)

        assert primero != segundo
        assert db.contar_facturas() == 2


class TestDetalle:
    """El detalle no trae texto crudo."""

    def test_detalle_no_trae_raw_text(self, db):
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
    """raw_text se guarda solo cuando hizo falta."""

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


class TestFiltros:
    """El único filtro es el estado de revisión, y va en el SELECT."""

    def test_filtro_por_review_status(self, db):
        _insertar(db, review_status="ok")
        _insertar(db, review_status="needs_review", review_reason="no_match")

        solo_ok = db.listar_facturas(review_status="ok")
        assert len(solo_ok) == 1
        assert solo_ok[0]["review_status"] == "ok"

        pendientes = db.listar_facturas(review_status="needs_review")
        assert len(pendientes) == 1

    def test_contar_respeta_el_filtro(self, db):
        _insertar(db, review_status="ok")
        _insertar(db, review_status="needs_review")

        assert db.contar_facturas() == 2
        assert db.contar_facturas(review_status="ok") == 1

    def test_sin_filtros_trae_todas(self, db):
        for _ in range(3):
            _insertar(db)
        assert db.contar_facturas() == 3
