import re

from model_detect.probes.capability import _tasks


def test_capability_lite_dataset_is_valid():
    tasks = _tasks()
    assert set(tasks) >= {
        "reasoning",
        "math",
        "coding",
        "chinese",
        "instruction_following",
    }
    assert sum(len(v) for v in tasks.values()) >= 90
    assert len(tasks["reasoning"]) >= 20
    assert len(tasks["math"]) >= 20
    assert len(tasks["coding"]) >= 10
    assert len(tasks["chinese"]) >= 20
    assert len(tasks["instruction_following"]) >= 20
    for category, items in tasks.items():
        for item in items:
            assert item["id"]
            assert item["prompt"]
            re.compile(item["pattern"])
