import { Link, Navigate, useSearchParams } from "react-router";
import Icon from "../components/Icon";
import ArchiveResults from "../components/ArchiveResults";
import { entryTarget, hasLegacyFilters, listContext, listTarget } from "../utils/entryNavigation";

export default function EntryListPage() {
  const [params] = useSearchParams();
  if (!localStorage.getItem("access_token")) return <Navigate to="/login" replace />;
  if (hasLegacyFilters(params)) return <Navigate to={listTarget(listContext("/search", params))} replace />;
  const context = listContext("/entries", params);
  return <>
    <header className="page-header">
      <div><p className="eyebrow">Your archive</p><h2>Entries</h2><p className="subtitle">Your recent records, ready to revisit.</p></div>
      <Link className="button-link primary" to={entryTarget("new", context)}><Icon name="note" />New note</Link>
    </header>
    <ArchiveResults />
  </>;
}
