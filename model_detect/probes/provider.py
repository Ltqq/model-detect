from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable

from ..models import Evidence, ProviderHypothesis


RULES = {
    "azure_apim": {
        "headers": {
            "apim-request-id": 0.55,
            "x-ms-request-id": 0.35,
            "x-ms-region": 0.25,
            "ocp-apim-subscription-id": 0.75,
        },
        "patterns": {
            "azure api management": 0.75,
            "apim": 0.25,
        },
    },
    "fireworks": {
        "headers": {
            "x-fireworks-request-id": 0.9,
            "fireworks-request-id": 0.9,
        },
        "patterns": {
            "fireworks": 0.8,
            "fw-kimi": 0.65,
            "fw-": 0.2,
        },
    },
    "openrouter": {
        "headers": {
            "x-openrouter": 0.8,
            "x-openrouter-version": 0.9,
        },
        "patterns": {
            "openrouter": 0.9,
        },
    },
    "together": {
        "headers": {
            "x-together-request-id": 0.9,
        },
        "patterns": {
            "together.ai": 0.9,
            "together": 0.5,
        },
    },
    "deepinfra": {
        "headers": {
            "x-deepinfra-request-id": 0.9,
        },
        "patterns": {
            "deepinfra": 0.9,
        },
    },
    "anthropic": {
        "headers": {
            "anthropic-ratelimit-requests-limit": 0.65,
            "anthropic-ratelimit-tokens-limit": 0.65,
        },
        "patterns": {
            "anthropic": 0.45,
            "claude": 0.15,
        },
    },
    "cloudflare": {
        "headers": {
            "cf-ray": 0.65,
            "cf-cache-status": 0.45,
        },
        "patterns": {
            "cloudflare": 0.6,
        },
    },
    "vllm": {
        "headers": {},
        "patterns": {
            "vllm": 0.75,
        },
    },
    "sglang": {
        "headers": {},
        "patterns": {
            "sglang": 0.8,
        },
    },
}


def _body_text(evidence: Evidence) -> str:
    try:
        return json.dumps(evidence.response_body, ensure_ascii=False, sort_keys=True).lower()
    except Exception:
        return str(evidence.response_body).lower()


def detect_provider_hypotheses(
    evidences: Iterable[Evidence],
) -> list[ProviderHypothesis]:
    scores: dict[str, float] = defaultdict(float)
    reasons: dict[str, list[str]] = defaultdict(list)

    for evidence in evidences:
        headers = {str(k).lower(): str(v) for k, v in evidence.response_headers.items()}
        body = _body_text(evidence)
        for provider, rule in RULES.items():
            for header, weight in rule["headers"].items():
                if header in headers:
                    scores[provider] += weight
                    reasons[provider].append(
                        f"{evidence.probe_id}: response header {header}"
                    )
            for pattern, weight in rule["patterns"].items():
                if pattern in body:
                    scores[provider] += weight
                    reasons[provider].append(
                        f"{evidence.probe_id}: response body contains {pattern!r}"
                    )

    out: list[ProviderHypothesis] = []
    for provider, raw_score in scores.items():
        # Multiple independent weak signals should increase confidence while remaining < 1.
        confidence = min(0.99, 1 - (0.5 ** max(raw_score, 0.01)))
        if confidence < 0.2:
            continue
        out.append(
            ProviderHypothesis(
                provider=provider,
                confidence=round(confidence, 3),
                evidence=list(dict.fromkeys(reasons[provider])),
            )
        )
    return sorted(out, key=lambda x: x.confidence, reverse=True)
