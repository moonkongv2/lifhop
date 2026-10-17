import { fetchAnswerStatus, recommendPassages, requestAnswer } from "./answers";
import { searchSemantic } from "./semantic";
import { assertCurrentSession, getAccessToken } from "../utils/session";

export type QuestionStage = "search" | "evidence" | "answer";

export async function askFromRecords(params: URLSearchParams, revision: number, signal: AbortSignal,
  progress: (stage: QuestionStage) => void) {
  const frozen = new URLSearchParams(params);
  const token = getAccessToken();
  if (!token) throw new Error("Please log in to continue.");
  const requestId = crypto.randomUUID().replaceAll("-", "");
  const check = () => { signal.throwIfAborted(); assertCurrentSession(token); };
  const unchanged = (value: number) => {
    check();
    if (value !== revision) throw new Error("Records or permissions changed. Review the question again. A completed request may have been charged.");
  };
  check();
  const status = await fetchAnswerStatus(signal);
  unchanged(status.policy_revision);
  if (!status.enabled) throw new Error("Answer generation is disabled. No question was sent.");
  progress("search");
  const search = await searchSemantic(frozen, signal, requestId);
  unchanged(search.coverage.policy_revision);
  if (search.coverage.state !== "available") throw new Error("No searchable index is available for these filters. No answer was requested.");
  if (!search.items.length) return { answer: null, proposal: null, search };
  progress("evidence");
  const proposal = await recommendPassages(frozen, search.items.map(h => h.embedding_id), revision, signal);
  unchanged(proposal.policy_revision);
  if (!proposal.passages.length) return { answer: null, proposal, search };
  progress("answer");
  // Reuse one action ID in the separate query/answer ledger domains. Each has
  // its own durable one-call cap; a reload or failed stage never retries either.
  check();
  const answer = await requestAnswer(frozen.get("q") ?? "", proposal.passages.map(p => p.id), "passage",
    { signal, requestId, revision });
  unchanged(answer.policy_revision);
  return { answer, proposal, search };
}
