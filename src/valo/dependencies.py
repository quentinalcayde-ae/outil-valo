"""FastAPI dependencies — session DB + providers."""
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from valo.config import settings
from valo.providers.yahoo_provider import YahooProvider
from valo.storage.sqlite_store import SQLiteStore

_store = SQLiteStore(settings.database_url)


def get_session() -> Generator[Session, None, None]:
    with _store.get_session() as session:
        yield session


def get_yahoo() -> YahooProvider:
    return YahooProvider()
