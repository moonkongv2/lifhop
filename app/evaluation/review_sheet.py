"""Owner-only local passage preview; never used as an AI prompt or score report."""
from html import escape
import time

from app.evaluation.drafting import real_records, candidate_anchor
from app.evaluation.evidence import check_anchor, passage
from app.evaluation.retrieval import check_binding
from app.evaluation.schemas import EvaluationError


def answer_candidates(snapshot,case):
    """Use the same bounded keyword/source scope as the local preview."""
    anchors=[a for g in case.evidence_groups for a in g.anchors]
    seen={a.entry_id for a in anchors}
    alternatives=[]
    for query in case.keyword_queries:
        for row in real_records(snapshot,filters=case.filters,query=query,limit=5):
            if row["id"] in seen or len(alternatives)>=5:
                continue
            seen.add(row["id"])
            try:
                alternatives.append(candidate_anchor(snapshot,row,query))
            except EvaluationError:
                continue
    return anchors+alternatives


def render_review_sheet(snapshot, dataset, *, seconds=60, include_alternatives=True):
    check_binding(snapshot,dataset)
    deadline=time.monotonic()+seconds
    sections=[]
    stats=dict(cases=len(dataset.cases),saved_spans=0,alternative_spans=0,unavailable_spans=0)

    def render_anchor(anchor,label):
        if time.monotonic()>=deadline:
            raise EvaluationError("REVIEW_SHEET_BUDGET")
        checked=check_anchor(snapshot.db,snapshot.owner_id,anchor)
        if checked["status"]!="valid":
            stats["unavailable_spans"]+=1
            return f'<p>{escape(label)}: {escape(checked["status"])} — no passage displayed.</p>'
        _,value=passage(snapshot.db,snapshot.owner_id,anchor.entry_id,anchor.version_id,
            anchor.field,anchor.start,anchor.end)
        return (f'<details><summary>{escape(label)} · Entry {anchor.entry_id} / version {anchor.version_id}</summary>'
            f'<p>{anchor.field} [{anchor.start}:{anchor.end}], {anchor.selection}; '
            f'external AI eligible: {str(checked["external_ai_eligible"]).lower()}</p>'
            f'<pre>{escape(value)}</pre><a href="http://localhost:5173/entries/{anchor.entry_id}" '
            'target="_blank" rel="noopener noreferrer">Open original record</a></details>')

    for case in dataset.cases:
        if time.monotonic()>=deadline:
            raise EvaluationError("REVIEW_SHEET_BUDGET")
        saved=[a for group in case.evidence_groups for a in group.anchors]
        previews=[render_anchor(a,"Saved candidate") for a in saved]
        stats["saved_spans"]+=len(saved)
        # Search each frozen auxiliary independently. Alternatives never replace gold.
        seen={a.entry_id for a in saved}
        alternatives=[]
        if case.status=="draft" and include_alternatives:
            for query in case.keyword_queries:
                for row in real_records(snapshot,filters=case.filters,query=query,limit=5):
                    if row["id"] in seen or len(alternatives)>=5:
                        continue
                    seen.add(row["id"])
                    try:
                        anchor=candidate_anchor(snapshot,row,query)
                        alternatives.append(render_anchor(anchor,"Alternative keyword match"))
                    except EvaluationError as error:
                        if str(error)=="REVIEW_SHEET_BUDGET":
                            raise
                        stats["unavailable_spans"]+=1
        stats["alternative_spans"]+=len(alternatives)
        claims="".join(f'<li>{escape(c.statement)}</li>' for c in case.claims)
        sections.append(f'<section id="{escape(case.id)}"><h2>{escape(case.id)} · {escape(case.question)}</h2>'
            f'<p>Status: {escape(case.status)}; proposed outcome: {escape(case.expected_outcome)}</p>'
            f'<p>{escape(case.review_notes)}</p><h3>Proposed facts</h3><ul>{claims}</ul>'
            '<p>Which displayed sentence actually answers the question? A file path, repeated question or proposed option '
            'alone is insufficient. Verify each fact and distinguish a proposal from an adopted decision.</p>'
            '<h3>Saved evidence</h3>'+(''.join(previews) or '<p>No saved evidence.</p>')+
            '<h3>Other records to inspect</h3>'+(''.join(alternatives) or '<p>No additional keyword matches displayed.</p>')+
            '<p>Alternatives are unapproved. Their absence does not prove a collection gap. '
            'Search is bounded to five matches per keyword and five distinct alternatives per draft case, '
            'using the saved case filters. Record any further review scope explicitly.</p></section>')
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Private evidence review</title><style>body{font:16px system-ui;max-width:1000px;margin:32px auto;padding:0 16px;color:#273449}section{border:1px solid #ddd;border-radius:12px;padding:20px;margin:24px 0;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 monospace;background:#f4f6fa;padding:16px}summary{cursor:pointer;padding:12px}details{margin:12px 0;border:1px solid #ddd;padding:8px}a{color:#355ab2}</style></head><body>
<h1>Private evidence review</h1><p>This local file contains personal source passages. Do not upload it to AI tools or commit it. No source text was sent to a model; no database records, policies or approvals were changed.</p>
<p>Each excerpt is pinned to a version and character range. Original links show the app's current record, which may differ. Re-export after edits/deletions; this immutable local snapshot can retain old passages.</p>'''+f'<p>Dataset revision: {dataset.revision}. Keyword matches are candidates, not verified answers.</p>'+''.join(sections)+'</body></html>'
    return html.encode(),stats
