from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable

import yaml

from ..models import Evidence, ProviderHypothesis


@lru_cache(maxsize=1)
def load_provider_rules() -> dict[str, Any]:
    path = files("model_detect").joinpath("data/providers.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw.get("providers", {})


def _body_text(evidence: Evidence) -> str:
    try:
        return json.dumps(evidence.response_body, ensure_ascii=False, sort_keys=True).lower()
    except Exception:
        return str(evidence.response_body).lower()


def detect_provider_hypotheses(
    evidences: Iterable[Evidence],
) -> list[ProviderHypothesis]:
    rules = load_provider_rules()
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, list[str]] = defaultdict(list)

    for evidence in evidences:
        headers = {str(k).lower(): str(v) for k, v in evidence.response_headers.items()}
        body = _body_text(evidence)
        for provider, rule in rules.items():
            for header, weight in (rule.get("headers") or {}).items():
                if str(header).lower() in headers:
                    scores[provider] += float(weight)
                    reasons[provider].append(
                        f"{evidence.probe_id}: response header {header}"
                    )
            for pattern, weight in (rule.get("patterns") or {}).items():
                if str(pattern).lower() in body:
                    scores[provider] += float(weight)
                    reasons[provider].append(
                        f"{evidence.probe_id}: response body contains {pattern!r}"
                    )

    out: list[ProviderHypothesis] = []
    for provider, raw_score in scores.items():
        confidence = min(0.99, 1 - (0.5 ** max(raw_score, 0.01)))
        if confidence < 0.2:
            continue
        label = str((rules.get(provider) or {}).get("label") or provider)
        out.append(
            ProviderHypothesis(
                provider=label,
                confidence=round(confidence, 3),
                evidence=list(dict.fromkeys(reasons[provider])),
            )
        )
    return sorted(out, key=lambda x: x.confidence, reverse=True)
