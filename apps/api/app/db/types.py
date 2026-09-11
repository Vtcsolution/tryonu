"""Cross-dialect column types.

`Vector` stores product/query embeddings as a native pgvector column on
PostgreSQL (enabling fast ANN search via an ivfflat/hnsw index — see the
Alembic migration) and transparently falls back to a JSON array on SQLite
for local development, where semantic search instead does a brute-force
cosine pass in Python (see services/search_service.py). Application code
never has to know which dialect it's talking to.
"""

from __future__ import annotations

import json

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator, UserDefinedType


class _PGVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **_kw) -> str:  # noqa: ANN003
        return f"vector({self.dim})"

    def bind_processor(self, dialect):  # noqa: ANN001, ANN201
        def process(value):  # noqa: ANN001, ANN202
            if value is None:
                return None
            return "[" + ",".join(str(float(x)) for x in value) + "]"

        return process

    def result_processor(self, dialect, coltype):  # noqa: ANN001, ANN201
        def process(value):  # noqa: ANN001, ANN202
            if value is None:
                return None
            if isinstance(value, str):
                return [float(x) for x in value.strip("[]").split(",") if x]
            return list(value)

        return process


class Vector(TypeDecorator):
    """Embedding column: pgvector on Postgres, JSON array elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 1536) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):  # noqa: ANN001, ANN201
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PGVector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(list(value))

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.loads(value) if isinstance(value, str) else value
