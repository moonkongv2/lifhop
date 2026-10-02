import { Link } from "react-router";
import useEntrySearch from "../hooks/useEntrySearch";
import { entryTarget, hasSearchConditions, listTarget } from "../utils/entryNavigation";
import type { EntryListContext } from "../utils/entryNavigation";
import { sourceLabels } from "../utils/entries";
import Icon from "./Icon";

export default function RecordSidebar({ selectedId, context }: { selectedId: number; context: EntryListContext }) {
  const searching = context.pathname === "/search";
  const params = new URLSearchParams(context.search);
  const enabled = !searching || hasSearchConditions(params);
  const records = useEntrySearch(params, enabled);
  return <aside className="panel reader-sidebar" aria-label="Record navigation">
    <div className="panel-heading"><Icon name="archive" /><h3>Records</h3></div>
    <p className="help-text">{searching ? "Your current search" : "Recently added to your archive"}</p>
    {records.isLoading && enabled && records.validOffset && <p>Loading records...</p>}
    {!records.validOffset && <p className="help-text">Invalid page value. Return to the list to reset the page.</p>}
    {!enabled && <p className="help-text">Start a search to see matching records.</p>}
    {records.error && <><p className="help-text">Record navigation is unavailable.</p><button onClick={() => void records.refetch()}>Retry records</button></>}
    {enabled && records.validOffset && records.data?.items.length === 0 && <p className="help-text">No records in this view.</p>}
    {enabled && records.validOffset && records.data?.items.map(record => <Link key={record.id} className="sidebar-record" to={entryTarget(record.id, context)} aria-current={record.id === selectedId ? "page" : undefined}>
      <span>{record.title}</span><small>{sourceLabels[record.source ?? "unknown"]} · {record.id === selectedId ? "Reading now" : "Open record"}</small>
    </Link>)}
    <Link className="button-link" to={listTarget(context)}>{searching ? "Back to search results" : "Browse all entries"}</Link>
  </aside>;
}
