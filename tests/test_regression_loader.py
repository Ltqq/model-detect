import pytest

from model_detect.regression import load_regression_suite


def test_load_regression_suite_supports_json_and_tool_assertions(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
version: 1
suite: kimi-k3-regression
model_patterns:
  - kimi-k3
cases:
  - id: json-schema
    category: protocol
    prompt: Return JSON
    request:
      response_format:
        type: json_object
    assertions:
      - type: is-json
        schema:
          type: object
          required: [ok]
          properties:
            ok:
              type: boolean

  - id: tool-call
    category: protocol
    prompt: Use get_weather
    tools:
      - type: function
        function:
          name: get_weather
          parameters:
            type: object
            properties:
              city:
                type: string
            required: [city]
    assertions:
      - type: is-valid-openai-tools-call
""",
        encoding="utf-8",
    )

    suite = load_regression_suite(path)

    assert suite.suite == "kimi-k3-regression"
    assert len(suite.cases) == 2
    assert suite.cases[0].assertions[0].schema["required"] == ["ok"]
    assert suite.cases[1].tools[0]["function"]["name"] == "get_weather"


def test_load_regression_suite_supports_http_status_and_repeat(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
version: 1
suite: protocol-regression
model_patterns: ["*"]
cases:
  - id: invalid-field
    prompt: Reply OK
    request:
      reasoning_effor: medium
    expect:
      http_status: 400
    repeat: 3
""",
        encoding="utf-8",
    )

    suite = load_regression_suite(path)

    case = suite.cases[0]
    assert case.expect.http_status == 400
    assert case.repeat == 3


@pytest.mark.parametrize("assertion_type", ["javascript", "python"])
def test_custom_code_assertions_are_disabled_by_default(
    tmp_path,
    assertion_type,
):
    path = tmp_path / "suite.yaml"
    path.write_text(
        f"""
version: 1
suite: unsafe
model_patterns: ["*"]
cases:
  - id: unsafe
    prompt: Reply OK
    assertions:
      - type: {assertion_type}
        value: return true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="disabled by default"):
        load_regression_suite(path)

    suite = load_regression_suite(path, allow_custom_assertions=True)
    assert suite.cases[0].assertions[0].type == assertion_type


def test_regression_yaml_rejects_secrets(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
version: 1
suite: bad
model_patterns: ["*"]
api_key: sk-secret
cases:
  - id: x
    prompt: Reply OK
    assertions:
      - type: equals
        value: OK
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not contain secrets"):
        load_regression_suite(path)


def test_regression_case_ids_must_be_unique(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text(
        """
version: 1
suite: duplicate
model_patterns: ["*"]
cases:
  - id: same
    prompt: A
    assertions:
      - type: equals
        value: A
  - id: same
    prompt: B
    assertions:
      - type: equals
        value: B
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        load_regression_suite(path)
