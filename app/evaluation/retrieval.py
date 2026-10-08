from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import subprocess
import time

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from fastapi import HTTPException

from app.evaluation.evidence import validate_case
from app.evaluation.metrics import average_scores, query_metrics, summarize
from app.evaluation.schemas import Dataset, EvaluationError, canonical_bytes, digest, now
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.user import User
from app.models.collection_run import CollectionRun
from app.security import verify_password
from app.services.entry_search import search_components

SEARCH_VERSION = "literal-current-entry-v1"


@dataclass
class Snapshot:
    db: Session
    owner_id: int
    owner_email: str
    database_fingerprint: str
    started_at: str


def database_identity(db: Session) -> str:
    url = db.get_bind().engine.url
    row = db.execute(text("SELECT current_database(), current_schema(), oid FROM pg_database WHERE datname=current_database()" )).first()
    return digest([url.host, url.port, *row])


@contextmanager
def readonly_snapshot(engine, email: str, password: str):
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            with Session(connection, autoflush=False, expire_on_commit=False) as db:
                row = db.execute(select(User.id, User.email, User.password_hash).where(User.email == email)).first()
                try:
                    valid = row is not None and verify_password(password, row.password_hash)
                except Exception:
                    valid = False
                if not valid:
                    raise EvaluationError("AUTH_FAILED")
                yield Snapshot(db, row.id, row.email, database_identity(db), now().isoformat())
        finally:
            if transaction.is_active:
                transaction.rollback()


def check_binding(snapshot: Snapshot, dataset: Dataset):
    if (dataset.owner_id != snapshot.owner_id or dataset.owner_email != snapshot.owner_email or
            dataset.database_fingerprint != snapshot.database_fingerprint):
        raise EvaluationError("OWNER_DATABASE_MISMATCH")


def retrieve(db: Session, *, owner_id: int, q: str, filters) -> dict:
    conditions, order, _, _ = search_components(user_id=owner_id, q=q, **filters.model_dump())
    total = db.scalar(select(func.count()).select_from(Entry).where(*conditions)) or 0
    hits = [dict(entry_id=row.id, version_id=row.current_version_id) for row in db.execute(
        select(Entry.id, Entry.current_version_id).where(*conditions).order_by(*order).limit(20))]
    return dict(total=total, hits=hits)


def corpus_manifest(db: Session, owner_id: int, *, deadline: float | None = None) -> dict:
    accumulator = hashlib.sha256()
    count = 0
    for row in db.execute(select(Entry.id, Entry.provider, Entry.source_scope, Entry.external_id,
        Entry.current_version_id, Entry.source_state, Entry.external_ai_allowed, Entry.review_required,
        Entry.created_at, Entry.event_at, Entry.updated_at, EntryVersion.content_hash,
        func.md5(func.coalesce(Entry.primary_content, "")).label("primary_hash"))
        .outerjoin(EntryVersion, (EntryVersion.id == Entry.current_version_id) & (EntryVersion.entry_id == Entry.id))
        .where(Entry.user_id == owner_id).order_by(Entry.id).execution_options(yield_per=200)):
        if deadline is not None and time.monotonic() >= deadline:
            raise EvaluationError("PREFLIGHT_BUDGET")
        accumulator.update(canonical_bytes([value.isoformat() if hasattr(value, "isoformat") else value for value in row]))
        accumulator.update(b"\n")
        count += 1
    for row in db.execute(select(SourcePolicy.provider, SourcePolicy.scope, SourcePolicy.collection_enabled,
        SourcePolicy.external_ai_allowed).where(SourcePolicy.user_id == owner_id)
        .order_by(SourcePolicy.provider, SourcePolicy.scope).execution_options(yield_per=200)):
        accumulator.update(canonical_bytes(list(row)))
        accumulator.update(b"\n")
    versions = db.scalar(select(func.count()).select_from(EntryVersion).join(Entry, Entry.id == EntryVersion.entry_id)
        .where(Entry.user_id == owner_id)) or 0
    providers = dict(db.execute(select(Entry.provider, func.count()).where(Entry.user_id == owner_id).group_by(Entry.provider)).all())
    # Keep provider/scope, status and gap codes; never copy source titles, paths or bodies.
    coverage = []
    runs = db.execute(select(CollectionRun.provider, CollectionRun.scope, CollectionRun.status,
        CollectionRun.coverage, CollectionRun.expected_items).where(CollectionRun.user_id == owner_id)
        .order_by(CollectionRun.id.desc()).limit(100)).all()
    seen = set()
    for provider, scope, status, details, expected in runs:
        if (provider, scope) in seen:
            continue
        seen.add((provider, scope))
        gaps = details.get("gaps", []) if isinstance(details, dict) else []
        coverage.append(dict(provider=provider, scope=scope, status=status, expected_items=expected,
            gap_codes=[gap for gap in gaps if isinstance(gap, str) and gap.isupper()][:100],
            lower_bound=bool(details.get("lower_bound")) if isinstance(details, dict) else False))
    return dict(fingerprint=accumulator.hexdigest(), entries=count, versions=versions,
        providers={provider or "unknown":value for provider, value in providers.items()}, coverage=coverage)


def composition(dataset: Dataset) -> dict:
    reviewed = [case for case in dataset.cases if case.status == "reviewed"]
    requirements = dict(reviewed_20=len(reviewed) >= 20,
        korean_3=sum(c.language == "ko" for c in reviewed) >= 3,
        english_3=sum(c.language == "en" for c in reviewed) >= 3)
    for tag, minimum in (("life",4),("cross_source",3),("history",2),("ai_excluded",2),("coverage_gap",2)):
        requirements[tag] = sum(tag in c.tags for c in reviewed) >= minimum
    seeds = ("모터 RPM", "오키나와")
    requirements["seed_questions"] = all(any(seed in case.question for case in reviewed) for seed in seeds)
    return dict(reviewed=len(reviewed), draft=len(dataset.cases)-len(reviewed), requirements=requirements,
        complete=dataset.material_kind == "private_real" and all(requirements.values()), material_kind=dataset.material_kind)


def git_revision() -> dict:
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=5, check=True).stdout)
        files = sorted((root/"app/evaluation").glob("*.py")) + [root/"app/services/entry_search.py"] + sorted((root/"app/services").glob("passage*.py"))
        return dict(commit=commit, dirty=dirty, implementation_digest=digest([hashlib.sha256(p.read_bytes()).hexdigest() for p in files]))
    except (OSError, subprocess.SubprocessError):
        return dict(commit=None, dirty=True, implementation_digest=None)


def evaluate(snapshot: Snapshot, dataset: Dataset, *, mode: str = "primary", seconds: float = 300, retriever: str = "literal") -> dict:
    if mode not in {"primary", "keywords"}:
        raise EvaluationError("INVALID_MODE")
    if retriever not in {"literal", "passages"}:
        raise EvaluationError("INVALID_RETRIEVER")
    from app.evaluation.passage_metrics import passage_metrics
    from app.evaluation.passage_retrieval import retrieve_passages
    from app.services.passage_search import SEARCH_VERSION as PASSAGE_SEARCH_VERSION, CONFIGURATION_HASH
    metrics = passage_metrics if retriever == "passages" else query_metrics
    check_binding(snapshot, dataset)
    started = time.monotonic()
    deadline = started + seconds
    results = []
    manifest = dict(dataset_digest=dataset.digest, revision=dataset.revision, set_id=dataset.set_id,
        owner_id=dataset.owner_id, database_fingerprint=dataset.database_fingerprint, material_kind=dataset.material_kind,
        observed_at=snapshot.started_at, mode=mode, search_version=PASSAGE_SEARCH_VERSION if retriever == "passages" else SEARCH_VERSION,
        retriever=retriever, ranking_configuration_hash=CONFIGURATION_HASH if retriever == "passages" else None,
        query_configuration_digest=digest([dict(case_id=c.id, question=c.question, keywords=c.keyword_queries,
            filters=c.filters.model_dump(mode="json")) for c in dataset.cases]),
        git=git_revision(), policy_revision=snapshot.db.scalar(select(User.policy_revision).where(User.id == snapshot.owner_id)),
        corpus=corpus_manifest(snapshot.db, snapshot.owner_id, deadline=deadline if seconds > 0 else None), composition=composition(dataset))
    if retriever == "passages":
        from app.models.passage import EntryPassage, PassageIndexState
        from app.services.passage_search import coverage
        states = snapshot.db.execute(select(PassageIndexState.entry_id, PassageIndexState.indexed_version_id,
            PassageIndexState.projection_version, PassageIndexState.content_hash, PassageIndexState.status,
            PassageIndexState.passage_count, PassageIndexState.gap_codes).join(Entry, Entry.id == PassageIndexState.entry_id)
            .where(Entry.user_id == snapshot.owner_id).order_by(PassageIndexState.entry_id)).all()
        size = snapshot.db.execute(select(func.count(), func.coalesce(func.sum(func.octet_length(EntryPassage.text)), 0))
            .select_from(EntryPassage).join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
            .join(Entry, Entry.id == EntryVersion.entry_id).where(Entry.user_id == snapshot.owner_id)).one()
        manifest["passage_index"] = dict(state_digest=digest([list(row) for row in states]),
            coverage=coverage(snapshot.db, snapshot.owner_id), passages=size[0], text_bytes=size[1])
    for case in dataset.cases:
        item = dict(case_id=case.id, language=case.language, tags=case.tags, expected_outcome=case.expected_outcome,
            status="draft" if case.status == "draft" else "ready", has_keywords=bool(case.keyword_queries),
            validation_errors=[], scored=False, scores={}, queries=[], groups={}, policy_blocked=False,
            filters=case.filters.model_dump(mode="json"),
            has_historical=any(a.selection == "historical" for g in case.required_groups() for a in g.anchors))
        results.append(item)
        if case.status == "draft":
            continue
        queries = [case.question] if mode == "primary" else case.keyword_queries
        current = any(a.selection == "current" for group in case.required_groups() for a in group.anchors)
        item["scored"] = bool(queries and current and case.required_groups() and
            case.expected_outcome in {"supported", "policy_excluded"})
        # Failed cases retain their denominator and a zero score, with an explicit failure status.
        if item["scored"]:
            item["scores"] = average_scores([query_metrics([], {g.id:[] for g in case.required_groups()})])
        if time.monotonic() >= deadline:
            item["status"] = "run_budget"
            continue
        try:
            # Savepoints let one canceled statement become a partial case without poisoning the snapshot.
            with snapshot.db.begin_nested():
                validated = validate_case(snapshot.db, snapshot.owner_id, case)
                item["validation_errors"] = validated["errors"]
                groups = {group.id:validated["groups"][group.id] for group in case.required_groups()}
                item["groups"] = groups
                if not validated["valid"]:
                    item["status"] = "evidence_invalid"
                item["policy_blocked"] = bool(groups) and not all(any(a.get("external_ai_eligible") for a in anchors) for anchors in groups.values())
                if not queries:
                    item["status"] = "no_keyword_query"
                    continue
                for index, query in enumerate(queries):
                    if time.monotonic() >= deadline:
                        raise EvaluationError("RUN_BUDGET")
                    before = time.monotonic()
                    found = (retrieve_passages(snapshot.db, owner_id=snapshot.owner_id, q=query, filters=case.filters, groups=groups)
                        if retriever == "passages" else retrieve(snapshot.db, owner_id=snapshot.owner_id, q=query, filters=case.filters))
                    scores = metrics(found["hits"], groups)
                    if not current:
                        scores.update({key:None for key in scores if key not in {"historical_entry_hit", "group_ranks"}})
                    item["queries"].append(dict(query_index=index, query_digest=digest(query),
                        elapsed_ms=round((time.monotonic()-before)*1000,2), **found, scores=scores))
                item["scores"] = average_scores([q["scores"] for q in item["queries"]])
                item["scored"] = bool(groups) and current and case.expected_outcome in {"supported", "policy_excluded"}
                if item["status"] == "ready":
                    item["status"] = ("evaluated" if item["scored"] else
                        "historical_only" if groups else case.expected_outcome)
        except EvaluationError as error:
            item["status"] = str(error).lower()
        except DBAPIError:
            item["status"] = "database_timeout_or_error"
        except HTTPException:
            # The shared retrieval deadline is a failed scored case, not a
            # reason to drop its denominator or abort the remaining dataset.
            item["status"] = "database_timeout_or_error"
    manifest["elapsed_ms"] = round((time.monotonic()-started)*1000,2)
    manifest["status"] = "partial" if any(c["status"] in {"run_budget", "database_timeout_or_error", "evidence_invalid"} for c in results) else "completed"
    return dict(manifest=manifest, cases=results, summary=summarize(results))
