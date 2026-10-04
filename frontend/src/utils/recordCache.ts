import type { QueryClient } from "@tanstack/react-query";

export async function invalidateRecordViews(cache: QueryClient) {
  await Promise.all(["archive", "entries", "codex-session", "presentation", "entry"].map(key => cache.invalidateQueries({ queryKey: [key] })));
}
