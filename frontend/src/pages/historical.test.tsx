import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import App from '../App';
import EntrySearchPage from './EntrySearchPage';
import PassagePage from './PassagePage';
import { setAccessToken } from '../utils/session';
const consent = 'Send this question, observation cutoff and the displayed historical excerpts with their dates to OpenAI';
const excerpt = { entry_id: 4, version_id: 7, current_version_id: 8, field: 'content', start: 0, end: 25,
  passage_hash: 'a'.repeat(64), title: 'Previous worker proposal', text: 'worker uses server Alpha.', event_at: '2025-12-01T00:00:00Z',
  observed_at: '2026-01-10T00:00:00Z', created_at: '2026-01-10T00:00:00Z', source_state: 'available', completeness: 'complete', freshness: 'updated' };
let revision: number, enabled: boolean, empty: boolean, failure: boolean, insufficient: boolean;
let delay: Promise<void> | undefined;
let requests: { url: string; options: RequestInit }[];
let partial = false;
beforeEach(() => {
  partial = false;
  localStorage.clear(); localStorage.setItem('access_token', 'test-token');
  revision = 1; enabled = true; empty = false; failure = false; insufficient = false; delay = undefined; requests = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit = {}) => {
    requests.push({ url, options });
    const preview = { scope: { q: 'worker', as_of: '2026-01-31', source: null, type: null },
      policy_revision: revision, preview_digest: String(revision).repeat(64), scope_records: 10, observed_records: 6,
      allowed_records: 4, matching_records: 2, examined_records: 2, input_skipped: 0, byte_skipped: 0,
      passages: empty ? [] : [excerpt], partial: true, timezone: 'Asia/Seoul' };
    if (url.includes('/historical/preview?')) return Response.json(preview);
    if (url.endsWith('/answers/status')) return Response.json({ enabled, policy_revision: revision });
    if (url.endsWith('/historical')) {
      await delay;
      return failure ? Response.json({ detail: 'HISTORICAL_PREVIEW_CHANGED' }, { status: 409 }) : Response.json({ preview,
        status: insufficient ? 'insufficient' : partial ? 'partial' : 'supported', answer: insufficient ? 'No explicit adoption is established.' : partial ? 'The retained proposal uses Alpha; adoption is unconfirmed in these versions.' : 'The observed proposal uses Alpha.',
        citations: insufficient ? [] : [excerpt] });
    }
    return Response.json(excerpt);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function mount(initial = '/search?mode=historical&q=worker&as_of=2026-01-31') {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[initial]}><Routes><Route element={<App />}>
    <Route path="/search" element={<EntrySearchPage />} /><Route path="/passages/:id" element={<PassagePage />} />
    <Route path="/login" element={<p>Login page</p>} />
  </Route></Routes></MemoryRouter></QueryClientProvider>);
  return cache;
}
const posts = () => requests.filter(r => r.options.method === 'POST');
async function start() {
  await screen.findByRole('button', { name: 'Answer from historical excerpts' });
  await waitFor(() => expect((screen.getByRole('checkbox', { name: consent }) as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('checkbox', { name: consent }));
  fireEvent.click(screen.getByRole('button', { name: 'Answer from historical excerpts' }));
}
it('previews local collection history before one consented call with an exact anchor', async () => {
  mount(); await screen.findByRole('button', { name: 'Answer from historical excerpts' });
  expect(posts()).toHaveLength(0); expect(screen.getByText(/6 of 10 scoped records/)).toBeTruthy();
  expect(screen.getAllByText(/Later imports are excluded/).length).toBeGreaterThan(0);
  expect(screen.queryByLabelText('Date field')).toBeNull(); expect(screen.queryByLabelText('Source status')).toBeNull();
  await start(); await screen.findByText('Draft historical answer'); expect(posts()).toHaveLength(1);
  const body = JSON.parse(posts()[0].options.body as string);
  expect(body.q).toBe('worker'); expect(body.as_of).toBe('2026-01-31'); expect(body.preview_digest).toBe('1'.repeat(64));
  expect(body.confirm_external_ai).toBe(true); expect(body.request_id).toMatch(/^[a-f0-9]{32}$/);
  expect((screen.getByRole('checkbox', { name: consent }) as HTMLInputElement).checked).toBe(false);
  const href = screen.getByRole('link', { name: 'Previous worker proposal · Version 7' }).getAttribute('href')!;
  expect(href).toContain('version_id=7'); expect(href).toContain('passage_hash=');
});
it('returns from a citation with historical mode and cutoff without paid replay', async () => {
  mount(); await start(); await screen.findByText('Draft historical answer');
  fireEvent.click(screen.getByRole('link', { name: 'Previous worker proposal · Version 7' }));
  await screen.findByText(/Showing the cited version 7/);
  expect(requests.some(r => r.url.includes('/passages/citation?'))).toBe(true);
  fireEvent.click(screen.getByRole('link', { name: 'Back to search' }));
  await screen.findByRole('button', { name: 'Answer from historical excerpts' });
  expect((screen.getByLabelText('Record version') as HTMLSelectElement).value).toBe('observed');
  expect((screen.getByLabelText('Observed through', { exact: true }) as HTMLInputElement).value).toBe('2026-01-31');
  expect(posts()).toHaveLength(1);
});
it.each(['empty', 'disabled'])('does not send when %s', async value => {
  if (value === 'empty') empty = true; else enabled = false;
  mount(); await screen.findByRole('button', { name: 'Answer from historical excerpts' });
  expect((screen.getByRole('button', { name: 'Answer from historical excerpts' }) as HTMLButtonElement).disabled).toBe(true);
  expect(posts()).toHaveLength(0);
});
it('shows insufficient support with no result citation', async () => {
  insufficient = true; mount(); await start(); await screen.findByText('No explicit adoption is established.');
  expect(screen.getByText('Insufficient evidence')).toBeTruthy();
  expect(screen.queryByRole('link', { name: 'Previous worker proposal · Version 7' })).toBeNull();
});
it('reports changed previews without automatic paid retry', async () => {
  failure = true; mount(); await start(); expect((await screen.findByRole('alert')).textContent).toContain('changed');
  expect(posts()).toHaveLength(1);
});
it.each(['cutoff', 'question', 'source', 'account', 'stop'])('discards delayed output after %s change', async change => {
  let finish!: () => void; delay = new Promise(resolve => { finish = resolve; });
  mount(); await start(); await screen.findByText('Checking historical evidence...');
  if (change === 'cutoff') fireEvent.change(screen.getByLabelText('Observed through', { exact: true }), { target: { value: '2026-02-28' } });
  if (change === 'question') fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'another question' } });
  if (change === 'source') fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'github' } });
  if (change === 'account') act(() => setAccessToken('other-account'));
  if (change === 'stop') fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
  await waitFor(() => expect(posts()[0].options.signal?.aborted).toBe(true)); finish();
  await waitFor(() => expect(screen.queryByText('Checking historical evidence...')).toBeNull());
  expect(screen.queryByText('The observed proposal uses Alpha.')).toBeNull(); expect(posts()).toHaveLength(1);
});
it('hides previous results when policy revision changes', async () => {
  const cache = mount(); await start(); await screen.findByText('Draft historical answer'); revision = 2;
  await act(async () => { await cache.refetchQueries({ queryKey: ['answer-status'] }); await cache.refetchQueries({ queryKey: ['history-preview'] }); });
  await waitFor(() => expect(screen.queryByText('Draft historical answer')).toBeNull());
  expect((screen.getByRole('checkbox', { name: consent }) as HTMLInputElement).checked).toBe(false);
});
it('requires a cutoff and submits only historical filters', async () => {
  mount('/search?mode=historical'); fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'worker' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  expect((await screen.findByRole('alert')).textContent).toContain('cutoff'); expect(requests).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Observed through', { exact: true }), { target: { value: '2026-01-31' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  await screen.findByRole('button', { name: 'Answer from historical excerpts' });
  const url = requests.find(r => r.url.includes('/historical/preview?'))!.url;
  expect(url).toContain('as_of=2026-01-31'); expect(url).not.toContain('date_field');
  expect(url).not.toContain('source_state'); expect(url).not.toContain('include_work_commentary');
});

it('preserves a completed answer across asynchronous availability rechecks', async () => {
  const cache = mount(); await start(); await screen.findByText('Draft historical answer');
  let finish!: () => void;
  const gate = new Promise<void>(resolve => { finish = resolve; });
  const previous = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn(async (...args: Parameters<typeof fetch>) => {
    if (String(args[0]).endsWith('/answers/status')) await gate;
    return previous(...args);
  }));
  let recheck!: Promise<void>;
  act(() => { recheck = cache.refetchQueries({ queryKey: ['answer-status'] }); });
  await waitFor(() => expect(screen.queryByText('Draft historical answer')).toBeNull());
  await act(async () => { finish(); await recheck; });
  await screen.findByText('Draft historical answer');
  expect(posts()).toHaveLength(1);
});

it("keeps original citations visible for a partial draft", async () => {
  partial = true; mount(); await start();
  await screen.findByText("Partial draft — some requested facts are unconfirmed");
  expect(screen.queryByText("Insufficient evidence")).toBeNull();
  expect(screen.getByRole("link", { name: /Previous worker proposal/ })).toBeTruthy();
});
