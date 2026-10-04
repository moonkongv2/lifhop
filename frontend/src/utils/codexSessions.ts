import { listTarget, resolveEntryContext, validPage } from "./entryNavigation";
import type { EntryListContext } from "./entryNavigation";

export type SessionRef = { source_scope: string; thread_id: string };
export function sessionTarget(ref: SessionRef, context: EntryListContext, focus?: number) {
  const params = new URLSearchParams({ scope: ref.source_scope, thread: ref.thread_id, returnTo: listTarget(context) });
  if (focus) params.set("focus", String(focus));
  return `/sessions/codex?${params}`;
}
export function safeSessionReturn(value: string | null): string | null {
  if (!value?.startsWith("/sessions/codex?") || value.startsWith("//")) return null;
  try {
    const url = new URL(value, "https://lifhop.invalid");
    const params = url.searchParams;
    const scope = params.get("scope"); const thread = params.get("thread");
    if (url.origin !== "https://lifhop.invalid" || url.pathname !== "/sessions/codex" || !scope || scope.length > 255 || !thread || thread.length > 1024 || !validPage(params)) return null;
    const result = new URLSearchParams({ scope, thread, returnTo: listTarget(resolveEntryContext(params.toString())) });
    for (const key of ["offset", "focus"]) {
      const raw = params.get(key);
      if (raw && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw))) result.set(key, raw);
    }
    return `/sessions/codex?${result}`;
  } catch { return null; }
}
