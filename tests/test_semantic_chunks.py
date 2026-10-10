import json
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.evaluation.semantic import prepare
from app.evaluation.semantic_chunks import CHUNKING, section_ranges, split_rows, embedding_anchor
from app.models.passage import EntryPassage
from app.services.ai_policy import send_passage_embeddings
from app.services.embedding_transport import EmbeddingError
from app.services.passage_index import text_hash, sync_current_passages
from app.services.source_history import record_version
from test_semantic import fixture, data, bounded_test_process


@pytest.mark.parametrize("value", ["", "short", "한글🙂"*700, "A\r\n\r\n## Heading\r\nText\r\n",
    "# First\n" + "paragraph\n\n"*100 + "## Second\nText",
    "```md\n# Inside fence\n\ntext\n```\n\n## Outside\nbody"])
def test_section_ranges_are_exact_bounded_and_complete(value):
    ranges = list(section_ranges(value))
    assert "".join(value[a:b] for a,b in ranges) == value
    assert all(0 < b-a <= 600 for a,b in ranges)
    assert all(ranges[i][1] == ranges[i+1][0] for i in range(len(ranges)-1))


def test_sections_break_before_headings_and_group_exact_document_slices():
    value = "Intro\n\n## Topic\nDetails\n"
    ranges = list(section_ranges(value))
    assert [value[a:b] for a,b in ranges] == ["Intro\n\n", "## Topic\nDetails\n"]
    base = dict(id=1, entry_id=1, text=value, start=100, end=100+len(value),
        field="content", passage_hash=text_hash(value), source_scope="repo:1", document_path="README.md")
    rows = split_rows([base, dict(base, id=2, entry_id=2)], 10)
    assert rows[0]["group_id"] == rows[2]["group_id"]
    assert rows[0]["id"] != rows[2]["id"]
    assert rows[1]["start"] == 107
    assert embedding_anchor(rows[1]) == dict(id=1, passage_hash=text_hash(value),
        start=107, end=100+len(value), slice_hash=text_hash("## Topic\nDetails\n"))
    assert rows[0]["group_id"] != split_rows([dict(base, document_path="OTHER.md")],10)[0]["group_id"]
    with pytest.raises(EmbeddingError, match="EXPERIMENT_CORPUS_LIMIT"):
        split_rows([base], 1)


def test_slice_gate_rechecks_parent_range_hash_and_permission(db_session, user):
    e = fixture(db_session, user)
    p = db_session.scalar(select(EntryPassage).where(EntryPassage.version_id==e.current_version_id,
                                                  EntryPassage.field=="content"))
    anchor = dict(id=p.id, passage_hash=p.passage_hash, start=p.start+12, end=p.end,
                  slice_hash=text_hash(p.text[12:]))
    sender = Mock(return_value="ok")
    args = dict(user_id=user.id, revision=user.policy_revision, transport=sender)
    assert send_passage_embeddings(db_session, passages=[anchor], **args) == "ok"
    assert sender.call_args.args[0] == [p.text[12:]]
    sender.reset_mock()
    for bad in (dict(anchor,start=-1), dict(anchor,end=p.end+1), dict(anchor,slice_hash="0"*64),
                dict(anchor,start=True), {k:v for k,v in anchor.items() if k!="end"}):
        with pytest.raises(HTTPException):
            send_passage_embeddings(db_session, passages=[bad], **args)
    sender.assert_not_called()
    e.external_ai_allowed = False
    db_session.flush()
    with pytest.raises(HTTPException):
        send_passage_embeddings(db_session, passages=[anchor], **args)
    sender.assert_not_called()


def test_section_preparation_uses_fts_without_mutating_index(db_session, user):
    e = fixture(db_session, user)
    e.content = "# Worker\nThe worker runs on the server.\n\n## Other\n" + "Different text. "*100
    e.current_version_id = record_version(db_session, e).id
    sync_current_passages(db_session,e)
    snap, dataset = data(db_session,user,e)
    before = list(db_session.scalars(select(EntryPassage.id).order_by(EntryPassage.id)))
    indexed = prepare(snap,dataset,provider="manual",scope="default")
    section = prepare(snap,dataset,provider="manual",scope="default",chunking=CHUNKING)
    assert len(section.rows) > len(indexed.rows)
    assert all(len(r["text"]) <= 600 for r in section.rows)
    assert section.manifest["configuration_hash"] != indexed.manifest["configuration_hash"]
    assert section.manifest["dataset_digest"] == indexed.manifest["dataset_digest"]
    assert before == list(db_session.scalars(select(EntryPassage.id).order_by(EntryPassage.id)))
    assert e.content not in json.dumps(section.manifest)
    assert dataset.cases[0].question not in json.dumps(section.manifest)
    e.external_ai_allowed = False
    db_session.flush()
    denied = prepare(snap,dataset,provider="manual",scope="default",chunking=CHUNKING)
    assert not denied.rows and denied.manifest["blocked_passages"] > 0
