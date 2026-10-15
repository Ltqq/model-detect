from __future__ import annotations

import hashlib
import html
import json
import math
import statistics
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml

from .capability_scoring import SCORER_VERSION, grade_answer
from .http_client import AuditHttpClient
from .usage_meter import usage_from_response


Mode = Literal["all", "protocol", "capability"]
CapabilityProfile = Literal["smoke", "standard"]

# Stable test selection and exact payloads are part of this versioned suite.
SUITE_VERSION = "glm53-customer-v1"
ABILITY_CATEGORIES = ("reasoning", "math", "coding", "chinese", "instruction_following")
_PROTOCOL_TOKENS = 1024
_ABILITY_TOKENS = 2048


def normalize_base_url(value: str) -> str:
    """Do not append /v1: official Z.ai URLs use /api/paas/v4."""
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("base URL must not contain query, fragment, or credentials")
    if raw.endswith("/chat/completions"):
        raw = raw[: -len("/chat/completions")]
    return raw


def _base_messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "仅回答 READY，其他内容不要输出。"}]


def protocol_cases() -> list[dict[str, Any]]:
    def body(messages=None, **kw):
        return {
            "model": "glm-5.3",
            "messages": messages if messages is not None else _base_messages(),
            "max_tokens": _PROTOCOL_TOKENS,
            "temperature": 1.0,
            **kw,
        }

    tool = {
        "type": "function",
        "function": {
            "name": "lookup_ticket",
            "description": "查询工单编号并返回其状态",
            "parameters": {
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
        },
    }
    cases = [
        ("chat.basic", "基础对话与 Usage", body(), "chat", "required"),
        (
            "thinking.enabled", "启用思考",
            body(thinking={"type": "enabled"}), "chat", "required",
        ),
        (
            "thinking.disabled", "拒绝关闭思考",
            body(thinking={"type": "disabled"}), "reject", "required",
        ),
    ]
    for effort in ("low", "high", "max"):
        cases.append((
            f"reasoning.{effort}", f"推理等级 {effort} 参数接收",
            body(thinking={"type": "enabled"}, reasoning_effort=effort),
            "chat", "required",
        ))
    cases.extend([
        (
            "chat.stream", "流式 SSE",
            body(stream=True, thinking={"type": "enabled"}), "stream", "required",
        ),
        (
            "tools.auto", "自动工具调用",
            body(
                messages=[{"role": "user", "content": "请调用 lookup_ticket 查询工单 T-17。"}],
                tools=[tool], tool_choice="auto",
                thinking={"type": "enabled"}, reasoning_effort="low",
            ),
            "tools", "required",
        ),
        (
            "json.object", "JSON 对象输出",
            body(
                messages=[{"role": "user", "content": '只输出 JSON 对象，内容是 {"ok":true}。'}],
                response_format={"type": "json_object"},
                thinking={"type": "enabled"}, reasoning_effort="low",
            ),
            "json", "required",
        ),
        (
            "chat.multiturn", "多轮上下文",
            body(
                messages=[
                    {"role": "user", "content": "请记住代号是阿林。"},
                    {"role": "assistant", "content": "好的，已记住。"},
                    {"role": "user", "content": "刚才给出的代号是什么？只回答代号。"},
                ],
                thinking={"type": "enabled"}, reasoning_effort="low",
            ),
            "multiturn", "required",
        ),
    ])
    return [
        {"id": case_id, "label": label, "payload": payload,
         "check": check, "authority": authority}
        for case_id, label, payload, check, authority in cases
    ]


def capability_cases(profile: CapabilityProfile) -> list[dict[str, Any]]:
    if profile not in {"smoke", "standard"}:
        raise ValueError("capability profile must be smoke or standard")
    per_category = 2 if profile == "smoke" else 5
    raw = yaml.safe_load(
        files("model_detect").joinpath("data/capability_lite.yaml").read_text(
            encoding="utf-8"
        )
    )
    tasks = raw["tasks"]
    out = []
    for category in ABILITY_CATEGORIES:
        for task in tasks[category][:per_category]:
            out.append({
                "id": f"{category}.{task['id']}",
                "category": category,
                "pattern": task["pattern"],
                "payload": {
                    "model": "glm-5.3",
                    "messages": [{"role": "user", "content": task["prompt"]}],
                    "temperature": 1.0,
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": "max",
                    "max_tokens": _ABILITY_TOKENS,
                },
            })
    return out


def selected_cases(
    mode: Mode = "all", profile: CapabilityProfile = "standard"
) -> list[dict[str, Any]]:
    if mode not in {"all", "protocol", "capability"}:
        raise ValueError("mode must be all, protocol or capability")
    return [
        *(protocol_cases() if mode in {"all", "protocol"} else []),
        *(capability_cases(profile) if mode in {"all", "capability"} else []),
    ]


def suite_digest(cases: list[dict[str, Any]]) -> str:
    canonical = [
        {"id": case["id"], "payload": case["payload"],
         "pattern": case.get("pattern"), "check": case.get("check")}
        for case in cases
    ]
    return hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def plan_comparison(
    *,
    mode: Mode = "all",
    profile: CapabilityProfile = "standard",
    official_runs: int = 3,
    customer_runs: int = 1,
    input_price_per_million: float | None = None,
    output_price_per_million: float | None = None,
) -> dict[str, Any]:
    if not 1 <= official_runs <= 5 or not 1 <= customer_runs <= 5:
        raise ValueError("official/customer runs must each be between 1 and 5")
    if input_price_per_million is not None and input_price_per_million < 0:
        raise ValueError("input price must be nonnegative")
    if output_price_per_million is not None and output_price_per_million < 0:
        raise ValueError("output price must be nonnegative")
    cases = selected_cases(mode, profile)
    total_runs = official_runs + customer_runs
    requests = len(cases) * total_runs
    # Heuristic only: UTF-8 bytes/3 is NOT a tokenizer bound.
    input_guess = sum(
        math.ceil(len(json.dumps(case["payload"], ensure_ascii=False).encode("utf-8")) / 3)
        for case in cases
    ) * total_runs
    output_cap = sum(case["payload"]["max_tokens"] for case in cases) * total_runs
    possible_cost = None
    if input_price_per_million is not None and output_price_per_million is not None:
        possible_cost = round(
            (input_guess * input_price_per_million +
             output_cap * output_price_per_million) / 1_000_000, 6
        )
    return {
        "suite_version": SUITE_VERSION,
        "mode": mode, "profile": profile,
        "official_runs": official_runs,
        "customer_runs": customer_runs,
        "protocol_cases": len(protocol_cases()) if mode in ("all", "protocol") else 0,
        "capability_cases": len(capability_cases(profile)) if mode in ("all", "capability") else 0,
        "requests": requests,
        "suite_sha256": suite_digest(cases),
        "estimated_input_tokens": input_guess,
        "nominal_output_token_cap": output_cap,
        "scenario_max_cost": possible_cost,
        "warning": (
            "Input tokens use UTF-8 bytes/3 as a rough guess (NOT an upper bound). "
            "Output cap is configured max_tokens, not expected usage. "
            "Reasoning, retries, provider accounting, and cache pricing can change real cost."
        ),
    }


def _assistant_message(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message")
    return message if isinstance(message, dict) else {}


def _content(body: Any) -> str:
    msg = _assistant_message(body)
    value = msg.get("content")
    return value.strip() if isinstance(value, str) else ""


def _finish_reason(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0].get("finish_reason")
    return None


def _usage(body: Any) -> dict[str, int] | None:
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return None
    result: dict[str, int] = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[field] = value
    details = usage.get("completion_tokens_details") or {}
    if isinstance(details, dict):
        reason = details.get("reasoning_tokens")
        if isinstance(reason, int) and reason >= 0:
            result["reasoning_tokens"] = reason
    details = usage.get("prompt_tokens_details") or {}
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
        if isinstance(cached, int) and cached >= 0:
            result["cached_read_tokens"] = cached
    return result or None


def _rejects_disabled_thinking(response: Any) -> bool:
    """Accept only an explicit GLM-5.3 thinking restriction, not any 400.

    The vendor's documented first-party error can be Chinese (code 1210).
    A code without a relevant message is not proof of correct model behavior.
    """
    if not isinstance(response, dict):
        return False
    error = response.get("error")
    if isinstance(error, dict):
        text = str(error.get("message") or "").casefold()
    elif isinstance(error, str):
        text = error.casefold()
    else:
        return False
    if not text:
        return False
    zh = (
        "始终思考" in text
        or ("思考" in text and any(
            marker in text for marker in (
                "不支持关闭", "不能关闭", "无法关闭", "不可关闭", "禁止关闭",
            )
        ))
    )
    en = (
        ("thinking" in text or "reasoning" in text)
        and (
            "must be enabled" in text
            or "cannot be disabled" in text
            or "can't be disabled" in text
            or "does not support disabling" in text
            or "not support disabling" in text
            or ("disabled" in text and any(
                marker in text for marker in (
                    "not supported", "unsupported", "not allowed",
                    "forbidden", "invalid_request",
                )
            ))
        )
    )
    return zh or en


def _check_protocol(case: dict[str, Any], call) -> tuple[str, str]:
    status = call.evidence.response_status
    if status is None:
        return "error", "未收到有效 HTTP 响应"
    check = case["check"]
    response = call.json_body
    if check == "reject":
        # A 401/403/429 can be auth/quota/routing failure, not proof of a
        # model-specific thinking restriction.
        if status in {400, 422}:
            if _rejects_disabled_thinking(response):
                return "pass", f"HTTP {status}：错误明确指向禁止关闭思考"
            return "insufficient", f"HTTP {status}：拒绝原因未知，不能认定思考限制生效"
        if status in {401, 403, 408, 409, 425, 429} or status >= 500:
            return "insufficient", f"HTTP {status}：鉴权、限流或服务错误，无法验证思考限制"
        return "fail", f"HTTP {status}：未按官方协议拒绝 disabled"
    if status in {401, 403, 408, 409, 425, 429} or status >= 500:
        return "insufficient", f"HTTP {status}：服务不可用或权限/限流，不能判定协议不支持"
    if status != 200:
        return "fail", f"HTTP {status}：有效请求被拒绝"
    if check == "stream":
        kind = str((call.evidence.response_headers or {}).get("content-type") or "").lower()
        if "text/event-stream" not in kind:
            return "fail", "返回类型不是 text/event-stream"
        if not isinstance(response, dict):
            return "insufficient", "未获取完整 SSE 证据"
        if response.get("_sse_truncated"):
            return "insufficient", "SSE 超过安全读取上限，不能判完整流"
        if not response.get("_sse_completed"):
            return "insufficient", "未收到 [DONE] 结束标记"
        reason = response.get("_sse_finish_reason")
        if reason == "length":
            return "insufficient", "SSE 完成但 token 预算耗尽"
        if reason not in {"stop", "tool_calls", "function_call"}:
            return "insufficient", "收到 [DONE] 但没有正常结束原因"
        return "pass", "SSE 已完整结束，包含终止原因及 [DONE] 标记"
    if not isinstance(response, dict):
        return "insufficient", "非 JSON 或响应体结构不符合 Chat Completions"
    if _finish_reason(response) == "length":
        return "insufficient", "输出达到 max_tokens 截断，不能判断能力"
    text = _content(response)
    if check == "tools":
        calls = _assistant_message(response).get("tool_calls")
        if not isinstance(calls, list) or not calls:
            return "insufficient", "tool_choice=auto 未触发工具，无法判定工具能力"
        for item in calls:
            if not isinstance(item, dict) or not isinstance(item.get("function"), dict):
                return "fail", "tool_calls 结构不合法"
            function = item["function"]
            if function.get("name") != "lookup_ticket":
                return "fail", "工具名不符合请求提供的工具定义"
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (TypeError, ValueError):
                    return "fail", "工具参数并非合法 JSON"
            if not isinstance(arguments, dict) or arguments.get("ticket_id") != "T-17":
                return "fail", "工具参数 ticket_id 不正确"
        return "pass", "工具名与 JSON 参数正确"
    if check == "json":
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            parsed = None
        return (
            ("pass", "返回可解析 JSON 对象") if isinstance(parsed, dict)
            else ("fail", "未返回可解析 JSON 对象")
        )
    if check == "multiturn":
        return (
            ("pass", "多轮记忆正确") if text == "阿林"
            else ("fail", "多轮问题没有按要求回忆代号")
        )
    if text:
        return "pass", "请求成功并收到模型答案（不证明推理等级实际生效）"
    return "insufficient", "HTTP 200 但无完整可判定的答案"


async def run_endpoint(
    *,
    base_url: str,
    api_key: str,
    cases: list[dict[str, Any]],
    runs: int,
    label: str,
    timeout: float = 120,
) -> list[dict[str, Any]]:
    client = AuditHttpClient(
        base_url=normalize_base_url(base_url),
        api_key=api_key,
        model="glm-5.3",
        timeout_seconds=timeout,
    )
    results = []
    for number in range(1, runs + 1):
        for case in cases:
            protocol = "check" in case
            call = await client.post_json(
                probe_id=f"glm53.{case['id']}",
                path="/chat/completions",
                payload=case["payload"],
                stream=protocol and case["check"] == "stream",
                stream_full=protocol and case["check"] == "stream",
                # Keep intentionally invalid thinking.disabled unchanged.
                constraint_exempt_fields={"thinking", "reasoning_effort"},
            )
            if protocol:
                verdict, explanation = _check_protocol(case, call)
            else:
                status = call.evidence.response_status
                content_type = str(
                    (call.evidence.response_headers or {}).get("content-type", "")
                ).lower()
                answer = _content(call.json_body)
                grade = None
                if status is None:
                    verdict, explanation = "error", "未收到有效 HTTP 响应，无法评分"
                elif status in {401, 403, 408, 409, 425, 429} or status >= 500:
                    verdict, explanation = "insufficient", (
                        f"HTTP {status}：鉴权、限流或服务异常，不判模型能力"
                    )
                elif status != 200:
                    verdict, explanation = "insufficient", (
                        f"HTTP {status}：请求被拒绝，未获得可评分答案"
                    )
                elif "text/html" in content_type:
                    verdict, explanation = "insufficient", (
                        "HTTP 200 返回 HTML，非模型答案"
                    )
                elif not isinstance(call.json_body, dict) or not _assistant_message(call.json_body):
                    verdict, explanation = "insufficient", (
                        "HTTP 200 响应结构不符合 Chat Completions"
                    )
                elif _finish_reason(call.json_body) == "length":
                    verdict, explanation = "insufficient", "输出预算耗尽，答案不完整"
                elif not answer:
                    verdict, explanation = "insufficient", "模型没有可评分的文本答案"
                else:
                    grade = grade_answer(
                        category=case["category"],
                        task_id=case["id"].split(".", 1)[1],
                        pattern=case["pattern"],
                        answer=answer,
                    )
                    verdict = "pass" if grade.matched else "fail"
                    explanation = (
                        "答案符合客观规则" if grade.matched
                        else "答案与客观评分规则不一致"
                    )
            results.append({
                "endpoint": label, "run": number,
                "id": case["id"],
                "kind": "protocol" if protocol else "capability",
                "category": case.get("category", "protocol"),
                "status": verdict,
                "explanation": explanation,
                "http_status": call.evidence.response_status,
                "finish_reason": _finish_reason(call.json_body),
                "usage": _usage(call.json_body),
                "usage_record": usage_from_response(
                    probe_id=f"glm53.{case['id']}",
                    stage="protocol" if protocol else "capability",
                    attempt=number,
                    response=call.json_body,
                    http_status=call.evidence.response_status,
                    stream_complete=not (
                        isinstance(call.json_body, dict)
                        and "_sse_completed" in call.json_body
                        and not call.json_body.get("_sse_completed")
                    ),
                ).model_dump(mode="json"),
                "elapsed_ms": call.evidence.elapsed_ms,
                "observed_answer_excerpt": (
                    _content(call.json_body)[:160] if not protocol else None
                ),
                "normalized_answer_excerpt": (
                    grade.normalized_answer[:160] if not protocol and grade is not None
                    else None
                ),
                "answer_normalization": (
                    grade.normalization if not protocol and grade is not None
                    else None
                ),
                "scorer_version": SCORER_VERSION if not protocol else None,
                "expected_pattern": (
                    case.get("pattern") if not protocol else None
                ),
                # Never persist raw responses, reasoning_content, credentials, or URL.
            })
    return results


def _by_case(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {}
    for row in records:
        grouped.setdefault(row["id"], []).append(row)
    return grouped


def _usage_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    available = [r["usage"] for r in rows if r.get("usage") is not None]
    return {
        "requests": len(rows),
        "metered_requests": len(available),
        "unmetered_requests": len(rows) - len(available),
        "prompt_tokens_observed": sum(x.get("prompt_tokens", 0) for x in available),
        "completion_tokens_observed": sum(x.get("completion_tokens", 0) for x in available),
        "reasoning_tokens_observed": sum(x.get("reasoning_tokens", 0) for x in available),
        "cached_read_tokens_observed": sum(x.get("cached_read_tokens", 0) for x in available),
        "complete_usage": len(available) == len(rows) and all(
            "prompt_tokens" in x and "completion_tokens" in x for x in available
        ),
    }


def build_comparison(
    official: list[dict[str, Any]],
    customer: list[dict[str, Any]],
    *,
    plan: dict[str, Any],
    input_price_per_million: float | None = None,
    output_price_per_million: float | None = None,
) -> dict[str, Any]:
    expected = selected_cases(plan["mode"], plan["profile"])
    expected_ids = {case["id"] for case in expected}
    for label, rows, runs in (
        ("official", official, plan["official_runs"]),
        ("customer", customer, plan["customer_runs"]),
    ):
        keys = [(row["run"], row["id"]) for row in rows]
        if (
            len(rows) != len(expected_ids) * runs
            or len(set(keys)) != len(keys)
            or set(row["id"] for row in rows) != expected_ids
            or set(row["run"] for row in rows) != set(range(1, runs + 1))
        ):
            raise ValueError(f"{label} audit has missing, duplicate, or unexpected cases")
    official_by = _by_case(official)
    customer_by = _by_case(customer)
    protocol = []
    for case in expected:
        if "check" not in case:
            continue
        first = official_by[case["id"]]
        second = customer_by[case["id"]]
        official_pass = all(x["status"] == "pass" for x in first)
        customer_pass = all(x["status"] == "pass" for x in second)
        comparison = (
            "official_inconclusive" if not official_pass
            else "consistent" if customer_pass
            else "customer_inconclusive" if any(
                x["status"] not in {"pass", "fail"} for x in second
            )
            else "deviation"
        )
        protocol.append({
            "id": case["id"], "label": case["label"],
            "source_url": (
                "https://docs.z.ai/guides/llm/glm-5.3"
                if case["id"].startswith(("thinking.", "reasoning."))
                else "https://docs.z.ai/api-reference/llm/chat-completion"
            ),
            "official_statuses": [x["status"] for x in first],
            "customer_statuses": [x["status"] for x in second],
            "verdict": comparison,
            "authority": case["authority"],
        })

    capability = []
    for category in ABILITY_CATEGORIES:
        cases = [x for x in expected if x.get("category") == category]
        if not cases:
            continue
        samples = len(cases)
        def summarize(rows, n_runs):
            matched = [
                [x for x in rows if x["id"] == task["id"] and x["run"] == run][0]
                for run in range(1, n_runs + 1)
                for task in cases
            ]
            success = [x["status"] == "pass" for x in matched]
            complete = all(x["status"] in {"pass", "fail"} for x in matched)
            per_run = [
                sum(x["status"] == "pass" for x in matched[(run-1)*samples:run*samples]) / samples
                for run in range(1, n_runs + 1)
            ]
            return {
                "score": sum(success) / len(success) if complete else None,
                "per_run_scores": per_run if complete else [],
                "pass_count": sum(success),
                "question_count": len(matched),
                "complete": complete,
            }
        baseline = summarize(official, plan["official_runs"])
        vendor = summarize(customer, plan["customer_runs"])
        lower_bound = None
        verdict = "insufficient"
        if (baseline["complete"] and vendor["complete"]
                and plan["official_runs"] >= 3):
            mean = statistics.mean(baseline["per_run_scores"])
            stdev = statistics.stdev(baseline["per_run_scores"])
            lower_bound = max(0.0, mean - max(2 * stdev, 1 / samples))
            verdict = (
                "observable_drop" if vendor["score"] < lower_bound
                else "no_observable_drop"
            )
        capability.append({
            "category": category,
            "official": baseline,
            "customer": vendor,
            "official_mean": (
                statistics.mean(baseline["per_run_scores"])
                if baseline["complete"] else None
            ),
            "lower_bound": lower_bound,
            "verdict": verdict,
            "note": (
                "仅为轻量题集的启发式对比，不构成官方 GLM-5.3 满血认证"
            ),
        })
    usage = {
        "official": _usage_totals(official), "customer": _usage_totals(customer)
    }
    for value in usage.values():
        value["observed_cost_partial"] = None
        if input_price_per_million is not None and output_price_per_million is not None:
            value["observed_cost_partial"] = round((
                value["prompt_tokens_observed"] * input_price_per_million
                + value["completion_tokens_observed"] * output_price_per_million
            ) / 1_000_000, 6)
    status = (
        "observed_deviation" if any(x["verdict"] == "deviation" for x in protocol)
        else "evidence_incomplete" if any(
            x["verdict"] in {"official_inconclusive", "customer_inconclusive"}
            for x in protocol
        ) else "observed_consistent"
    )
    return {
        "assessment": {
            "protocol_observed": status,
            "capability": "lightweight_observation_only",
            "identity": "not_assessed",
            "supplier_accreditation": "not_determined",
        },
        "suite_version": SUITE_VERSION,
        "suite_sha256": plan["suite_sha256"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "glm-5.3",
        "plan": plan,
        "protocol": protocol,
        "capability": capability,
        "usage": usage,
        "runs": {"official": official, "customer": customer},
        "warnings": [
            "官方端点由用户提供；程序无法密码学证明其所有权。",
            "reasoning_effort 被接受，不等于计算预算完全按档位生效。",
            "轻量任务存在天花板效应；不应据此判断轻微降智或模型身份。",
            "低样本对照阈值仅是启发式规则，不代表正式统计显著性。",
            "Usage/费用仅计 HTTP 响应中上报的数据；SSE 预览、外部调用和缓存折扣可能遗漏。",
        ],
    }


def write_comparison(data: dict[str, Any], root: str | Path) -> dict[str, Path]:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    json_path = path / "glm53-comparison.json"
    md_path = path / "glm53-comparison.md"
    html_path = path / "glm53-comparison.html"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    protocol_summary = {
        status: sum(item["verdict"] == status for item in data["protocol"])
        for status in ("consistent", "deviation", "official_inconclusive", "customer_inconclusive")
    }
    lines = [
        "# GLM-5.3 客户协议与能力官方对照报告",
        "",
        f"Suite：{data['suite_version']}  |  测试配置 SHA256：{data['suite_sha256']}",
        f"官方轮数：{data['plan']['official_runs']}；客户轮数：{data['plan']['customer_runs']}",
        "",
        "## 判定边界", "",
        f"协议同表现：{protocol_summary['consistent']}；"
        f"客户偏离官方通过用例：{protocol_summary['deviation']}；"
        f"官方无可判定结果：{protocol_summary['official_inconclusive']}；"
        f"客户证据不足：{protocol_summary['customer_inconclusive']}。",
        "协议判定属于本次调用的有限观察；能力抽检是启发式筛查；"
        "模型身份和正式供应商准入结论均未评定。",
        "所有结论仅针对本次测试的 API 行为；不构成模型权重身份或 GLM-5.3 满血认证。",
        "",
        "## 协议符合性（官方文档要求 + 双端点实测）", "",
        "| 用例 | 官方 | 客户 | 对照结论 | 官方依据 |",
        "|---|---|---|---|---|",
    ]
    for row in data["protocol"]:
        lines.append(
            f"| {row['label']} | {','.join(row['official_statuses'])} "
            f"| {','.join(row['customer_statuses'])} | {row['verdict']} "
            f"| {row['source_url']} |"
        )
    lines.extend([
        "", "## 能力抽检：同题官方 vs 客户", "",
        "| 分类 | 官方均值 | 客户得分 | 保守下界 | 结论 |",
        "|---|---:|---:|---:|---|",
    ])
    def fmt(x):
        return "证据不足" if x is None else f"{x:.1%}"
    for row in data["capability"]:
        lines.append(
            f"| {row['category']} | {fmt(row['official_mean'])} "
            f"| {fmt(row['customer']['score'])} | {fmt(row['lower_bound'])} "
            f"| {row['verdict']} |"
        )
    lines.extend([
        "", "## 实际 Usage（部分数据不代表完整账单）", "",
        "| 端点 | 请求 | Usage 可获得 | 输入 Token（已观察） | 输出 Token（已观察） | 未计量请求 |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for label in ("official", "customer"):
        row = data["usage"][label]
        lines.append(
            f"| {label} | {row['requests']} | {row['metered_requests']} "
            f"| {row['prompt_tokens_observed']} | {row['completion_tokens_observed']} "
            f"| {row['unmetered_requests']} |"
        )
    lines.extend([
        "", "## 失败 / 证据不足的逐题记录", "",
        "| 端点/轮次 | 类型 | Case | 状态 | 说明 / 观测答案 |",
        "|---|---|---|---|---|",
    ])
    for label in ("official", "customer"):
        for item in data["runs"][label]:
            if item["status"] == "pass":
                continue
            detail = (
                item.get("observed_answer_excerpt")
                or item.get("explanation")
                or "无可用响应"
            )
            # Quote safe for Markdown tables and stop adversarial newlines.
            detail = str(detail).replace("|", "/").replace("\\n", " ")[:180]
            lines.append(
                f"| {label} #{item['run']} | {item['kind']} "
                f"| {item['id']} | {item['status']} | {detail} |"
            )
    benchmark = data.get("standard_benchmark")
    if isinstance(benchmark, dict):
        lines.extend([
            "", "## 标准 Benchmark（lm-evaluation-harness）", "",
        ])
        if benchmark.get("result") == "error":
            lines.append(
                "**未完成：外部标准评测执行失败，不能从缺失成绩得出官方一致结论。**"
            )
            lines.append("失败类型：" + str(benchmark.get("error_type") or "unknown"))
        else:
            lines.extend([
                f"评测框架版本：{benchmark.get('harness_version') or '未知'}；"
                f"配置 SHA256：{benchmark.get('suite_sha256') or '未记录'}",
                "",
                "| 任务 | 评分指标 | 主指标 | 有效题数 | 官方 | 客户 | 差值 | 可比性 |",
                "|---|---|---|---:|---:|---:|---:|---|",
            ])
            for item in benchmark.get("tasks") or []:
                def as_pct(value):
                    return "不可比" if value is None else f"{value:.2%}"
                metrics = item.get("metrics") or [{
                    "metric": item.get("metric"), "primary": True,
                    "official_mean": item.get("official_mean"),
                    "customer_mean": item.get("customer_mean"),
                    "delta": item.get("delta"),
                }]
                for metric in metrics:
                    lines.append(
                        f"| {item['task']} | {metric.get('metric') or '未知'} "
                        f"| {'是' if metric.get('primary') else '否'} "
                        f"| {item.get('sample_count') or '未知'} "
                        f"| {as_pct(metric.get('official_mean'))} "
                        f"| {as_pct(metric.get('customer_mean'))} "
                        f"| {as_pct(metric.get('delta'))} | {item['status']} |"
                    )
            lines.extend(["", "此处是独立标准任务成绩，不是厂商发布的 GLM-5.3 官方榜单复现。"])
            for warning in benchmark.get("limitations") or []:
                lines.append("- " + warning)
    lines.extend(["", "## 证据边界", ""])
    lines.extend(f"- {warning}" for warning in data["warnings"])
    text = "\n".join(lines) + "\n"
    md_path.write_text(text, encoding="utf-8")
    html_path.write_text(
        render_qualification_html(text), encoding="utf-8"
    )
    return {"json": json_path, "markdown": md_path, "html": html_path}



def render_qualification_html(markdown: str) -> str:
    """Safe standalone HTML; no Markdown or third-party renderer required."""
    fragments = []
    in_table = False
    in_list = False
    for source in markdown.splitlines():
        line = source.strip()
        if not line:
            if in_table:
                fragments.append("</tbody></table>")
                in_table = False
            if in_list:
                fragments.append("</ul>")
                in_list = False
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [x.strip() for x in line.strip("|").split("|")]
            if all(set(x) <= {"-", ":"} for x in cells):
                continue
            if in_list:
                fragments.append("</ul>")
                in_list = False
            if not in_table:
                fragments.append("<table><tbody>")
                in_table = True
            fragments.append(
                "<tr>" + "".join(
                    "<td>" + html.escape(cell) + "</td>" for cell in cells
                ) + "</tr>"
            )
            continue
        if in_table:
            fragments.append("</tbody></table>")
            in_table = False
        if line.startswith("- "):
            if not in_list:
                fragments.append("<ul>")
                in_list = True
            fragments.append("<li>" + html.escape(line[2:]) + "</li>")
            continue
        if in_list:
            fragments.append("</ul>")
            in_list = False
        depth = len(line) - len(line.lstrip("#"))
        if 1 <= depth <= 4 and line[depth:depth + 1] == " ":
            fragments.append(
                f"<h{depth}>" + html.escape(line[depth + 1:]) + f"</h{depth}>"
            )
        else:
            fragments.append("<p>" + html.escape(line) + "</p>")
    if in_table:
        fragments.append("</tbody></table>")
    if in_list:
        fragments.append("</ul>")
    return (
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>GLM-5.3 客户准入对照</title>"
        "<style>:root{color-scheme:light}body{max-width:1150px;margin:40px auto;"
        "padding:0 28px;font:15px/1.7 system-ui;color:#273240;background:#fff}"
        "h1{font-size:26px}h2{margin-top:38px;border-bottom:1px solid #dce2e9;"
        "padding-bottom:8px}table{border-collapse:collapse;display:block;"
        "overflow-x:auto;width:100%;margin:16px 0 24px}"
        "td{border:1px solid #d8dfe8;padding:9px 11px;white-space:pre-wrap}"
        "tr:first-child{background:#edf3f9;font-weight:650}"
        "tr:nth-child(even){background:#f8fafc}p{overflow-wrap:anywhere}"
        "li{overflow-wrap:anywhere}</style><main>"
        + "\n".join(fragments) + "</main></html>"
    )
