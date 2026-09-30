import asyncio
import json
from unittest.mock import patch

from model_detect.config import AuditConfig
from model_detect.models import AuditTarget, ProbeStatus
from model_detect.probes.coding import coding_tasks, extract_code, run_coding_suite
from model_detect.http_client import CallResult
from model_detect.models import Evidence
from model_detect.sandbox import DockerSandbox, SandboxLimits, SandboxResult, _redact_mount_source


class NoCallClient:
    async def post_json(self, **kwargs):
        raise AssertionError("HTTP client should not be called when Docker is unavailable")


def test_extract_code_prefers_language_fence():
    text = "before\n" + chr(96)*3 + "python\ndef f():\n    return 1\n" + chr(96)*3
    assert extract_code(text, "python") == "def f():\n    return 1"


def test_coding_task_counts():
    tasks = coding_tasks()
    assert len(tasks["python"]) >= 5
    assert len(tasks["go"]) >= 5
    assert sum(len(items) for items in tasks.values()) >= 10
    for language, items in tasks.items():
        for item in items:
            assert item["filename"]
            assert item["test_filename"]
            assert item["test_content"]
            assert item["command"]


def test_coding_sandbox_default_is_explicitly_disabled():
    cfg = AuditConfig(
        target=AuditTarget(base_url="https://example.com/v1", model="m")
    )
    assert cfg.coding_sandbox_enabled is False


def test_docker_command_contains_security_controls(tmp_path):
    runner = DockerSandbox(
        limits=SandboxLimits(
            memory="128m",
            cpus="0.5",
            pids_limit=32,
            timeout_seconds=5,
        ),
        auto_pull=False,
    )
    runner.binary = "/usr/bin/docker"
    command = runner._docker_command(
        container_name="model-detect-test",
        workspace=tmp_path,
        image="python:3.12-alpine",
        command=["python", "/workspace/test_solution.py"],
        language="python",
    )
    joined = " ".join(command)
    assert "--network none" in joined
    assert "--read-only" in command
    assert "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges" in joined
    assert "--user 65534:65534" in joined
    assert "--memory 128m" in joined
    assert "--cpus 0.5" in joined
    assert "--pids-limit 32" in joined
    assert "type=bind,src=" in joined
    assert "readonly" in joined
    assert "--privileged" not in command


def test_redacted_sandbox_command_hides_host_workspace():
    command = [
        "docker",
        "run",
        "--mount",
        "type=bind,src=/home/user/private/path,dst=/workspace,readonly",
    ]
    got = _redact_mount_source(command)
    assert "/home/user/private/path" not in " ".join(got)
    assert "src=<temporary-workspace>" in " ".join(got)


def test_coding_suite_skips_without_docker():
    with patch(
        "model_detect.probes.coding.sandbox_availability",
        return_value={"available": False, "binary": None},
    ):
        results, evidence, meta = asyncio.run(
            run_coding_suite(
                NoCallClient(),
                "m",
                profile="standard",
            )
        )
    assert results[0].status == ProbeStatus.SKIPPED
    assert evidence == []
    assert meta["status"] == "unavailable"


class GeneratedCodeClient:
    def __init__(self):
        self.count = 0

    async def post_json(self, **kwargs):
        self.count += 1
        prompt = kwargs["payload"]["messages"][-1]["content"]
        if "Python" in prompt or "def " in prompt:
            code = "def sum_even(numbers):\n    return sum(x for x in numbers if x % 2 == 0)"
        else:
            code = "package main\nfunc SumEven(numbers []int) int { total := 0; for _, x := range numbers { if x%2==0 { total += x } }; return total }"
        body = {"choices": [{"message": {"content": code}, "finish_reason": "stop"}]}
        return CallResult(
            evidence=Evidence(
                id=f"ev_gen_{self.count}",
                probe_id="coding",
                url="https://example.com/v1/chat/completions",
                response_status=200,
                response_body=body,
            ),
            json_body=body,
            text_body=json.dumps(body),
        )


class AlwaysPassRunner:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return SandboxResult(
            status="pass",
            exit_code=0,
            stdout="OK",
            image="test-image",
        )


def test_standard_coding_suite_runs_two_tasks_per_language():
    runner = AlwaysPassRunner()
    client = GeneratedCodeClient()
    with patch(
        "model_detect.probes.coding.sandbox_availability",
        return_value={"available": True, "binary": "docker"},
    ), patch(
        "model_detect.probes.coding.DockerSandbox",
        return_value=runner,
    ):
        results, evidence, meta = asyncio.run(
            run_coding_suite(client, "m", profile="standard")
        )
    assert meta["tasks"] == 4
    assert meta["passed"] == 4
    assert client.count == 4
    assert len(evidence) == 4
    assert next(x for x in results if x.probe_id == "capability.coding_execute").score == 1.0
    go_calls = [x for x in runner.calls if x["language"] == "go"]
    assert len(go_calls) == 2
    assert all("go.mod" in x["files"] for x in go_calls)
