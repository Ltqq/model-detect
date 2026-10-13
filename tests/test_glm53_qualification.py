import asyncio
import json

import pytest
from typer.testing import CliRunner

from model_detect.cli import app
from model_detect.glm53_qualification import (
    _usage, build_comparison, capability_cases, normalize_base_url,
    plan_comparison, protocol_cases, run_endpoint, selected_cases,
    suite_digest, write_comparison,
)
from model_detect.models import Evidence
from model_detect.http_client import CallResult
from model_detect.rules import match_model_rule, preferred_feature_value


def test_glm53_model_rule_and_official_base_url():
    rule = match_model_rule("glm-5.3")
    assert rule.id == "glm-5.3"
    assert rule.declared_context_tokens == 1_000_000
    assert preferred_feature_value(
        "glm-5.3", "reasoning_effort", preferred="medium"
    ) == "max"
    assert normalize_base_url(
        "https://api.z.ai/api/paas/v4/chat/completions"
    ) == "https://api.z.ai/api/paas/v4"
    assert normalize_base_url("https://api.z.ai/api/coding/paas/v4") == (
        "https://api.z.ai/api/coding/paas/v4"
    )
    with pytest.raises(ValueError):
        normalize_base_url("https://user:secret@example.org/v1")
    with pytest.raises(ValueError):
        normalize_base_url("https://example.org/v1?token=secret")


def test_budget_can_be_calculated_before_any_api_calls():
    plan = plan_comparison()
    assert plan["official_runs"] == 3
    assert plan["customer_runs"] == 1
    assert plan["protocol_cases"] == 10
    assert plan["capability_cases"] == 25
    assert plan["requests"] == 140
    assert plan["nominal_output_token_cap"] == (
        (10 * 1024 + 25 * 2048) * 4
    )
    assert plan["estimated_input_tokens"] > 0
    assert plan["scenario_max_cost"] is None

    priced = plan_comparison(
        mode="capability", profile="smoke",
        input_price_per_million=10, output_price_per_million=50,
    )
    assert priced["requests"] == 40
    assert priced["scenario_max_cost"] > 0
    assert priced["suite_sha256"] == suite_digest(capability_cases("smoke"))
    assert plan_comparison()["suite_sha256"] == plan["suite_sha256"]
    with pytest.raises(ValueError, match="between 1 and 5"):
        plan_comparison(official_runs=0)


def test_disabled_thinking_is_intentionally_not_rewritten():
    disabled = next(c for c in protocol_cases() if c["id"] == "thinking.disabled")
    assert disabled["payload"]["thinking"]["type"] == "disabled"
    for c in protocol_cases():
        assert c["payload"]["model"] == "glm-5.3"
    for c in capability_cases("smoke"):
        assert c["payload"]["reasoning_effort"] == "max"
        assert c["payload"]["max_tokens"] == 2048


def _row(case, run, endpoint, status="pass", usage=True):
    return {
        "endpoint": endpoint, "run": run, "id": case["id"],
        "kind": "protocol" if "check" in case else "capability",
        "category": case.get("category", "protocol"),
        "status": status,
        "usage": (
            {"prompt_tokens": 20, "completion_tokens": 60,
             "reasoning_tokens": 30, "cached_read_tokens": 3}
            if usage else None
        ),
    }


def test_same_suite_official_three_runs_vendor_compares_and_reports(tmp_path):
    cases = selected_cases("all", "smoke")
    plan = plan_comparison(profile="smoke")
    official = [_row(case, run, "official")
                for run in range(1, 4) for case in cases]
    vendor = [_row(case, 1, "customer") for case in cases]
    for row in vendor:
        if row["id"].startswith("reasoning.") and row["kind"] == "capability":
            row["status"] = "fail"
    protocol = next(row for row in vendor if row["id"] == "thinking.enabled")
    protocol["status"] = "fail"
    report = build_comparison(
        official, vendor, plan=plan,
        input_price_per_million=10, output_price_per_million=50
    )
    assert report["suite_version"] == plan["suite_version"]
    assert next(x for x in report["protocol"] if x["id"] == "thinking.enabled")["verdict"] == "deviation"
    reasoning = next(x for x in report["capability"] if x["category"] == "reasoning")
    assert reasoning["verdict"] == "observable_drop"
    assert reasoning["customer"]["score"] == 0
    assert report["usage"]["official"]["complete_usage"] is True
    assert report["usage"]["official"]["reasoning_tokens_observed"] > 0
    # reasoning tokens are not added on top of completion tokens
    assert report["usage"]["official"]["prompt_tokens_observed"] == 20 * len(official)
    outputs = write_comparison(report, tmp_path)
    assert all(path.is_file() for path in outputs.values())
    assert "协议符合性" in outputs["markdown"].read_text(encoding="utf-8")
    assert "reasoning" in outputs["markdown"].read_text(encoding="utf-8")
    assert "<table>" in outputs["html"].read_text(encoding="utf-8")
    assert "api-reference/llm/chat-completion" in outputs["html"].read_text(encoding="utf-8")
    assert "sk-" not in outputs["json"].read_text(encoding="utf-8")


def test_failed_reference_and_incomplete_score_cannot_pass():
    cases = selected_cases("capability", "smoke")
    plan = plan_comparison(mode="capability", profile="smoke")
    official = [_row(case, run, "official", "error" if run == 2 else "pass")
                for run in range(1, 4) for case in cases]
    vendor = [_row(case, 1, "customer") for case in cases]
    comparison = build_comparison(official, vendor, plan=plan)
    assert all(row["verdict"] == "insufficient" for row in comparison["capability"])
    with pytest.raises(ValueError, match="missing, duplicate"):
        build_comparison(official[:-1], vendor, plan=plan)


def test_usage_extraction_reports_unknown_and_nested_fields():
    assert _usage({}) is None
    assert _usage({"usage": {
        "prompt_tokens": 17, "completion_tokens": 29,
        "prompt_tokens_details": {"cached_tokens": 7},
        "completion_tokens_details": {"reasoning_tokens": 11},
    }}) == {
        "prompt_tokens": 17, "completion_tokens": 29,
        "cached_read_tokens": 7, "reasoning_tokens": 11,
    }


def test_glm53_cli_dry_run_requires_no_keys_and_cannot_charge(monkeypatch, tmp_path):
    monkeypatch.delenv("GLM53_OFFICIAL_KEY", raising=False)
    monkeypatch.delenv("GLM53_CUSTOMER_KEY", raising=False)
    result = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://customer.example/v1",
        "--mode", "protocol",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code == 0, result.output
    assert "预览完成" in result.output
    assert not (tmp_path / "out").exists()
    wrong = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://customer.example/v1",
        "--mode", "protocol", "--execute",
    ])
    assert wrong.exit_code != 0


def test_endpoint_runner_uses_documented_parameters_without_rewriting(monkeypatch):
    sent = []

    async def fake_post(self, *, probe_id, path, payload, stream=False,
                        stream_full=False, constraint_exempt_fields=None):
        sent.append((probe_id, self.base_url, payload, stream, constraint_exempt_fields))
        code = 400 if probe_id == "glm53.thinking.disabled" else 200
        if stream:
            content = {
                "_sse_completed": True,
                "_sse_truncated": False,
                "_sse_finish_reason": "stop",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
            headers = {"content-type": "text/event-stream"}
        elif probe_id == "glm53.thinking.disabled":
            content = {"error": {"message": "thinking disabled is not supported"}}
            headers = {}
        elif probe_id == "glm53.tools.auto":
            content = {"choices": [{"message": {"tool_calls": [{
                "type": "function", "function": {
                    "name": "lookup_ticket", "arguments": '{"ticket_id":"T-17"}'
                }
            }]}}]}
            headers = {}
        elif probe_id == "glm53.json.object":
            content = {"choices": [{"message": {"content": '{"ok":true}'}}]}
            headers = {}
        else:
            content = {"choices": [{"message": {
                "content": "阿林" if probe_id == "glm53.chat.multiturn" else "READY"
            }}], "usage": {"prompt_tokens": 16, "completion_tokens": 24}}
            headers = {}
        evidence = Evidence(
            id="ev-mock", probe_id=probe_id,
            url="https://api.z.ai/api/paas/v4/chat/completions",
            request_body=payload, response_status=code,
            response_headers=headers,
        )
        return CallResult(evidence=evidence, json_body=content)
    monkeypatch.setattr(
        "model_detect.glm53_qualification.AuditHttpClient.post_json", fake_post
    )
    records = asyncio.run(run_endpoint(
        base_url="https://api.z.ai/api/paas/v4", api_key="SECRET",
        cases=protocol_cases(), runs=1, label="official",
    ))
    assert len(records) == 10
    assert all(x["status"] == "pass" for x in records)
    assert all("/api/paas/v4" in x[1] for x in sent)
    assert next(x[2] for x in sent if x[0] == "glm53.thinking.disabled")["thinking"]["type"] == "disabled"
    assert all(x[4] == {"thinking", "reasoning_effort"} for x in sent)
    assert "SECRET" not in json.dumps(records)



def test_glm53_cli_executed_report_with_mocked_official_and_customer(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "sk-official-mock")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "sk-customer-mock")
    seen = []

    async def fake_run_endpoint(*, base_url, api_key, cases, runs, label,
                                timeout=120):
        seen.append((base_url, label, runs))
        return [
            _row(case, run, label)
            for run in range(1, runs + 1)
            for case in cases
        ]

    monkeypatch.setattr(
        "model_detect.glm53_cli.run_endpoint", fake_run_endpoint
    )
    output = tmp_path / "glm53"
    result = CliRunner().invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://customer.example/v1",
        "--mode", "protocol",
        "--official-runs", "3",
        "--customer-runs", "1",
        "--execute",
        "--output-dir", str(output),
    ])
    assert result.exit_code == 0, result.output
    assert seen == [
        ("https://api.z.ai/api/paas/v4", "official", 3),
        ("https://customer.example/v1", "customer", 1),
    ]
    report = json.loads(
        (output / "glm53-comparison.json").read_text(encoding="utf-8")
    )
    assert report["plan"]["requests"] == 40
    assert len(report["protocol"]) == 10
    assert report["capability"] == []
    assert "sk-official-mock" not in json.dumps(report)
    assert "sk-customer-mock" not in json.dumps(report)


def test_malformed_model_result_is_not_counted_as_success(monkeypatch):
    from model_detect.glm53_qualification import _assistant_message
    assert _assistant_message({"choices": "malformed"}) == {}
    assert _assistant_message({"choices": [{"message": "wrong"}]}) == {}
    assert _assistant_message(None) == {}



def test_official_protocol_rejection_must_relate_to_thinking():
    from model_detect.glm53_qualification import _check_protocol
    from model_detect.http_client import CallResult
    def response(status, body):
        evidence = Evidence(
            id="e", probe_id="glm53.thinking.disabled",
            url="https://example.test/chat/completions",
            response_status=status,
        )
        return CallResult(evidence=evidence, json_body=body)
    disabled = next(c for c in protocol_cases() if c["id"] == "thinking.disabled")
    assert _check_protocol(disabled, response(429, {"error":"quota"}))[0] == "insufficient"
    assert _check_protocol(disabled, response(401, {"error":"no auth"}))[0] == "insufficient"
    assert _check_protocol(disabled, response(400, {"error":"unrelated"}))[0] == "insufficient"
    assert _check_protocol(disabled, response(400, {"error":"thinking disabled unsupported"}))[0] == "pass"
    assert _check_protocol(disabled, response(200, {}))[0] == "fail"


def test_sse_must_be_complete_not_just_initial_chunks():
    from model_detect.glm53_qualification import _check_protocol
    from model_detect.http_client import CallResult
    case = next(c for c in protocol_cases() if c["id"] == "chat.stream")
    def outcome(completed, truncated=False, reason="stop"):
        return CallResult(
            evidence=Evidence(
                id="e", probe_id="x", url="https://example.test",
                response_status=200,
                response_headers={"content-type":"text/event-stream"},
            ),
            json_body={
                "_sse_completed":completed, "_sse_truncated":truncated,
                "_sse_finish_reason":reason,
            },
        )
    assert _check_protocol(case, outcome(False))[0] == "insufficient"
    assert _check_protocol(case, outcome(True, True))[0] == "insufficient"
    assert _check_protocol(case, outcome(True, False, None))[0] == "insufficient"
    assert _check_protocol(case, outcome(True))[0] == "pass"


def test_tool_malformed_arguments_do_not_pass():
    from model_detect.glm53_qualification import _check_protocol
    from model_detect.http_client import CallResult
    case = next(c for c in protocol_cases() if c["id"] == "tools.auto")
    def response(arguments):
        return CallResult(evidence=Evidence(
            id="e",probe_id="x",url="https://example.test", response_status=200,
        ),json_body={"choices":[{"message":{"tool_calls":[{
            "function":{"name":"lookup_ticket","arguments":arguments}
        }]}}]})
    assert _check_protocol(case, response("{not json}"))[0] == "fail"
    assert _check_protocol(case, response('{"ticket_id":"wrong"}'))[0] == "fail"
    assert _check_protocol(case, response('{"ticket_id":"T-17"}'))[0] == "pass"



def test_glm53_first_party_reference_and_no_accidental_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("GLM53_OFFICIAL_KEY", "off")
    monkeypatch.setenv("GLM53_CUSTOMER_KEY", "ven")
    from typer.testing import CliRunner
    runner = CliRunner()
    command = [
        "glm53", "compare",
        "--official-url", "https://fake-vendor.example/v1",
        "--customer-url", "https://customer.example/v1",
    ]
    rejected = runner.invoke(app, command)
    assert rejected.exit_code != 0
    assert "official reference" in rejected.output
    allowed = runner.invoke(app, command + ["--allow-unverified-reference"])
    assert allowed.exit_code == 0, allowed.output
    # Refuse to replace an existing real report before any model API calls.
    output = tmp_path / "data"
    output.mkdir()
    (output / "glm53-comparison.json").write_text("existing report")
    denied = runner.invoke(app, [
        "glm53", "compare",
        "--official-url", "https://api.z.ai/api/paas/v4",
        "--customer-url", "https://customer.example/v1",
        "--output-dir", str(output), "--execute",
    ])
    assert denied.exit_code != 0
    assert (output / "glm53-comparison.json").read_text() == "existing report"



def test_complete_sse_reader_requires_done_and_retains_usage(monkeypatch):
    import httpx
    from model_detect.http_client import AuditHttpClient
    original = httpx.AsyncClient
    wire = (
        'data: {"choices":[{"delta":{"reasoning_content":"secret reasoning"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"READY"},"finish_reason":"stop"}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":23}}\n\n'
        'data: [DONE]\n\n'
    )
    transport = httpx.MockTransport(lambda req: httpx.Response(
        200, text=wire, headers={"content-type": "text/event-stream"}
    ))
    monkeypatch.setattr(
        "model_detect.http_client.httpx.AsyncClient",
        lambda **kw: original(transport=transport, **kw),
    )
    client = AuditHttpClient(
        base_url="https://api.z.ai/api/paas/v4",
        api_key="mock-key", model="glm-5.3",
    )
    response = asyncio.run(client.post_json(
        probe_id="glm53.chat.stream", path="/chat/completions",
        payload={"model":"glm-5.3","messages":[{"role":"user","content":"hi"}],
                 "stream":True},
        stream=True, stream_full=True,
    ))
    assert response.json_body["_sse_completed"] is True
    assert response.json_body["_sse_finish_reason"] == "stop"
    assert response.json_body["usage"]["prompt_tokens"] == 12
    assert "secret reasoning" not in json.dumps(response.evidence.model_dump())


def test_incomplete_sse_reader_does_not_claim_end_of_stream(monkeypatch):
    import httpx
    from model_detect.http_client import AuditHttpClient
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: httpx.Response(
        200,
        text='data: {"choices":[{"delta":{"content":"a"}}]}\n\n',
        headers={"content-type":"text/event-stream"},
    ))
    monkeypatch.setattr(
        "model_detect.http_client.httpx.AsyncClient",
        lambda **kw: original(transport=transport, **kw),
    )
    client = AuditHttpClient(
        base_url="https://api.z.ai/api/paas/v4",
        api_key="mock-key", model="glm-5.3",
    )
    response = asyncio.run(client.post_json(
        probe_id="glm53.chat.stream", path="/chat/completions",
        payload={"model":"glm-5.3","messages":[{"role":"user","content":"hi"}],
                 "stream":True},
        stream=True, stream_full=True,
    ))
    assert response.json_body["_sse_completed"] is False



def test_html_report_sanitizes_response_excerpts():
    from model_detect.glm53_qualification import render_qualification_html
    generated = render_qualification_html(
        "# 测试报告\n\n| Case | 恶意响应 |\n|---|---|\n"
        "| evidence | <script>alert(1)</script> |\n"
    )
    assert "<table>" in generated
    assert "<script>" not in generated
    assert "&lt;script&gt;" in generated
