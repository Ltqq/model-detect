import json

from model_detect.glm53_benchmark import _classify_benchmark_failure


def test_failure_categories_are_specific_and_do_not_echo_exception_message():
    samples = [
        (FileNotFoundError("sk-SECRET"), "framework_dependency_missing"),
        (ImportError("sk-SECRET"), "framework_dependency_missing"),
        (json.JSONDecodeError("sk-SECRET", "x", 0), "result_parse_error"),
        (TimeoutError("sk-SECRET"), "execution_timeout"),
        (ValueError("sk-SECRET"), "result_incomplete_or_invalid"),
        (RuntimeError("sk-SECRET"), "subprocess_nonzero_or_execution_error"),
        (Exception("sk-SECRET"), "unexpected_framework_error"),
    ]
    for error, expected in samples:
        classified = _classify_benchmark_failure(error)
        assert classified == expected
        assert "SECRET" not in classified
