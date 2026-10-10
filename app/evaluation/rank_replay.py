"""Private bounded rank capture and offline A-D evaluation; no provider imports."""
from collections import Counter
import time
from app.evaluation.schemas import canonical_bytes, digest, now, EvaluationError
from app.evaluation.storage import MAX_DATASET_BYTES, read_private, write_private
from app.evaluation.semantic import group_rank, fuse, filtered_rows, ranking_diagnostics, MAX_PASSAGES
from app.evaluation.passage_metrics import passage_metrics

VERSION = "lifhop-rank-capture-v1"
RULES = {"A":(2,2), "B":(None,2), "C":(2,None), "D":(None,None)}
RULE_DIGEST = digest(dict(schema=VERSION, variants=RULES, rrf_k=60, weights=[1,1], candidates=100, results=20))
MAX_RUN_BYTES = 16 * 1024 * 1024
ROW_KEYS = ("id", "group_id", "entry_id", "version_id", "field", "start", "end",
            "passage_hash", "parent_id", "parent_hash", "event_at")


def metadata(row):
    family = [row["provider"], row["source_scope"], row.get("document_path") or row["entry_id"]]
    return dict({k:row[k] for k in ROW_KEYS if k in row}, family_id=digest(family))


def selection(hits):
    return [dict(id=h["id"], group_id=h["group_id"], entry_id=h["entry_id"],
                 locations=h["gold_locations"]) for h in hits]


class RankCapture:
    def __init__(self, experiment):
        self.experiment = experiment
        self.cases = {}

    def collect(self, case_id, lexical_ids, semantic_ids, methods):
        if case_id in self.cases:
            raise EvaluationError("CAPTURE_DUPLICATE_CASE")
        self.cases[case_id] = dict(case_id=case_id, lexical_ids=list(lexical_ids),
            semantic_ids=list(semantic_ids), baseline={k:selection(v) for k,v in methods.items()},
            baseline_scores={k:passage_metrics(v, self.experiment.gold[case_id]) for k,v in methods.items()})

    def publish(self, path, report, *, root):
        if report["status"] != "measured" or len(self.cases) != len(self.experiment.cases):
            raise EvaluationError("CAPTURE_INCOMPLETE")
        header = dict(schema=VERSION, run_id=report["run_id"], captured_at=now().isoformat(),
            manifest_digest=self.experiment.manifest["digest"], rule_digest=RULE_DIGEST,
            manifest=self.experiment.manifest, rows=[metadata(r) for r in self.experiment.rows],
            usage=report["usage"], elapsed_ms=report["elapsed_ms"],
            cases=[dict(case_id=c.id, file=f"case-{i:02d}.json", digest=digest(self.cases[c.id]))
                for i,c in enumerate(self.experiment.cases)])
        # The manifest has no body, but section manifests contain private paths;
        # persist only its binding digest and metadata needed to refresh preparation.
        header["manifest"] = {k:self.experiment.manifest[k] for k in
            ("provider", "scope", "entry_ids", "owner_id", "database_fingerprint", "dataset_digest",
             "policy_revision", "model", "configuration_hash", "corpus")}
        header["manifest"]["chunking"] = self.experiment.manifest.get("chunking", "indexed")
        header["digest"] = digest(header)
        documents = [(path / item["file"], self.cases[item["case_id"]]) for item in header["cases"]]
        documents.append((path / "capture.json", header))
        sizes = [len(canonical_bytes(value)) for _,value in documents]
        if any(n > MAX_DATASET_BYTES for n in sizes) or sum(sizes) > MAX_RUN_BYTES:
            raise EvaluationError("CAPTURE_SIZE_LIMIT")
        # The index is published last. Partial case files are never replayable.
        for target,value in documents:
            write_private(target, value, root=root)
        return path / "capture.json"


def load_capture(path, experiment, *, root):
    header = read_private(path, root)
    if header.get("schema") != VERSION or header.get("rule_digest") != RULE_DIGEST:
        raise EvaluationError("CAPTURE_CONFIGURATION_CHANGED")
    if header.get("digest") != digest({k:v for k,v in header.items() if k != "digest"}):
        raise EvaluationError("CAPTURE_INVALID")
    if header["manifest_digest"] != experiment.manifest["digest"]:
        raise EvaluationError("CAPTURE_STALE")
    if header["rows"] != [metadata(r) for r in experiment.rows]:
        raise EvaluationError("CAPTURE_ROWS_CHANGED")
    expected_ids = [c.id for c in experiment.cases]
    if [c["case_id"] for c in header["cases"]] != expected_ids:
        raise EvaluationError("CAPTURE_CASES_CHANGED")
    size = len(canonical_bytes(header))
    cases = {}
    for index,item in enumerate(header["cases"]):
        if item["file"] != f"case-{index:02d}.json":
            raise EvaluationError("CAPTURE_INVALID")
        value = read_private(path.parent / item["file"], root)
        size += len(canonical_bytes(value))
        if size > MAX_RUN_BYTES or digest(value) != item["digest"] or value["case_id"] != item["case_id"]:
            raise EvaluationError("CAPTURE_INVALID")
        cases[value["case_id"]] = value
    return header,cases


def replay(experiment, header, captures):
    result = dict(schema="lifhop-rank-replay-v1", source_run_id=header["run_id"],
        capture_digest=header["digest"], rule_digest=RULE_DIGEST,
        dataset_digest=experiment.manifest["dataset_digest"],
        manifest_digest=experiment.manifest["digest"],
        status="measured", b2_gate="independent_validation_required", provider_calls=0, variants={})
    by_case = {c.id:c for c in experiment.cases}
    for name,(early,late) in RULES.items():
        results = []
        for case_id,captured in captures.items():
            before = time.monotonic()
            case = by_case[case_id]
            rows = filtered_rows(experiment.rows, case.filters)
            ids = {r["id"] for r in rows}
            semantic_ids, lexical_ids = captured["semantic_ids"], captured["lexical_ids"]
            if (len(semantic_ids) > MAX_PASSAGES or len(lexical_ids) > MAX_PASSAGES
                    or len(set(semantic_ids)) != len(semantic_ids) or set(semantic_ids) != ids
                    or len(set(lexical_ids)) != len(lexical_ids)
                    or lexical_ids != [pid for pid in experiment.lexical[case_id] if pid in ids]):
                raise EvaluationError("CAPTURE_RANKS_INVALID")
            lexical = group_rank(rows, lexical_ids, per_entry_limit=early)
            semantic = group_rank(rows, semantic_ids, per_entry_limit=early)
            methods = dict(lexical=lexical[:20], semantic=semantic[:20],
                           hybrid=fuse(lexical, semantic, per_entry_limit=late))
            if name == "A" and {k:selection(v) for k,v in methods.items()} != captured["baseline"]:
                raise EvaluationError("BASELINE_REPLAY_MISMATCH")
            groups = experiment.gold[case_id]
            if any(a["status"] != "valid" or a["selection"] != "current" or not a["external_ai_eligible"]
                   for anchors in groups.values() for a in anchors):
                raise EvaluationError("CAPTURE_EVIDENCE_INVALID")
            families = {r["id"]:metadata(r)["family_id"] for r in rows}
            outputs = {}
            for method,hits in methods.items():
                counts = Counter(families[h["id"]] for h in hits)
                outputs[method] = dict(scores=passage_metrics(hits, groups), hits=selection(hits),
                    distinct_families=len(counts), max_family_results=max(counts.values(),default=0))
            if name == "A" and {k:v["scores"] for k,v in outputs.items()} != captured["baseline_scores"]:
                raise EvaluationError("BASELINE_REPLAY_MISMATCH")
            results.append(dict(case_id=case_id, language=case.language,
                expected_outcome=case.expected_outcome, methods=outputs,
                status="negative_review_required" if not groups and case.expected_outcome in
                    {"insufficient_evidence", "coverage_gap"} else "measured",
                diagnostics=dict(lexical=ranking_diagnostics(rows,lexical_ids,groups,per_entry_limit=early),
                    semantic=ranking_diagnostics(rows,semantic_ids,groups,per_entry_limit=early),
                    fusion_before_quota=passage_metrics(fuse(lexical,semantic,per_entry_limit=None,limit=200),groups)["group_ranks"],
                    fusion_after_quota=passage_metrics(fuse(lexical,semantic,per_entry_limit=late,limit=200),groups)["group_ranks"]),
                replay_ms=round((time.monotonic()-before)*1000,2)))
        result["variants"][name] = dict(early_entry_limit=early, final_entry_limit=late,
            product_candidate=name != "D", cases=results)
    return result
