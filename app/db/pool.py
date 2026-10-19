"""Pool de conexiones a PostgreSQL.

Es el unico lugar del proyecto que abre conexiones. El resto de las features pide
una conexion con `conexion()` y la devuelve sola al pool.

El pool es propio y no usa `psycopg_pool` a proposito: esa libreria no esta en la
lista de dependencias autorizadas de `CONSTITUTION.md`, y agregar una exige
preguntar primero. Son unas 60 lineas y solo hace falta lo basico que la app usa.

Ver `specs/001-base-datos/design.md`.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import psycopg
from psycopg.rows import dict_row

from app.config import config


class _Pool:
    """Conjunto de conexiones prestadas y devueltas.

    Se crean `min_size` conexiones al arrancar y se crean mas bajo demanda hasta
    `max_size`. Pasado ese tope, quien pide espera a que alguien devuelva una.
    """

    def __init__(self, conninfo: str, min_size: int, max_size: int) -> None:
        self._conninfo = conninfo
        self._max_size = max(1, max_size)
        self._libres: queue.LifoQueue[psycopg.Connection] = queue.LifoQueue()
        self._lock = threading.Lock()
        self._total = 0

        for _ in range(min(1, self._max_size)):
            self._libres.put(self._nueva())
            with self._lock:
                self._total += 1

    def _nueva(self) -> psycopg.Connection:
        """Abre una conexion con las filas como diccionarios."""
        return psycopg.connect(self._conninfo, row_factory=dict_row)

    def tomar(self, timeout: float = 30.0) -> psycopg.Connection:
        """Presta una conexion, esperando si todas estan ocupadas."""
        try:
            return self._libres.get_nowait()
        except queue.Empty:
            pass

        with self._lock:
            if self._total < self._max_size:
                self._total += 1
                abrir = True
            else:
                abrir = False

        if abrir:
            try:
                return self._nueva()
            except Exception:
                with self._lock:
                    self._total -= 1
                raise

        try:
            return self._libres.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("No se pudo obtener una conexion a tiempo") from exc

    def devolver(self, conn: psycopg.Connection) -> None:
        """Devuelve la conexion al pool, o la descarta si quedo rota.

        Una conexion que fallo queda rota y no sirve para la siguiente peticion:
        volver a meterla al pool seria un fallo que aparece mucho despues y en
        otra peticion, que es la peor forma de fallar.
        """
        if conn.closed:
            with self._lock:
                self._total -= 1
            return

        if conn.info.transaction_status not in (
            psycopg.pq.TransactionStatus.IDLE,
            psycopg.pq.TransactionStatus.INTRANS,
        ):
            with suppress(psycopg.Error):
                conn.rollback()

        self._libres.put(conn)

    def cerrar(self) -> None:
        """Cierra todas las conexiones abiertas."""
        with self._lock:
            self._total = 0
        while True:
            try:
                conn = self._libres.get_nowait()
            except queue.Empty:
                return
            with suppress(psycopg.Error):
                conn.close()


_pool: _Pool | None = None
_pool_lock = threading.Lock()


def obtener_pool() -> _Pool:
    """Devuelve el pool, creandolo la primera vez."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = _Pool(
                    conninfo=config.database_url,
                    min_size=1,
                    max_size=config.db_pool_size,
                )
    return _pool


@contextmanager
def conexion() -> Iterator[psycopg.Connection]:
    """Presta una conexion del pool y la devuelve al terminar."""
    pool = obtener_pool()
    conn = pool.tomar()
    try:
        yield conn
        if not conn.closed and conn.info.transaction_status != (
            psycopg.pq.TransactionStatus.IDLE
        ):
            conn.commit()
    except Exception:
        if not conn.closed:
            with suppress(psycopg.Error):
                conn.rollback()
        raise
    finally:
        pool.devolver(conn)


def cerrar_pool() -> None:
    """Cierra el pool. Se llama al apagar el servidor."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.cerrar()
            _pool = None


def esta_conectada() -> bool:
    """Dice si la base responde. Lo usa GET /health, que responde 200 igual."""
    try:
        with conexion() as conn:
            conn.execute("SELECT 1")
        return True
    except (psycopg.Error, TimeoutError):
        return False