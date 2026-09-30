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

    per_category = 3 if profile.lower() == "standard" else None
    results: list[ProbeResult] = []
    evidences: list[Evidence] = []

    for category, tasks in _tasks().items():
        selected = tasks[:per_category] if per_category is not None else list(tasks)
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


def _aggregate_dimension(
    existing: list[ProbeResult],
    *,
    probe_id: str,
    source_ids: list[str],
    label: str,
) -> ProbeResult | None:
    by_id = {r.probe_id: r for r in existing}
    sources = [by_id[x] for x in source_ids if x in by_id]
    scored = [r for r in sources if r.score is not None]
    if not sources:
        return None
    if scored:
        score = sum(float(r.score) for r in scored) / len(scored)
        if score >= 0.8:
            status = ProbeStatus.PASS
        elif score >= 0.5:
            status = ProbeStatus.WARN
        else:
            status = ProbeStatus.FAIL
    else:
        score = None
        status = ProbeStatus.INSUFFICIENT

    evidence_ids = []
    for source in sources:
        evidence_ids.extend(source.evidence_ids)

    return ProbeResult(
        probe_id=probe_id,
        category="capability",
        status=status,
        score=score,
        confidence=min(
            0.95,
            sum(source.confidence for source in sources) / len(sources),
        ),
        summary=(
            f"{label}: aggregated {len(sources)} scenario probes"
            + (f", score={score:.2f}" if score is not None else "")
        ),
        observed={
            "sources": [
                {
                    "probe_id": source.probe_id,
                    "status": source.status.value,
                    "score": source.score,
                    "summary": source.summary,
                }
                for source in sources
            ]
        },
        evidence_ids=list(dict.fromkeys(evidence_ids)),
        metadata={
            "capability_dimension": label,
            "derived_from": [source.probe_id for source in sources],
            "aggregation": "mean-of-available-scores",
        },
    )


def derived_capability_results(existing: list[ProbeResult]) -> list[ProbeResult]:
    out: list[ProbeResult] = []

    tool = _aggregate_dimension(
        existing,
        probe_id="capability.tool_use",
        label="tool_use",
        source_ids=[
            "protocol.tools.basic",
            "protocol.tools.arguments_schema",
            "protocol.tools.tool_choice",
            "protocol.tools.parallel",
            "integrity.tool_definitions",
            "integrity.tools.preserved",
        ],
    )
    if tool:
        out.append(tool)

    structured = _aggregate_dimension(
        existing,
        probe_id="capability.structured_output",
        label="structured_output",
        source_ids=[
            "protocol.json_mode",
            "protocol.json_schema",
            "integrity.json_schema.preserved",
        ],
    )
    if structured:
        out.append(structured)

    return out
