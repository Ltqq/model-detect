from __future__ import annotations

import asyncio
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus
from ..sandbox import DockerSandbox, availability as sandbox_availability


@lru_cache(maxsize=1)
def coding_tasks() -> dict[str, list[dict[str, Any]]]:
    path = files("model_detect").joinpath("data/coding_tasks.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("tasks", {})


def extract_code(text: str, language: str) -> str:
    value = text.strip()
    aliases = {"python": ["python", "py"], "go": ["go", "golang"]}.get(language, [language])
    for alias in aliases:
        match = re.search(r"(?is)\x60\x60\x60" + re.escape(alias) + r"\s*\n(.*?)\x60\x60\x60", value)
        if match:
            return match.group(1).strip()
    match = re.search(r"(?is)\x60\x60\x60[^\n]*\n(.*?)\x60\x60\x60", value)
    return match.group(1).strip() if match else value


def _message_text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


async def run_coding_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
    auto_pull: bool = True,
) -> tuple[list[ProbeResult], list[Evidence], dict[str, Any]]:
    profile = profile.lower()
    if profile == "quick":
        return [], [], {"status": "not_run", "reason": "quick profile"}

    available = sandbox_availability()
    if not available.get("available"):
        return [
            ProbeResult(
                probe_id="capability.coding_execute",
                category="capability",
                status=ProbeStatus.SKIPPED,
                score=None,
                confidence=1.0,
                summary="Docker unavailable; untrusted generated code was not executed",
                metadata={"sandbox": available},
            )
        ], [], {"status": "unavailable", **available}

    per_language = 2 if profile == "standard" else 5
    runner = DockerSandbox(auto_pull=auto_pull)
    all_rows: list[dict[str, Any]] = []
    evidences: list[Evidence] = []
    results: list[ProbeResult] = []

    for language, tasks in coding_tasks().items():
        language_rows = []
        for task in tasks[:per_language]:
            probe_id = f"capability.coding_execute.{language}.{task['id']}"
            call = await client.post_json(
                probe_id=probe_id,
                path="/chat/completions",
                payload={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are in a code-generation benchmark. Return only requested source code.",
                        },
                        {"role": "user", "content": task["prompt"]},
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            )
            evidences.append(call.evidence)
            code = extract_code(_message_text(call.json_body), language)
            sandbox_data = None
            passed = False
            if call.evidence.response_status == 200 and code.strip():
                sandbox_files = {
                    task["filename"]: code,
                    task["test_filename"]: task["test_content"],
                }
                if language == "go":
                    sandbox_files["go.mod"] = "module modeldetectbench\n\ngo 1.24\n"
                sandbox_result = await asyncio.to_thread(
                    runner.run,
                    language=language,
                    files=sandbox_files,
                    command=list(task["command"]),
                )
                sandbox_data = sandbox_result.to_dict()
                passed = sandbox_result.passed

            row = {
                "task_id": task["id"],
                "language": language,
                "passed": passed,
                "generation_http_status": call.evidence.response_status,
                "generated_code": code[:8000],
                "sandbox": sandbox_data,
                "evidence_id": call.evidence.id,
            }
            language_rows.append(row)
            all_rows.append(row)

        passed = sum(bool(x["passed"]) for x in language_rows)
        score = passed / len(language_rows) if language_rows else None
        status = (
            ProbeStatus.INSUFFICIENT if score is None
            else ProbeStatus.PASS if score >= 0.8
            else ProbeStatus.WARN if score >= 0.5
            else ProbeStatus.FAIL
        )
        results.append(
            ProbeResult(
                probe_id=f"capability.coding_execute.{language}",
                category="capability",
                status=status,
                score=score,
                confidence=0.9,
                summary=f"{language} executable coding tasks passed {passed}/{len(language_rows)}",
                observed={"tasks": language_rows},
                evidence_ids=[x["evidence_id"] for x in language_rows],
                metadata={"capability_dimension": "coding_execute", "language": language, "sandbox": "docker"},
            )
        )

    passed_total = sum(bool(x["passed"]) for x in all_rows)
    total = len(all_rows)
    score = passed_total / total if total else None
    status = (
        ProbeStatus.INSUFFICIENT if score is None
        else ProbeStatus.PASS if score >= 0.8
        else ProbeStatus.WARN if score >= 0.5
        else ProbeStatus.FAIL
    )
    results.append(
        ProbeResult(
            probe_id="capability.coding_execute",
            category="capability",
            status=status,
            score=score,
            confidence=0.9,
            summary=f"executable coding tasks passed {passed_total}/{total}",
            observed={"tasks": all_rows},
            evidence_ids=[x["evidence_id"] for x in all_rows],
            metadata={"capability_dimension": "coding_execute", "sandbox": "docker", "profile": profile},
        )
    )
    return results, evidences, {
        "status": "completed",
        **available,
        "profile": profile,
        "tasks": total,
        "passed": passed_total,
        "auto_pull": auto_pull,
    }
