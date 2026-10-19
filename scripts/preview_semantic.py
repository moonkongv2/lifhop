"""Disposable Semantic demo: isolated test schema, synthetic records, mock OpenAI."""
import argparse
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.main import app
from app.models.entry import Entry, EntryType
from app.models.user import User
from app.security import hash_password, create_access_token
from app.services.source_history import record_version, select_version, source_policy
from app.services.embedding_jobs import prepare_indexing, activate_indexing
from app.services.embedding_call import embed
from app.services.embedding_transport import MODEL
from app.services.answer_call import answer as paid_answer
from app.services.answer_transport import MODEL as ANSWER_MODEL
from app.evaluation.storage import write_private
from app.workers.embedding_worker import process_one


def fake_provider(inputs):
    values = []
    for i, value in enumerate(inputs):
        axis = 0 if "worker" in value.lower() or "워커" in value else 1
        vector = [0.0] * 1536
        vector[axis] = 1.0
        values.append(dict(index=i, embedding=vector))
    return dict(model=MODEL, data=values, usage=dict(prompt_tokens=len(inputs), total_tokens=len(inputs)))


def fake_answer(value):
    excerpts = json.loads(value["input"])["excerpts"]
    result = dict(status="supported", answer="[Synthetic] This answer cites the selected passage.",
                  citation_ids=[excerpts[0]["id"]], unconfirmed_aspects=[])
    if 'newline-separated items' in value['instructions']:
        def summary(item):
            category = 'Proposal' if 'proposal' in item['text'].lower() else 'Completed work' if 'completed' in item['text'].lower() else 'Recorded activity'
            return f'[{item["id"]}] {category}: [Synthetic] {item["text"]}'
        result.update(answer='\n'.join(summary(item) for item in excerpts), citation_ids=[item['id'] for item in excerpts])
    if "observed_through" in json.loads(value["input"]):
        result.update(answer="[Synthetic] Reviewed observation: " + excerpts[0]["text"])
    return dict(model=ANSWER_MODEL, status="completed",
                output=[dict(type="message", content=[dict(type="output_text", text=json.dumps(dict(result=result)))])],
                usage=dict(input_tokens=10, output_tokens=10, total_tokens=20))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args(argv)
    url = make_url(args.database_url)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (url.database or "").endswith("_test"):
        parser.error("Only a local disposable database ending in _test is allowed")
    bind = create_engine(url)
    schema = "semantic_demo_" + uuid4().hex
    config = Config("alembic.ini", toml_file="pyproject.toml")
    with bind.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    def checkout(connection, record, proxy):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{schema}", public')
        finally:
            connection.autocommit = previous
    event.listen(bind, "checkout", checkout)
    try:
        # Demo tokens cannot authenticate against the real application.
        settings.jwt_secret_key = "disposable-semantic-demo-" + uuid4().hex
        runtime = SimpleNamespace(embedding_mode="openai", answer_mode="openai", openai_api_key=SecretStr("synthetic-key"),
            embedding_monthly_limit_micro_usd=1000000, embedding_billing_scope="demo-" + uuid4().hex)
        with Session(bind) as db:
            user = User(email="demo@example.test", password_hash=hash_password("demo-password"))
            db.add(user)
            db.flush()
            assert db.scalar(text("SELECT current_schema()")) == schema
            source_policy(db, user.id, "manual").external_ai_allowed = True
            for day, (title, body) in enumerate([("[Synthetic] Worker location", "The import worker runs on the deployment server, separately from the API."),
                    ("[Synthetic] Backup procedure", "The backup is stored privately and restored in a separate database."),
                    ("[Synthetic] Backup proposal", "Proposal: add a scheduled backup check. This has not been implemented."),
                    ("[Synthetic] Recorded completion", "Completed work recorded in this synthetic fixture: a disposable backup restore was checked.")], 10):
                entry = Entry(user_id=user.id, provider="manual", type=EntryType.NOTE,
                    title=title, content=body, external_ai_allowed=True,
                    event_at=datetime(2026, 1, day, 3, tzinfo=timezone.utc))
                db.add(entry)
                select_version(db, entry, record_version(db, entry))
            # Deliberately dated synthetic observations: current February text
            # must not leak into a January observation-cutoff answer.
            history = Entry(user_id=user.id, provider="manual", type=EntryType.NOTE,
                title="[Synthetic] Deployment history", content="Deployment history: proposal to run the worker on server Alpha.",
                external_ai_allowed=True, created_at=datetime(2026, 1, 15, 3, tzinfo=timezone.utc),
                event_at=datetime(2026, 1, 14, 3, tzinfo=timezone.utc))
            db.add(history)
            old = record_version(db, history)
            old.observed_at = datetime(2026, 1, 15, 3, tzinfo=timezone.utc)
            history.content = "Deployment history: recorded decision to use server Beta. No deployment is proven by this note."
            history.event_at = datetime(2026, 2, 14, 3, tzinfo=timezone.utc)
            current = record_version(db, history)
            current.observed_at = datetime(2026, 2, 15, 3, tzinfo=timezone.utc)
            select_version(db, history, current)
            manifest = prepare_indexing(db, owner_id=user.id, provider="manual", scope="default")
            activate_indexing(db, owner_id=user.id, manifest=manifest, confirm_external_ai=True)
            owner_id = user.id
            db.commit()
        while process_one(bind, runtime, transport=fake_provider):
            pass
        import app.api.semantic as api
        api.engine, api.settings = bind, runtime
        api.embed = lambda *a, **kw: embed(*a, **kw, transport=fake_provider)
        import app.api.answers as answers_api
        answers_api.engine, answers_api.settings = bind, runtime
        answers_api.answer = lambda *a, **kw: paid_answer(*a, **kw, transport=fake_answer)
        def demo_db():
            with Session(bind) as db:
                yield db
        app.dependency_overrides[get_db] = demo_db
        root = Path(__file__).resolve().parents[1] / ".local" / "verification" / "semantic-demo"
        write_private(root / (schema + ".json"), dict(token=create_access_token(owner_id),
            api=f"http://127.0.0.1:{args.port}", schema=schema), root=root)
        print(f"Synthetic-only API: http://127.0.0.1:{args.port}")
        print("Login: demo@example.test / demo-password; provider is mocked, no external request.")
        print("Private fixture:", root / (schema + ".json"))
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)
    finally:
        app.dependency_overrides.clear()
        event.remove(bind, "checkout", checkout)
        with bind.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        bind.dispose()


if __name__ == "__main__":
    main()
