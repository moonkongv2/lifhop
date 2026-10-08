import type { QueryClient } from "@tanstack/react-query";

export async function invalidateRecordViews(cache: QueryClient) {
  await Promise.all(["archive", "entries", "codex-session", "presentation", "entry", "github-repository", "github-records", "github-discussions", "github-presentation", "passages", "passage", "passage-snapshots"].map(key => cache.invalidateQueries({ queryKey: [key] })));
}
