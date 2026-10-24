"""Tests de la capa de base de datos.

Trabajan contra una base **aislada** que se crea y se tira al terminar. Nunca tocan
la base `facturas`, ni sus datos.

Ver `specs/001-base-datos/tasks.md`.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

# Importar `app.config` carga el `.env` en `os.environ` como efecto secundario.
# Se hace aqui, a nivel de modulo, y no dentro de un fixture, para que ningun
# fixture dependa del orden en que pytest los construye.
import app.config
from app.config import ARCHIVO_ENV  # noqa: F401

BASE_DATOS_PRUEBA = f"facturas_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def url_base() -> str:
    """Devuelve la URL de la base `facturas`, leida de `.env`."""
    return app.config.config.database_url


@pytest.fixture(scope="session")
def url_admin() -> str:
    """Devuelve la URL de un usuario con CREATE DATABASE, solo para los tests.

    El usuario de la app **no** es superusuario ni tiene CREATEDB, a proposito.
    Para levantar y tirar la base aislada hace falta un usuario con ese permiso,
    y por eso es una variable aparte que la app nunca lee.

    Si falta, los tests **no** se saltan: se aborta la sesion. Una variable de
    entorno faltante es un error de configuracion, no un caso sin cobertura, y
    saltarse haria que `pytest` reportara verde sin haber probado nada.
    """
    admin = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if not admin:
        pytest.exit(
            "Falta TEST_ADMIN_DATABASE_URL en .env.\n"
            "Los tests de base de datos no pueden correr sin ella: la app no tiene "
            "CREATEDB por diseño. Agregala a .env con un usuario que sí lo tenga.",
            returncode=1,
        )
    return admin


@pytest.fixture
def base_aislada(url_base: str, url_admin: str):
    """Crea una base vacia para el test, aplica la migracion, y la borra."""
    admin = psycopg.connect(url_admin, autocommit=True)
    try:
        with admin.cursor() as cur:
            # OWNER facturas_app: desde PostgreSQL 15 el esquema public no es
            # escribible por PUBLIC, asi que sin esto la migracion falla.
            cur.execute(f'CREATE DATABASE "{BASE_DATOS_PRUEBA}" OWNER facturas_app')
    finally:
        admin.close()

    partes = url_base.rsplit("/", 1)
    url_prueba = f"{partes[0]}/{BASE_DATOS_PRUEBA}"

    original = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url_prueba

    app.config.config = app.config.Config.desde_entorno()

    # `app.db.pool` pudo haberse importado antes (por ejemplo, al importar
    # `app.main` en otros tests) y en ese caso cacheo el objeto `config` viejo.
    # Hay que apuntarlo al nuevo antes de crear el pool; si no, los tests
    # escribirian en la base real sin que nadie se entere.
    from app.db import pool as pool_mod

    pool_mod.config = app.config.config
    pool_mod._pool = None

    from app.db import queries

    queries.aplicar_migraciones()

    yield url_prueba

    pool_mod.cerrar_pool()
    os.environ["DATABASE_URL"] = original
    app.config.config = app.config.Config.desde_entorno()
    pool_mod.config = app.config.config

    admin = psycopg.connect(url_admin, autocommit=True)
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s",
                (BASE_DATOS_PRUEBA,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{BASE_DATOS_PRUEBA}"')
    finally:
        admin.close()


@pytest.fixture
def db(base_aislada: str):
    """Devuelve el modulo de queries apuntando a la base aislada."""
    from app.db import queries

    return queries


def _valores(ejemplo: bool = False) -> list[dict[str, object]]:
    """Valores que el contador pidio, tal como los guarda la 003."""
    return [
        {
            "frase": "Total a pagar",
            "encabezado": "Total factura",
            "value": "116.00" if ejemplo else "1234.56",
            "confidence": 92.0,
        },
        {
            "frase": "IVA",
            "encabezado": "Monto IVA",
            "value": "197.13",
            "confidence": 88.5,
        },
    ]