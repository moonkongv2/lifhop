"""Deterministic local candidate authoring; source text never goes to a model."""
from html import escape
import re

from sqlalchemy import select, func, Text

from app.evaluation.schemas import Case, EvaluationError, dataset_from, now
from app.evaluation.evidence import make_anchor, MAX_FIELD_BYTES
from app.evaluation.retrieval import check_binding
from app.models.entry import Entry, EntrySource
from app.models.history import EntryVersion
from app.services.entry_search import search_components

SEEDS = (
    "우리가 이전에 진행했던 모터 RPM 제어 최적화 문제에서 제어 주기 설정을 어떤 기준으로 했었지?",
    "2026년 4월 오키나와 여행 시 이용했던 렌터카 업체와 선정 이유?",
)


def real_records(snapshot, *, provider=None, kind=None, query="", oldest=False, limit=20, filters=None):
    options=filters.model_dump() if filters else {}
    if provider:
        options["source"]=EntrySource(provider)
    conditions, order, _, _ = search_components(user_id=snapshot.owner_id,q=query,**options)
    conditions.append(~Entry.title.startswith("[Synthetic]",autoescape=True))
    if kind:
        conditions.append(EntryVersion.payload["kind"].astext==kind)
    if oldest:
        order=[Entry.event_at.asc().nulls_last(),Entry.id.asc()]
    elif not query:
        order=[Entry.event_at.desc().nulls_last(),Entry.id.desc()]
    return snapshot.db.execute(select(Entry.id,Entry.current_version_id,Entry.provider,Entry.event_at,Entry.source_scope,
        EntryVersion.payload["sha"].astext.label("sha"),EntryVersion.payload["path"].astext.label("path"))
        .join(EntryVersion,(EntryVersion.id==Entry.current_version_id)&(EntryVersion.entry_id==Entry.id))
        .where(*conditions).order_by(*order).limit(limit)).mappings().all()


def candidate_anchor(snapshot,row,query=""):
    metadata=snapshot.db.execute(select(EntryVersion.content,EntryVersion.payload)
        .join(Entry,Entry.id==EntryVersion.entry_id).where(Entry.user_id==snapshot.owner_id,
            Entry.id==row["id"],EntryVersion.id==row["current_version_id"],
            func.octet_length(EntryVersion.content)<=MAX_FIELD_BYTES,
            func.coalesce(func.octet_length(EntryVersion.payload.cast(Text)),0)<=MAX_FIELD_BYTES)).first()
    if not metadata or not metadata.content:
        raise EvaluationError("CANDIDATE_FIELD_UNAVAILABLE")
    content,payload=metadata.content,metadata.payload or {}
    preferred=payload.get("message") or payload.get("content") or ""
    if row["provider"]=="codex":
        messages=[m for m in payload.get("messages",[]) if m.get("role")=="assistant" and
            payload.get("message_phases",{}).get(m.get("message_id"))!="commentary"]
        preferred=messages[-1].get("content","") if messages else ""
    prefix=preferred[:1500].strip()
    start=content.find(prefix) if prefix else -1
    if start>=0:
        end=start+len(prefix)
    else:
        match=content.lower().find(query.lower()) if query else -1
        boundary=content.rfind("\n\n",0,match) if match>=0 else -1
        start=boundary+2 if boundary>=0 else 0
        end=min(len(content),start+1500)
    return make_anchor(snapshot.db,owner_id=snapshot.owner_id,entry_id=row["id"],
        version_id=row["current_version_id"],field="content",start=start,end=end)


def draft_candidates(snapshot,dataset):
    check_binding(snapshot,dataset)
    if dataset.revision!=1 or len(dataset.cases)!=20 or any(c.status!="draft" or
        c.claims or c.evidence_groups or c.question not in {"",*SEEDS} for c in dataset.cases):
        raise EvaluationError("DRAFT_ALREADY_AUTHORED")
    totals=dict(snapshot.db.execute(select(Entry.provider,func.count()).where(Entry.user_id==snapshot.owner_id,
        ~Entry.title.startswith("[Synthetic]",autoescape=True)).group_by(Entry.provider)).all())
    commits=real_records(snapshot,provider="github",kind="github_commit",limit=1000)
    docs=real_records(snapshot,provider="github",kind="github_document")
    chronological_docs=real_records(snapshot,provider="github",kind="github_document",oldest=True,limit=1000)
    oldest=real_records(snapshot,provider="github",kind="github_commit",oldest=True,limit=1)
    # Only explicit commit-SHA overlap is proposed as cross-source evidence.
    codex_rows=real_records(snapshot,provider="codex",limit=100)
    overlaps=[]
    for row in codex_rows:
        text=snapshot.db.scalar(select(Entry.primary_content).where(Entry.user_id==snapshot.owner_id,
            Entry.id==row["id"],func.octet_length(Entry.primary_content)<=MAX_FIELD_BYTES)) or ""
        tokens=set(re.findall(r"(?<![a-f0-9])[a-f0-9]{7,40}(?![a-f0-9])",text))
        for commit in commits:
            if commit["sha"] and any(commit["sha"].startswith(token) for token in tokens):
                overlaps.append([row,commit])
                break
    specs=[
        (SEEDS[0],None,["RPM","제어 주기"],["decision","coverage_gap"]),
        (SEEDS[1],None,["오키나와","렌터카"],["life","coverage_gap"]),
        ("새 노트의 저장 위치와 PostgreSQL·S3의 역할은 어떻게 설명됐나?","codex",["PostgreSQL","S3"],["decision"]),
        ("import_worker를 실행하는 이유와 실행 위치는 무엇인가?","codex",["import_worker","워커"],["decision"]),
        ("500MB ChatGPT ZIP을 처리하기 위해 어떤 제한과 검증을 검토했나?","codex",["500MB","ZIP"],["decision"]),
        ("Codex 기록에서 reasoning·command 결과와 최종 답변의 표시를 어떻게 검토했나?","codex",["reasoning","최종 답변"],["decision"]),
        ("What change does the latest retained GitHub commit record?","github",[],["decision","ai_excluded"]),
        ("가장 오래된 GitHub 커밋에는 어떤 변경이 기록되어 있나?","github",[],["history"]),
        ("수집된 README에는 프로젝트에 관해 어떤 내용이 기록되어 있나?","github",["README"],["decision"]),
        ("What does the latest retained document snapshot describe?","github",[],["decision"]),
        ("같은 문서의 두 시점 스냅샷에는 각각 어떤 내용이 기록되어 있나?","github",[],["history","changed_decision"]),
        ("What message and change evidence does the selected GitHub commit contain?","github",[],["decision","ai_excluded"]),
        ("Codex에 언급된 커밋과 GitHub 커밋 기록을 연결해 확인할 수 있나?",None,[],["cross_source"]),
        ("Codex에 언급된 다른 커밋도 GitHub 기록에서 확인할 수 있나?",None,[],["cross_source"]),
        ("두 출처에 공통으로 기록된 커밋의 설명은 서로 어떤 맥락을 제공하나?",None,[],["cross_source"]),
        ("여행 숙소를 선택할 때 실제로 채택한 기준은 무엇이었나?",None,["숙소"],["life","coverage_gap"]),
        ("여행 중 이용한 교통수단과 선택 이유는 무엇이었나?",None,["교통수단"],["life","coverage_gap"]),
        ("여행에서 실제 지출한 주차요금의 근거 기록은 무엇인가?",None,["주차요금"],["life","coverage_gap"]),
        ("검색 화면 분리와 로그인 상태 표시를 어떻게 검토했나?","codex",["Search","login"],["decision"]),
        ("선택한 GitHub 저장소의 실제 PR·이슈 토론에서 어떤 결정이 기록됐나?","github",[],["coverage_gap"]),
    ]
    authored=[]
    stats=dict(real_records=sum(totals.values()),providers={p or "unknown":n for p,n in totals.items()},
        excluded_synthetic=snapshot.db.scalar(select(func.count()).select_from(Entry).where(
            Entry.user_id==snapshot.owner_id,Entry.title.startswith("[Synthetic]",autoescape=True))),
        cross_source_sha_candidates=len(overlaps),supported_candidates=0,coverage_gap_candidates=0)
    for index,(question,provider,queries,tags) in enumerate(specs):
        selected=[]
        if index==6: selected=commits[:1]
        elif index==7: selected=oldest
        elif index==9: selected=docs[:1]
        elif index==10:
            for row in docs:
                same=[r for r in chronological_docs
                      if r["path"]==row["path"] and r["source_scope"]==row["source_scope"]]
                if len(same)>=2:
                    selected=[same[0],same[-1]]
                    break
        elif index==11: selected=commits[1:2]
        elif index in (12,13,14): selected=overlaps[index-12] if len(overlaps)>index-12 else []
        elif index==19:
            selected=real_records(snapshot,provider="github",kind="github_pull_request",limit=1) or real_records(snapshot,provider="github",kind="github_issue",limit=1)
        else:
            for query in queries:
                selected=real_records(snapshot,provider=provider,query=query,kind="github_document" if index==8 else None,limit=1)
                if selected:
                    break
        groups=[]
        for n,row in enumerate(selected):
            try:
                anchor=candidate_anchor(snapshot,row,queries[0] if queries else "")
                groups.append(dict(id=f"evidence-{n+1}",anchors=[anchor.model_dump(mode="json")]))
            except EvaluationError:
                pass
        if index in (10,12,13,14) and len(groups)!=len(selected):
            groups=[]
        keywords=queries[:3] if queries else list(dict.fromkeys(row["sha"][:12] for row in selected if row["sha"]))[:3]
        if any(row["provider"]=="github" and row["path"] for row in selected):
            keywords=list(dict.fromkeys(keywords+[row["path"] for row in selected if row["path"] and len(row["path"])<=256]))[:3]
        outcome="supported" if groups else "coverage_gap"
        authored.append(Case(id=dataset.cases[index].id,question=question,
            language="en" if index in (6,9,11) else "ko",
            tags=tags,expected_outcome=outcome,keyword_queries=keywords,
            filters=dict(source=provider) if provider else {},
            claims=[dict(id="claim-01",statement="[Candidate] Replace this with a fact verified in the linked original records.",
                required_group_ids=[g["id"] for g in groups])] if groups else [],evidence_groups=groups,
            review_scope="Selected owner's retained non-synthetic current Entries; default Codex primary search. Cross-source candidates inspect up to 100 Codex turns and 1000 commits; document history up to 1000 snapshots. No other account or external source was read.",
            review_notes="Local rules connected candidate spans; their relevance and the factual answer need owner review." if groups else
                "No candidate support was connected within this retained scope. This is a collection/evidence gap, not proof of universal absence."))
        stats["supported_candidates" if groups else "coverage_gap_candidates"]+=1
    value=dataset.model_dump(mode="json",exclude={"digest"})
    value.update(revision=2,parent_digest=dataset.digest,created_at=now(),cases=[c.model_dump(mode="json") for c in authored])
    return dataset_from(value),stats


def candidate_sheet(dataset,stats) -> bytes:
    rows=[]
    for case in dataset.cases:
        anchors=[a for g in case.evidence_groups for a in g.anchors]
        links=" ".join(f'<a href="http://localhost:5173/entries/{a.entry_id}" target="_blank" rel="noopener noreferrer">Entry {a.entry_id}</a> (version {a.version_id}, {a.field} [{a.start}:{a.end}])' for a in anchors)
        rows.append(f'<tr><td>{escape(case.id)}</td><td>{escape(case.question)}</td><td>{escape(case.expected_outcome)}</td><td>{links or "No candidate evidence"}</td></tr>')
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Private evaluation candidates</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 16px;color:#273449}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:12px;text-align:left}a{display:inline-block;margin:4px}</style></head><body>
<h1>Private evaluation candidates — all draft</h1><p>Generated by local rules. No source text was sent to an AI model. Questions/spans are candidates; no factual answers or relevance have been approved.</p>
<p>Open a linked record in the local app as the dataset owner. A keyword match may only repeat the question or mention an option; it does not establish an answer or adopted decision. Check the cited version and character span, and edit the [Candidate] claim into a checked fact before reviewing. Gap cases describe this retained scope only.</p>'''+
        f'<p>{stats["supported_candidates"]} cases with candidate spans; {stats["coverage_gap_candidates"]} gaps; {stats["excluded_synthetic"]} synthetic records excluded.</p>'+
        '<table><thead><tr><th>Case</th><th>Question</th><th>Candidate outcome</th><th>Original records</th></tr></thead><tbody>'+"".join(rows)+
        '</tbody></table></body></html>').encode()
