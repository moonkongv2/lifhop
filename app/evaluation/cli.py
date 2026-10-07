"""Author private evaluation questions and measure existing keyword retrieval."""
import argparse
import getpass
import json
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, select

from app.evaluation.schemas import Case, Dataset, EvaluationError, dataset_from, now
from app.evaluation.storage import PRIVATE_ROOT, private_directory, load_dataset, save_dataset
from app.evaluation.evidence import approve_case, make_anchor, validate_case, version_metadata, check_anchor, passage
from app.evaluation.retrieval import check_binding, composition, evaluate, readonly_snapshot, retrieve
from app.evaluation.report import save_report
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.evaluation.drafting import draft_candidates, candidate_sheet
from app.evaluation.storage import write_private
from app.evaluation.review_sheet import render_review_sheet, answer_candidates


SEEDS = (
    "우리가 이전에 진행했던 모터 RPM 제어 최적화 문제에서 제어 주기 설정을 어떤 기준으로 했었지?",
    "2026년 4월 오키나와 여행 시 이용했던 렌터카 업체와 선정 이유?",
)


def initialize(snapshot, *, root=PRIVATE_ROOT):
    set_id = uuid4().hex
    dataset = dataset_from(dict(set_id=set_id, revision=1, owner_id=snapshot.owner_id,
        owner_email=snapshot.owner_email, database_fingerprint=snapshot.database_fingerprint, created_at=now(),
        cases=[dict(id=f"case-{index+1:02d}", question=SEEDS[index] if index < 2 else "",
            tags=["decision"] if index == 0 else ["life"] if index == 1 else []) for index in range(20)]))
    directory = root / set_id
    private_directory(directory, root)
    save_dataset(directory, dataset, root=root)
    return directory, dataset


def replace_case(dataset: Dataset, changed: Case) -> Dataset:
    if changed.id not in {case.id for case in dataset.cases}:
        raise EvaluationError("UNKNOWN_CASE")
    value = dataset.model_dump(mode="json", exclude={"digest"})
    value.update(revision=dataset.revision+1, parent_digest=dataset.digest, created_at=now(),
        cases=[changed.model_dump(mode="json") if case.id == changed.id else case.model_dump(mode="json") for case in dataset.cases])
    return dataset_from(value)


def choose_case(dataset):
    for case in dataset.cases:
        print(f"{case.id}: {case.status} [{case.language}] {display_text(case.question) or '(blank)'}")
    identity = input("Case ID: ").strip()
    case = next((case for case in dataset.cases if case.id == identity), None)
    if not case:
        raise EvaluationError("UNKNOWN_CASE")
    return case


def display_text(value):
    return "".join(character if character in "\n\t" or 32 <= ord(character) != 127 else
                   f"\\u{ord(character):04x}" for character in value)


def ask(label, current=""):
    value = input(f"{label} [{current}]: ")
    return current if value == "" else "" if value == "-" else value


def edit_case(case):
    print("Blank keeps the value; '-' clears it. JSON fields use one line. Source quotes are not needed.")
    value = case.model_dump(mode="json")
    value.update(status="draft", reviewed_by=None, reviewed_at=None)
    for field in ("question", "language", "expected_outcome", "review_scope", "review_notes"):
        value[field] = ask(field, value[field])
    for field in ("tags", "keyword_queries", "filters", "claims", "evidence_groups"):
        raw = ask(field + " JSON", json.dumps(value[field], ensure_ascii=False))
        value[field] = json.loads(raw)
    return Case.model_validate(value)


def add_anchor(snapshot, case):
    groups = case.model_dump(mode="json")["evidence_groups"]
    print("Existing groups:", ", ".join(group["id"] for group in groups) or "none")
    group_id = input("Evidence group ID (existing or new): ").strip()
    entry_id, version_id = int(input("Entry ID: ")), int(input("Version ID: "))
    field = input("Field [content]: ").strip() or "content"
    metadata = version_metadata(snapshot.db, snapshot.owner_id, entry_id, version_id, field)
    start = int(input("Start character offset [0]: ") or "0")
    if not 0 <= start < metadata["characters"]:
        raise EvaluationError("INVALID_ANCHOR")
    # Bounded display from the pinned version, never copied to a report or gold file.
    column = getattr(EntryVersion, field)
    preview = snapshot.db.scalar(select(func.substr(column, start+1, 8000))
        .join(Entry, Entry.id == EntryVersion.entry_id).where(Entry.user_id == snapshot.owner_id,
            Entry.id == entry_id, EntryVersion.id == version_id))
    print(f"Pinned version has {metadata['characters']} characters; preview starts at {start}:")
    offset = start
    for line in preview.splitlines(keepends=True):
        print(f"[{offset}] {display_text(line).rstrip()}")
        offset += len(line)
    end = int(input("End character offset (exclusive): "))
    selection = input("Selection current/historical [current]: ").strip() or "current"
    anchor = make_anchor(snapshot.db, owner_id=snapshot.owner_id, entry_id=entry_id, version_id=version_id,
        field=field, start=start, end=end, selection=selection)
    group = next((group for group in groups if group["id"] == group_id), None)
    if group is None:
        group = dict(id=group_id, anchors=[])
        groups.append(group)
    group["anchors"].append(anchor.model_dump(mode="json"))
    value = case.model_dump(mode="json")
    value.update(evidence_groups=groups, status="draft", reviewed_by=None, reviewed_at=None)
    return Case.model_validate(value)


def inspect(snapshot, dataset):
    case = choose_case(dataset)
    query = input("Search query: ")
    if not 0 < len(query.strip()) <= 256:
        raise EvaluationError("QUERY_LIMIT")
    found = retrieve(snapshot.db, owner_id=snapshot.owner_id, q=query, filters=case.filters)
    print(f"{found['total']} records; top {len(found['hits'])}")
    for rank, hit in enumerate(found["hits"],1):
        print(f"{rank}. Entry {hit['entry_id']}, current version {hit['version_id']}: http://localhost:5173/entries/{hit['entry_id']}")


def record_answer(snapshot,case):
    if case.status!="draft":
        raise EvaluationError("CASE_ALREADY_REVIEWED")
    candidates=answer_candidates(snapshot,case)
    if not candidates:
        raise EvaluationError("NO_ANSWER_CANDIDATES")
    for index,anchor in enumerate(candidates,1):
        print(f"{index}. Entry {anchor.entry_id} / version {anchor.version_id}: {anchor.field} [{anchor.start}:{anchor.end}]")
    print("Choose evidence for each fact you verified. Blank evidence number finishes. Nothing is saved until REVIEWED.")
    claims,groups=[],[]
    while len(claims)<20:
        choice=input("Evidence number (blank to finish): ").strip()
        if not choice:
            break
        index=int(choice)-1
        if not 0<=index<len(candidates):
            raise EvaluationError("INVALID_EVIDENCE_NUMBER")
        anchor=candidates[index]
        if check_anchor(snapshot.db,snapshot.owner_id,anchor)["status"]!="valid":
            raise EvaluationError("EVIDENCE_REVIEW_REQUIRED")
        _,value=passage(snapshot.db,snapshot.owner_id,anchor.entry_id,anchor.version_id,
            anchor.field,anchor.start,anchor.end)
        print(display_text(value))
        statement=input("Verified fact (one sentence supported by this passage): ").strip()
        if not statement:
            raise EvaluationError("EMPTY_VERIFIED_FACT")
        group_id=f"evidence-{len(groups)+1:02d}"
        groups.append(dict(id=group_id,anchors=[anchor.model_dump(mode="json")]))
        claims.append(dict(id=f"claim-{len(claims)+1:02d}",statement=statement,required_group_ids=[group_id]))
    if not claims:
        raise EvaluationError("NO_VERIFIED_FACTS")
    value=case.model_dump(mode="json")
    value.update(expected_outcome="supported",claims=claims,evidence_groups=groups,
        review_scope="Owner inspected the selected pinned passages; each factual claim names its required evidence group.",
        review_notes="Owner entered verified facts locally and explicitly confirmed their support. Other corpus coverage was not certified.")
    changed=Case.model_validate(value)
    for claim in changed.claims:
        print(display_text(claim.statement))
    return approve_case(snapshot.db,snapshot.owner_id,changed,
        confirmed=input("I checked every fact against its passage. Type REVIEWED: ")=="REVIEWED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "draft", "review-sheet", "record-answer", "edit", "inspect", "anchor", "validate", "review", "run"))
    parser.add_argument("--email", help="Local lifhop account; defaults to the dataset owner")
    parser.add_argument("--set", type=Path, dest="directory")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--mode", choices=("primary", "keywords"), default="primary")
    args = parser.parse_args(argv)
    if args.command == "init" and (not args.email or args.directory or args.revision):
        parser.error("init requires --email and creates a new private set")
    if args.command != "init" and not args.directory:
        parser.error("--set is required")
    try:
        from app.db import engine
        dataset = load_dataset(args.directory, revision=args.revision) if args.directory else None
        email = args.email or dataset.owner_email
        password = getpass.getpass("Local lifhop password: ")
        with readonly_snapshot(engine, email, password) as snapshot:
            password = None
            if dataset:
                check_binding(snapshot, dataset)
            if args.command == "init":
                directory, dataset = initialize(snapshot)
                print(f"Private set: {directory}")
                print("20 draft cases, including two seed questions. No case has been approved.")
            elif args.command == "record-answer":
                changed=record_answer(snapshot,choose_case(dataset))
                updated=replace_case(dataset,changed)
                save_dataset(args.directory,updated)
                print(f"Saved immutable revision {updated.revision}; case {changed.id}: reviewed")
                for mode in ("primary","keywords"):
                    result=evaluate(snapshot,updated,mode=mode)
                    path=save_report(args.directory,result)
                    print(f"{mode} report: {path/'report.html'}")
                    print(json.dumps(result["summary"]))
            elif args.command in {"edit", "anchor", "review"}:
                case = choose_case(dataset)
                if args.command == "edit":
                    changed = edit_case(case)
                elif args.command == "anchor":
                    changed = add_anchor(snapshot, case)
                else:
                    print(json.dumps(case.model_dump(mode="json"), ensure_ascii=False, indent=2))
                    changed = approve_case(snapshot.db, snapshot.owner_id, case,
                        confirmed=input("I checked the evidence meaning and claims. Type REVIEWED: ") == "REVIEWED")
                updated = replace_case(dataset, changed)
                save_dataset(args.directory, updated)
                print(f"Saved immutable revision {updated.revision}; case {changed.id}: {changed.status}")
            elif args.command == "inspect":
                inspect(snapshot, dataset)
            elif args.command == "review-sheet":
                html,stats=render_review_sheet(snapshot,dataset)
                path=args.directory/"reviews"/(uuid4().hex+".html")
                write_private(path,html,root=PRIVATE_ROOT)
                print(f"Private evidence review: {path}")
                print(json.dumps(stats))
            elif args.command == "draft":
                updated, stats=draft_candidates(snapshot,dataset)
                save_dataset(args.directory,updated)
                write_private(args.directory/"candidates-revision-000002.html",candidate_sheet(updated,stats),root=PRIVATE_ROOT)
                print("Local draft candidates saved:",json.dumps(stats))
                print(f"Review sheet: {args.directory/'candidates-revision-000002.html'}")
            elif args.command == "validate":
                results = [validate_case(snapshot.db, snapshot.owner_id, case) for case in dataset.cases]
                print(json.dumps(dict(composition=composition(dataset), cases=results), ensure_ascii=False, indent=2))
            elif args.command == "run":
                result = evaluate(snapshot, dataset, mode=args.mode)
                run = save_report(args.directory, result)
                print(f"Report: {run/'report.html'}")
                print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
                print("Real evaluation completeness:", result["manifest"]["composition"]["complete"])
        return 0
    except EvaluationError as error:
        print(f"Evaluation failed: {error}")
    except (ValidationError, ValueError, TypeError, KeyError):
        print("Evaluation failed: INVALID_INPUT_OR_DATASET")
    except SQLAlchemyError:
        print("Evaluation failed: DATABASE_ERROR")
    except (OSError, EOFError):
        print("Evaluation failed: LOCAL_FILE_OR_INPUT_ERROR")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
