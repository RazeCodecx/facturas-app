"""`POST /api/v1/invoices/scan`: recibe la foto, delega el OCR y persiste.

El endpoint no sabe de OCR ni de SQL: valida, llama a la 002, guarda con la 001 y
traduce cada fallo a un código HTTP (`specs/003-api-captura/design.md`).
"""

from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import config
from app.db import queries
from app.export.excel import sincronizar
from app.export.plantilla import Plantilla, PlantillaError, leer_plantilla
from app.models.api import ScanResponse
from app.models.invoice import ExtractionResult
from app.ocr.pipeline import leer_factura
from app.ocr.rapidocr_engine import RapidOCRNoDisponible

router = APIRouter(tags=["captura"])
logger = logging.getLogger(__name__)

TIPOS_PERMITIDOS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
}
MOTIVOS_CON_TEXTO_CRUDO = ("no_match", "ambiguous", "low_confidence")


def _avisos(reason: str | None) -> list[str]:
    if not reason:
        return []
    return [aviso.strip() for aviso in reason.split(";") if aviso.strip()]


def _guardar_imagenes(
    datos: bytes,
    extension: str,
    imagen: Image.Image,
) -> tuple[Path, Path]:
    """Guarda el original tal como llegó y la copia RGB que va al OCR."""
    nombre = uuid.uuid4().hex
    original = config.image_dir / "original" / f"{nombre}{extension}"
    convertida = config.image_dir / "convertida" / f"{nombre}.jpg"

    original.parent.mkdir(parents=True, exist_ok=True)
    convertida.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(datos)
    imagen.save(convertida, format="JPEG", quality=95)
    return original, convertida


def _valores(resultado: ExtractionResult, plantilla: Plantilla) -> list[dict[str, Any]]:
    """Arma el JSONB con el primer texto que produjo cada valor (`SCHEMAS.md` §3.1)."""
    return [
        {
            "frase": columna.frase,
            "encabezado": columna.encabezado,
            "value": valor.value,
            "confidence": valor.confidence,
        }
        for columna, valor in zip(plantilla.columnas, resultado.values, strict=False)
    ]


def _necesita_texto_crudo(reason: str | None) -> bool:
    if not reason:
        return False
    motivos = {aviso.split(":", 1)[0].strip() for aviso in reason.split(";")}
    return any(motivo in motivos for motivo in MOTIVOS_CON_TEXTO_CRUDO)


def _confianza(resultado: ExtractionResult) -> float | None:
    valores = [valor.confidence for valor in resultado.values if valor.value is not None]
    if not valores:
        return None
    return sum(valores) / len(valores)


@router.post("/api/v1/invoices/scan", response_model=ScanResponse, status_code=201)
async def escanear(file: UploadFile = File(...)) -> ScanResponse:
    """Valida la imagen, la lee con la 002 y guarda la factura."""
    tipo = (file.content_type or "").lower()
    if tipo not in TIPOS_PERMITIDOS:
        raise HTTPException(
            status_code=415,
            detail="El archivo debe ser una imagen (JPEG, PNG o HEIC).",
        )

    limite = config.max_upload_mb * 1024 * 1024
    datos = await file.read(limite + 1)
    if len(datos) > limite:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera los {config.max_upload_mb} MB.",
        )

    try:
        original_pil = Image.open(io.BytesIO(datos))
        original_pil.load()
        convertida_pil = ImageOps.exif_transpose(original_pil).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="No se pudo leer la imagen.") from exc

    try:
        plantilla = leer_plantilla()
    except PlantillaError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        resultado = leer_factura(
            convertida_pil,
            plantilla.columnas,
            plantilla.formato,
            config.ocr_confidence_threshold,
        )
    except RapidOCRNoDisponible as exc:
        raise HTTPException(
            status_code=503,
            detail="No hay ningún motor de OCR disponible.",
        ) from exc

    invoice_id = queries.insertar_factura(
        review_status=resultado.review_status,
        review_reason=resultado.review_reason,
        values=_valores(resultado, plantilla),
    )

    original, convertida = _guardar_imagenes(
        datos, TIPOS_PERMITIDOS[tipo], convertida_pil
    )
    queries.registrar_ocr_run(
        invoice_id=invoice_id,
        original_path=str(original),
        converted_path=str(convertida),
        raw_text=resultado.raw_text if _necesita_texto_crudo(resultado.review_reason) else None,
        engine_version=resultado.engines_used[0] if resultado.engines_used else "rapidocr",
        confidence=_confianza(resultado),
    )

    try:
        sincronizar(plantilla)
    except Exception:
        logger.exception("No se pudo actualizar el Excel de salida.")

    return ScanResponse(
        invoice_id=invoice_id,
        review_status=resultado.review_status,
        warnings=_avisos(resultado.review_reason),
    )


__all__ = ["router"]
