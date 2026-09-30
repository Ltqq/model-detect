from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_reports(old_path: str | Path, new_path: str | Path) -> dict[str, Any]:
    old = _load(old_path)
    new = _load(new_path)

    old_scores = (old.get("summary") or {}).get("category_scores") or {}
    new_scores = (new.get("summary") or {}).get("category_scores") or {}
    categories = sorted(set(old_scores) | set(new_scores))
    score_deltas = {
        key: {
            "old": old_scores.get(key),
            "new": new_scores.get(key),
            "delta": (
                round(float(new_scores[key]) - float(old_scores[key]), 2)
                if key in old_scores and key in new_scores
                else None
            ),
        }
        for key in categories
    }

    def result_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(item.get("probe_id")): item
            for item in (report.get("results") or [])
            if item.get("probe_id")
        }

    old_results = result_map(old)
    new_results = result_map(new)
    probe_changes = []
    for key in sorted(set(old_results) | set(new_results)):
        a = old_results.get(key)
        b = new_results.get(key)
        a_status = a.get("status") if a else None
        b_status = b.get("status") if b else None
        a_score = a.get("score") if a else None
        b_score = b.get("score") if b else None
        if a_status != b_status or a_score != b_score:
            probe_changes.append(
                {
                    "probe_id": key,
                    "old_status": a_status,
                    "new_status": b_status,
                    "old_score": a_score,
                    "new_score": b_score,
                }
            )

    def providers(report: dict[str, Any]) -> dict[str, float]:
        out = {}
        for item in report.get("provider_hypotheses") or []:
            name = str(item.get("provider") or "")
            if name:
                try:
                    out[name] = float(item.get("confidence") or 0)
                except Exception:
                    out[name] = 0.0
        return out

    old_providers = providers(old)
    new_providers = providers(new)

    return {
        "old": {
            "path": str(old_path),
            "model": (old.get("target") or {}).get("model"),
            "verdict": (old.get("summary") or {}).get("final_verdict"),
            "overall_score": (old.get("summary") or {}).get("overall_score"),
        },
        "new": {
            "path": str(new_path),
            "model": (new.get("target") or {}).get("model"),
            "verdict": (new.get("summary") or {}).get("final_verdict"),
            "overall_score": (new.get("summary") or {}).get("overall_score"),
        },
        "category_deltas": score_deltas,
        "probe_changes": probe_changes,
        "provider_changes": {
            "old": old_providers,
            "new": new_providers,
            "added": sorted(set(new_providers) - set(old_providers)),
            "removed": sorted(set(old_providers) - set(new_providers)),
        },
    }
