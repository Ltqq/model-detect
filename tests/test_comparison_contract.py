from model_detect.baseline import aggregate_baseline_reports
from model_detect.comparison_contract import build_dimension_contracts
from model_detect.comparison import compare_report_to_baseline
from model_detect.models import AuditReport, AuditSummary, Evidence, ProbeResult, ProbeStatus


def native_report(*, temperature=0, prompt="固定测试题", order=("a", "b")):
    return AuditReport(
        target={"base_url": "https://supplier.example/v1", "model": "kimi-k3"},
        profile="standard",
        results=[
            ProbeResult(
                probe_id="capability.reasoning", category="capability",
                score=1.0, status=ProbeStatus.PASS, summary="2/2",
                evidence_ids=["a", "b"],
                observed={"tasks": [{"id": name, "matched": True} for name in order]},
            )
        ],
        evidences=[
            Evidence(
                id=task_id, probe_id=f"capability.reasoning.{task_id}",
                url="https://supplier.example/v1/chat/completions",
                request_headers={"Authorization": "Bearer secret"},
                request_body={
                    "model": "kimi-k3",
                    "messages": [{"role": "user", "content": f"{prompt}-{task_id}"}],
                    "temperature": temperature, "max_tokens": 96,
                },
            )
            for task_id in ("a", "b")
        ],
        summary=AuditSummary(),
    )


def benchmark_report(
    *,
    dataset_version=2,
    harness_version="0.4.8",
    limit=25,
    benchmark_profile="standard",
    task="gsm8k",
    metric="exact_match,flexible-extract",
):
    return AuditReport(
        target={"base_url": "https://supplier.example/v1", "model": "kimi-k3"},
        profile="standard",
        results=[
            ProbeResult(
                probe_id=f"capability.external.lm_eval.{task}",
                category="capability", status=ProbeStatus.PASS,
                score=0.86, summary="benchmark score",
                observed={"version": dataset_version, "task": task},
                metadata={
                    "engine": "lm-evaluation-harness", "task": task,
                    "benchmark_profile": benchmark_profile,
                    "benchmark_limit": limit,
                    "benchmark_harness_version": harness_version,
                    "primary_metric": metric,
                    "benchmark_task_metadata": {"dimension": "math"},
                    "benchmark_model_type": "local-chat-completions",
                    "benchmark_apply_chat_template": True,
                    "benchmark_num_fewshot": "task-default",
                    "benchmark_run_config": {"num_concurrent": 1},
                },
            )
        ],
    )


def test_native_contract_tracks_prompts_and_sampling_without_exposing_text():
    first = build_dimension_contracts(native_report())
    changed_prompt = build_dimension_contracts(native_report(prompt="替换题目"))
    changed_param = build_dimension_contracts(native_report(temperature=1))
    changed_order = build_dimension_contracts(native_report(order=("b", "a")))
    assert first["reasoning"]["sha256"] != changed_prompt["reasoning"]["sha256"]
    assert first["reasoning"]["sha256"] != changed_param["reasoning"]["sha256"]
    assert first["reasoning"]["sha256"] != changed_order["reasoning"]["sha256"]
    assert "secret" not in str(first)
    assert "固定测试题" not in str(first)
    assert len(first["reasoning"]["sha256"]) == 64


def test_baseline_repeated_runs_refuse_mixed_inputs():
    baseline = aggregate_baseline_reports([
        native_report(), native_report(temperature=1), native_report()
    ])
    assert "reasoning" in baseline.incompatible_dimensions
    assert "reasoning" not in baseline.dimension_contracts
    comparison, _ = compare_report_to_baseline(native_report(), baseline)
    assert comparison.verdict == "baseline_insufficient"


def test_benchmark_contract_includes_harness_dataset_metric_and_limit():
    valid = build_dimension_contracts(benchmark_report())["benchmark:gsm8k"]
    changes = [
        benchmark_report(dataset_version=3),
        benchmark_report(harness_version="0.5.0"),
        benchmark_report(limit=100),
        benchmark_report(benchmark_profile="deep"),
        benchmark_report(metric="exact_match,strict-match"),
    ]
    for report in changes:
        current = build_dimension_contracts(report)["benchmark:gsm8k"]
        assert current["sha256"] != valid["sha256"]


def test_same_benchmark_profile_can_compare_and_mismatch_is_blocked():
    baseline = aggregate_baseline_reports([
        benchmark_report(), benchmark_report(), benchmark_report(),
    ])
    assert baseline.dimension_contracts["benchmark:gsm8k"]["kind"] == "benchmark"
    same, _ = compare_report_to_baseline(benchmark_report(), baseline)
    assert same.verdict == "baseline_match"
    mismatch, _ = compare_report_to_baseline(
        benchmark_report(dataset_version=3), baseline
    )
    assert mismatch.verdict == "baseline_insufficient"
    assert mismatch.dimensions["benchmark:gsm8k"].verdict == "incomparable"


def test_unknown_benchmark_provenance_is_not_comparable():
    report = benchmark_report(dataset_version=None)
    assert "benchmark:gsm8k" not in build_dimension_contracts(report)
