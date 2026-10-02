import { Navigate, useSearchParams } from "react-router";
import EntrySearchForm from "../components/EntrySearchForm";
import EntryResults from "../components/EntryResults";
import Icon from "../components/Icon";
import { hasSearchConditions, listParams } from "../utils/entryNavigation";

export default function EntrySearchPage() {
  const [rawParams, setParams] = useSearchParams();
  const params = listParams(rawParams, "/search");
  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  const active = hasSearchConditions(params);
  return <>
    <header className="page-header"><div><p className="eyebrow">Find your context</p><h2>Search</h2><p className="subtitle">Find a phrase, a decision, or a detail you want to return to.</p></div></header>
    <EntrySearchForm key={params.toString()} params={params} onApply={next => setParams(hasSearchConditions(next) ? next : new URLSearchParams())} />
    {active ? <EntryResults searching /> : <section className="panel empty-state"><Icon name="search" /><h3>What would you like to find?</h3><p>Search titles and content, or use filters to narrow your archive.</p></section>}
  </>;
}
