"""
Database connection and schema for GridOptima.
Uses PostgreSQL via psycopg2. Connection string read from environment.

Table: hourly_prices
  - One row per (date, hour, node)
  - Unique constraint prevents duplicates on re-fetch
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

def get_conn():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Copy backend/.env.example to backend/.env and fill it in."
        )

    return psycopg2.connect(database_url)


@contextmanager
def cursor():
    """Context manager that auto-commits or rolls back."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hourly_prices (
                id          SERIAL PRIMARY KEY,
                price_date  DATE        NOT NULL,
                hour        SMALLINT    NOT NULL CHECK (hour BETWEEN 0 AND 23),
                node        TEXT        NOT NULL,
                price_cents NUMERIC(8,4) NOT NULL,
                source      TEXT        NOT NULL DEFAULT 'iso_ne_csv',
                fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                UNIQUE (price_date, hour, node)
            );

            CREATE INDEX IF NOT EXISTS idx_prices_date_node
                ON hourly_prices (price_date, node);
        """)
    print("[db] Schema ready")