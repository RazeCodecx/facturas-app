"""Modelos Pydantic de request y response de la API.

Las respuestas **no** llevan `raw_text`, rutas de imagen ni confianza detallada
(`CONSTITUTION.md` regla 4). El escaneo sí devuelve los avisos de `SCHEMAS.md` §3.3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScanResponse(BaseModel):
    """Respuesta del escaneo: la factura creada y sus avisos."""

    invoice_id: int
    review_status: str
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Estado del servicio y de la conexión con PostgreSQL."""

    status: str
    database: str


class InvoiceListItem(BaseModel):
    """Una factura en la lista paginada. Sin texto crudo ni rutas."""

    id: int
    review_status: str
    review_reason: str | None = None
    values: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class InvoiceListResponse(BaseModel):
    """Lista paginada de facturas."""

    items: list[InvoiceListItem]
    total: int
    limit: int
    offset: int


class InvoiceDetail(InvoiceListItem):
    """Detalle de una factura."""


__all__ = [
    "HealthResponse",
    "InvoiceDetail",
    "InvoiceListItem",
    "InvoiceListResponse",
    "ScanResponse",
]
