"""Synchronise la base SQLite locale avec les modèles SQLAlchemy (dev).

Note : la réconciliation est désormais lancée AUTOMATIQUEMENT au démarrage de l'API
(SQLiteStore.__init__ → reconcile_schema). Ce script reste utile pour l'appliquer
hors API. Idempotent, non destructif.

Usage : python scripts/sync_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine  # noqa: E402

from valo.config import settings  # noqa: E402
from valo.models import Base  # noqa: E402
from valo.storage.sqlite_store import reconcile_schema  # noqa: E402


def main() -> None:
    db_path = settings.database_url.replace("sqlite:///", "").lstrip("./")
    if not Path(db_path).exists():
        print(f"Base absente ({db_path}) — créée au démarrage de l'API. Rien à faire.")
        return
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    added = reconcile_schema(engine)
    print(f"Terminé — {added} colonne(s) ajoutée(s)." if added else "Base déjà à jour.")


if __name__ == "__main__":
    main()
