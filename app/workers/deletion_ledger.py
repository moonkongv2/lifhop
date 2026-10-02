"""Operator-only restore helper. Apply the latest ledger before serving a backup."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from app.db import SessionLocal
from app.models.entry import Entry
from app.models.history import EntrySuppression
from app.services.source_history import owner_lock, delete_record, markdown_identity


def export_ledger(db) -> list[dict]:
    return [dict(user_id=row.user_id, provider=row.provider, external_id=row.external_id,
                 deleted_at=row.deleted_at.isoformat(), reimport_allowed=row.reimport_allowed)
            for row in db.scalars(select(EntrySuppression).order_by(EntrySuppression.id))]


def apply_ledger(db, rows: list[dict]) -> int:
    removed = 0
    for row in rows:
        owner_lock(db, row["user_id"])
        deleted_at = datetime.fromisoformat(row["deleted_at"])
        existing = db.scalar(select(EntrySuppression).where(EntrySuppression.user_id == row["user_id"],
            EntrySuppression.provider == row["provider"], EntrySuppression.external_id == row["external_id"]))
        if existing is None:
            existing = EntrySuppression(user_id=row["user_id"], provider=row["provider"], external_id=row["external_id"])
            db.add(existing)
        for entry in list(db.scalars(select(Entry).where(Entry.user_id == row["user_id"], Entry.provider == row["provider"]))):
            identity = entry.external_id or (markdown_identity(entry.content or "") if entry.provider == "markdown" else None)
            if identity == row["external_id"] and entry.created_at <= deleted_at:
                delete_record(db, entry)
                removed += 1
        existing.deleted_at, existing.reimport_allowed = deleted_at, row.get("reimport_allowed", False)
    db.commit()
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "apply"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.action == "export":
            fd = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(export_ledger(db), output)
        else:
            print(f"Removed {apply_ledger(db, json.loads(args.path.read_text()))} restored records; run purge worker before serving")


if __name__ == "__main__":
    main()
