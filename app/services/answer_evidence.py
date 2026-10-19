"""Local bounded parent selection. No provider, ledger or persistence."""
import re
from fastapi import HTTPException
from sqlalchemy import select
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding
from app.models.user import User
from app.schemas.answer import RecommendationOmission, RecommendationResponse
from app.services.answer_transport import payload
from app.services.answer_context import current_excerpt
from app.services.embedding_transport import EmbeddingError
from app.services.passage_search import read_passage
from app.services.semantic_search import filtered_vectors, read_slice


def choose_parents(question, candidates):
    """Keep the leading context and one explicitly requested commit, if retrieved."""
    ranked = list(enumerate(candidates, 1))
    wants_commit = re.search(r'커밋|\bcommits?\b', question, re.IGNORECASE)
    excludes_commit = re.search(r'커밋(?:은|을|는)?\s*(?:제외|말고|빼고)|\b(?:without|excluding|no)\s+commits?\b',
        question, re.IGNORECASE)
    if wants_commit and not excludes_commit:
        # This is a question-kind preference within the checked candidates, not
        # a provider quota or an expected source/ID injected into retrieval.
        preferred = next((item for item in ranked if item[1][1].repository_ref
            and item[1][1].repository_ref.kind == 'commit'), None)
        if preferred and preferred != ranked[0]:
            ranked = [ranked[0], preferred, *[item for item in ranked[1:] if item != preferred]]
    selected, omissions, seen = [], [], set()
    request_bytes = 0
    for rank, (embedding_id, parent, group_key) in ranked:
        key = ("document", group_key) if group_key else ("passage", parent.id)
        reason = None
        if key in seen:
            reason = "duplicate_parent"
        elif len(selected) >= 5:
            reason = "count_limit"
        else:
            try:
                _, upper = payload(question, [current_excerpt(p) for p in [*selected, parent]])
                request_bytes = upper - 1024
                selected.append(parent)
            except EmbeddingError:
                reason = "byte_limit"
        seen.add(key)
        if reason:
            omissions.append(RecommendationOmission(embedding_id=embedding_id, rank=rank, reason=reason))
    return selected, sorted(omissions, key=lambda item: item.rank), request_bytes


def recommend(db, owner_id, question, embedding_ids, filters, revision):
    if db.scalar(select(User.policy_revision).where(User.id == owner_id)) != revision:
        raise HTTPException(409, "ANSWER_CONTEXT_CHANGED")
    # Reject the entire request if any candidate became foreign, filtered or stale.
    # The caller holds the shared owner lock throughout these bounded local reads.
    rows = {row.id: row for row in db.scalars(filtered_vectors(owner_id, filters).where(
        PassageEmbedding.id.in_(embedding_ids)))}
    if set(rows) != set(embedding_ids):
        raise HTTPException(404, "ANSWER_SLICE_UNAVAILABLE")
    candidates = []
    for embedding_id in embedding_ids:
        read_slice(db, owner_id, embedding_id)
        parent = read_passage(db, owner_id, rows[embedding_id].passage_id)
        group_key = db.scalar(select(EntryPassage.group_key).where(EntryPassage.id == parent.id))
        candidates.append((embedding_id, parent, group_key))
    selected, omissions, size = choose_parents(question, candidates)
    return RecommendationResponse(passages=selected, omissions=omissions,
        policy_revision=revision, request_bytes=size)
