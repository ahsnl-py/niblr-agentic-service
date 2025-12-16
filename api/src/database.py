"""Database configuration and session management.

This module sets up SQLAlchemy for database operations.
Uses SQLite by default but can easily migrate to PostgreSQL by changing the database URL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Database URL - defaults to SQLite, can be overridden with DATABASE_URL env var
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost/dbname
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./niblr_api.db"  # SQLite database file in current directory
)

# Create engine
# For SQLite, we need check_same_thread=False
# For PostgreSQL, this is not needed
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("SQL_ECHO", "false").lower() == "true"  # Set SQL_ECHO=true for SQL logging
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true"
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

