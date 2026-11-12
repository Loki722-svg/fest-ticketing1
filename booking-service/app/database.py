import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fest.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. create_all() does not alter existing tables,
# so this adds anything missing and keeps old data (works for Postgres and SQLite).
NEW_COLUMNS = {
    "events": [("min_team_size", "INTEGER DEFAULT 1"), ("max_team_size", "INTEGER DEFAULT 1")],
    "tickets": [("checked_in_at", "TIMESTAMP"), ("team_name", "VARCHAR"), ("members", "TEXT")],
}


def migrate(eng=None):
    eng = eng or engine
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
