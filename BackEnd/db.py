import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

def _connect_args(url: str) -> dict:
    """TLS to PostgreSQL in production, unless the URL already says otherwise.

    Render's managed Postgres accepts TLS; a plain `postgresql://` URL without
    `sslmode` would otherwise connect in the clear.
    """
    is_production = (os.getenv("APP_ENV") or ("production" if os.getenv("RENDER") else "development")).strip().lower() == "production"
    if is_production and url.startswith("postgresql") and "sslmode" not in url:
        return {"sslmode": "require"}
    return {}


engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
