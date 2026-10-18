"""Bounded local period sampling from current permitted body passages; no egress."""
from sqlalchemy import String, case, cast, func, literal, select
from app.api.passages import search_filters
from app.evaluation.schemas import digest
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage, PassageIndexState
from app.models.user import User
from app.schemas.retrospective import RetrospectivePreview
from app.services.answer_call import answer_excerpts
from app.services.answer_transport import CONFIG_HASH, payload
from app.services.embedding_transport import EmbeddingError
from app.services.entry_search import search_components
from app.services.passage_search import eligible_conditions, read_passage
from app.services.ai_sources import allowed_type


def summary_question(scope):
    basis = 'source/event dates' if scope.date_field == 'event_at' else 'collection dates'
    return (f'Summarize selected current records for {scope.date_from} through {scope.date_to} by {basis}. '
        'This is a partial retrospective. Distinguish proposals, decisions and completed work. Answer in English.')


def spread_positions(total, limit):
    count = min(total, limit)
    return [round(i * (total - 1) / (count - 1)) for i in range(count)] if count > 1 else [0] if count else []


def preview(db, owner_id, scope):
    filters = search_filters(source=scope.source, type=scope.type, date_field=scope.date_field,
        date_from=scope.date_from, date_to=scope.date_to)
    conditions, _, _, _ = search_components(user_id=owner_id, **filters)
    matched = select(Entry.id).where(*conditions)
    matched_count = db.scalar(select(func.count()).select_from(matched.subquery()))
    allowed = matched.join(SourcePolicy, (SourcePolicy.user_id == Entry.user_id) &
        (SourcePolicy.provider == func.coalesce(Entry.provider, 'unknown')) & (SourcePolicy.scope == Entry.source_scope)).where(
        SourcePolicy.external_ai_allowed.is_(True), Entry.external_ai_allowed.is_(True), Entry.source_state != 'deleted',
        allowed_type())
    allowed_count = db.scalar(select(func.count()).select_from(allowed.subquery()))
    timestamp = Entry.event_at if scope.date_field == 'event_at' else Entry.created_at
    body = select(EntryPassage.id.label('passage_id'), Entry.id.label('entry_id'), timestamp.label('at'),
        func.coalesce(EntryPassage.group_key, literal('p:') + cast(EntryPassage.id, String)).label('group_key'),
        func.row_number().over(partition_by=Entry.id, order_by=[
            case(((Entry.provider == 'codex') & EntryPassage.text.startswith('assistant:'), 0), else_=1),
            EntryPassage.ordinal]).label('position')
        ).select_from(EntryPassage).join(EntryVersion, EntryVersion.id == EntryPassage.version_id).join(
            Entry, Entry.id == EntryVersion.entry_id).join(PassageIndexState, PassageIndexState.entry_id == Entry.id).where(
                *eligible_conditions(owner_id, filters), Entry.id.in_(allowed), EntryPassage.field == 'content').cte('period_bodies')
    ready_count = db.scalar(select(func.count()).select_from(body).where(body.c.position == 1))
    grouped = select(body, func.row_number().over(partition_by=body.c.group_key,
        order_by=[body.c.at.desc(), body.c.entry_id.desc()]).label('alias_position')).where(body.c.position == 1).cte('period_groups')
    unique_count = db.scalar(select(func.count()).select_from(grouped).where(grouped.c.alias_position == 1))
    ranked = select(grouped, func.row_number().over(order_by=[grouped.c.at, grouped.c.entry_id]).label('rank')
        ).where(grouped.c.alias_position == 1).cte('period_order')
    rows = list(db.execute(select(ranked).where(ranked.c.rank.in_([
        i + 1 for i in spread_positions(unique_count, 20)])).order_by(ranked.c.rank)).mappings())
    # Spread the first five choices across time, then try remaining candidates if
    # an entire parent cannot fit. Never truncate or add a second parent silently.
    priority = spread_positions(len(rows), 5)
    priority += [i for i in range(len(rows)) if i not in priority]
    selected, skipped = [], 0
    for i in priority:
        if len(selected) == 5:
            break
        parent = read_passage(db, owner_id, rows[i]['passage_id'])
        anchors = [dict(id=p.id, reference_id=p.id) for p in [*selected, parent]]
        excerpts = answer_excerpts(db, owner_id, anchors, [p.text for p in [*selected, parent]], True)
        try:
            payload(summary_question(scope), excerpts, retrospective=True)
        except EmbeddingError:
            skipped += 1
            continue
        selected.append(parent)
    selected.sort(key=lambda p: (p.event_at if scope.date_field == 'event_at' else p.created_at, p.entry_id))
    undated_filters = dict(filters, date_from=None, date_to=None)
    undated, _, _, _ = search_components(user_id=owner_id, **undated_filters)
    missing = db.scalar(select(func.count()).select_from(Entry).where(*undated, Entry.event_at.is_(None)))
    revision = db.scalar(select(User.policy_revision).where(User.id == owner_id))
    incomplete = sum(p.completeness != 'complete' or p.index_status == 'partial' for p in selected)
    protocol = dict(owner_id=owner_id, configuration_hash=CONFIG_HASH,
        scope=scope.model_dump(mode='json'), revision=revision,
        counts=[matched_count, allowed_count, ready_count, unique_count, len(rows), skipped, missing, incomplete],
        selected=[dict(id=p.id, entry_id=p.entry_id, version_id=p.version_id, field=p.field,
            source=p.source, completeness=p.completeness, index_status=p.index_status,
            hash=p.passage_hash, start=p.start, end=p.end,
            event_at=p.event_at.isoformat() if p.event_at else None, added_at=p.created_at.isoformat()) for p in selected])
    return RetrospectivePreview(scope=scope, policy_revision=revision, preview_digest=digest(protocol),
        matched_records=matched_count, allowed_records=allowed_count, ready_records=ready_count,
        unique_records=unique_count, candidate_records=len(rows), selected_records=len(selected), byte_skipped=skipped,
        missing_event_dates=missing, incomplete_selected=incomplete, passages=selected)
