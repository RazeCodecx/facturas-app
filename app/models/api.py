"""Modelos Pydantic de request y response de la API.

Las respuestas **no** llevan `raw_text`, rutas de imagen ni confianza detallada
(`CONSTITUTION.md` regla 4). El escaneo sí devuelve los avisos de `SCHEMAS.md` §3.3.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ScanResponse(BaseModel):
    """Respuesta del escaneo. `detail` solo viaja en el `409`."""

    invoice_id: int
    review_status: str
    warnings: list[str] = Field(default_factory=list)
    detail: str | None = None


class HealthResponse(BaseModel):
    """Estado del servicio y de la conexión con PostgreSQL."""

    status: str
    database: str


class InvoiceItem(BaseModel):
    """Una línea de la factura."""

    id: int
    line_number: int
    code: str | None = None
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class Tax(BaseModel):
    """Un impuesto o retención de la factura."""

    id: int
    item_id: int | None = None
    tax_type: str
    rate: float | None = None
    base_amount: float | None = None
    amount: float | None = None


class InvoiceListItem(BaseModel):
    """Una factura en la lista paginada. Sin texto crudo ni rutas."""

    id: int
    supplier_rif: str | None = None
    serie: str | None = None
    numero: str | None = None
    issue_date: date | None = None
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
    """Detalle de una factura, con sus líneas e impuestos."""

    items: list[InvoiceItem] = Field(default_factory=list)
    taxes: list[Tax] = Field(default_factory=list)


__all__ = [
    "HealthResponse",
    "InvoiceDetail",
    "InvoiceItem",
    "InvoiceListItem",
    "InvoiceListResponse",
    "ScanResponse",
    "Tax",
]
