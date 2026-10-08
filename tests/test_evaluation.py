from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.evaluation.schemas import Case, Filters, EvaluationError, dataset_from, now
from app.evaluation.evidence import make_anchor, check_anchor, approve_case
from app.evaluation.storage import load_dataset, save_dataset, write_private
from app.evaluation.retrieval import Snapshot, database_identity, retrieve, evaluate, readonly_snapshot
from app.evaluation.metrics import query_metrics, average_scores
from app.evaluation.report import render_report, save_report
from app.models.entry import Entry, EntryType
from app.models.history import EntryVersion, SourcePolicy
from app.models.user import User
from app.security import hash_password
from app.services.source_history import record_version
from app.evaluation.cli import initialize, replace_case, main
from app.evaluation.drafting import draft_candidates, candidate_sheet


def record(db, owner, content="[Synthetic] 제주 여행 120 RPM 😀\nUse 100% use_state.", **values):
    entry = Entry(user_id=owner.id, title=values.pop("title", "[Synthetic] Evidence"),
        type=values.pop("type", EntryType.NOTE), content=content, **values)
    db.add(entry)
    db.flush()
    entry.current_version_id = record_version(db, entry).id
    db.flush()
    return entry


def snap(db, owner):
    return Snapshot(db, owner.id, owner.email, database_identity(db), now().isoformat())


def gold(db, owner, entry, *, identity="case-01", question="제주 여행", keywords=None, selection="current"):
    anchor = make_anchor(db, owner_id=owner.id, entry_id=entry.id, version_id=entry.current_version_id,
        field="content", start=0, end=min(len(entry.content),100), selection=selection)
    case = Case(id=identity, question=question, language="ko", keyword_queries=keywords or [],
        claims=[dict(id="claim-01", statement="Synthetic claim", required_group_ids=["group-01"])],
        evidence_groups=[dict(id="group-01", anchors=[anchor])])
    return approve_case(db, owner.id, case, confirmed=True)


def dataset(snapshot, cases):
    return dataset_from(dict(set_id="synthetic", revision=1, owner_id=snapshot.owner_id,
        owner_email=snapshot.owner_email, database_fingerprint=snapshot.database_fingerprint,
        created_at=now(), cases=[c.model_dump(mode="json") for c in cases]))


def test_passage_evaluation_same_api_rank_and_complete_span(db_session, authenticated_user, client):
    from app.services.passage_index import sync_current_passages
    owner, headers = authenticated_user
    entry = record(db_session, owner, content="[Synthetic] The worker runs on the deployment server.", provider="manual")
    sync_current_passages(db_session, entry)
    db_session.commit()
    snapshot = snap(db_session, owner)
    case = gold(db_session, owner, entry, question="where does the deployment worker run", keywords=["deployment worker"])
    data = dataset(snapshot, [case])
    result = evaluate(snapshot, data, retriever="passages")
    assert result["summary"]["scores"]["group_recall_at_5"] == 1
    hit = result["cases"][0]["queries"][0]["hits"][0]
    found = client.get("/passages/search", headers=headers, params={"q": case.question}).json()
    assert hit["passage_id"] == found["items"][0]["id"]
    assert entry.content not in json.dumps(result) and case.question not in json.dumps(result)
    rendered = render_report(result).decode()
    assert "Passage-level" in rendered and f'/passages/{hit["passage_id"]}' in rendered


def test_passage_deadline_keeps_failed_case_in_denominator(db_session, authenticated_user, monkeypatch):
    from fastapi import HTTPException
    owner, _ = authenticated_user
    entry = record(db_session, owner, provider="manual")
    snapshot = snap(db_session, owner)
    data = dataset(snapshot, [gold(db_session, owner, entry)])
    def expired(*args, **kwargs):
        raise HTTPException(503, "search_timeout")
    monkeypatch.setattr("app.evaluation.passage_retrieval.retrieve_passages", expired)
    result = evaluate(snapshot, data, retriever="passages")
    assert result["manifest"]["status"] == "partial"
    assert result["summary"]["failed_scored_cases"] == result["summary"]["scored_cases"] == 1
    assert result["summary"]["scores"]["group_recall_at_20"] == 0


@pytest.mark.parametrize("phrase", ["제주 여행","Alice Kim","120 RPM","3.5 km","use_state","100%",r"C:\notes","foo::bar()"])
def test_retrieval_same_as_api_and_owner_scope(db_session, client, authenticated_user, another_user, phrase):
    owner, headers = authenticated_user
    instant = datetime(2026,10,1,tzinfo=timezone.utc)
    for title, content in ((phrase,None),(phrase+" trip",None),("body",phrase)):
        record(db_session,owner,content=content or "Other",title=title,created_at=instant,provider="manual")
    record(db_session,another_user,content=phrase,title=phrase,provider="manual")
    api = client.get("/entries/search",headers=headers,params=dict(q=phrase,source="manual",limit=20)).json()
    result = retrieve(db_session,owner_id=owner.id,q=phrase,filters=Filters(source="manual"))
    assert result["total"] == api["total"] == 3
    assert [hit["entry_id"] for hit in result["hits"]] == [row["id"] for row in api["items"]]
    assert "content" not in str(result) and "Synthetic" not in str(result)


def test_retrieval_filters_dates_commentary(db_session, client, authenticated_user):
    owner, headers = authenticated_user
    start = datetime(2026,9,30,15,tzinfo=timezone.utc)
    record(db_session,owner,content="work-only",provider="codex",primary_content="final",event_at=start)
    record(db_session,owner,content="work-only",provider="codex",primary_content="final",event_at=datetime(2026,10,1,15,tzinfo=timezone.utc))
    for include in (False,True):
        filters = Filters(source="codex",date_field="event_at",date_from="2026-10-01",date_to="2026-10-01",include_work_commentary=include)
        result = retrieve(db_session,owner_id=owner.id,q="work-only",filters=filters)
        params = dict(q="work-only",source="codex",date_field="event_at",date_from="2026-10-01",date_to="2026-10-01",include_work_commentary=include)
        api = client.get("/entries/search",headers=headers,params=params).json()
        assert result["total"] == api["total"] == int(include)
        assert [h["entry_id"] for h in result["hits"]] == [r["id"] for r in api["items"]]
    for values in (dict(date_to="9999-12-31"),dict(date_from="2026-11-01",date_to="2026-10-01")):
        with pytest.raises(ValidationError):
            Filters(**values)


def test_anchor_unicode_versions_owner_and_budget(db_session, authenticated_user, another_user):
    owner,_ = authenticated_user
    entry = record(db_session,owner)
    start = entry.content.index("😀")
    anchor = make_anchor(db_session,owner_id=owner.id,entry_id=entry.id,version_id=entry.current_version_id,
        field="content",start=start,end=start+2)
    assert check_anchor(db_session,owner.id,anchor)["status"] == "valid"
    assert check_anchor(db_session,another_user.id,anchor)["status"] == "unavailable"
    for field, replacement in (("passage_sha256","a"*64),("content_hash","b"*64),("source_scope","wrong")):
        assert check_anchor(db_session,owner.id,anchor.model_copy(update={field:replacement}))["status"] == "invalid_anchor"
    foreign = record(db_session,another_user)
    assert check_anchor(db_session,owner.id,anchor.model_copy(update={"version_id":foreign.current_version_id}))["status"] == "unavailable"
    entry.content = "New observed content"
    entry.current_version_id = record_version(db_session,entry).id
    db_session.flush()
    assert check_anchor(db_session,owner.id,anchor)["status"] == "stale_current"
    assert check_anchor(db_session,owner.id,anchor.model_copy(update={"selection":"historical"}))["status"] == "valid"
    oversized = record(db_session,owner,content="x"*(8*1024*1024+1))
    with pytest.raises(EvaluationError,match="FIELD_BUDGET"):
        make_anchor(db_session,owner_id=owner.id,entry_id=oversized.id,version_id=oversized.current_version_id,field="content",start=0,end=1)
    db_session.delete(entry)
    db_session.flush()
    assert check_anchor(db_session,owner.id,anchor)["status"] == "unavailable"


def test_policy_observation_does_not_insert_and_source_deleted(db_session, authenticated_user):
    owner,_ = authenticated_user
    entry = record(db_session,owner,provider="manual",external_ai_allowed=True)
    anchor = gold(db_session,owner,entry).evidence_groups[0].anchors[0]
    before = db_session.scalar(select(func.count()).select_from(SourcePolicy))
    assert check_anchor(db_session,owner.id,anchor)["external_ai_eligible"] is False
    assert db_session.scalar(select(func.count()).select_from(SourcePolicy)) == before
    policy = SourcePolicy(user_id=owner.id,provider="manual",scope="default",collection_enabled=False,external_ai_allowed=True)
    db_session.add(policy)
    db_session.flush()
    checked = check_anchor(db_session,owner.id,anchor)
    assert checked["external_ai_eligible"] and not checked["collection_enabled"]
    entry.source_state="deleted"
    db_session.flush()
    assert check_anchor(db_session,owner.id,anchor)["external_ai_eligible"] is False
    assert retrieve(db_session,owner_id=owner.id,q="제주 여행",filters=Filters())["total"] == 1


def test_revision_flow_permissions_tamper_and_draft_reset(tmp_path,db_session,authenticated_user):
    owner,_ = authenticated_user
    snapshot = snap(db_session,owner)
    directory, initial = initialize(snapshot,root=tmp_path)
    assert len(initial.cases) == 20 and all(c.status == "draft" for c in initial.cases)
    entry = record(db_session,owner)
    reviewed = gold(db_session,owner,entry)
    updated = replace_case(initial,reviewed)
    save_dataset(directory,updated,root=tmp_path)
    assert load_dataset(directory,root=tmp_path).digest == updated.digest
    assert load_dataset(directory,revision=1,root=tmp_path).digest == initial.digest
    assert (directory/"revision-000002.json").stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700
    with pytest.raises(EvaluationError,match="OUTPUT_EXISTS"):
        save_dataset(directory,updated,root=tmp_path)
    changed = reviewed.model_dump(mode="json")
    changed.update(question="Changed",status="draft",reviewed_by=None,reviewed_at=None)
    third=replace_case(updated,Case.model_validate(changed))
    save_dataset(directory,third,root=tmp_path)
    assert load_dataset(directory,root=tmp_path).cases[0].status == "draft"
    value=json.loads((directory/"revision-000003.json").read_text())
    value["cases"][0]["question"]="Tamper"
    (directory/"revision-000003.json").write_text(json.dumps(value))
    with pytest.raises(ValidationError,match="DATASET_DIGEST"):
        load_dataset(directory,root=tmp_path)
    link=tmp_path/"linked"
    link.symlink_to(directory,target_is_directory=True)
    with pytest.raises(EvaluationError,match="UNSAFE_PATH"):
        load_dataset(link,root=tmp_path)
    with pytest.raises(EvaluationError,match="UNSAFE_PATH"):
        write_private(tmp_path/".."/"escape.json",{},root=tmp_path)


def test_review_requires_explicit_meaning_and_negative_scope(db_session,authenticated_user):
    owner,_=authenticated_user
    case=Case(id="case-01",question="Unknown",expected_outcome="insufficient_evidence")
    with pytest.raises(EvaluationError,match="REVIEW_NOT_CONFIRMED"):
        approve_case(db_session,owner.id,case,confirmed=False)
    with pytest.raises(ValidationError,match="NEGATIVE_REVIEW_REQUIRED"):
        approve_case(db_session,owner.id,case,confirmed=True)
    case.review_scope="Synthetic scope"
    case.review_notes="No supporting passage found in the reviewed scope; not a universal absence claim."
    assert approve_case(db_session,owner.id,case,confirmed=True).status == "reviewed"


def test_metrics_boundaries_alternatives_multi_query_average():
    hits=[dict(entry_id=i,version_id=i) for i in range(1,21)]
    groups={"g1":[dict(status="valid",selection="current",entry_id=5,version_id=5),
                  dict(status="valid",selection="current",entry_id=10,version_id=10)],
            "g2":[dict(status="valid",selection="current",entry_id=20,version_id=20)]}
    scores=query_metrics(hits,groups)
    assert scores["group_recall_at_5"] == .5
    assert scores["group_recall_at_10"] == .5
    assert scores["group_recall_at_20"] == scores["all_groups_hit_at_20"] == 1
    assert scores["mrr_at_20"] == .2
    missing=query_metrics([],groups)
    assert average_scores([scores,missing])["group_recall_at_20"] == .5
    assert query_metrics(hits,{})["group_recall_at_20"] is None


def test_baseline_modes_invalid_denominators_and_private_report(tmp_path,db_session,authenticated_user,monkeypatch):
    owner,_=authenticated_user
    entry=record(db_session,owner,content="Sensitive synthetic phrase",annotation="Private synthetic annotation",provider="manual")
    current=gold(db_session,owner,entry,question="Natural question that is not a substring",keywords=["Sensitive","not-found","phrase"])
    historical=gold(db_session,owner,entry,identity="case-02",selection="historical",question="Sensitive",keywords=["Sensitive"])
    no_keywords=gold(db_session,owner,entry,identity="case-03",question="Sensitive")
    draft=Case(id="case-04",question="Sensitive")
    snapshot=snap(db_session,owner)
    data=dataset(snapshot,[current,historical,no_keywords,draft])
    import urllib.request
    monkeypatch.setattr(urllib.request.OpenerDirector,"open",lambda *a,**k:pytest.fail("Unexpected outbound HTTP"))
    primary=evaluate(snapshot,data)
    keywords=evaluate(snapshot,data,mode="keywords")
    assert primary["cases"][0]["scores"]["group_recall_at_20"] == 0
    assert keywords["cases"][0]["scores"]["group_recall_at_20"] == pytest.approx(2/3)
    assert keywords["cases"][1]["status"] == "historical_only"
    assert keywords["cases"][1]["scores"]["historical_entry_hit"] == 1
    assert keywords["cases"][1]["scores"]["group_recall_at_20"] is None
    assert keywords["summary"]["historical_cases"] == 1
    assert keywords["cases"][2]["status"] == "no_keyword_query"
    assert primary["summary"]["scored_cases"] == 2
    assert keywords["summary"]["scored_cases"] == 1
    entry.content="Changed"
    entry.current_version_id=record_version(db_session,entry).id
    db_session.flush()
    stale=evaluate(snapshot,data)
    assert stale["summary"]["scored_cases"] == 2
    assert stale["summary"]["invalid_scored_cases"] == 2
    assert stale["summary"]["scores"]["group_recall_at_20"] == 0
    run=save_report(tmp_path/"synthetic",primary,root=tmp_path)
    for file in run.iterdir():
        content=file.read_text()
        assert "Sensitive synthetic phrase" not in content
        assert "Natural question that" not in content
        assert "Private synthetic annotation" not in content
        assert file.stat().st_mode & 0o777 == 0o600
    copy=deepcopy(primary)
    copy["cases"][0]["case_id"]='<script>alert("x")</script>'
    assert b"<script>" not in render_report(copy)
    copy["manifest"]["material_kind"]="synthetic"
    assert b'<a href=' not in render_report(copy)
    assert b"Synthetic fixture" in render_report(copy)
    timed=evaluate(snapshot,data,seconds=0)
    assert timed["manifest"]["status"] == "partial"
    assert timed["summary"]["state_counts"]["run_budget"] == 3
    assert timed["summary"]["scored_cases"] == 2
    assert timed["summary"]["failed_scored_cases"] == 2
    assert timed["summary"]["scores"]["group_recall_at_20"] == 0
    with pytest.raises(EvaluationError,match="OWNER_DATABASE_MISMATCH"):
        evaluate(Snapshot(db_session,owner.id,owner.email,"f"*64,now().isoformat()),data)


@pytest.fixture
def committed_evaluation_owner():
    from conftest import test_engine
    email="evaluation-"+uuid4().hex+"@example.com"
    password="Synthetic local test password"
    with Session(test_engine) as db:
        owner=User(email=email,password_hash=hash_password(password))
        db.add(owner)
        db.flush()
        entry=record(db,owner,content="Snapshot synthetic evidence")
        owner_id,entry_id=owner.id,entry.id
        db.commit()
    try:
        yield test_engine,email,password,owner_id,entry_id
    finally:
        with Session(test_engine) as db:
            db.execute(delete(Entry).where(Entry.user_id==owner_id))
            db.execute(delete(User).where(User.id==owner_id))
            db.commit()


def test_readonly_authenticated_snapshot_concurrent_write_and_no_mutation(committed_evaluation_owner):
    test_engine,email,password,owner_id,entry_id=committed_evaluation_owner
    with readonly_snapshot(test_engine,email,password) as snapshot:
        assert snapshot.db.scalar(text("SHOW transaction_read_only")) == "on"
        assert snapshot.db.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert retrieve(snapshot.db,owner_id=owner_id,q="Snapshot",filters=Filters())["total"] == 1
        with Session(test_engine) as writer:
            entry=writer.get(Entry,entry_id)
            entry.content="Replaced synthetic evidence"
            entry.current_version_id=record_version(writer,entry).id
            writer.commit()
        assert retrieve(snapshot.db,owner_id=owner_id,q="Snapshot",filters=Filters())["total"] == 1
        with pytest.raises(DBAPIError):
            with snapshot.db.begin_nested():
                snapshot.db.execute(text("UPDATE users SET policy_revision=999 WHERE id=:id"),{"id":owner_id})
        assert snapshot.db.scalar(select(User.policy_revision).where(User.id==owner_id)) == 0
    with readonly_snapshot(test_engine,email,password) as snapshot:
        assert retrieve(snapshot.db,owner_id=owner_id,q="Snapshot",filters=Filters())["total"] == 0
    with pytest.raises(EvaluationError,match="AUTH_FAILED"):
        with readonly_snapshot(test_engine,email,"wrong"):
            pytest.fail("Authentication accepted")


def test_cli_init_run_and_draft_edit_flow(tmp_path,db_session,authenticated_user,monkeypatch):
    from contextlib import contextmanager
    import app.evaluation.cli as cli
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    @contextmanager
    def mocked_snapshot(*args):
        yield snapshot
    monkeypatch.setattr(cli,"readonly_snapshot",mocked_snapshot)
    monkeypatch.setattr(cli.getpass,"getpass",lambda *args:"never saved")
    monkeypatch.setattr(cli,"initialize",lambda s:initialize(s,root=tmp_path))
    assert main(["init","--email",owner.email]) == 0
    directory=next(tmp_path.iterdir())
    data=load_dataset(directory,root=tmp_path)
    # CLI confines real outputs to its private root; inject only storage roots for this test.
    monkeypatch.setattr(cli,"load_dataset",lambda d,revision=None:load_dataset(d,revision=revision,root=tmp_path))
    monkeypatch.setattr(cli,"save_dataset",lambda d,s:save_dataset(d,s,root=tmp_path))
    monkeypatch.setattr(cli,"save_report",lambda d,r:save_report(d,r,root=tmp_path))
    assert main(["run","--set",str(directory)]) == 0
    assert main(["validate","--set",str(directory)]) == 0
    answers=iter([data.cases[0].id,"Actual synthetic question","en","coverage_gap","Synthetic uncollected source","No real answer asserted","[\"coverage_gap\"]","[]","{}","[]","[]"])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["edit","--set",str(directory)]) == 0
    changed=load_dataset(directory,root=tmp_path)
    assert changed.revision==2 and changed.cases[0].status=="draft"
    answers=iter([data.cases[0].id,"REVIEWED"])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["review","--set",str(directory)]) == 0
    assert load_dataset(directory,root=tmp_path).cases[0].status=="reviewed"


def test_database_timeout_keeps_denominator_and_recovers_snapshot(db_session,authenticated_user,monkeypatch):
    import app.evaluation.retrieval as retrieval
    owner,_=authenticated_user
    entry=record(db_session,owner)
    case=gold(db_session,owner,entry)
    snapshot=snap(db_session,owner)
    data=dataset(snapshot,[case])
    db_session.execute(text("SET LOCAL statement_timeout = '20ms'"))
    original=retrieval.retrieve
    def timed_query(db,**kwargs):
        db.execute(text("SELECT pg_sleep(0.1)"))
        return original(db,**kwargs)
    monkeypatch.setattr(retrieval,"retrieve",timed_query)
    result=evaluate(snapshot,data)
    assert result["manifest"]["status"]=="partial"
    assert result["summary"]["scored_cases"]==result["summary"]["failed_scored_cases"]==1
    assert result["summary"]["clean_cases"]==0
    assert result["summary"]["scores"]["group_recall_at_20"]==0
    assert db_session.scalar(text("SELECT 1"))==1


def test_cli_supported_case_edit_anchor_review_run(tmp_path,db_session,authenticated_user,monkeypatch):
    from contextlib import contextmanager
    import app.evaluation.cli as cli
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    directory,_=initialize(snapshot,root=tmp_path)
    entry=record(db_session,owner,content="Synthetic exact supporting passage.")
    @contextmanager
    def mocked_snapshot(*args):
        yield snapshot
    monkeypatch.setattr(cli,"readonly_snapshot",mocked_snapshot)
    monkeypatch.setattr(cli.getpass,"getpass",lambda *args:"never saved")
    monkeypatch.setattr(cli,"load_dataset",lambda d,revision=None:load_dataset(d,revision=revision,root=tmp_path))
    monkeypatch.setattr(cli,"save_dataset",lambda d,s:save_dataset(d,s,root=tmp_path))
    monkeypatch.setattr(cli,"save_report",lambda d,r:save_report(d,r,root=tmp_path))
    answers=iter(["case-01","Synthetic exact supporting passage.","en","supported","","",
        '["decision"]','["Synthetic exact"]','{}',
        '[{"id":"claim-01","statement":"Synthetic assertion","required_group_ids":["reason"]}]',
        '[{"id":"reason","anchors":[]}]'])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["edit","--set",str(directory)])==0
    answers=iter(["case-01","reason",str(entry.id),str(entry.current_version_id),"content","0",str(len(entry.content)),"current"])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["anchor","--set",str(directory)])==0
    answers=iter(["case-01","REVIEWED"])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["review","--set",str(directory)])==0
    assert main(["run","--set",str(directory)])==0
    final=load_dataset(directory,root=tmp_path)
    result=evaluate(snapshot,final)
    assert final.revision==4 and result["summary"]["scores"]["group_recall_at_20"]==1
    assert final.cases[0].evidence_groups[0].anchors[0].passage_sha256


def test_local_candidate_drafting_excludes_synthetic_and_other_owners(tmp_path,db_session,authenticated_user,another_user):
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    _,initial=initialize(snapshot,root=tmp_path)
    sha="a"*40
    commit=record(db_session,owner,title="Private title",content="Private source body",provider="github")
    db_session.get(EntryVersion,commit.current_version_id).payload={"kind":"github_commit","sha":sha,"message":"Private source body"}
    turn=record(db_session,owner,title="Private turn",content="Private source body",primary_content=sha[:12],provider="codex")
    record(db_session,owner,provider="github")
    record(db_session,another_user,title="Foreign title",content="RPM",provider="codex")
    db_session.flush()
    changed,stats=draft_candidates(snapshot,initial)
    assert changed.revision==2 and changed.parent_digest==initial.digest
    assert len(changed.cases)==20 and all(c.status=="draft" for c in changed.cases)
    assert sum(c.language=="en" for c in changed.cases)==3
    assert stats["real_records"]==2 and stats["excluded_synthetic"]==1
    assert stats["cross_source_sha_candidates"]==1
    assert changed.cases[0].expected_outcome=="coverage_gap"
    assert {a.entry_id for g in changed.cases[12].evidence_groups for a in g.anchors}=={turn.id,commit.id}
    for case in changed.cases:
        for group in case.evidence_groups:
            for anchor in group.anchors:
                assert check_anchor(db_session,owner.id,anchor)["status"]=="valid"
    html=candidate_sheet(changed,stats).decode()
    assert "Private source body" not in html and "Private title" not in html
    assert "Private source body" not in changed.model_dump_json()
    with pytest.raises(ValidationError,match="CANDIDATE_CLAIM_REQUIRES_EDIT"):
        approve_case(db_session,owner.id,changed.cases[6],confirmed=True)
    with pytest.raises(EvaluationError,match="DRAFT_ALREADY_AUTHORED"):
        draft_candidates(snapshot,changed)
    edited=initial.model_copy(update={"cases":[initial.cases[0].model_copy(update={"question":"Owner-authored question"}),*initial.cases[1:]]})
    with pytest.raises(EvaluationError,match="DRAFT_ALREADY_AUTHORED"):
        draft_candidates(snapshot,edited)


def test_candidate_sheet_escapes_private_questions(db_session,authenticated_user,tmp_path):
    owner,_=authenticated_user
    _,initial=initialize(snap(db_session,owner),root=tmp_path)
    initial.cases[0].question='<script>alert("x")</script>'
    html=candidate_sheet(initial,dict(supported_candidates=0,coverage_gap_candidates=20,excluded_synthetic=0)).decode()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_cli_draft_publishes_private_revision_and_sheet(tmp_path,db_session,authenticated_user,monkeypatch):
    from contextlib import contextmanager
    import app.evaluation.cli as cli
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    directory,_=initialize(snapshot,root=tmp_path)
    @contextmanager
    def mocked_snapshot(*args):
        yield snapshot
    monkeypatch.setattr(cli,"readonly_snapshot",mocked_snapshot)
    monkeypatch.setattr(cli.getpass,"getpass",lambda *args:"never saved")
    monkeypatch.setattr(cli,"PRIVATE_ROOT",tmp_path)
    monkeypatch.setattr(cli,"load_dataset",lambda d,revision=None:load_dataset(d,revision=revision,root=tmp_path))
    monkeypatch.setattr(cli,"save_dataset",lambda d,s:save_dataset(d,s,root=tmp_path))
    assert main(["draft","--set",str(directory)])==0
    assert load_dataset(directory,root=tmp_path).revision==2
    sheet=directory/"candidates-revision-000002.html"
    assert sheet.is_file() and sheet.stat().st_mode & 0o777==0o600
    assert main(["draft","--set",str(directory)])==1


def test_private_review_sheet_pins_passages_and_scopes_alternatives(db_session,authenticated_user,another_user):
    from app.evaluation.review_sheet import render_review_sheet
    owner,_=authenticated_user
    entry=record(db_session,owner,title="Real-shaped fixture",content="worker <script>unsafe()</script>",provider="manual")
    alternative=record(db_session,owner,title="Another fixture",content="worker alternative",provider="manual")
    record(db_session,owner,content="worker synthetic hidden",provider="manual")
    record(db_session,another_user,title="Foreign",content="worker foreign hidden",provider="manual")
    record(db_session,owner,title="Other source",content="worker wrong source hidden",provider="github")
    case=gold(db_session,owner,entry,question="worker",keywords=["worker"])
    case=case.model_copy(update={"status":"draft","reviewed_by":None,"reviewed_at":None,"filters":Filters(source="manual")})
    snapshot=snap(db_session,owner)
    data=dataset(snapshot,[case])
    before=data.digest
    html,stats=render_review_sheet(snapshot,data)
    html=html.decode()
    assert "&lt;script&gt;unsafe()&lt;/script&gt;" in html and "<script>" not in html
    assert "worker alternative" in html and f"Entry {alternative.id}" in html
    assert "synthetic hidden" not in html and "foreign hidden" not in html and "wrong source hidden" not in html
    assert stats["saved_spans"]==stats["alternative_spans"]==1
    assert data.digest==before and data.cases[0].status=="draft"
    snapshot.owner_id=another_user.id
    with pytest.raises(EvaluationError,match="OWNER_DATABASE_MISMATCH"):
        render_review_sheet(snapshot,data)


def test_private_review_sheet_hides_invalid_or_deleted_spans(db_session,authenticated_user):
    from app.evaluation.review_sheet import render_review_sheet
    owner,_=authenticated_user
    entry=record(db_session,owner,content="Do not render stale evidence")
    case=gold(db_session,owner,entry)
    snapshot=snap(db_session,owner)
    data=dataset(snapshot,[case])
    entry.content="Replacement"
    entry.current_version_id=record_version(db_session,entry).id
    db_session.flush()
    html,stats=render_review_sheet(snapshot,data)
    assert b"Do not render stale evidence" not in html and b"stale_current" in html
    assert stats["unavailable_spans"]==1
    db_session.delete(entry)
    db_session.flush()
    html,_=render_review_sheet(snapshot,data)
    assert b"Do not render stale evidence" not in html and b"unavailable" in html
    with pytest.raises(EvaluationError,match="REVIEW_SHEET_BUDGET"):
        render_review_sheet(snapshot,data,seconds=0)


def test_cli_review_sheet_leaves_revision_unchanged(tmp_path,db_session,authenticated_user,monkeypatch):
    from contextlib import contextmanager
    import app.evaluation.cli as cli
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    directory,initial=initialize(snapshot,root=tmp_path)
    @contextmanager
    def mocked_snapshot(*args):
        yield snapshot
    monkeypatch.setattr(cli,"readonly_snapshot",mocked_snapshot)
    monkeypatch.setattr(cli.getpass,"getpass",lambda *args:"never saved")
    monkeypatch.setattr(cli,"PRIVATE_ROOT",tmp_path)
    monkeypatch.setattr(cli,"load_dataset",lambda d,revision=None:load_dataset(d,revision=revision,root=tmp_path))
    assert main(["review-sheet","--set",str(directory)])==0
    assert load_dataset(directory,root=tmp_path).digest==initial.digest
    files=list((directory/"reviews").glob("*.html"))
    assert len(files)==1 and files[0].stat().st_mode & 0o777==0o600


@pytest.mark.parametrize("confirmation",["REVIEWED","cancel"])
def test_record_answer_local_facts_confirmation_and_both_baselines(tmp_path,db_session,authenticated_user,monkeypatch,confirmation):
    from contextlib import contextmanager
    import app.evaluation.cli as cli
    owner,_=authenticated_user
    snapshot=snap(db_session,owner)
    directory,initial=initialize(snapshot,root=tmp_path)
    entry=record(db_session,owner,title="Worker fixture",content="worker processes queued imports. worker runs separately.",
        primary_content="worker processes queued imports. worker runs separately.",provider="codex")
    case=Case(id="case-04",question="Why run the import worker?",language="en",expected_outcome="insufficient_evidence",
        keyword_queries=["worker"],filters=Filters(source="codex"))
    initial=replace_case(initial,case)
    save_dataset(directory,initial,root=tmp_path)
    @contextmanager
    def mocked_snapshot(*args):
        yield snapshot
    monkeypatch.setattr(cli,"readonly_snapshot",mocked_snapshot)
    monkeypatch.setattr(cli.getpass,"getpass",lambda *args:"never saved")
    monkeypatch.setattr(cli,"load_dataset",lambda d,revision=None:load_dataset(d,revision=revision,root=tmp_path))
    monkeypatch.setattr(cli,"save_dataset",lambda d,s:save_dataset(d,s,root=tmp_path))
    monkeypatch.setattr(cli,"save_report",lambda d,r:save_report(d,r,root=tmp_path))
    answers=iter(["case-04","1","The worker processes queued imports.","1","The worker runs separately.","",confirmation])
    monkeypatch.setattr("builtins.input",lambda *args:next(answers))
    assert main(["record-answer","--set",str(directory)])==(0 if confirmation=="REVIEWED" else 1)
    final=load_dataset(directory,root=tmp_path)
    if confirmation=="REVIEWED":
        updated=next(c for c in final.cases if c.id=="case-04")
        assert final.revision==3 and updated.status=="reviewed" and updated.expected_outcome=="supported"
        assert len(updated.claims)==len(updated.evidence_groups)==2
        assert all(g.anchors[0].entry_id==entry.id for g in updated.evidence_groups)
        reports=list((directory/"runs").glob("*/report.html"))
        assert len(reports)==2 and all("The worker processes" not in p.read_text() for p in reports)
        assert evaluate(snapshot,final,mode="keywords")["summary"]["scores"]["group_recall_at_20"]==1
    else:
        assert final.digest==initial.digest and not (directory/"runs").exists()
    assert entry.external_ai_allowed is False and entry.content=="worker processes queued imports. worker runs separately."


def test_small_review_can_show_only_selected_evidence(db_session,authenticated_user,monkeypatch):
    import app.evaluation.review_sheet as review
    owner,_=authenticated_user
    entry=record(db_session,owner,content="[Synthetic] Exact verified statement")
    case=gold(db_session,owner,entry,keywords=["statement"])
    case=case.model_copy(update={"status":"draft","reviewed_by":None,"reviewed_at":None})
    snapshot=snap(db_session,owner)
    def forbidden_search(*args,**kwargs):
        pytest.fail("Selected-only review searched unrelated records")
    monkeypatch.setattr(review,"real_records",forbidden_search)
    html,stats=review.render_review_sheet(snapshot,dataset(snapshot,[case]),include_alternatives=False)
    assert b"Exact verified statement" in html and stats["saved_spans"]==1 and stats["alternative_spans"]==0
    assert case.status=="draft"
