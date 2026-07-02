"""Synchronise la base SQLite locale avec les modèles SQLAlchemy (dev only).

`create_all` crée les tables manquantes mais N'AJOUTE PAS les colonnes ajoutées ensuite.
Ce script compare le modèle à la base et applique les `ALTER TABLE ... ADD COLUMN` manquants.
Idempotent, non destructif (n'enlève jamais de colonne, ne touche pas aux données).

Usage (uvicorn arrêté) :
    python scripts/sync_db.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import Boolean, Float, Integer  # noqa: E402

from valo.config import settings  # noqa: E402
from valo.models import Base  # noqa: E402


def _sqlite_type(col) -> str:
    t = col.type
    if isinstance(t, Integer):
        return "INTEGER"
    if isinstance(t, Float):
        return "FLOAT"
    if isinstance(t, Boolean):
        return "BOOLEAN"
    return "TEXT"  # String / Text / JSON / DateTime → TEXT en SQLite


def main() -> None:
    db_path = settings.database_url.replace("sqlite:///", "").lstrip("./")
    if not Path(db_path).exists():
        print(f"Base absente ({db_path}) — elle sera créée au démarrage de l'API. Rien à faire.")
        return

    con = sqlite3.connect(db_path)
    existing_tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    added = 0

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            print(f"[skip] table absente : {table_name} (sera créée par create_all)")
            continue
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table_name})")}
        for col in table.columns:
            if col.name not in cols:
                sql = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {_sqlite_type(col)}'
                con.execute(sql)
                print(f"[+] {table_name}.{col.name} ({_sqlite_type(col)})")
                added += 1

    con.commit()
    con.close()
    print(f"Terminé — {added} colonne(s) ajoutée(s)." if added else "Base déjà à jour.")


if __name__ == "__main__":
    main()
