"""Conservative deterministic grading shared by generic and model suites.

This is format normalization for objectively specified tasks, not an LLM judge.
Do not normalize away negation, unrelated text, alternative numbers or units.
"""

from __future__ import annotations

import re
from typing import NamedTuple


SCORER_VERSION = "capability-scorer-v2"
_ALGEBRA_TASKS = {"math.algebra-1", "math.algebra-2"}
_EQUATION_RE = re.compile(r"^[xX]\s*=\s*(-?\d+(?:\.\d+)?)$")


class Grade(NamedTuple):
    matched: bool
    normalized_answer: str
    normalization: str


def grade_answer(
    *,
    category: str,
    task_id: str,
    pattern: str,
    answer: str,
) -> Grade:
    original = answer.strip()
    normalized = original
    applied = []
    # Only exact outer Markdown bold wrappers are considered formatting.
    for marker in ("**", "__"):
        if (normalized.startswith(marker) and normalized.endswith(marker)
                and len(normalized) > 2 * len(marker)):
            normalized = normalized[len(marker):-len(marker)].strip()
            applied.append("markdown-emphasis")
            break
    if f"{category}.{task_id}" in _ALGEBRA_TASKS:
        found = _EQUATION_RE.fullmatch(normalized)
        if found:
            normalized = found.group(1)
            applied.append("simple-x-equation")
    try:
        matched = re.fullmatch(pattern, normalized, flags=re.I) is not None
    except re.error:
        matched = False
    return Grade(matched, normalized, "+".join(applied) if applied else "none")
