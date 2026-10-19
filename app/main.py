"""Arranque de la app: FastAPI, CORS de la red local, `/health` y routers.

**No hay autenticación** (decisión A-02): el servidor escucha en `0.0.0.0` y toda
la red Wi-Fi puede exportar los datos fiscales. La red debe ser privada y con clave.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pillow_heif import register_heif_opener

from app.api import export, invoices, scan
from app.db.pool import cerrar_pool, esta_conectada
from app.models.api import HealthResponse

register_heif_opener()

_ORIGEN_LOCAL = re.compile(
    r"^https?://("
    r"localhost|127\.0\.0\.1"
    r"|10(?:\.\d{1,3}){3}"
    r"|192\.168(?:\.\d{1,3}){2}"
    r"|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
    r")(?::\d+)?$"
)


@asynccontextmanager
async def _ciclo(_: FastAPI) -> AsyncIterator[None]:
    yield
    cerrar_pool()


app = FastAPI(title="App de Facturas", lifespan=_ciclo)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_ORIGEN_LOCAL.pattern,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Diagnóstico: responde `200` aunque la base esté caída."""
    return HealthResponse(
        status="ok",
        database="connected" if esta_conectada() else "disconnected",
    )


app.include_router(scan.router)
app.include_router(invoices.router)
app.include_router(export.router)


__all__ = ["app"]
