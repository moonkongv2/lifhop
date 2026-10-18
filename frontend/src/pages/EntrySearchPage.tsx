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
import HistoricalQuestion from "../components/HistoricalQuestion";
import SearchResults from "../components/SearchResults";
import PeriodRetrospective from "../components/PeriodRetrospective";

export default function EntrySearchPage() {
  const [rawParams, setParams] = useSearchParams();
  const token = useAccessToken();
  const [draftChanged, setDraftChanged] = useState(false);
  const params = listParams(rawParams, "/search");
  if (!token) return <Navigate to="/login" replace />;
  const active = params.get("mode") === "historical" ? Boolean(params.get("q") && params.get("as_of")) : params.get("mode") === "retrospective" ? Boolean(params.get("date_from") && params.get("date_to"))
    : ["passages", "semantic", "answer"].includes(params.get("mode") ?? "") ? Boolean(params.get("q")) : hasSearchConditions(params);
  let results = <section className="panel empty-state"><Icon name="search" /><h3>What would you like to find?</h3><p>Search titles and content, or use filters to narrow your archive.</p></section>;
  if (active) {
    const mode = params.get("mode");
    const key = `${token}-${params.toString()}`;
    if (draftChanged) {
      results = <p role="status">Review your updated question and filters before asking.</p>;
    } else if (mode === "search") results = <SearchResults key={key} params={params} />;
    else if (mode === "historical") results = <HistoricalQuestion key={key} params={params} />;
    else if (mode === "retrospective") results = <PeriodRetrospective key={key} params={params} />;
    else if (mode === "answer") results = <QuestionAnswer key={key} params={params} />;
    else if (mode === "semantic") results = <SemanticResults key={key} params={params} />;
    else if (mode === "passages") results = <PassageResults key={key} params={params} />;
    else results = <EntryResults searching />;
  }
  return <>
    <header className="page-header"><div><p className="eyebrow">Find your context</p><h2>Search</h2><p className="subtitle">Find a phrase, a decision, or a detail you want to return to.</p></div></header>
    <EntrySearchForm key={params.toString()} params={params} onDraftChange={() => setDraftChanged(true)} onApply={next => { setDraftChanged(false); setParams(hasSearchConditions(next) ? next : new URLSearchParams()); }} />
    {results}
  </>;
}
