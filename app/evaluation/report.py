from html import escape
from pathlib import Path
from uuid import uuid4

from app.evaluation.storage import PRIVATE_ROOT, private_directory, write_private


def render_report(result: dict) -> bytes:
    manifest, summary = result["manifest"], result["summary"]
    def score(value):
        return "N/A" if value is None else f"{value:.3f}"
    rows = []
    synthetic = manifest.get("material_kind") == "synthetic"
    for case in result["cases"]:
        queries = []
        for query in case["queries"]:
            labels = [(hit, f'{rank}: Entry {int(hit["entry_id"])} / v{escape(str(hit["version_id"]))}')
                      for rank, hit in enumerate(query["hits"], 1)]
            links = " ".join(label if synthetic else
                f'<a href="http://localhost:5173/entries/{int(hit["entry_id"])}" target="_blank" rel="noopener noreferrer">{label}</a>'
                for hit, label in labels)
            queries.append(f'<p>Query {query["query_index"]+1}: {query["total"]} results · {query["elapsed_ms"]} ms</p><div>{links}</div>')
        values = case["scores"]
        ai_status = "blocked" if case["policy_blocked"] else "eligible (observed)" if case["groups"] else "N/A"
        rows.append(f'<tr><td>{escape(case["case_id"])}</td><td>{escape(case["status"])}'
            f'<br>AI: {ai_status}</td>'
            f'<td>{score(values.get("group_recall_at_20"))}</td><td>{score(values.get("all_groups_hit_at_20"))}</td>'
            f'<td>{score(values.get("mrr_at_20"))}</td><td>{"".join(queries)}</td></tr>')
    scores = summary["scores"]
    content = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Private retrieval evaluation</title><style>
body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 16px;color:#273449;background:#f6f7fa}}
table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:12px;border:1px solid #ddd;text-align:left;vertical-align:top}}
a{{display:inline-block;margin:4px;color:#355ab2}}.table{{overflow-x:auto}}code{{overflow-wrap:anywhere}}</style></head><body>
<h1>Private retrieval evaluation</h1>
<p>{"Synthetic fixture; not the real owner evaluation. Fixture record links are disabled." if synthetic else "Private real dataset; reviewed-case completeness is recorded in the manifest."}</p>
<p>{escape(manifest["mode"])} · {escape(manifest["status"])} · revision {manifest["revision"]}</p>
<p>Real set ready: {str(manifest["composition"]["complete"]).lower()}.</p>
<p>Dataset: <code>{escape(manifest["dataset_digest"])}</code></p>
<p>Scored cases: {summary["scored_cases"]} / {summary["total_cases"]}; clean: {summary["clean_cases"]};
invalid scored cases: {summary["invalid_scored_cases"]}.</p>
<p>Group recall@20: {score(scores.get("group_recall_at_20"))}; all groups@20:
{score(scores.get("all_groups_hit_at_20"))}; MRR@20: {score(scores.get("mrr_at_20"))}.</p>
<p>Targets: group recall@20 ≥ 0.80, all groups@20 ≥ 0.70. Low baselines are valid measurements.</p>
<p>Entry-level current-version retrieval. Historical Entry hits do not prove historical passage retrieval.
AI eligibility is a policy observation; no AI answer was generated or sent.</p>
<p>Question/claim text and source bodies are kept out of this report. See the private dataset for questions.
Real record links require the local app using the same database and login as the dataset owner. Old results describe the observation time,
not current availability; a deleted record remains unavailable.</p>
<div class="table"><table><thead><tr><th>Case</th><th>Status</th><th>Recall@20</th><th>All groups@20</th><th>MRR@20</th><th>Ranked records</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div></body></html>'''
    return content.encode()


def save_report(directory: Path, result: dict, *, root: Path = PRIVATE_ROOT) -> Path:
    run_dir = directory / "runs" / uuid4().hex
    private_directory(run_dir, root)
    write_private(run_dir/"manifest.json", result["manifest"], root=root)
    write_private(run_dir/"results.json", dict(cases=result["cases"], summary=result["summary"]), root=root)
    write_private(run_dir/"report.html", render_report(result), root=root)
    return run_dir
