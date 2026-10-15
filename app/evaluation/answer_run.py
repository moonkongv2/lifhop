"""One fixed answer-validation run; a durable local marker prevents replay."""
from time import perf_counter
from app.evaluation.schemas import EvaluationError, digest, now
from app.evaluation.storage import write_private
from app.services.answer_transport import CONFIG_HASH


def run_answers(protocol, review, *, approval_digest, client, output, root):
    unsigned = {k:v for k,v in protocol.items() if k != "digest"}
    if (digest(unsigned) != protocol.get("digest") or approval_digest != protocol["digest"] or
            protocol.get("configuration_hash") != CONFIG_HASH or
            protocol.get("call_limit") != len(review) or not 1 <= len(review) <= 3 or
            protocol.get("max_micro_usd") != len(review)*10000 or
            protocol.get("automatic_retry") is not False or protocol.get("validation_runs") != 1):
        raise EvaluationError("ANSWER_VALIDATION_APPROVAL_INVALID")
    for case, frozen in zip(review, protocol["cases"]):
        if (case["id"] != frozen["id"] or digest(case["question"]) != frozen["question_digest"] or
                len(case["excerpts"]) != len(frozen["selected"]) or
                any(x["id"] != a["embedding_id"] or digest(x["text"]) != a["text_digest"]
                    for x,a in zip(case["excerpts"],frozen["selected"]))):
            raise EvaluationError("ANSWER_VALIDATION_INPUT_CHANGED")
    requests = {c["id"]:digest(["answer-validation-v1",protocol["digest"],c["id"]])[:32] for c in review}
    # Exclusive create happens before any HTTP. A crash never silently restarts this run.
    write_private(output / "run-start.json", dict(protocol_digest=protocol["digest"],
        approved_at=now().isoformat(), request_ids=requests), root=root)
    report = dict(protocol_digest=protocol["digest"], state="completed", cases=[])
    for case in review:
        start = perf_counter()
        response = client.post("/answers", json=dict(q=case["question"],
            embedding_ids=[x["id"] for x in case["excerpts"]],
            request_id=requests[case["id"]], confirm_external_ai=True))
        seconds = perf_counter()-start
        body = response.json()
        write_private(output / (case["id"] + ".json"), dict(case_id=case["id"],
            request_id=requests[case["id"]], http_status=response.status_code,
            seconds=seconds, response=body), root=root)
        report["cases"].append(dict(id=case["id"],http_status=response.status_code,
            seconds=seconds,status=body.get("status"),error=body.get("detail")))
        if response.status_code != 200:
            report["state"] = "stopped_after_failure"
            break
    write_private(output / "report.json", report, root=root)
    return report
