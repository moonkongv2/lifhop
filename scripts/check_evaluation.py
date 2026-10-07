"""Create private synthetic evaluation reports in a disposable migrated test schema."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.evaluation.schemas import Case, dataset_from, now
from app.evaluation.evidence import make_anchor, approve_case
from app.evaluation.retrieval import readonly_snapshot, evaluate
from app.evaluation.storage import PRIVATE_ROOT, save_dataset
from app.evaluation.report import save_report
from app.models.entry import Entry, EntryType
from app.models.user import User
from app.models.history import SourcePolicy
from app.services.source_history import record_version
from app.security import hash_password


def main():
    url = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test")
    if make_url(url).database != "lifhop_test":
        raise RuntimeError("Synthetic check requires lifhop_test")
    engine = create_engine(url)
    schema = "evaluation_check_" + uuid4().hex
    listener_added = False
    created = False
    email, password = "evaluation-"+uuid4().hex+"@example.com", uuid4().hex
    directory = PRIVATE_ROOT / ("synthetic-" + uuid4().hex)
    root = Path(__file__).resolve().parents[1]
    try:
        with engine.begin() as connection:
            if connection.scalar(text("SELECT current_database()")) != "lifhop_test":
                raise RuntimeError("Unsafe database")
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(root/"alembic.ini"), toml_file=str(root/"pyproject.toml"))
            config.attributes["connection"] = connection
            command.upgrade(config,"head")
        created = True
        def set_schema(dbapi_connection, *_):
            original = dbapi_connection.autocommit
            dbapi_connection.autocommit = True
            try:
                with dbapi_connection.cursor() as cursor:
                    cursor.execute(f'SET search_path TO "{schema}"')
            finally:
                dbapi_connection.autocommit = original
        event.listen(engine,"checkout",set_schema)
        listener_added = True
        cases = []
        with Session(engine) as db:
            if db.scalar(text("SELECT current_schema()")) != schema:
                raise RuntimeError("Unsafe schema")
            owner=User(email=email,password_hash=hash_password(password))
            db.add(owner)
            db.flush()
            for index in range(16):
                provider="manual" if index%2==0 else "markdown"
                entry=Entry(user_id=owner.id,type=EntryType.NOTE,provider=provider,
                    title=f"[Synthetic] Decision {index+1}",content=f"[Synthetic] decision-marker-{index+1}: adopted the documented option after measuring latency. Proposed alternatives were not adopted.",
                    external_ai_allowed=index%3!=0)
                db.add(entry)
                db.flush()
                entry.current_version_id=record_version(db,entry).id
                db.flush()
                anchor=make_anchor(db,owner_id=owner.id,entry_id=entry.id,version_id=entry.current_version_id,
                    field="content",start=0,end=len(entry.content),selection="historical" if index>=14 else "current")
                case=Case(id=f"case-{index+1:02d}",question=f"Why did we adopt synthetic option {index+1}?",
                    language="en",tags=["history"] if index>=14 else ["decision"],
                    keyword_queries=[f"decision-marker-{index+1}:","not-found-in-synthetic-evidence"],
                    claims=[dict(id="adopted",statement="Synthetic measured latency supported the adopted option.",required_group_ids=["reason"])],
                    evidence_groups=[dict(id="reason",anchors=[anchor])])
                cases.append(approve_case(db,owner.id,case,confirmed=True))
            for index in range(16,20):
                case=Case(id=f"case-{index+1:02d}",question=f"What does missing synthetic source {index} say?",
                    language="en",expected_outcome="coverage_gap" if index%2 else "insufficient_evidence",
                    tags=["coverage_gap"],review_scope="Synthetic records only",review_notes="No source evidence was created for this question.")
                cases.append(approve_case(db,owner.id,case,confirmed=True))
            db.add_all([SourcePolicy(user_id=owner.id,provider=p,scope="default",collection_enabled=True,external_ai_allowed=True) for p in ("manual","markdown")])
            db.commit()
        with readonly_snapshot(engine,email,password) as snapshot:
            data=dataset_from(dict(set_id=directory.name,revision=1,owner_id=snapshot.owner_id,
                owner_email=email,database_fingerprint=snapshot.database_fingerprint,created_at=now(),
                material_kind="synthetic",cases=[case.model_dump(mode="json") for case in cases]))
            save_dataset(directory,data)
            reports=[]
            for mode in ("primary","keywords"):
                result=evaluate(snapshot,data,mode=mode)
                assert result["manifest"]["status"]=="completed"
                assert result["summary"]["scored_cases"]==14
                expected=0 if mode=="primary" else .5
                assert result["summary"]["scores"]["group_recall_at_20"]==expected
                assert result["manifest"]["composition"]["complete"] is False
                reports.append((mode,save_report(directory,result)/"report.html"))
        print("Synthetic verification passed: 20 reviewed fixture cases; primary recall 0; keyword mean recall 0.5.")
        for mode,path in reports:
            print(f"{mode} report: {path}")
        print("The migrated test schema is removed. Report links intentionally have no live fixture records.")
        print("This is a synthetic demonstration, not the real owner evaluation set.")
    finally:
        if listener_added:
            event.remove(engine,"checkout",set_schema)
        if created:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    main()
