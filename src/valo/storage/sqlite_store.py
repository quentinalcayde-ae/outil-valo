import os
from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from valo.logging import logger
from valo.models import Base
from valo.storage.base import Storage


def reconcile_schema(engine) -> int:
    """Ajoute les colonnes manquantes aux tables existantes (create_all ne migre pas).

    Idempotent, non destructif (ALTER ADD COLUMN uniquement). Retourne le nombre ajouté.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    added = 0
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            cols = {c["name"] for c in insp.get_columns(table_name)}
            for col in table.columns:
                if col.name not in cols:
                    ddl_type = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN "{col.name}" {ddl_type}'))
                    logger.info("schema_column_added", table=table_name, column=col.name)
                    added += 1
    return added


class SQLiteStore(Storage):
    def __init__(self, database_url: str) -> None:
        os.makedirs("data", exist_ok=True)
        self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        reconcile_schema(self.engine)  # auto-migration des colonnes ajoutées après coup
        self._Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False,
                                     expire_on_commit=False)

    @contextmanager
    def get_session(self) -> Session:
        session = self._Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
