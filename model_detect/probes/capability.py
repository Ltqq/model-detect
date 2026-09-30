from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files
from typing import Any

import yaml

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus


@lru_cache(maxsize=1)
def _tasks() -> dict[str, list[dict[str, Any]]]:
    path = files("model_detect").joinpath("data/capability_lite.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("tasks", {})


def _text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content.strip() if isinstance(content, str) else ""


async def run_capability_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
) -> tuple[list[ProbeResult], list[Evidence]]:
    if profile.lower() == "quick":
        return [], []

    per_category = 2 if profile.lower() == "standard" else 5
    results: list[ProbeResult] = []
    evidences: list[Evidence] = []

    for category, tasks in _tasks().items():
        selected = tasks[:per_category]
        rows = []
        for task in selected:
            probe_id = f"capability.{category}.{task['id']}"
            call = await client.post_json(
                probe_id=probe_id,
                path="/chat/completions",
                payload={
                    "model": model,
                    "messages": [{"role": "user", "content": task["prompt"]}],
                    "temperature": 0,
                    "max_tokens": 96,
                },
            )
            evidences.append(call.evidence)
            answer = _text(call.json_body)
            try:
                matched = bool(re.fullmatch(task["pattern"], answer, flags=re.I))
            except re.error:
                matched = False
            rows.append(
                {
                    "id": task["id"],
                    "answer": answer[:500],
                    "pattern": task["pattern"],
                    "matched": matched,
                    "http_status": call.evidence.response_status,
                    "evidence_id": call.evidence.id,
                }
            )

        passed = sum(bool(x["matched"]) for x in rows)
        score = passed / len(rows) if rows else None
        if score is None:
            status = ProbeStatus.INSUFFICIENT
        elif score >= 0.8:
            status = ProbeStatus.PASS
        elif score >= 0.5:
            status = ProbeStatus.WARN
        else:
            status = ProbeStatus.FAIL
        results.append(
            ProbeResult(
                probe_id=f"capability.{category}",
                category="capability",
                status=status,
                score=score,
                confidence=0.65 if profile.lower() == "standard" else 0.8,
                summary=f"{category}: {passed}/{len(rows)} deterministic tasks passed",
                observed={"tasks": rows},
                evidence_ids=[x["evidence_id"] for x in rows],
                metadata={"capability_dimension": category},
            )
        )

    return results, evidences


def derived_capability_results(existing: list[ProbeResult]) -> list[ProbeResult]:
    by_id = {r.probe_id: r for r in existing}
    out: list[ProbeResult] = []

    tool = by_id.get("protocol.tools.basic")
    if tool:
        out.append(
            ProbeResult(
                probe_id="capability.tool_use",
                category="capability",
                status=tool.status,
                score=tool.score,
                confidence=tool.confidence,
                summary="derived from protocol.tools.basic: " + tool.summary,
                evidence_ids=tool.evidence_ids,
                metadata={"derived_from": tool.probe_id},
            )
        )

    structured = by_id.get("protocol.json_schema") or by_id.get("protocol.json_mode")
    if structured:
        out.append(
            ProbeResult(
                probe_id="capability.structured_output",
                category="capability",
                status=structured.status,
                score=structured.score,
                confidence=structured.confidence,
                summary="derived from structured-output protocol probe: " + structured.summary,
                evidence_ids=structured.evidence_ids,
                metadata={"derived_from": structured.probe_id},
            )
        )
    return out
