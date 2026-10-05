import type { components } from "../api/generated/schema";
export default function GitHubRecordStatus({record}: {record: components["schemas"]["GitHubRecordSummary"]}) {
  return <span className="badges">
    {record.partial && <span className="badge">Partial evidence</span>}
    {record.review_required && <span className="badge">Version review</span>}
    {record.source_state === "deleted" && <span className="badge">Deleted at source</span>}
  </span>;
}
