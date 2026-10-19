"""One fixed answer-validation run; a durable local marker prevents replay."""
import asyncio
import hashlib
from time import perf_counter
from app.evaluation.schemas import EvaluationError, digest, now
from app.evaluation.storage import write_private, read_private, PRIVATE_ROOT
from app.services.answer_transport import CONFIG_HASH, request, AnswerOutputError, AnswerProviderError
from app.services.answer_call import answer as paid_answer


def run_answers(protocol, review, *, approval_digest, client, output, root):
    unsigned = {k:v for k,v in protocol.items() if k != "digest"}
    if (digest(unsigned) != protocol.get("digest") or approval_digest != protocol["digest"] or
            protocol.get("configuration_hash") != CONFIG_HASH or
            len(protocol.get("cases", [])) != len(review) or
            len({c["id"] for c in review}) != len(review) or
            protocol.get("call_limit") != len(review) or not 1 <= len(review) <= 3 or
            protocol.get("max_micro_usd") != len(review)*10000 or
            protocol.get("automatic_retry") is not False or protocol.get("validation_runs") != 1):
        raise EvaluationError("ANSWER_VALIDATION_APPROVAL_INVALID")
    for case, frozen in zip(review, protocol["cases"]):
        if (case["id"] != frozen["id"] or digest(case["question"]) != frozen["question_digest"] or
                digest(case["excerpts"]) != frozen.get("input_digest") or
                len(case["excerpts"]) != len(frozen["selected"]) or
                any(x["id"] != a["embedding_id"] or digest(x["text"]) != a["text_digest"]
                    for x,a in zip(case["excerpts"],frozen["selected"]))):
            raise EvaluationError("ANSWER_VALIDATION_INPUT_CHANGED")
    requests = {c["id"]:digest(["answer-validation-v1",protocol["digest"],c["id"]])[:32] for c in review}
    # Exclusive create happens before any HTTP. A crash never silently restarts this run.
    write_private(output / "run-start.json", dict(protocol_digest=protocol["digest"],
        approved_at=now().isoformat(), request_ids=requests), root=root)
    report = dict(protocol_digest=protocol["digest"], state="completed", cases=[],
        unsent_cases=[c["id"] for c in review])
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
        reason_path = output / (case["id"] + "-diagnostic.json")
        provider_path = output / (case["id"] + "-rejection.json")
        reason = None
        if reason_path.exists():
            diagnostic = read_private(reason_path, root)
            expected_run = hashlib.sha256(
                f'answer-v1:{protocol["owner_id"]}:{requests[case["id"]]}'.encode()).hexdigest()[:32]
            if diagnostic.get("run_id") != expected_run or diagnostic.get("reason") not in AnswerOutputError.REASONS:
                raise EvaluationError("ANSWER_VALIDATION_DIAGNOSTIC_INVALID")
            reason = diagnostic["reason"]
        report["unsent_cases"].remove(case["id"])
        report["cases"].append(dict(id=case["id"], reason=reason,http_status=response.status_code,
            seconds=seconds,status=body.get("status"),error=body.get("detail")))
        if provider_path.exists():
            diagnostic = read_private(provider_path, root)
            if not isinstance(diagnostic, dict) or not isinstance(diagnostic.get("provider"), dict):
                raise EvaluationError("ANSWER_VALIDATION_DIAGNOSTIC_INVALID")
            expected_run = hashlib.sha256(
                f'answer-v1:{protocol["owner_id"]}:{requests[case["id"]]}'.encode()).hexdigest()[:32]
            fields = diagnostic.get("provider", {})
            safe = AnswerProviderError(fields.get("http_status"), dict(error=dict(
                type=fields.get("error_type"), code=fields.get("error_code"), param=fields.get("error_param"))))
            if diagnostic.get("run_id") != expected_run or fields != safe.diagnostic():
                raise EvaluationError("ANSWER_VALIDATION_DIAGNOSTIC_INVALID")
            report["cases"][-1]["provider"] = fields
        if response.status_code != 200:
            report["state"] = "stopped_after_failure"
            break
    write_private(output / "report.json", report, root=root)
    return report

def capturing_answer(runtime, output, case_runs, *, caller=paid_answer, provider=None, root=PRIVATE_ROOT):
    def captured_answer(*a, **kw):
        case_id = case_runs[kw["request_id"]]
        def transport(value):
            raw = provider(value) if provider else asyncio.run(
                request(value,runtime.openai_api_key.get_secret_value()))
            write_private(output / (case_id + "-provider.json"),raw,root=root)
            return raw
        try:
            return caller(*a, **kw, transport=transport)
        except AnswerOutputError as error:
            try:
                write_private(output / (case_id + "-diagnostic.json"),
                    dict(run_id=kw["request_id"], reason=error.reason), root=root)
            except (OSError, EvaluationError):
                # Diagnostic persistence cannot replace the settled answer failure.
                pass
            raise
        except AnswerProviderError as error:
            try:
                write_private(output / (case_id + "-rejection.json"),
                    dict(run_id=kw["request_id"], provider=error.diagnostic()), root=root)
            except (OSError, EvaluationError):
                pass
            raise
    return captured_answer
