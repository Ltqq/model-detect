"""Homepage contract: normal users see one audit task before optional internals."""

from importlib.resources import files


def test_task_first_homepage_keeps_main_js_contract_and_collapses_advanced():
    html = files("model_detect").joinpath("templates/index.html").read_text(encoding="utf-8")
    assert html.index('id="audit-start"') < html.index('id="advanced-compare"')
    assert html.index('id="audit-start"') < html.index('id="history-list"')
    assert html.index('id="profile"') < html.index('id="reference_id"')
    assert '<option value="quick" selected>' in html
    for control in ("base_url", "api_key", "model", "profile", "run",
                    "reference_id", "context_tokens", "benchmark_profile",
                    "compare_run", "jobs"):
        assert f'id="{control}"' in html
    assert '<details class="card secondary-panel" id="advanced-compare">' in html
    assert 'id="reference_id"' in html.split('<details class="advanced">', 1)[1]
    assert html.count("<details") == html.count("</details>")
