"""Endpoints de exportación: `invoices.csv` y `avisos.csv`.

Los filtros se aplican en el `SELECT` de la 001. Si `plantilla.csv` tiene un
error, se responde `500` con el mensaje del contador y no se emite un CSV a medias.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from fastapi.responses import Response

from app.db import queries
from app.export.avisos import generar_avisos
from app.export.csv import generar_csv
from app.export.plantilla import PlantillaError, leer_plantilla

router = APIRouter(prefix="/api/v1/export", tags=["exportacion"])

CABECERAS = {
    "Content-Type": "text/csv; charset=utf-8",
    "Content-Disposition": 'attachment; filename="facturas.csv"',
}


def _respuesta(contenido: bytes, nombre: str) -> Response:
    cabeceras = dict(CABECERAS)
    cabeceras["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return Response(content=contenido, media_type="text/csv", headers=cabeceras)


def _error_plantilla(exc: PlantillaError) -> Response:
    return Response(
        content=str(exc),
        media_type="text/plain",
        status_code=500,
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )


def _facturas(
    review_status: str | None, issue_date: date | None
) -> list[dict[str, object]]:
    return queries.listar_para_exportar(
        review_status=review_status,
        issue_date=issue_date.isoformat() if issue_date else None,
    )


@router.get("/invoices.csv")
def exportar_facturas(
    review_status: str | None = None,
    issue_date: date | None = None,
) -> Response:
    """CSV de facturas: una cabecera con los segundos textos y una fila por factura."""
    try:
        plantilla = leer_plantilla()
    except PlantillaError as exc:
        return _error_plantilla(exc)

    contenido = generar_csv(
        _facturas(review_status, issue_date), plantilla.columnas, plantilla.formato
    )
    return _respuesta(contenido, "facturas.csv")


@router.get("/avisos.csv")
def exportar_avisos(
    review_status: str | None = None,
    issue_date: date | None = None,
) -> Response:
    """CSV de avisos: sale siempre, aunque solo traiga la cabecera."""
    contenido = generar_avisos(_facturas(review_status, issue_date))
    return _respuesta(contenido, "avisos.csv")


__all__ = ["router"]
