from model_detect.probes.protocol import DEEP_PROBES, QUICK_PROBES, STANDARD_PROBES


def names(items):
    return {fn.__name__ for fn in items}


def test_profiles_are_incremental():
    quick = names(QUICK_PROBES)
    standard = names(STANDARD_PROBES)
    deep = names(DEEP_PROBES)

    assert quick < standard
    assert standard < deep
    assert "probe_json_schema" in standard
    assert "probe_reasoning_valid" in standard
    assert "probe_tools_parallel" in deep
