"""Local draft evidence review for six acceptance cases; never activate or send."""
from html import escape
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from app.evaluation.schemas import EvaluationError, Filters, digest
from app.models.entry import Entry
from app.models.history import SourcePolicy
from app.models.passage import EntryPassage
from app.models.user import User
from app.schemas.historical import HistoricalScope
from app.schemas.retrospective import RetrospectiveScope
from app.services.ai_policy import embedding_inputs
from app.services.ai_sources import allowed_type
from app.services.ai_usage import budget_summary
from app.services.answer_call import answer_excerpts
from app.services.answer_transport import CONFIG_HASH, MODEL, OUTPUT_LIMIT, cost_micro, payload
from app.services.embedding_jobs import allowed_selection
from app.services.embedding_store import STORAGE_CONFIG
from app.services.embedding_transport import EmbeddingError
from app.services.historical import preview as historical_preview, excerpts as historical_excerpts
from app.services.passage_search import candidate_query, coverage as projection_coverage, read_passage, score_order
from app.services.retrospective import preview as period_preview, summary_question
from app.services.source_history import owner_lock

CASE_IDS = ['decision-implementation', 'reason-change', 'ordinary-life',
    'period-review', 'historical-cutoff', 'missing-proof']
PREPARATION_VERSION = 'evidence-drafts-v3-partial'


def default_spec(date_from, date_to, as_of):
    period = RetrospectiveScope(date_from=date_from, date_to=date_to)
    history = HistoricalScope(q='Where should the worker (워커) run?', as_of=as_of)
    rows = [
        ('Where should the import worker run, and what implementation was recorded?', 'worker 워커',
            ['Identify the recorded decision and implementation; cite Codex and GitHub.', 'Do not infer production deployment.']),
        ('What proposal changed later, and what reason for the adopted decision was recorded?', 'proposal decision 이유 변경',
            ['Identify the proposal and later decision.', 'Cite an explicit reason; do not invent a missing reason.']),
        ('Which rental car company was used in Okinawa in April 2026, and why was it selected?', 'Okinawa 오키나와 렌터카',
            ['Distinguish assistant recommendations, booking progress and actual use.',
             'Cite known facts and attribute advice; mark unconfirmed use/personal reasons explicitly.',
             'Review whether supported, partial or insufficient matches the selected evidence before approval.']),
        (summary_question(period), 'period', ['Separate proposals, decisions and completed assertions.', 'Cite each item and disclose partial/date coverage.']),
        (history.q, 'worker 워커', ['Use the latest observation by the cutoff.', 'Do not substitute current text for a historical gap.']),
        ('Do these records prove that production deployment and its verification succeeded?', 'worker 워커',
            ['Return insufficient if production use or successful verification is not established.',
             'If the selected text does prove it, revise this provisional case before evaluation.'])]
    return AcceptanceSpec(cases=[AcceptanceCase(id=case_id, question=q, query=query,
        expected_outcome='insufficient' if case_id == 'missing-proof' else 'supported', checklist=checks,
        period=period if case_id == 'period-review' else None,
        historical=history if case_id == 'historical-cutoff' else None)
        for case_id, (q, query, checks) in zip(CASE_IDS, rows)])


class AcceptanceCase(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Literal['decision-implementation', 'reason-change', 'ordinary-life',
        'period-review', 'historical-cutoff', 'missing-proof']
    question: str = Field(min_length=1, max_length=256)
    query: str = Field(min_length=1, max_length=256)
    expected_outcome: Literal['supported', 'partial', 'insufficient']
    checklist: list[str] = Field(min_length=1, max_length=8)
    unconfirmed_aspects: list[str] = Field(default_factory=list, max_length=8)
    filters: Filters = Field(default_factory=Filters)
    period: RetrospectiveScope | None = None
    historical: HistoricalScope | None = None
    deferred_reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode='after')
    def matching_scope(self):
        if (not self.question.strip() or not self.query.strip() or
                any(not value.strip() or len(value) > 1000 for value in self.checklist) or
                any(not value.strip() or len(value) > 1000 for value in self.unconfirmed_aspects) or
                (self.expected_outcome == 'partial') != bool(self.unconfirmed_aspects) or
                (self.id == 'period-review') != (self.period is not None) or
                (self.id == 'historical-cutoff') != (self.historical is not None) or
                self.id == 'missing-proof' and self.expected_outcome != 'insufficient' or
                self.deferred_reason is not None and not self.deferred_reason.strip() or
                self.historical is not None and self.question != self.historical.q or
                self.period is not None and self.question != summary_question(self.period) or
                self.filters.include_work_commentary or self.filters.source_state == 'deleted'):
            raise ValueError('Acceptance case scope is inconsistent')
        return self


class AcceptanceSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cases: list[AcceptanceCase] = Field(min_length=6, max_length=6)

    @model_validator(mode='after')
    def six_distinct_cases(self):
        if [c.id for c in self.cases] != CASE_IDS:
            raise ValueError('Use the six ordered acceptance cases')
        return self


def matching_policy_counts(db, query):
    """Count matching records before AI policy, without selecting their text."""
    matched = query.with_only_columns(Entry.id, Entry.external_ai_allowed.label('record_allowed'),
        SourcePolicy.external_ai_allowed.label('source_allowed'), allowed_type().label('type_allowed')).distinct().subquery()
    permitted = matched.c.record_allowed.is_(True) & matched.c.source_allowed.is_(True) & matched.c.type_allowed.is_(True)
    row = db.execute(select(func.count(), func.count().filter(permitted),
        func.count().filter(matched.c.record_allowed.is_not(True)),
        func.count().filter(matched.c.source_allowed.is_not(True)),
        func.count().filter(matched.c.type_allowed.is_not(True))).select_from(matched)).one()
    return dict(zip(['local_matching_records', 'ai_allowed_matching_records', 'record_denied_records',
        'source_denied_records', 'type_excluded_records'], row))


def source_permissions(db, owner):
    rows = db.execute(select(Entry.provider, Entry.type, Entry.external_ai_allowed,
        SourcePolicy.external_ai_allowed, func.count()).outerjoin(SourcePolicy,
        (SourcePolicy.user_id == Entry.user_id) & (SourcePolicy.provider == func.coalesce(Entry.provider, 'unknown')) &
        (SourcePolicy.scope == Entry.source_scope)).where(Entry.user_id == owner).group_by(
            Entry.provider, Entry.type, Entry.external_ai_allowed, SourcePolicy.external_ai_allowed).order_by(
                Entry.provider, Entry.type, Entry.external_ai_allowed, SourcePolicy.external_ai_allowed)).all()
    return [dict(source=r[0] or 'unknown', type=r[1].value, record_allowed=r[2], source_allowed=r[3], records=r[4]) for r in rows]


def current_candidates(db, owner, case, revision):
    # Candidate bodies are not materialized until live owner/type/AI-policy joins
    # have passed. This is bounded lexical discovery, not Semantic validation.
    query = candidate_query(owner, case.query, case.filters.model_dump()).add_columns(Entry.provider.label('source'))
    query = query.outerjoin(SourcePolicy, (SourcePolicy.user_id == Entry.user_id) &
        (SourcePolicy.provider == func.coalesce(Entry.provider, 'unknown')) &
        (SourcePolicy.scope == Entry.source_scope)).where(EntryPassage.field == 'content')
    counts = matching_policy_counts(db, query)
    query = query.where(*allowed_selection(owner))
    ranked = query.subquery()
    rows = list(db.execute(select(ranked).order_by(*score_order(ranked.c)).limit(20)).mappings())
    # Expose a cross-source draft even if one source dominates the first ranks.
    # Never present this deliberate selection as the product's automatic rank.
    if case.id == 'decision-implementation':
        priority = [next((i for i, row in enumerate(rows) if row['source'] == source), None)
            for source in ['codex', 'github']]
        indices = [i for i in priority if i is not None]
        rows = [rows[i] for i in indices] + [row for i, row in enumerate(rows) if i not in indices]
    selected, groups, seen = [], set(), set()
    skipped = 0
    for row in rows:
        if len(selected) == 5:
            break
        if row['group_id'] in groups or row['entry_id'] in seen:
            continue
        p = read_passage(db, owner, row['id'])
        embedding_inputs(db, user_id=owner, passages=[dict(id=p.id, passage_hash=p.passage_hash)], revision=revision)
        try:
            payload(case.question, [dict(id=x.id, text=x.text) for x in [*selected, p]])
        except EmbeddingError:
            skipped += 1
            continue
        selected.append(p)
        groups.add(row['group_id'])
        seen.add(row['entry_id'])
    return selected, dict(candidate_passages=len(rows), byte_skipped=skipped, candidate_limit=20, **counts)


def prepare_acceptance(snapshot, spec, settings):
    db, owner = snapshot.db, snapshot.owner_id
    owner_lock(db, owner)
    revision = db.scalar(select(User.policy_revision).where(User.id == owner))
    if revision is None:
        raise EvaluationError('OWNER_UNAVAILABLE')
    cases, review = [], []
    for case in spec.cases:
        scope = None
        if case.deferred_reason:
            passages, excerpts = [], []
            coverage = dict(selection='deferred', reason_digest=digest(case.deferred_reason))
            scope = case.period.model_dump(mode='json') if case.period else case.historical.model_dump(mode='json') if case.historical else None
        elif case.period:
            preview = period_preview(db, owner, case.period)
            passages = preview.passages
            coverage = preview.model_dump(mode='json', exclude={'passages'})
            texts = embedding_inputs(db, user_id=owner, revision=revision,
                passages=[dict(id=p.id, passage_hash=p.passage_hash) for p in passages])
            excerpts = answer_excerpts(db, owner, [dict(id=p.id, reference_id=p.id) for p in passages], texts, True)
            scope = case.period.model_dump(mode='json')
        elif case.historical:
            preview = historical_preview(db, owner, case.historical)
            passages = preview.passages
            coverage = preview.model_dump(mode='json', exclude={'passages'})
            excerpts = historical_excerpts(passages)
            scope = case.historical.model_dump(mode='json')
        else:
            passages, coverage = current_candidates(db, owner, case, revision)
            excerpts = [dict(id=p.id, text=p.text) for p in passages]
        source_by_entry = dict(db.execute(select(Entry.id, func.coalesce(Entry.provider, 'unknown')).where(
            Entry.user_id == owner, Entry.id.in_([p.entry_id for p in passages]))).all())
        passage_data = [dict(p.model_dump(mode='json'), source=source_by_entry[p.entry_id]) for p in passages]
        gaps = ['DEFERRED_FOR_MISSING_EVIDENCE'] if case.deferred_reason else [] if passages else ['NO_ELIGIBLE_PRIMARY_EVIDENCE']
        if not passages and not case.deferred_reason:
            if case.period and coverage['matched_records'] and not coverage['allowed_records']:
                gaps.append('PERIOD_RECORDS_AI_EXCLUDED')
            elif case.historical:
                if not coverage['observed_records']:
                    gaps.append('NO_OBSERVED_VERSION_BY_CUTOFF')
                elif not coverage['allowed_records']:
                    gaps.append('HISTORICAL_RECORDS_AI_EXCLUDED')
                elif not coverage['matching_records']:
                    gaps.append('NO_HISTORICAL_KEYWORD_MATCH')
            elif not case.period:
                if coverage['local_matching_records'] and not coverage['ai_allowed_matching_records']:
                    gaps.append('MATCHING_PRIMARY_TEXT_AI_EXCLUDED')
                elif not coverage['local_matching_records']:
                    gaps.append('NO_LOCAL_PRIMARY_MATCH')
        sources = sorted({p['source'] for p in passage_data})
        if not case.deferred_reason and case.id == 'decision-implementation' and not {'codex', 'github'}.issubset(sources):
            gaps.append('CODEX_AND_GITHUB_EVIDENCE_REQUIRED')
        upper = 0
        if passages:
            _, upper = payload(case.question, excerpts, retrospective=case.period is not None,
                historical_as_of=str(case.historical.as_of) if case.historical else None)
        estimate = cost_micro(upper, OUTPUT_LIMIT) if upper else 0
        if estimate > 10000:
            gaps.append('ANSWER_COST_LIMIT')
        selected = [dict(entry_id=p.entry_id, version_id=p.version_id, field=p.field,
            start=p.start, end=p.end, passage_hash=p.passage_hash, source=source_by_entry[p.entry_id],
            passage_id=getattr(p, 'id', None)) for p in passages]
        cases.append(dict(id=case.id, endpoint='/retrospectives' if case.period else '/historical' if case.historical else '/answers',
            question_digest=digest(case.question), checklist_digest=digest(case.checklist),
            unconfirmed_aspects_digest=digest(case.unconfirmed_aspects),
            expected_outcome=case.expected_outcome, scope=scope, selected=selected, coverage=coverage,
            deferred=bool(case.deferred_reason),
            positive_category_unverified=case.expected_outcome == 'insufficient' and case.id != 'missing-proof',
            estimated_max_micro_usd=estimate, input_upper_bound=upper, gaps=gaps))
        review.append(dict(id=case.id, question=case.question, expected_outcome=case.expected_outcome,
            checklist=case.checklist, unconfirmed_aspects=case.unconfirmed_aspects,
            passages=passage_data, gaps=gaps, deferred_reason=case.deferred_reason))
    budget = budget_summary(db, scope=settings.embedding_billing_scope,
        monthly_limit=settings.embedding_monthly_limit_micro_usd)
    prepared = [c['id'] for c in cases if c['selected'] and not c['gaps']]
    unresolved = [c['id'] for c in cases if c['gaps'] or c['positive_category_unverified']]
    protocol = dict(schema='lifhop-phase33-preflight-v1', preparation_version=PREPARATION_VERSION, owner_id=owner,
        database=snapshot.database_fingerprint, policy_revision=revision, spec_digest=digest(spec.model_dump(mode='json')),
        model=MODEL, configuration_hash=CONFIG_HASH, storage_configuration=STORAGE_CONFIG,
        projection_coverage=projection_coverage(db, owner), source_permissions=source_permissions(db, owner),
        selection='local-keyword-draft-context', automatic_retrieval_evaluated=False,
        state='coverage_gaps' if any(c['gaps'] for c in cases) or unresolved else 'needs_owner_review',
        cases=cases, question_count=6, excerpt_count=sum(len(c['selected']) for c in cases),
        prepared_answer_cases=prepared, unresolved_acceptance_categories=unresolved,
        answer_call_limit=len(prepared), answer_max_micro_usd=len(prepared)*10000,
        estimated_max_micro_usd=sum(c['estimated_max_micro_usd'] for c in cases if c['id'] in prepared),
        budget=budget, approved=False, provider_calls=0, indexing_activated=False, validation_runs=0)
    protocol['digest'] = digest(protocol)
    return protocol, review


def review_html(protocol, review):
    sections = []
    by_id = {c['id']: c for c in protocol['cases']}
    count_fields = ['local_matching_records', 'ai_allowed_matching_records', 'record_denied_records',
        'source_denied_records', 'type_excluded_records', 'matched_records', 'allowed_records',
        'ready_records', 'observed_records', 'matching_records']
    for case in review:
        paragraphs = ''.join(f'<h3>{escape(p["source"])} · Entry {p["entry_id"]} · Version {p["version_id"]}</h3>'
            f'<pre>{escape(p["text"])}</pre>' for p in case['passages'])
        checks = ''.join(f'<li>{escape(x)}</li>' for x in case['checklist'])
        unknowns = ''.join(f'<li>{escape(x)}</li>' for x in case.get('unconfirmed_aspects', []))
        partial = ('<p>Partial answer: cite every recovered fact, explicitly bound the following unknowns to '
            'the selected evidence, and do not infer final choice, actual use or personal motivation.</p>'
            f'<ul>{unknowns}</ul>') if case['expected_outcome'] == 'partial' else ''
        counts = ''.join(f'<li>{key}: {by_id[case["id"]]["coverage"][key]}</li>'
            for key in count_fields if key in by_id[case['id']]['coverage'])
        deferred = f'<p>Deferred: {escape(case["deferred_reason"])}</p>' if case.get('deferred_reason') else ''
        category = '<p>The positive fact-recall requirement for this category remains unverified.</p>' if by_id[case['id']].get('positive_category_unverified') else ''
        sections.append(f'<section><h2>{escape(case["id"])}: {escape(case["question"])}</h2>'
            f'<p>Provisional expectation: {escape(case["expected_outcome"])}; owner review required.</p>'
            f'{deferred}{category}{partial}<p>Coverage gaps: {escape(", ".join(case["gaps"]) or "none detected")}</p><ul>{counts}</ul><ul>{checks}</ul>{paragraphs}</section>')
    inventory = ''.join(f'<li>{escape(row["source"])} · {escape(row["type"])} · '
        f'record allowed: {row["record_allowed"]} · source allowed: {row["source_allowed"]} · '
        f'{row["records"]} records</li>' for row in protocol.get('source_permissions', []))
    projections = ', '.join(f'{key}: {value}' for key, value in protocol.get('projection_coverage', {}).items())
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Phase 3.3 local evidence review</title><style>body{max-width:960px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui}'
        'section{border-top:1px solid #ccc;margin-top:32px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f8;padding:20px}</style>'
        '<h1>Phase 3.3 local evidence review</h1><p>No provider request, indexing activation or permission change.</p>'
        '<p>This is a local keyword draft. It does not measure automatic Semantic retrieval, prove expected answers, '
        'or authorize a paid run. Review evidence relevance and every provisional expectation, including missing-proof.</p>'
        f'<h2>Local coverage</h2><p>{escape(projections)}</p><ul>{inventory}</ul>'
        '<p>Inventory covers this owner only. Record/source denial counts can overlap; do not add them. '
        'A ready projection does not grant external AI permission. No excluded source body is shown.</p>'
        f'<p>{protocol["question_count"]} questions · {protocol["excerpt_count"]} excerpts · '
        f'{protocol["answer_call_limit"]} prepared answer candidates; deferred/blocked cases are excluded. '
        f'Future answer-only ceiling USD {protocol["answer_max_micro_usd"]/1000000:.2f}; indexing/query embeddings excluded.</p>'
        f'<p>Unresolved acceptance categories: {escape(", ".join(protocol["unresolved_acceptance_categories"]) or "none detected; evidence still needs owner review")}</p>'
        f'<p>State: {escape(protocol["state"])} · Digest: {protocol["digest"]}</p>' + ''.join(sections) + '</html>').encode()
