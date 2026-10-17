import { Navigate, useSearchParams } from "react-router";
import { useState } from "react";
import EntrySearchForm from "../components/EntrySearchForm";
import EntryResults from "../components/EntryResults";
import Icon from "../components/Icon";
import PassageResults from "../components/PassageResults";
import SemanticResults from "../components/SemanticResults";
import { hasSearchConditions, listParams } from "../utils/entryNavigation";
import { useAccessToken } from "../utils/session";
import QuestionAnswer from "../components/QuestionAnswer";

export default function EntrySearchPage() {
  const [rawParams, setParams] = useSearchParams();
  const token = useAccessToken();
  const [draftChanged, setDraftChanged] = useState(false);
  const params = listParams(rawParams, "/search");
  if (!token) return <Navigate to="/login" replace />;
  const active = ["passages", "semantic", "answer"].includes(params.get("mode") ?? "") ? Boolean(params.get("q")) : hasSearchConditions(params);
  return <>
    <header className="page-header"><div><p className="eyebrow">Find your context</p><h2>Search</h2><p className="subtitle">Find a phrase, a decision, or a detail you want to return to.</p></div></header>
    <EntrySearchForm key={params.toString()} params={params} onDraftChange={() => { if (params.get("mode") === "answer") setDraftChanged(true); }} onApply={next => { setDraftChanged(false); setParams(hasSearchConditions(next) ? next : new URLSearchParams()); }} />
    {active ? params.get("mode") === "answer" ? draftChanged ? <p role="status">Review your updated question and filters before asking.</p> : <QuestionAnswer key={`question-${token}-${params.toString()}`} params={params} /> : params.get("mode") === "semantic" ? <SemanticResults key={`results-${token}-${params.toString()}`} params={params} /> : params.get("mode") === "passages" ? <PassageResults key={`results-${token}-${params.toString()}`} params={params} /> : <EntryResults searching /> : <section className="panel empty-state"><Icon name="search" /><h3>What would you like to find?</h3><p>Search titles and content, or use filters to narrow your archive.</p></section>}
  </>;
}
