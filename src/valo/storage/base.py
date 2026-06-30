"""Storage interface — swap SQLiteStore (V1) → SupabaseStore (V2) sans réécriture."""
from abc import ABC, abstractmethod
from typing import Any


class Storage(ABC):
    @abstractmethod
    def get_session(self) -> Any:
        """Return a DB session / client."""
        ...
