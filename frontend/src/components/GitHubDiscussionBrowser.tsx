import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { historyRequest } from "../api/history";
import { fetchEntry } from "../api/entries";
import { repositoryRecordsUrl, repositoryTarget, githubEntryTarget } from "../utils/githubRepositories";
import type { RepositoryContext, Discussions, DiscussionThread } from "../utils/githubRepositories";
import { formatEntryDate } from "../utils/entries";
import DateInput from "./DateInput";
import GitHubReader from "./GitHubReader";
import GitHubRecordStatus from "./GitHubRecordStatus";
import { validDate } from "../utils/dates";

function DiscussionEvidence({id}: {id:number}) {
  const entry = useQuery({queryKey:["entry",String(id)],queryFn:()=>fetchEntry(String(id))});
  if (entry.isLoading) return <p role="status">Loading record...</p>;
  if (entry.error) return <><p role="alert">{entry.error.message}</p><button onClick={()=>void entry.refetch()}>Retry record</button></>;
  return entry.data ? <GitHubReader entry={entry.data} /> : null;
}

function DiscussionFilters({context,change}: {context:RepositoryContext; change:(next:RepositoryContext)=>void}) {
  const [kind,setKind] = useState(context.discussion_kind ?? "");
  const [state,setState] = useState(context.discussion_state ?? "");
  const [from,setFrom] = useState(context.discussion_from ?? "");
  const [to,setTo] = useState(context.discussion_to ?? "");
  const [unknown,setUnknown] = useState(context.unknown_date ?? false);
  const invalid = !!((from && !validDate(from)) || (to && (!validDate(to) || to === "9999-12-31")) || (from && to && from > to));
  return <form className="discussion-filters" onSubmit={event=>{event.preventDefault(); if (!invalid || unknown) change({...context,
    discussion_kind:kind as RepositoryContext["discussion_kind"] || undefined, discussion_state:state as RepositoryContext["discussion_state"] || undefined,
    discussion_from:unknown ? undefined : from || undefined, discussion_to:unknown ? undefined : to || undefined,
    unknown_date:unknown, discussion_offset:0});}}>
    <label>Kind<select value={kind} onChange={event=>setKind(event.target.value)}><option value="">All discussions</option><option value="pull_request">Pull requests</option><option value="issue">Issues</option></select></label>
    <label>State<select value={state} onChange={event=>setState(event.target.value)}><option value="">All states</option>{["open","closed","merged","unknown"].map(value=><option key={value} value={value}>{value[0].toUpperCase()+value.slice(1)}</option>)}</select></label>
    {!unknown && <><div><label htmlFor="discussion-from">Start date</label><DateInput id="discussion-from" label="Start date" value={from} onChange={setFrom} /></div>
      <div><label htmlFor="discussion-to">End date</label><DateInput id="discussion-to" label="End date" value={to} onChange={setTo} /></div></>}
    <label><input type="checkbox" checked={unknown} onChange={event=>setUnknown(event.target.checked)} />Unknown date</label>
    {invalid && !unknown && <p role="alert">Enter valid dates with the start on or before the end.</p>}
    <button disabled={invalid && !unknown}>Apply filters</button>
  </form>;
}

export default function GitHubDiscussionBrowser({context,change}: {context:RepositoryContext; change:(next:RepositoryContext)=>void}) {
  const thread = !!context.thread_id;
  const url = repositoryRecordsUrl(context);
  const query = useQuery({queryKey:["github-discussions",url],queryFn:()=>historyRequest<Discussions | DiscussionThread>(url)});
  const data = query.data;
  const offset = thread ? context.thread_offset ?? 0 : context.discussion_offset ?? 0;
  const serialized = repositoryTarget(context);
  useEffect(()=>{
    if (data && data.offset !== offset) {
      change({...context,thread_offset:data.offset,focus_entry_id:undefined});
    } else if (data && offset > 0 && offset >= data.total) {
      change({...context,[thread ? "thread_offset" : "discussion_offset"]:Math.max(0,Math.ceil(data.total/20)-1)*20,focus_entry_id:undefined});
    }
  },[data,offset,context,change,thread]);
  const [expanded,setExpanded] = useState<number | null>(context.focus_entry_id ?? null);
  useEffect(()=>{
    if (expanded && data) document.getElementById(`github-discussion-record-${expanded}`)?.scrollIntoView?.({block:"center"});
  },[expanded,data]);
  const discussion = data && "discussion" in data ? data.discussion : null;
  return <div className="discussion-browser">
    {!thread && <DiscussionFilters key={serialized} context={context} change={change} />}
    <p className="help-text">Dates describe the original records. Missing parents use the first retained comment date. Counts describe retained records.</p>
    {thread && <button onClick={()=>change({...context,thread_kind:undefined,thread_id:undefined,thread_offset:0,focus_entry_id:undefined})}>All discussions</button>}
    {query.isLoading && <p role="status">Loading discussions...</p>}
    {query.error && <><p role="alert">{query.error.message}</p><button onClick={()=>void query.refetch()}>Retry discussions</button></>}
    {discussion && <article className="discussion-root">
      <span className="badge">{discussion.parent_kind === "pull_request" ? "PR" : "Issue"} #{discussion.number} · {discussion.state}</span>
      <h3>{discussion.title}</h3><p className="record-date">{discussion.orphan ? "First retained comment date" : "Created"}: {formatEntryDate(discussion.event_at)}</p>
      {discussion.orphan ? <p>Parent not retained. The remaining records are independently preserved.</p> : discussion.root_entry_id && <>
        <Link to={githubEntryTarget(discussion.root_entry_id,context)}>Open parent record and history</Link>
        <DiscussionEvidence id={discussion.root_entry_id} />
      </>}
      {(discussion.partial || discussion.review_required) && <p className="help-text">Some evidence is partial or needs version review.</p>}
    </article>}
    {data && <>
      <div className="records-toolbar"><p>{data.total} {thread ? "comments and reviews" : "discussions"} · Page {Math.floor(data.offset/20)+1}</p><span>{thread ? "Oldest first" : "Newest first"}</span></div>
      {!data.items.length && <p>No retained {thread ? "comments or reviews" : "discussions"} in this view.</p>}
      <div className="repository-rows">{data.items.map(row=>{
        if ("parent_kind" in row) {
          return <article className="repository-row" key={`${row.parent_kind}:${row.parent_id}`}>
            <span className="badge">{row.parent_kind === "pull_request" ? "PR" : "Issue"} #{row.number} · {row.state}</span>
            <Link to={repositoryTarget({...context,thread_kind:row.parent_kind,thread_id:row.parent_id,thread_offset:0,focus_entry_id:undefined})}>{row.title}</Link>
            <p className="record-date">{row.orphan ? "First retained comment date" : "Created"}: {formatEntryDate(row.event_at)} · {row.child_count} comments and reviews</p>
            {row.orphan && <p>Parent not retained</p>}{row.partial && <span className="badge">Partial evidence</span>}{row.review_required && <span className="badge">Version review needed</span>}
          </article>;
        }
        const open = expanded === row.id || context.focus_entry_id === row.id;
        return <article id={`github-discussion-record-${row.id}`} className={`repository-row ${open ? "discussion-focus" : ""}`} key={row.id}>
          <span className="badge">{row.kind.replaceAll("_"," ")}</span><h4>{row.title}</h4>
          <p className="record-date">{formatEntryDate(row.event_at)}</p><GitHubRecordStatus record={row} />
          <div className="actions"><button onClick={()=>{setExpanded(open ? null : row.id); if (context.focus_entry_id) change({...context,focus_entry_id:undefined});}}>{open ? "Collapse record" : "Read record"}</button>
            <Link to={githubEntryTarget(row.id,{...context,thread_offset:data.offset,focus_entry_id:undefined})}>Open record and history</Link></div>
          {open && <DiscussionEvidence id={row.id} />}
        </article>;
      })}</div>
      <div className="actions pagination"><button disabled={query.isFetching || !data.offset} onClick={()=>change({...context,[thread ? "thread_offset" : "discussion_offset"]:Math.max(0,data.offset-20),focus_entry_id:undefined})}>Previous page</button>
        <button disabled={query.isFetching || data.offset+20>=data.total} onClick={()=>change({...context,[thread ? "thread_offset" : "discussion_offset"]:data.offset+20,focus_entry_id:undefined})}>Next page</button></div>
    </>}
  </div>;
}
