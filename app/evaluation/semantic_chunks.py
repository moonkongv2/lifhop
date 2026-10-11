"""Experimental exact subranges; never rewrite the live passage index."""
from functools import reduce
from sqlalchemy import String, Text, DateTime, Integer, column, values, select, func, literal, case, or_
from app.evaluation.schemas import digest
from app.services.passage_index import text_hash
from app.services.passage_search import query_tokens, score_order
from app.services.embedding_transport import EmbeddingError
from app.services.semantic_chunks import CHUNKING, section_ranges


def split_rows(rows, maximum):
    result = []
    for row in rows:
        for left, right in section_ranges(row["text"]):
            value = row["text"][left:right]
            if not value.strip():
                continue
            start, end = row["start"] + left, row["start"] + right
            hashed = text_hash(value)
            # The parent projection has already verified repository/path identity.
            group = digest([row["source_scope"], row["document_path"], row["field"], hashed]) if row.get("document_path") else None
            identity = f'{row["id"]}:{start}:{end}'
            result.append(dict(row, id=identity, parent_id=row["id"],
                parent_hash=row["passage_hash"], start=start, end=end, text=value,
                bytes=len(value.encode("utf-8")), passage_hash=hashed,
                group_id=group or identity))
            if len(result) > maximum:
                raise EmbeddingError("EXPERIMENT_CORPUS_LIMIT")
    return result


def embedding_anchor(row):
    if "parent_id" not in row:
        return dict(id=row["id"], passage_hash=row["passage_hash"])
    return dict(id=row["parent_id"], passage_hash=row["parent_hash"],
                start=row["start"], end=row["end"], slice_hash=row["passage_hash"])


def lexical_order(db, rows, question):
    """Use the same PostgreSQL simple-FTS scores on temporary in-memory slices."""
    if not rows:
        return []
    from datetime import datetime
    table = values(column("id", String), column("text", Text), column("event_at", DateTime(timezone=True)),
        column("entry_id", Integer), name="experimental_chunks").data([
            (r["id"], r["text"], datetime.fromisoformat(r["event_at"]) if r["event_at"] else None, r["entry_id"])
            for r in rows])
    vector = func.to_tsvector("simple", table.c.text)
    escaped = question.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    phrase = table.c.text.ilike(f"%{escaped}%", escape="\\")
    tokens = [func.plainto_tsquery("simple", token) for token in query_tokens(question)]
    query = reduce(lambda a,b: a.op("||")(b), tokens) if tokens else None
    count = sum((case((vector.op("@@")(token), 1), else_=0) for token in tokens), literal(0))
    base = select(table.c.id, table.c.event_at, table.c.entry_id,
        case((phrase, 3), else_=0).label("phrase_score"), count.label("body_tokens"),
        (func.ts_rank_cd(vector, query) if query is not None else literal(0)).label("relevance"))
    base = base.where(or_(phrase, vector.op("@@")(query)) if query is not None else phrase).cte()
    return list(db.scalars(select(base.c.id).order_by(*score_order(base.c))))
