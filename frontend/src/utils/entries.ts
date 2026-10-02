import type { Entry } from "../api/entries";

export const sourceLabels: Record<NonNullable<Entry["source"]>, string> = {
  manual: "Manual", markdown: "Markdown", chatgpt: "ChatGPT", codex: "Codex", github: "GitHub", unknown: "Unknown source",
};
export function formatEntryDate(value: string | null): string {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));
}
