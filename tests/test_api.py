"""Tests de la API con `TestClient`: base y OCR mockeados (003 T4.1-T4.5)."""

from __future__ import annotations

import io
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytesseract
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import export as api_export
from app.api import invoices as api_invoices
from app.api import scan as api_scan
from app.export.plantilla import Plantilla, PlantillaError
from app.main import app as fastapi_app
from app.models.invoice import Columna, ControlFields, ExtractedValue, ExtractionResult, Formato

_png = io.BytesIO()
Image.new("RGB", (24, 24), "white").save(_png, format="PNG")
PNG = _png.getvalue()

_heic = io.BytesIO()
Image.new("RGB", (24, 24), "white").save(_heic, format="HEIF")
HEIC = _heic.getvalue()


class FakeQueries:
    """Base en memoria con la misma forma que `app.db.queries`."""

    def __init__(self) -> None:
        self.facturas: dict[str, dict[str, Any]] = {}
        self.ocr_runs: list[dict[str, Any]] = []
        self.siguiente_id = 1
        self._lock = threading.Lock()

    def armar_dedupe_key(self, rif, serie, numero, fecha) -> str:
        return "|".join([rif or "", serie or "", numero or "", fecha or ""])

    def insertar_factura(self, **campos: Any) -> int | None:
        with self._lock:
            return self._insertar(campos)

    def _insertar(self, campos: dict[str, Any]) -> int | None:
        clave = self.armar_dedupe_key(
            campos["supplier_rif"],
            campos["serie"],
            campos["numero"],
            campos["issue_date"],
        )
        if clave in self.facturas:
            return None

        invoice_id = self.siguiente_id
        self.siguiente_id += 1
        self.facturas[clave] = {
            "id": invoice_id,
            "supplier_rif": campos["supplier_rif"],
            "serie": campos["serie"],
            "numero": campos["numero"],
            "issue_date": campos["issue_date"],
            "review_status": campos["review_status"],
            "review_reason": campos["review_reason"],
            "values": campos["values"],
            "created_at": "2026-10-12T10:00:00Z",
            "items": list(campos["items"]),
            "taxes": list(campos["taxes"]),
        }
        return invoice_id

    def existe_dedupe_key(self, clave: str) -> int | None:
        factura = self.facturas.get(clave)
        return factura["id"] if factura else None

    def obtener_factura(self, invoice_id: int) -> dict[str, Any] | None:
        for factura in self.facturas.values():
            if factura["id"] == invoice_id:
                return factura
        return None

    def registrar_ocr_run(self, **campos: Any) -> int:
        self.ocr_runs.append(campos)
        return len(self.ocr_runs)

    def _filtrar(self, supplier_rif=None, issue_date=None, review_status=None):
        return [
            factura
            for factura in self.facturas.values()
            if (not supplier_rif or factura["supplier_rif"] == supplier_rif)
            and (not issue_date or factura["issue_date"] == issue_date)
            and (not review_status or factura["review_status"] == review_status)
        ]

    def listar_facturas(self, *, limit=50, offset=0, **filtros):
        return self._filtrar(**filtros)[offset : offset + limit]

    def contar_facturas(self, **filtros):
        return len(self._filtrar(**filtros))

    def listar_para_exportar(self, **filtros):
        return self._filtrar(**filtros)


def _resultado(motivo: str | None = None) -> ExtractionResult:
    valor = ExtractedValue("Base imponible", "116.00", 92.0, "tesseract")
    if motivo is not None:
        valor = ExtractedValue("Base imponible", None, 0.0, "tesseract")
    return ExtractionResult(
        values=[valor],
        control=ControlFields("J-31245678-7", "001", "00001234", "2026-10-12"),
        items=[],
        raw_text="TOTAL 116,00",
        engines_used=["tesseract"],
        review_status="needs_review" if motivo else "ok",
        review_reason=motivo,
    )


def _columna() -> Columna:
    return Columna("Total", "Base imponible", 1)


@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path) -> FakeQueries:
    base = FakeQueries()
    monkeypatch.setattr(api_scan, "queries", base)
    monkeypatch.setattr(api_invoices, "queries", base)
    monkeypatch.setattr(api_export, "queries", base)
    monkeypatch.setattr(api_scan, "config", SimpleNamespace(
        max_upload_mb=10, ocr_confidence_threshold=60.0, image_dir=tmp_path
    ))
    monkeypatch.setattr(
        api_scan, "leer_plantilla", lambda: Plantilla([_columna()], Formato())
    )
    monkeypatch.setattr(api_scan, "leer_factura", lambda *args: _resultado())
    monkeypatch.setattr(
        api_export, "leer_plantilla", lambda: Plantilla([_columna()], Formato())
    )
    return base


@pytest.fixture()
def cliente() -> TestClient:
    return TestClient(fastapi_app)


def _subir(cliente: TestClient, datos: bytes | None = None, tipo: str = "image/png"):
    return cliente.post(
        "/api/v1/invoices/scan",
        files={"file": ("factura", PNG if datos is None else datos, tipo)},
    )


def test_health_connected_y_disconnected(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.esta_conectada", lambda: True)
    assert cliente.get("/health").json() == {"status": "ok", "database": "connected"}

    monkeypatch.setattr("app.main.esta_conectada", lambda: False)
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["database"] == "disconnected"


def test_scan_crea_la_factura(cliente: TestClient, fake: FakeQueries, tmp_path) -> None:
    respuesta = _subir(cliente)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["invoice_id"] == 1
    assert cuerpo["review_status"] == "ok"
    assert cuerpo["warnings"] == []
    assert len(fake.facturas) == 1
    assert fake.ocr_runs[0]["raw_text"] is None
    assert list((tmp_path / "original").iterdir())
    assert list((tmp_path / "convertida").iterdir())


def test_scan_guarda_raw_text_solo_si_hace_falta(
    cliente: TestClient, fake: FakeQueries, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        api_scan,
        "leer_factura",
        lambda *args: _resultado('no_match:Total (columna "Base imponible")'),
    )

    respuesta = _subir(cliente)

    assert respuesta.status_code == 201
    assert respuesta.json()["review_status"] == "needs_review"
    assert respuesta.json()["warnings"] == ['no_match:Total (columna "Base imponible")']
    assert fake.ocr_runs[0]["raw_text"] == "TOTAL 116,00"


def test_scan_acepta_heic_y_guarda_las_dos_rutas(
    cliente: TestClient, fake: FakeQueries
) -> None:
    respuesta = _subir(cliente, HEIC, "image/heic")

    assert respuesta.status_code == 201
    original = fake.ocr_runs[0]["original_path"]
    convertida = fake.ocr_runs[0]["converted_path"]
    assert original.endswith(".heic")
    assert convertida.endswith(".jpg")
    assert original != convertida


def test_scan_rechaza_pdf(cliente: TestClient, fake: FakeQueries) -> None:
    respuesta = _subir(cliente, b"%PDF-1.4", "application/pdf")

    assert respuesta.status_code == 415
    assert respuesta.json()["detail"] == "El archivo debe ser una imagen (JPEG, PNG o HEIC)."
    assert fake.facturas == {}


def test_scan_rechaza_archivo_grande(
    cliente: TestClient,
    fake: FakeQueries,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(api_scan, "config", SimpleNamespace(
        max_upload_mb=1, ocr_confidence_threshold=60.0, image_dir=tmp_path
    ))

    respuesta = _subir(cliente, b"x" * (1024 * 1024 + 1))

    assert respuesta.status_code == 413
    assert "1 MB" in respuesta.json()["detail"]
    assert fake.facturas == {}


def test_scan_rechaza_imagen_corrupta(cliente: TestClient, fake: FakeQueries) -> None:
    respuesta = _subir(cliente, b"no soy una imagen")

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == "No se pudo leer la imagen."
    assert fake.facturas == {}


def test_scan_sin_motor_responde_503(
    cliente: TestClient, fake: FakeQueries, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _sin_motor(*args):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(api_scan, "leer_factura", _sin_motor)

    respuesta = _subir(cliente)

    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == "No hay ningún motor de OCR disponible."


def test_doble_toque_responde_409_con_el_id_existente(
    cliente: TestClient, fake: FakeQueries
) -> None:
    primera = _subir(cliente)
    segunda = _subir(cliente)

    assert primera.status_code == 201
    assert segunda.status_code == 409
    assert segunda.json()["invoice_id"] == primera.json()["invoice_id"]
    assert len(fake.facturas) == 1
    assert segunda.json()["detail"] == "Esta factura ya estaba registrada."


def test_dos_peticiones_simultaneas_dejan_una_sola_fila(
    fake: FakeQueries,
) -> None:
    def _pedir(_: int):
        with TestClient(fastapi_app) as cliente:
            return _subir(cliente)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        respuestas = list(ejecutor.map(_pedir, range(2)))

    assert sorted(respuesta.status_code for respuesta in respuestas) == [201, 409]
    assert len(fake.facturas) == 1


def test_scan_sigue_sin_easyocr(
    cliente: TestClient,
    fake: FakeQueries,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ocr import easyocr_engine, preprocess, tesseract_engine
    from app.ocr.pipeline import leer_factura
    from app.ocr.tesseract_engine import Lectura, Palabra

    monkeypatch.setattr(preprocess, "preprocesar", lambda imagen: imagen)
    monkeypatch.setattr(
        tesseract_engine,
        "leer",
        lambda imagen: Lectura(
            texto="Total 116.00",
            palabras=[Palabra("Total", 95.0, 0), Palabra("116.00", 95.0, 0)],
        ),
    )
    monkeypatch.setattr(easyocr_engine, "leer", lambda imagen: None)
    monkeypatch.setattr(api_scan, "leer_factura", leer_factura)

    respuesta = _subir(cliente)

    assert respuesta.status_code == 201
    assert respuesta.json()["invoice_id"] == 1


def test_listado_filtra_y_pagina(cliente: TestClient, fake: FakeQueries) -> None:
    _subir(cliente)

    respuesta = cliente.get(
        "/api/v1/invoices",
        params={"supplier_rif": "J-31245678-7", "issue_date": "2026-10-12"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 1
    assert respuesta.json()["items"][0]["id"] == 1
    assert cliente.get(
        "/api/v1/invoices", params={"review_status": "needs_review"}
    ).json()["total"] == 0


def test_detalle_y_404(cliente: TestClient, fake: FakeQueries) -> None:
    _subir(cliente)

    respuesta = cliente.get("/api/v1/invoices/1")
    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == 1
    assert respuesta.json()["items"] == []
    assert "raw_text" not in respuesta.json()

    assert cliente.get("/api/v1/invoices/99").status_code == 404


def test_export_endpoints(cliente: TestClient, fake: FakeQueries) -> None:
    _subir(cliente)

    facturas = cliente.get("/api/v1/export/invoices.csv")
    avisos = cliente.get("/api/v1/export/avisos.csv")

    assert facturas.status_code == 200
    assert facturas.headers["content-type"] == "text/csv; charset=utf-8"
    assert facturas.content.startswith(b"\xef\xbb\xbf")
    assert "Base imponible" in facturas.content.decode("utf-8-sig")
    assert avisos.status_code == 200
    assert avisos.content.decode("utf-8-sig").splitlines() == [
        "invoice_id,frase,columna,motivo"
    ]


def test_export_propaga_error_de_plantilla(
    cliente: TestClient, fake: FakeQueries, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _error():
        raise PlantillaError('plantilla.csv línea 4: falta el "=".')

    monkeypatch.setattr(api_export, "leer_plantilla", _error)

    respuesta = cliente.get("/api/v1/export/invoices.csv")

    assert respuesta.status_code == 500
    assert "línea 4" in respuesta.text
    assert not respuesta.headers["content-type"].startswith("text/csv")


def test_ninguna_respuesta_expone_datos_internos(
    cliente: TestClient, fake: FakeQueries, tmp_path
) -> None:
    _subir(cliente)
    respuestas = [
        cliente.get("/health"),
        cliente.get("/api/v1/invoices"),
        cliente.get("/api/v1/invoices/1"),
        cliente.get("/api/v1/export/invoices.csv"),
        cliente.get("/api/v1/export/avisos.csv"),
    ]

    for respuesta in respuestas:
        texto = respuesta.text
        for prohibido in ("raw_text", "image_path", "original_path", "converted_path"):
            assert prohibido not in texto
        assert str(tmp_path) not in texto


def test_las_rutas_no_exigen_token(cliente: TestClient, fake: FakeQueries) -> None:
    assert _subir(cliente).status_code == 201
    assert cliente.get("/api/v1/invoices").status_code == 200
    assert cliente.get("/api/v1/invoices/1").status_code == 200
    assert cliente.get("/api/v1/export/invoices.csv").status_code == 200
    assert cliente.get("/api/v1/export/avisos.csv").status_code == 200
