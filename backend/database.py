from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./signage.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def ensure_device_schedule_columns():
    inspector = inspect(engine)
    if "devices" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("devices")}
    statements = []

    if "broadcast_start_time" not in columns:
        statements.append(
            "ALTER TABLE devices ADD COLUMN broadcast_start_time VARCHAR(5)"
        )
    if "broadcast_end_time" not in columns:
        statements.append(
            "ALTER TABLE devices ADD COLUMN broadcast_end_time VARCHAR(5)"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
