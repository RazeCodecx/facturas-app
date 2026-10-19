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


def armar_dedupe_key(
    supplier_rif: str | None,
    serie: str | None,
    numero: str | None,
    issue_date: str | None,
) -> str:
    """Construye la clave de duplicado (`SCHEMAS.md` 2.1).

    Las partes que no se pudieron leer van vacias. Con el RIF vacio la clave puede
    chocar entre proveedores distintos: es el riesgo asumido de la seccion 2.1, y
    por eso la app avisa con `unreadable_rif` en vez de descartar la factura.
    """
    return "|".join([supplier_rif or "", serie or "", numero or "", issue_date or ""])


def insertar_factura(
    *,
    supplier_rif: str | None,
    serie: str | None,
    numero: str | None,
    issue_date: str | None,
    fiscal_profile_id: int | None,
    review_status: str,
    review_reason: str | None,
    values: Sequence[dict[str, Any]],
    items: Sequence[dict[str, Any]],
    taxes: Sequence[dict[str, Any]],
) -> int | None:
    """Guarda una factura con sus lineas e impuestos.

    Devuelve el `id` de la factura creada, o `None` si ya existia una con la
    misma `dedupe_key`. El `ON CONFLICT DO NOTHING` resuelve la carrera del doble
    toque del Atajo sin necesidad de un lock: el UNIQUE es la garantia.
    """
    dedupe_key = armar_dedupe_key(supplier_rif, serie, numero, issue_date)
    payload = json.dumps(list(values), ensure_ascii=False)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                INSERT INTO invoices (
                    supplier_rif, serie, numero, issue_date, fiscal_profile_id,
                    dedupe_key, review_status, review_reason, values
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id
                """,
            (
                supplier_rif,
                serie,
                numero,
                issue_date,
                fiscal_profile_id,
                dedupe_key,
                review_status,
                review_reason,
                payload,
            ),
        )
        fila = cur.fetchone()
        if fila is None:
            return None
        invoice_id = fila["id"]

        if items:
            cur.executemany(
                """
                    INSERT INTO invoice_items (
                        invoice_id, line_number, code, description,
                        quantity, unit_price, amount
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                [
                    (
                        invoice_id,
                        item["line_number"],
                        item.get("code"),
                        item.get("description"),
                        item.get("quantity"),
                        item.get("unit_price"),
                        item.get("amount"),
                    )
                    for item in items
                ],
            )

        if taxes:
            cur.executemany(
                """
                    INSERT INTO taxes (
                        invoice_id, item_id, tax_type, rate, base_amount, amount
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                [
                    (
                        invoice_id,
                        tax.get("item_id"),
                        tax["tax_type"],
                        tax.get("rate"),
                        tax.get("base_amount"),
                        tax.get("amount", 0),
                    )
                    for tax in taxes
                ],
            )

    return invoice_id


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
    """Devuelve una factura con sus items e impuestos, o `None` si no existe.

    Nunca trae `raw_text`: el texto reconocido es dato interno
    (`CONSTITUTION.md` regla 4).
    """
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT id, supplier_rif, serie, numero, issue_date,
                       fiscal_profile_id, review_status, review_reason,
                       values, created_at
                FROM invoices
                WHERE id = %s
                """,
            (invoice_id,),
        )
        factura = cur.fetchone()
        if factura is None:
            return None

        cur.execute(
            """
                SELECT id, line_number, code, description,
                       quantity, unit_price, amount
                FROM invoice_items
                WHERE invoice_id = %s
                ORDER BY line_number
                """,
            (invoice_id,),
        )
        factura["items"] = cur.fetchall()

        cur.execute(
            """
                SELECT id, item_id, tax_type, rate, base_amount, amount
                FROM taxes
                WHERE invoice_id = %s
                """,
            (invoice_id,),
        )
        factura["taxes"] = cur.fetchall()

    return factura


def _filtros(
    supplier_rif: str | None,
    issue_date: str | None,
    review_status: str | None,
) -> tuple[str, list[Any]]:
    """Arma el `WHERE` de los listados. Filtra en SQL, nunca en Python."""
    condiciones: list[str] = []
    argumentos: list[Any] = []

    if supplier_rif:
        condiciones.append("supplier_rif = %s")
        argumentos.append(supplier_rif)
    if issue_date:
        condiciones.append("issue_date = %s")
        argumentos.append(issue_date)
    if review_status:
        condiciones.append("review_status = %s")
        argumentos.append(review_status)

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    return where, argumentos


def listar_facturas(
    *,
    supplier_rif: str | None = None,
    issue_date: str | None = None,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Lista facturas con filtros opcionales. El filtro va en el SELECT.

    Nunca se lee todo y se filtra en Python: con lotes de miles de facturas eso
    carga la base sin motivo.
    """
    where, argumentos = _filtros(supplier_rif, issue_date, review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
                SELECT id, supplier_rif, serie, numero, issue_date,
                       review_status, review_reason, values, created_at
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
    supplier_rif: str | None = None,
    issue_date: str | None = None,
    review_status: str | None = None,
) -> list[dict[str, Any]]:
    """Devuelve todas las facturas que cumplen los filtros, sin paginar.

    Es la consulta del CSV: incluye las `needs_review` y respeta el orden de
    llegada, para que el contador vea el lote como lo escaneó.
    """
    where, argumentos = _filtros(supplier_rif, issue_date, review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
                SELECT id, supplier_rif, serie, numero, issue_date,
                       review_status, review_reason, values, created_at
                FROM invoices
                {where}
                ORDER BY created_at ASC, id ASC
                """,
            argumentos,
        )
        return cur.fetchall()


def contar_facturas(
    *,
    supplier_rif: str | None = None,
    issue_date: str | None = None,
    review_status: str | None = None,
) -> int:
    """Cuenta las facturas que cumplen los filtros, para la paginacion."""
    where, argumentos = _filtros(supplier_rif, issue_date, review_status)

    with conexion() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS total FROM invoices {where}", argumentos)
        fila = cur.fetchone()
        return int(fila["total"])


def existe_dedupe_key(dedupe_key: str) -> int | None:
    """Devuelve el id de la factura con esa clave, o `None`.

    Lo usa el endpoint para responder `409` con el `invoice_id` que ya existia.
    """
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM invoices WHERE dedupe_key = %s",
            (dedupe_key,),
        )
        fila = cur.fetchone()
        return fila["id"] if fila else None


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
    "armar_dedupe_key",
    "contar_facturas",
    "existe_dedupe_key",
    "existe_factura",
    "insertar_factura",
    "listar_facturas",
    "listar_para_exportar",
    "obtener_factura",
    "registrar_ocr_run",
]