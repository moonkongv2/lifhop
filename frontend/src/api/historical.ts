import type { components } from './generated/schema';
import { assertCurrentSession, expireSession, sessionExpiredMessage } from '../utils/session';
export type HistoryPreview = components['schemas']['HistoricalPreview'];
export type HistoryResult = components['schemas']['HistoricalResult'];
export type HistoryExcerpt = components['schemas']['HistoricalExcerpt'];

async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
  const token = localStorage.getItem('access_token');
  if (!token) throw new Error('Please log in to continue.');
  signal?.throwIfAborted();
  const response = await fetch(`/api/historical${path}`, { signal, cache: 'no-store', method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}) });
  if (response.status === 401) { expireSession(token); throw new Error(sessionExpiredMessage); }
  assertCurrentSession(token); signal?.throwIfAborted();
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const messages: Record<string, string> = {
      HISTORICAL_PREVIEW_CHANGED: 'The history scope, records or permissions changed. Review history again.',
      HISTORICAL_NO_EVIDENCE: 'No eligible historical excerpts remain.',
      ANSWER_CONTEXT_CHANGED: 'The evidence or permissions changed. Review history again.',
      ANSWER_DISABLED: 'Answer generation is disabled on this server.',
      EMBEDDING_BUDGET_EXHAUSTED: 'The AI budget is exhausted.',
      ANSWER_REQUEST_ALREADY_USED: 'This request was already attempted and will not be repeated.',
    };
    throw new Error((messages[error.detail] ?? (response.status === 422 ? 'Enter a question and valid observation cutoff.' : 'The historical question could not finish.'))
      + (body ? ' A sent request may have been charged. No automatic retry will be made.' : ' No AI request was made by this preview.'));
  }
  const value = await response.json(); signal?.throwIfAborted(); assertCurrentSession(token); return value as T;
}
export function previewHistory(params: URLSearchParams, signal?: AbortSignal) {
  const query = new URLSearchParams();
  for (const name of ['q', 'as_of', 'source', 'type']) if (params.get(name)) query.set(name, params.get(name)!);
  return request<HistoryPreview>(`/preview?${query}`, signal);
}
export const answerHistory = (preview: HistoryPreview, signal: AbortSignal) => request<HistoryResult>('', signal, {
  ...preview.scope, preview_digest: preview.preview_digest, request_id: crypto.randomUUID().replaceAll('-', ''), confirm_external_ai: true,
});
export function historyCitationTarget(p: HistoryExcerpt, returnTo: string) {
  return `/passages/${p.version_id}?${new URLSearchParams({ returnTo, version_id: String(p.version_id),
    field: p.field, start: String(p.start), end: String(p.end), passage_hash: p.passage_hash })}`;
}
