"""Postgres connection helpers (reads POSTGRES_* from env / .env)."""
from __future__ import annotations

import os

import psycopg2

from . import config as _config  # noqa: F401  (importing loads .env)


def dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'pubmed')} "
        f"user={os.getenv('POSTGRES_USER', 'pubmed')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'pubmed')}"
    )


def connect():
    return psycopg2.connect(dsn())
