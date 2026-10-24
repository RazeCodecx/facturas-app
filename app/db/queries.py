"""Queries de la app. **Todo el SQL vive aqui.**

Ningun endpoint ni ningun otro modulo escribe SQL. Este modulo no sabe de HTTP,
de OCR ni de CSV: solo recibe datos y devuelve filas.

Ver `specs/001-base-datos/design.md` para el esquema y las decisiones.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.db.pool import conexion


def insertar_factura(
    *,
    review_status: str,
    review_reason: str | None,
    values: Sequence[dict[str, Any]],
) -> int:
    """Guarda una factura con los valores que pidio el contador.

    Cada foto crea una fila. La app no deduplica: si la misma foto llega dos
    veces, se registra dos veces.
    """
    payload = json.dumps(list(values), ensure_ascii=False)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO invoices (review_status, review_reason, values)
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
                """,
            (review_status, review_reason, payload),
        )
        fila = cur.fetchone()
        return fila["id"]


def registrar_ocr_run(
    *,
    invoice_id: int | None,
    original_path: str,
    converted_path: str | None,
    raw_text: str | None,
    engine_version: str,
    confidence: float | None,
) -> int:
    """Guarda la corrida de OCR. Es la fila interna, nunca sale por la API.

    `raw_text` llega en `None` cuando todo salio bien: solo se guarda el texto
    reconocido cuando sirve para depurar algo que quedo dudoso.
    """
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO ocr_runs (
                    invoice_id, original_path, converted_path, raw_text,
                    engine_version, confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
            (
                invoice_id,
                original_path,
                converted_path,
                raw_text,
                engine_version,
                confidence,
            ),
        )
        fila = cur.fetchone()
        return fila["id"]


def obtener_factura(invoice_id: int) -> dict[str, Any] | None:
    """Devuelve una factura o `None` si no existe.

    Nunca trae `raw_text`: el texto reconocido es dato interno
    (`CONSTITUTION.md` regla 4).
    """
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT id, review_status, review_reason, values, created_at
                FROM invoices
                WHERE id = %s
                """,
            (invoice_id,),
        )
        return cur.fetchone()


def _filtros(review_status: str | None) -> tuple[str, list[Any]]:
    """Arma el `WHERE` de los listados. Filtra en SQL, nunca en Python."""
    if not review_status:
        return "", []
    return "WHERE review_status = %s", [review_status]


def listar_facturas(
    *,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lista facturas con filtro opcional. El filtro va en el SELECT.

    Nunca se lee todo y se filtra en Python: con lotes de miles de facturas eso
    carga la base sin motivo.
    """
    where, argumentos = _filtros(review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
                SELECT id, review_status, review_reason, values, created_at
                FROM invoices
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
            [*argumentos, limit, offset],
        )
        return cur.fetchall()


def listar_para_exportar(
    *,
    review_status: str | None = None,
) -> list[dict[str, Any]]:
    """Devuelve todas las facturas que cumplen el filtro, sin paginar.

    Es la consulta del CSV: incluye las `needs_review` y respeta el orden de
    llegada, para que el contador vea el lote como lo escaneó.
    """
    where, argumentos = _filtros(review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
                SELECT id, review_status, review_reason, values, created_at
                FROM invoices
                {where}
                ORDER BY created_at ASC, id ASC
                """,
            argumentos,
        )
        return cur.fetchall()


def contar_facturas(*, review_status: str | None = None) -> int:
    """Cuenta las facturas que cumplen el filtro, para la paginacion."""
    where, argumentos = _filtros(review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS total FROM invoices {where}", argumentos)
        fila = cur.fetchone()
        return int(fila["total"])


def existe_factura() -> bool:
    """Dice si la tabla de facturas existe, para aplicar la migracion si falta."""
    with conexion() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.invoices') AS tabla")
        fila = cur.fetchone()
        return fila["tabla"] is not None


def aplicar_migraciones() -> None:
    """Aplica los archivos de `app/db/migrations/` que falten.

    Los archivos ya aplicados **no se reescriben nunca**: se numeran y se aplican
    en orden. Asi una base existente siempre se puede actualizar.
    """
    ruta_migraciones = Path(__file__).parent / "migrations"

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
        )
        cur.execute("SELECT version FROM schema_migrations")
        aplicadas = {fila["version"] for fila in cur.fetchall()}

    for archivo in sorted(ruta_migraciones.glob("*.sql")):
        if archivo.name in aplicadas:
            continue
        sql = archivo.read_text(encoding="utf-8")
        with conexion() as conn, conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (archivo.name,),
            )


__all__ = [
    "aplicar_migraciones",
    "contar_facturas",
    "existe_factura",
    "insertar_factura",
    "listar_facturas",
    "listar_para_exportar",
    "obtener_factura",
    "registrar_ocr_run",
]