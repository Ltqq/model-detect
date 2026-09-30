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
    assert sum(len(v) for v in tasks.values()) >= 25
    for category, items in tasks.items():
        for item in items:
            assert item["id"]
            assert item["prompt"]
            re.compile(item["pattern"])
