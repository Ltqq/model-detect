import asyncio
import re

import pytest
import yaml

from model_detect.capability_scoring import SCORER_VERSION, grade_answer
from model_detect.glm53_qualification import capability_cases, run_endpoint
from model_detect.http_client import CallResult
from model_detect.models import Evidence


@pytest.mark.parametrize(("category", "task", "pattern", "answer", "expected"), [
    ("coding", "complexity", r"^O\(log\s*n\)$", "O(log n)", True),
    ("coding", "complexity", r"^O\(log\s*n\)$", "O(n)", False),
    ("math", "algebra-1", "^8$", "x = 8", True),
    ("math", "algebra-1", "^8$", "**x = 8**", True),
    ("math", "algebra-1", "^8$", "x=9", False),
    ("math", "algebra-1", "^8$", "x = 8 or x = 9", False),
    ("math", "fraction-1", "^11/8$", "**11/8**", True),
    ("math", "fraction-1", "^11/8$", "**10/8**", False),
    ("reasoning", "conditional-1", "^NO$", "**NO**", True),
    ("reasoning", "conditional-1", "^NO$", "**YES**", False),
    ("reasoning", "conditional-1", "^NO$", "**NO** however YES", False),
])
def test_conservative_format_scoring(category, task, pattern, answer, expected):
    grade = grade_answer(
        category=category, task_id=task, pattern=pattern, answer=answer
    )
    assert grade.matched is expected


def test_bigo_regex_matches_expected_complexity_in_published_yaml():
    from importlib.resources import files
    raw = yaml.safe_load(
        files("model_detect").joinpath("data/capability_lite.yaml").read_text(
            encoding="utf-8"
        )
    )
    for cat, tasks in raw["tasks"].items():
        for task in tasks:
            re.compile(task["pattern"])
    complexity = next(
        x for x in raw["tasks"]["coding"] if x["id"] == "complexity"
    )
    assert re.fullmatch(complexity["pattern"], "O(log n)") is not None


def test_glm53_live_derived_answers_share_generic_scorer(monkeypatch):
    cases = [c for c in capability_cases("standard")
             if c["id"] in {
                 "math.algebra-1", "math.fraction-1",
                 "reasoning.conditional-1", "coding.complexity",
             }]
    answers = {
        "math.algebra-1": "**x = 8**",
        "math.fraction-1": "**11/8**",
        "reasoning.conditional-1": "**NO**",
        "coding.complexity": "O(log n)",
    }

    async def fake_post(self, *, probe_id, payload, **kwargs):
        case_id = probe_id.removeprefix("glm53.")
        return CallResult(
            evidence=Evidence(
                id="safe", probe_id=probe_id,
                url="https://example.test/chat/completions",
                response_status=200,
            ),
            json_body={"choices": [{
                "finish_reason": "stop",
                "message": {"content": answers[case_id]},
            }]},
        )

    monkeypatch.setattr(
        "model_detect.glm53_qualification.AuditHttpClient.post_json",
        fake_post,
    )
    rows = asyncio.run(run_endpoint(
        base_url="https://example.test/v1", api_key="local-fixture",
        cases=cases, runs=1, label="official",
    ))
    assert len(rows) == 4
    assert all(row["status"] == "pass" for row in rows)
    assert all(row["scorer_version"] == SCORER_VERSION for row in rows)
    assert next(x for x in rows if x["id"] == "math.algebra-1")[
        "normalized_answer_excerpt"
    ] == "8"
    assert all("local-fixture" not in str(row) for row in rows)
