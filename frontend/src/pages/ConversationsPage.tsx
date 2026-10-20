import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { fetchConversations } from "../api/answerConversations";
import { useAccessToken } from "../utils/session";

export default function ConversationsPage() {
  const token = useAccessToken();
  const [cursor, setCursor] = useState<string>();
  const query = useQuery({ queryKey: ["conversations", token, cursor], queryFn: ({ signal }) => fetchConversations(cursor, signal), enabled: !!token, retry: false, gcTime: 0 });
  return <><header className="page-header"><div><h2>Saved conversations</h2><p>Conversations remain until you delete them. Opening a conversation makes no AI request.</p></div><Link to="/search">Start a question</Link></header>
    {query.isLoading && <p role="status">Loading conversations...</p>}
    {query.error && <p role="alert">{query.error.message}</p>}
    {!query.isFetching && !query.error && query.data && <section className="panel">
      {!query.data.items.length && <p>No saved conversations yet.</p>}
      <ul>{query.data.items.map(c => <li key={c.id}><Link to={`/conversations/${c.id}`}>{c.title}</Link> · {c.state} · {new Date(c.updated_at).toLocaleString()}</li>)}</ul>
      {cursor && <button onClick={() => setCursor(undefined)}>Newest conversations</button>}
      {query.data.next_cursor && <button onClick={() => setCursor(query.data!.next_cursor!)}>Older conversations</button>}
    </section>}
  </>;
}
