"""`GET /api/v1/invoices` y `GET /api/v1/invoices/{id}`.

Solo consultan: los filtros se aplican en el `SELECT` de la 001. Ninguna respuesta
incluye texto crudo ni rutas (`CONSTITUTION.md` regla 4).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import queries
from app.models.api import InvoiceDetail, InvoiceListResponse

router = APIRouter(prefix="/api/v1/invoices", tags=["facturas"])


@router.get("", response_model=InvoiceListResponse)
def listar(
    review_status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> InvoiceListResponse:
    """Lista las facturas con filtro opcional y paginación."""
    items = queries.listar_facturas(
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
    total = queries.contar_facturas(review_status=review_status)
    return InvoiceListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def detalle(invoice_id: int) -> InvoiceDetail:
    """Devuelve una factura."""
    factura = queries.obtener_factura(invoice_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="No existe una factura con ese id.")
    return InvoiceDetail(**factura)


__all__ = ["router"]
