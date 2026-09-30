from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import ProbeResult, ProbeStatus


def _rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("results")
    if isinstance(raw, dict):
        nested = raw.get("results")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    raise ValueError("promptfoo result JSON does not contain a result row list")


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    test_case = row.get("testCase")
    if not isinstance(test_case, dict):
        return {}
    metadata = test_case.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_.") or "unknown"


def _row_passed(row: dict[str, Any]) -> bool | None:
    grading = row.get("gradingResult")
    if isinstance(grading, dict) and isinstance(grading.get("pass"), bool):
        return bool(grading["pass"])
    if isinstance(row.get("success"), bool):
        return bool(row["success"])
    return None


def _row_score(row: dict[str, Any]) -> float | None:
    candidates = [row.get("score")]
    grading = row.get("gradingResult")
    if isinstance(grading, dict):
        candidates.append(grading.get("score"))
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numeric = float(value)
            if 0.0 <= numeric <= 1.0:
                return numeric
    return None


def _response(row: dict[str, Any]) -> dict[str, Any]:
    response = row.get("response")
    if not isinstance(response, dict):
        response = row.get("providerResponse")
    return response if isinstance(response, dict) else {}


def _compact_output(value: Any, limit: int = 1200) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:limit]
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return text[:limit]


def parse_promptfoo_payload(
    data: dict[str, Any],
    *,
    source_path: str | None = None,
) -> list[ProbeResult]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in _rows(data):
        metadata = _metadata(row)
        suite = metadata.get("model_detect_suite")
        case_id = metadata.get("model_detect_case_id")
        category = metadata.get("model_detect_category")
        if not all(
            isinstance(value, str) and value
            for value in (suite, case_id, category)
        ):
            continue
        grouped[(suite, case_id, category)].append(row)

    if not grouped:
        raise ValueError(
            "promptfoo result JSON contains no model-detect regression metadata"
        )

    results: list[ProbeResult] = []
    for (suite, case_id, category), rows in sorted(grouped.items()):
        pass_count = 0
        fail_count = 0
        unknown_count = 0
        error_count = 0
        numeric_scores: list[float] = []
        observed_rows: list[dict[str, Any]] = []

        for row in rows:
            passed = _row_passed(row)
            error = row.get("error")
            if error:
                error_count += 1
            if passed is True:
                pass_count += 1
            elif passed is False:
                fail_count += 1
            else:
                unknown_count += 1

            score_value = _row_score(row)
            if score_value is not None:
                numeric_scores.append(score_value)

            grading = row.get("gradingResult")
            grading = grading if isinstance(grading, dict) else {}
            response = _response(row)
            provider = row.get("provider")
            provider = provider if isinstance(provider, dict) else {}

            observed_rows.append(
                {
                    "success": passed,
                    "score": score_value,
                    "reason": grading.get("reason"),
                    "assertion": grading.get("assertion"),
                    "output": _compact_output(response.get("output")),
                    "provider_id": provider.get("id"),
                    "error": _compact_output(error, 600),
                }
            )

        total = len(rows)
        if error_count == total:
            status = ProbeStatus.ERROR
        elif pass_count == total:
            status = ProbeStatus.PASS
        elif pass_count == 0 and (fail_count > 0 or error_count > 0):
            status = ProbeStatus.FAIL
        elif pass_count > 0:
            status = ProbeStatus.WARN
        else:
            status = ProbeStatus.INSUFFICIENT

        if numeric_scores:
            score_value = sum(numeric_scores) / len(numeric_scores)
        elif total and (pass_count or fail_count):
            score_value = pass_count / total
        else:
            score_value = None

        results.append(
            ProbeResult(
                probe_id=(
                    f"regression.{_safe_id(suite)}.{_safe_id(case_id)}"
                ),
                category=category,
                status=status,
                score=(
                    round(score_value, 4)
                    if score_value is not None
                    else None
                ),
                confidence=(
                    0.95
                    if status != ProbeStatus.INSUFFICIENT
                    else 0.5
                ),
                summary=(
                    f"promptfoo regression {case_id}: "
                    f"{pass_count}/{total} runs passed"
                ),
                observed={
                    "total": total,
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "error_count": error_count,
                    "unknown_count": unknown_count,
                    "runs": observed_rows,
                },
                metadata={
                    "engine": "promptfoo",
                    "suite": suite,
                    "case_id": case_id,
                    "artifact_path": source_path,
                    "regression_only": True,
                    "identity_strength": "none",
                },
            )
        )

    return results


def parse_promptfoo_file(path: str | Path) -> list[ProbeResult]:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("promptfoo result JSON root must be an object")
    return parse_promptfoo_payload(raw, source_path=str(source))
