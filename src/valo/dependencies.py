"""FastAPI dependencies — session DB + providers (marché & LLM)."""
from collections.abc import Generator

from sqlalchemy.orm import Session

from valo.config import settings
from valo.providers.base import LLMProvider
from valo.providers.mock_llm import MockLLMProvider
from valo.providers.yahoo_provider import YahooProvider
from valo.storage.sqlite_store import SQLiteStore

_store = SQLiteStore(settings.database_url)


def get_session() -> Generator[Session, None, None]:
    with _store.get_session() as session:
        yield session


def get_yahoo() -> YahooProvider:
    return YahooProvider()


def get_llm() -> LLMProvider:
    """OpenAIProvider si OPENAI_API_KEY présente, sinon MockLLMProvider (fallback sans clé)."""
    if settings.openai_api_key:
        from valo.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    return MockLLMProvider()
