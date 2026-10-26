"""Carga de configuracion desde `.env` y valores por defecto.

Se importa una vez al arrancar la app. Ningun modulo deberia leer variables de
entorno por su cuenta: las pide de aca, para que exista un solo lugar donde se
decide que valor se usa.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = RAIZ / ".env"

load_dotenv(ARCHIVO_ENV)


def _texto(clave: str, por_defecto: str | None = None) -> str:
    """Devuelve una variable de entorno, o el valor por defecto si no esta."""
    valor = os.environ.get(clave)
    if valor is not None and valor.strip():
        return valor.strip()
    if por_defecto is not None:
        return por_defecto
    raise RuntimeError(f"Falta la variable {clave} en {ARCHIVO_ENV.name}")


def _entero(clave: str, por_defecto: int) -> int:
    """Devuelve una variable de entorno como entero."""
    valor = os.environ.get(clave)
    if valor is None or not valor.strip():
        return por_defecto
    return int(valor)


@dataclass(frozen=True)
class Config:
    """Configuracion de la app, leida de `.env` al arrancar."""

    database_url: str
    db_pool_size: int
    ocr_confidence_threshold: float
    max_upload_mb: int
    image_dir: Path

    @classmethod
    def desde_entorno(cls) -> Config:
        """Construye la configuracion leyendo `.env`."""
        return cls(
            database_url=_texto("DATABASE_URL"),
            db_pool_size=_entero("DB_POOL_SIZE", 5),
            ocr_confidence_threshold=float(_entero("OCR_CONFIDENCE_THRESHOLD", 60)),
            max_upload_mb=_entero("MAX_UPLOAD_MB", 10),
            image_dir=RAIZ / _texto("IMAGE_DIR", "imagenes"),
        )


config = Config.desde_entorno()