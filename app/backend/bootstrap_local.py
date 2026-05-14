"""Create schema + seed for local SQLite dev without running alembic.

Migrations target PostgreSQL (JSONB, USING-clauses, etc.) and don't all replay
cleanly on SQLite. For the local preview stack we instead create tables
straight from the model metadata (which uses portable type variants) and run
the idempotent seed.

Production deploys (Render) still go through `alembic upgrade head` from
render.yaml — this module is local-dev only.
"""
from __future__ import annotations

from .database import Base, engine
from . import models  # noqa: F401  -- register models on Base.metadata
from .seed import run as seed_run


def main() -> None:
    Base.metadata.create_all(engine)
    seed_run()


if __name__ == "__main__":
    main()
