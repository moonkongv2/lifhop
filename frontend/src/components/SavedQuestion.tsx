import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { claimTurn, conversationStage, createConversation, runTurn, type Conversation } from "../api/answerConversations";
import { getAccessToken } from "../utils/session";

export default function SavedQuestion({ params, available }: { params: URLSearchParams; available: boolean }) {
  const navigate = useNavigate();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [savedId, setSavedId] = useState<string>();
  const active = useRef<Conversation | null>(null);
  const controller = useRef<AbortController | null>(null);
  const pending = useRef(false);
  const token = getAccessToken();
  const stop = async () => {
    controller.current?.abort();
    const c = active.current;
    if (c?.unfinished && getAccessToken() === token) await conversationStage(c.id, c.unfinished, "stop");
  };
  useEffect(() => () => {
    controller.current?.abort();
    const c = active.current;
    if (c?.unfinished && getAccessToken() === token) void conversationStage(c.id, c.unfinished, "stop").catch(() => {});
  }, [token]);
  const run = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    const control = new AbortController(); controller.current = control;
    const timer = window.setTimeout(() => { void stop().catch(() => {}); }, 120000);
    try {
      let c = await createConversation(params, control.signal);
      setSavedId(c.id);
      c = await claimTurn(c.id, { q: params.get("q") ?? "", request_id: crypto.randomUUID().replaceAll("-", ""), expected_revision: c.revision, context_mode: "continue", confirm_external_ai: true }, control.signal);
      active.current = c;
      const result = await runTurn(c, control.signal, value => { active.current = value; });
      if (getAccessToken() === token) navigate(`/conversations/${result.id}`);
    } catch (e) { if (getAccessToken() === token) setError((e as Error).message); }
    finally { window.clearTimeout(timer); pending.current = false; if (getAccessToken() === token) { setBusy(false); setConsent(false); } }
  };
  return <section className="panel"><h3>Ask in a saved conversation</h3>
    <p>{params.get("q")}</p>
    <p className="help-text">Your question and answer are saved until you delete the conversation, including after logout. OpenAI receives this question and up to five allowed original passages. At most two AI calls, reservation up to USD 0.008745.</p>
    <label><input type="checkbox" checked={consent} disabled={!available || busy} onChange={e => setConsent(e.target.checked)} />Allow this question and selected originals to be sent to OpenAI and save this conversation</label>
    <div className="actions"><button className="primary" disabled={!available || !consent || busy} onClick={() => void run()}>Ask from my records</button>{busy && <button onClick={() => void stop().catch(e => setError(e.message))}>Stop</button>}</div>
    {busy && <p role="status">Finding records and saving your answer...</p>}
    {error && <p role="alert">{error}</p>}
    {savedId && <Link to={`/conversations/${savedId}`}>Open saved conversation and execution state</Link>}
  </section>;
}
