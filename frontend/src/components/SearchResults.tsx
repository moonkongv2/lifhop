import { useState } from "react";
import EntryResults from "./EntryResults";
import PassageResults from "./PassageResults";
import QuestionAnswer from "./QuestionAnswer";

export default function SearchResults({ params }: { params: URLSearchParams }) {
  const [ask, setAsk] = useState(false);
  const exact = params.get("exact") === "true";
  const question = Boolean(params.get("q"));
  return <>
    {question && !exact && <section className="search-answer-action" aria-label="Ask about these records">
      <button aria-expanded={ask} onClick={() => setAsk(!ask)}>{ask ? "Close answer request" : "Get an answer with sources"}</button>
      {ask && <QuestionAnswer params={params} productView />}
    </section>}
    {exact && <p className="help-text">Exact phrase search is local. Turn off Match exact phrase to request an AI answer.</p>}
    <h3>Matching records</h3>
    <p className="help-text">These results are found locally and can include records excluded from AI.</p>
    {exact || !question ? <EntryResults searching /> : <PassageResults params={params} showAnswerControls={false} productView />}
  </>;
}
