import type { Entry } from "../api/entries";

export const sourceLabels: Record<NonNullable<Entry["source"]>, string> = {
  manual: "직접 작성", markdown: "Markdown", chatgpt: "ChatGPT", unknown: "출처 미상",
};
export function formatEntryDate(value: string | null): string {
  if (!value) return "알 수 없음";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));
}
