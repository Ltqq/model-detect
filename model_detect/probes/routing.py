from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from ..http_client import AuditHttpClient
from ..models import Evidence, ProbeResult, ProbeStatus


def _text(body: Any) -> str:
    try:
        content = body["choices"][0]["message"].get("content")
    except Exception:
        return ""
    return content if isinstance(content, str) else ""


def _response_signature(body: Any) -> str:
    if not isinstance(body, dict):
        return "non-json"
    keys = sorted(body.keys())
    choices = body.get("choices")
    choice_keys = []
    message_keys = []
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice_keys = sorted(choices[0].keys())
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            message_keys = sorted(msg.keys())
    return json.dumps(
        {"top": keys, "choice": choice_keys, "message": message_keys},
        sort_keys=True,
    )


def _id_prefix(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^([A-Za-z_-]+)", value)
    return match.group(1) if match else None


async def run_routing_suite(
    client: AuditHttpClient,
    model: str,
    *,
    profile: str,
) -> tuple[list[ProbeResult], list[Evidence]]:
    if profile.lower() == "quick":
        return [], []
    repeats = 4 if profile.lower() == "standard" else 10
    evidences: list[Evidence] = []
    rows = []
    for i in range(repeats):
        call = await client.post_json(
            probe_id="routing.repeat.same_probe",
            path="/chat/completions",
            payload={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Answer only the integer result of 37 + 58.",
                    }
                ],
                "temperature": 0,
                "max_tokens": 16,
            },
        )
        evidences.append(call.evidence)
        body = call.json_body if isinstance(call.json_body, dict) else {}
        choice = None
        if isinstance(body.get("choices"), list) and body["choices"]:
            choice = body["choices"][0]
        rows.append(
            {
                "status": call.evidence.response_status,
                "model": body.get("model"),
                "id_prefix": _id_prefix(body.get("id")),
                "signature": _response_signature(body),
                "answer": _text(body).strip(),
                "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
            }
        )

    model_values = sorted({str(x["model"]) for x in rows if x["model"]})
    signatures = sorted({x["signature"] for x in rows})
    id_prefixes = sorted({x["id_prefix"] for x in rows if x["id_prefix"]})
    answers = [x["answer"] for x in rows if x["answer"]]
    correct = sum(x == "95" for x in answers)
    distinct_answers = len(set(answers))

    flags = []
    if len(model_values) > 1:
        flags.append("model field changed")
    if len(signatures) > 1:
        flags.append("response schema changed")
    if len(id_prefixes) > 1:
        flags.append("response id prefix changed")
    if distinct_answers > 2:
        flags.append("temperature=0 answer was unusually unstable")

    if len(model_values) > 1:
        status = ProbeStatus.FAIL
        score = 0.0
        verdict = "mixed-routing-likely"
    elif flags:
        status = ProbeStatus.WARN
        score = 0.6
        verdict = "suspicious"
    elif len(answers) >= max(2, repeats // 2):
        status = ProbeStatus.PASS
        score = 1.0
        verdict = "stable"
    else:
        status = ProbeStatus.INSUFFICIENT
        score = None
        verdict = "insufficient"

    results = [
        ProbeResult(
            probe_id="routing.repeat.same_probe",
            category="routing",
            status=status,
            score=score,
            confidence=0.85 if repeats >= 8 else 0.7,
            summary=(
                f"routing verdict={verdict}"
                + (f"; {', '.join(flags)}" if flags else "")
            ),
            observed={
                "repeats": repeats,
                "models": model_values,
                "id_prefixes": id_prefixes,
                "signature_count": len(signatures),
                "answer_count": len(answers),
                "distinct_answers": distinct_answers,
                "correct_answers": correct,
                "rows": rows,
            },
            evidence_ids=[e.id for e in evidences],
            metadata={"verdict": verdict},
        )
    ]

    if profile.lower() == "deep":
        # A simple quality-inversion check: a trivial deterministic task should not
        # systematically fail while a harder deterministic task succeeds.
        pairs = [
            ("simple", "What is 2 + 2? Answer only the integer.", "4"),
            (
                "complex",
                "If a train travels 60 km in 45 minutes at constant speed, how many km does it travel in 2 hours? Answer only the integer.",
                "160",
            ),
        ]
        pair_rows = {}
        pair_evs = []
        for label, prompt, expected in pairs:
            outs = []
            for _ in range(3):
                call = await client.post_json(
                    probe_id="routing.quality_inversion",
                    path="/chat/completions",
                    payload={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 32,
                    },
                )
                pair_evs.append(call.evidence)
                outs.append(_text(call.json_body).strip())
            pair_rows[label] = {
                "outputs": outs,
                "expected": expected,
                "pass_count": sum(x == expected for x in outs),
            }
        simple_pass = pair_rows["simple"]["pass_count"]
        complex_pass = pair_rows["complex"]["pass_count"]
        inversion = simple_pass == 0 and complex_pass >= 2
        results.append(
            ProbeResult(
                probe_id="routing.quality_inversion",
                category="routing",
                status=ProbeStatus.WARN if inversion else ProbeStatus.PASS,
                score=0.5 if inversion else 1.0,
                confidence=0.55,
                summary=(
                    "quality inversion observed; mixed routing is possible"
                    if inversion
                    else "no quality inversion observed"
                ),
                observed=pair_rows,
                evidence_ids=[e.id for e in pair_evs],
                metadata={"quality_inversion": inversion},
            )
        )
        evidences.extend(pair_evs)

    return results, evidences
