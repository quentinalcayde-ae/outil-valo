import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from valo.models import Base
from valo.storage.base import Storage


class SQLiteStore(Storage):
    def __init__(self, database_url: str) -> None:
        os.makedirs("data", exist_ok=True)
        self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self._Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

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
