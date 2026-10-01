import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, useSearchParams } from "react-router";
import { fetchEntrySearch } from "../api/entries";
import { formatEntryDate, sourceLabels } from "../utils/entries";

function SearchForm({ params, onApply }: { params: URLSearchParams; onApply: (params: URLSearchParams) => void }) {
  const [q, setQ] = useState(params.get("q") ?? "");
  const [source, setSource] = useState(params.get("source") ?? "");
  const [type, setType] = useState(params.get("type") ?? "");
  const [dateField, setDateField] = useState(params.get("date_field") ?? "created_at");
  const [from, setFrom] = useState(params.get("date_from") ?? "");
  const [to, setTo] = useState(params.get("date_to") ?? "");
  const [validation, setValidation] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (from && to && from > to) { setValidation("시작일은 종료일보다 늦을 수 없어."); return; }
    setValidation("");
    const next = new URLSearchParams();
    for (const [key, value] of Object.entries({ q: q.trim(), source, type, date_field: dateField, date_from: from, date_to: to })) {
      if (value && !(key === "date_field" && value === "created_at")) next.set(key, value);
    }
    onApply(next);
  }

  return (
    <form onSubmit={submit}>
      <label htmlFor="search-q">검색어</label>
      <input id="search-q" value={q} maxLength={256} onChange={(event) => setQ(event.target.value)} placeholder="제목·본문의 문구, 이름, 숫자, 코드" />
      <div className="search-filters">
        <label>출처<select value={source} onChange={(event) => setSource(event.target.value)}>
          <option value="">전체 출처</option>
          {Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label>유형<select value={type} onChange={(event) => setType(event.target.value)}>
          <option value="">전체 유형</option><option value="NOTE">노트</option><option value="LOG">로그</option>
          <option value="DOCUMENT">문서</option><option value="CONVERSATION">대화</option><option value="PROJECT_EVENT">프로젝트 기록</option>
        </select></label>
        <label>날짜 기준<select value={dateField} onChange={(event) => setDateField(event.target.value)}>
          <option value="created_at">등록일</option><option value="event_at">원본/사건 날짜</option>
        </select></label>
        <label>시작일<input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>종료일<input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
      </div>
      <p>날짜 범위는 Asia/Seoul 기준이며 종료일을 포함해. 원본/사건 날짜가 없는 기록은 해당 날짜 필터에서 제외돼.</p>
      <div className="actions"><button type="submit">검색</button><button type="button" onClick={() => onApply(new URLSearchParams())}>초기화</button></div>
      {validation && <p role="alert">{validation}</p>}
    </form>
  );
}

function EntryListPage() {
  const [params, setParams] = useSearchParams();
  const serialized = params.toString();
  const offset = Number(params.get("offset") ?? 0);
  const validOffset = Number.isSafeInteger(offset) && offset >= 0;
  const token = localStorage.getItem("access_token");
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["entries", serialized],
    queryFn: ({ signal }) => fetchEntrySearch(params, signal),
    enabled: Boolean(token && validOffset),
  });
  useEffect(() => {
    if (data && offset > 0 && offset >= data.total) {
      const next = new URLSearchParams(serialized);
      const last = Math.max(0, Math.ceil(data.total / 20) - 1) * 20;
      if (last === 0) next.delete("offset"); else next.set("offset", String(last));
      setParams(next, { replace: true });
    }
  }, [data, offset, serialized, setParams]);

  function page(nextOffset: number) {
    const next = new URLSearchParams(params);
    if (nextOffset === 0) next.delete("offset"); else next.set("offset", String(nextOffset));
    setParams(next);
  }
  if (!token) return <Navigate to="/login" replace />;
  const filtered = ["q", "source", "type", "date_from", "date_to"].some((key) => params.get(key));
  return (
    <>
      <h2>Entries</h2>
      <Link to="/entries/new" state={{ entryListSearch: serialized }}>새 노트 작성</Link>
      <SearchForm key={serialized} params={params} onApply={setParams} />
      {!validOffset && <p role="alert">페이지 값이 올바르지 않아. 초기화해 줘.</p>}
      {isLoading && <p role="status">불러오는 중...</p>}
      {error && <><p role="alert">{error.message}</p><button onClick={() => void refetch()}>다시 시도</button></>}
      {data && <>
        <p>총 {data.total}개 · {Math.floor(offset / 20) + 1}페이지</p>
        {data.items.length === 0 && <p>{filtered ? "검색 조건에 맞는 기록이 없어." : "저장된 Entry가 없어."}</p>}
        {data.items.map((entry) => <article key={entry.id}>
          <Link to={`/entries/${entry.id}`} state={{ entryListSearch: serialized }}><h3>{entry.title}</h3></Link>
          <p>{sourceLabels[entry.source ?? "unknown"]} · {entry.type}</p>
          <p>등록일: {formatEntryDate(entry.created_at)} · 원본/사건 날짜: {formatEntryDate(entry.event_at)} (Asia/Seoul)</p>
          <p className="entry-content">{entry.content ?? "내용 없음"}</p>
        </article>)}
        <div className="actions">
          <button disabled={isFetching || offset === 0} onClick={() => page(Math.max(0, offset - 20))}>이전 페이지</button>
          <button disabled={isFetching || offset + 20 >= data.total} onClick={() => page(offset + 20)}>다음 페이지</button>
        </div>
      </>}
    </>
  );
}

export default EntryListPage;
