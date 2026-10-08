from __future__ import annotations

from typing import Any

from .models import AuditReport, ProbeResult, ProbeStatus


STATUS_ZH = {
    "pass": "通过",
    "warn": "需关注",
    "fail": "失败",
    "error": "执行错误",
    "skipped": "已跳过",
    "insufficient": "证据不足",
}

VERDICT_ZH = {
    "pass": "通过",
    "review": "建议复核",
    "fail": "不通过",
    "mismatch": "身份不一致",
    "insufficient": "证据不足",
    "invalid_target": "检测地址无效",
    "match": "匹配",
}

CONFIDENCE_ZH = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

CATEGORY_ZH = {
    "identity": "模型身份",
    "protocol": "协议兼容",
    "integrity": "参数完整性",
    "context": "上下文能力",
    "routing": "路由一致性",
    "capability": "能力抽检",
    "provider": "上游 / 网关",
    "quality": "官方基准差异",
    "target": "目标地址",
    "internal": "检测器内部",
}

CATEGORY_HELP = {
    "identity": "判断被测接口的行为是否与声明模型及可信参考一致。强身份结论依赖 Trusted Reference / Statistical Fingerprint。",
    "protocol": "检查 OpenAI 兼容接口、流式、工具调用、JSON、推理参数等是否按预期工作。",
    "integrity": "检查中转是否吞掉、改写或忽略关键请求参数与结构。",
    "context": "检查较长输入是否能正确保留并取回关键信息，区分上下文失败和输出被截断。",
    "routing": "多次重复请求观察 model、响应结构、ID、Header、输出风格是否稳定，用于发现混路由迹象。",
    "capability": "用小型任务抽检基础能力。它只能辅助判断质量，不能单独证明模型身份。",
}

PROBE_TITLES = {
    "target.api.preflight": "API 地址有效性",
    "protocol.chat.basic": "基础对话接口",
    "protocol.chat.stream": "流式 SSE 接口",
    "protocol.usage": "Token 用量字段",
    "protocol.finish_reason": "结束原因字段",
    "protocol.system": "System 指令",
    "protocol.multiturn": "多轮上下文",
    "protocol.tools.basic": "工具调用",
    "protocol.json_mode": "JSON 输出模式",
    "protocol.json_schema": "JSON Schema",
    "protocol.reasoning.valid_field": "推理强度合法参数",
    "protocol.reasoning.invalid_field": "推理参数拼写错误校验",
    "protocol.reasoning.invalid_value": "推理强度非法值校验",
    "protocol.thinking.disable": "关闭思考参数",
    "protocol.invalid.unknown_field": "未知字段校验",
    "protocol.invalid.bad_enum": "非法参数类型校验",
    "provider.error.invalid_model": "不存在模型拒绝",
    "provider.error.invalid_model_status": "不存在模型 HTTP 状态码",
    "provider.upstream_policy": "上游准入策略",
    "identity.fingerprint.reference_compare": "统计指纹与可信参考对比",
    "identity.self_consistency": "统计指纹自一致性",
    "routing.fingerprint.consistency": "指纹路由稳定性",
    "routing.repeat.same_probe": "重复请求稳定性",
    "routing.cluster": "路由特征聚类",
    "routing.tool_style": "工具调用风格一致性",
    "routing.fact_inversion": "事实回答一致性",
    "routing.quality_inversion": "能力层级异常反转",
    "routing.summary": "路由综合判断",
    "context.summary": "上下文综合结果",
    "integrity.max_tokens": "最大输出长度",
    "integrity.stop": "停止词",
    "integrity.temperature": "Temperature 参数",
    "integrity.top_p": "Top-p 参数",
    "integrity.sampling_controls": "采样参数组合",
    "integrity.system_prompt": "System Prompt 保留",
    "integrity.tools_preserved": "工具定义保留",
    "integrity.json_schema_preserved": "JSON Schema 保留",
    "quality.baseline.summary": "官方 / 可信质量基准综合对比",
}


def status_label(value: ProbeStatus | str) -> str:
    raw = value.value if isinstance(value, ProbeStatus) else str(value)
    return STATUS_ZH.get(raw.casefold(), raw)


def verdict_label(value: str | None) -> str:
    raw = str(value or "insufficient").casefold()
    return VERDICT_ZH.get(raw, raw)


def confidence_label(value: str | None) -> str:
    raw = str(value or "low").casefold()
    return CONFIDENCE_ZH.get(raw, raw)


def category_label(value: str) -> str:
    return CATEGORY_ZH.get(value, value)


def probe_title(probe_id: str) -> str:
    if probe_id in PROBE_TITLES:
        return PROBE_TITLES[probe_id]
    if probe_id.startswith("context.needle."):
        level = probe_id.rsplit(".", 1)[-1].upper()
        return f"长上下文回忆（约 {level}）"
    if probe_id.startswith("identity.family_features."):
        feature = probe_id.rsplit(".", 1)[-1]
        return f"模型官方特征：{feature}"
    if probe_id.startswith("capability."):
        return "能力抽检：" + probe_id.split(".", 1)[1]
    if probe_id.startswith("quality.baseline."):
        dimension = probe_id.split(".", 2)[2]
        labels = {
            "reasoning": "推理能力保持",
            "math": "数学能力保持",
            "coding_reasoning": "代码理解能力保持",
            "chinese": "中文能力保持",
            "instruction_following": "指令遵循能力保持",
            "tool_use": "工具调用能力保持",
            "structured_output": "结构化输出能力保持",
            "coding_execute_python": "Python 实执行能力保持",
            "coding_execute_go": "Go 实执行能力保持",
            "context": "上下文能力保持",
            "routing": "路由稳定性保持",
            "summary": "官方 / 可信质量基准综合对比",
        }
        return labels.get(dimension, "质量基准：" + dimension)
    if probe_id.startswith("regression."):
        return "回归规则：" + probe_id.split(".", 1)[1]
    return probe_id


def _result_action(result: ProbeResult) -> str | None:
    probe_id = result.probe_id
    if probe_id == "target.api.preflight":
        return "检查 Base URL 是否指向模型 API；OpenAI 兼容接口通常应包含 /v1。"
    if probe_id == "provider.upstream_policy":
        return "如果命中禁止上游，请切换渠道或上游；不要用 429 单独判断供应商身份。"
    if probe_id == "identity.fingerprint.reference_compare":
        return "优先确认 Trusted Reference 是否来自官方 / 可信端点，并再次采样复测。"
    if probe_id.startswith("routing."):
        return "建议跨时间窗口重复检测；如果仍出现多个稳定 Cluster，再排查混路由或多上游。"
    if probe_id.startswith("context."):
        return "检查声明的上下文长度、网关截断策略和输出预算；必要时降低测试长度复测。"
    if probe_id in {"protocol.chat.basic", "protocol.chat.stream"}:
        return "这是基础协议项，建议先修复接口兼容问题再做供应商准入。"
    if probe_id == "protocol.reasoning.invalid_field":
        return "如果错误字段被静默忽略，建议网关增加严格字段校验，避免用户误以为参数已生效。"
    if probe_id == "provider.error.invalid_model_status":
        return "模型拒绝语义可能正确，但建议使用更标准的 4xx 状态码。"
    if probe_id.startswith("integrity."):
        return "检查中转层是否改写、丢弃或固定了该参数，并与官方模型规则对照。"
    if probe_id.startswith("quality.baseline."):
        return (
            "先使用同一 Suite 复测；若持续低于可信基准范围，再排查模型版本、"
            "reasoning 配置、量化/蒸馏、网关参数改写或后端路由。"
        )
    if probe_id.startswith("capability."):
        return "能力抽检异常建议复测，但不要单独用能力题结果判断模型真假。"
    return None


def result_explanation(result: ProbeResult) -> str:
    status = result.status
    title = probe_title(result.probe_id)
    if status == ProbeStatus.PASS:
        return f"{title}符合当前检测预期。"
    if status == ProbeStatus.SKIPPED:
        return f"{title}本次不适用或未启用，不计入失败。"
    if status == ProbeStatus.INSUFFICIENT:
        return f"{title}没有形成足够证据，不能据此判定通过或失败。"
    if status == ProbeStatus.ERROR:
        return f"{title}执行过程中发生错误，本项结果不可用于判断。"
    if status == ProbeStatus.FAIL:
        return f"{title}出现明确异常，需要优先处理。"
    return f"{title}存在非标准或可疑行为，建议结合 Evidence 与复测结果判断。"


def _issue_level(result: ProbeResult) -> int:
    return {
        ProbeStatus.FAIL: 0,
        ProbeStatus.ERROR: 1,
        ProbeStatus.WARN: 2,
        ProbeStatus.INSUFFICIENT: 3,
    }.get(result.status, 9)


def _provider_summary(report: AuditReport) -> dict[str, Any]:
    from .probes.provider import load_provider_rules

    provider_rules = load_provider_rules()
    hypotheses = [
        {
            "provider": item.provider,
            "label": (
                provider_rules[item.provider].label
                if item.provider in provider_rules
                else item.provider
            ),
            "confidence": item.confidence,
            "evidence": list(item.evidence),
        }
        for item in report.provider_hypotheses[:5]
    ]
    policy = report.adapters.get("upstream_policy")
    policy = policy if isinstance(policy, dict) else {}
    config = policy.get("config") if isinstance(policy.get("config"), dict) else {}
    observed = policy.get("observed") if isinstance(policy.get("observed"), dict) else {}
    detected = observed.get("detected") if isinstance(observed.get("detected"), list) else []
    disallowed = config.get("disallowed") if isinstance(config.get("disallowed"), list) else []
    rate_limit_count = int(observed.get("http_429_count") or 0)

    if policy.get("status") == "violation":
        text = "已观察到禁止上游的强证据，当前渠道不满足准入策略。"
        state = "violation"
    elif disallowed:
        text = (
            "本轮未观察到禁止上游的足够证据。"
            "这表示“未发现”，不等于从密码学意义证明后端绝对不存在该上游。"
        )
        state = "clear"
    else:
        text = "未配置禁止上游策略；下方 Provider 仅表示可观测指纹，不等同于最终模型供应商证明。"
        state = "not_configured"

    return {
        "state": state,
        "label": {
            "violation": "命中禁止上游",
            "clear": "未观察到禁止上游",
            "not_configured": "未配置禁止上游",
        }.get(state, state),
        "text": text,
        "disallowed": disallowed,
        "detected": detected,
        "http_429_count": rate_limit_count,
        "hypotheses": hypotheses,
    }


def _identity_summary(report: AuditReport) -> dict[str, Any]:
    strong = [
        result for result in report.results
        if result.category == "identity"
        and result.metadata.get("identity_strength") == "strong"
    ]
    mismatch = any(
        result.metadata.get("verdict") == "mismatch"
        and result.status == ProbeStatus.FAIL
        for result in strong
    )
    match = any(
        result.metadata.get("verdict") == "match"
        and result.status == ProbeStatus.PASS
        for result in strong
    )
    fingerprint = next(
        (
            result for result in strong
            if result.probe_id == "identity.fingerprint.reference_compare"
        ),
        None,
    )

    if mismatch:
        state = "mismatch"
        text = "强身份证据与可信参考不一致，不建议将该接口视为声明模型的可靠等价渠道。"
    elif match:
        state = "match"
        text = "统计行为指纹与可信参考匹配，当前具备较强模型身份依据。"
    elif strong:
        state = "uncertain"
        text = "已经运行强身份检测，但结果仍不确定，需要增加样本或重新采集可信参考。"
    else:
        state = "missing"
        text = (
            "缺少 Trusted Reference / Statistical Fingerprint 等强身份证据。"
            "协议和能力通过只能说明“行为像且能用”，不能证明模型身份。"
        )

    return {
        "state": state,
        "label": {
            "match": "已有强身份匹配",
            "mismatch": "强身份不一致",
            "uncertain": "强身份结果不确定",
            "missing": "缺少强身份依据",
        }.get(state, state),
        "text": text,
        "fingerprint_verdict": (
            fingerprint.metadata.get("verdict") if fingerprint else None
        ),
        "mean_jsd": (
            fingerprint.observed.get("mean_jsd")
            if fingerprint and isinstance(fingerprint.observed, dict)
            else None
        ),
    }


QUALITY_DIMENSION_ZH = {
    "reasoning": "推理",
    "math": "数学",
    "coding_reasoning": "代码理解",
    "chinese": "中文",
    "instruction_following": "指令遵循",
    "tool_use": "工具调用",
    "structured_output": "结构化输出",
    "coding_execute_python": "Python 实执行",
    "coding_execute_go": "Go 实执行",
    "context": "上下文",
    "routing": "路由稳定性",
}


def _quality_summary(report: AuditReport) -> dict[str, Any]:
    raw = report.adapters.get("official_baseline_comparison")
    if not isinstance(raw, dict) or raw.get("status") == "not_configured":
        return {
            "state": "not_configured",
            "label": "未配置质量基准",
            "text": (
                "当前没有可比较的 Official Baseline。选择包含质量 Baseline 的官方 / "
                "可信 Reference 后，才能判断当前渠道是否相对基准退化。"
            ),
            "dimensions": [],
            "regression_dimensions": [],
            "baseline_runs": 0,
        }

    verdict = str(raw.get("verdict") or "baseline_insufficient")
    if verdict == "quality_regression":
        state = "regression"
        regression_dimensions = list(raw.get("regression_dimensions") or [])
        names = [
            QUALITY_DIMENSION_ZH.get(item, item)
            for item in regression_dimensions
        ]
        text = (
            "相对重复采集的官方 / 可信基准，以下维度低于基准自身正常波动范围："
            + "、".join(names)
            + "。这说明存在质量退化证据，但不能单独确定是量化、蒸馏、低 reasoning "
            "档位还是后端路由造成。"
        )
        label = "检测到质量退化"
    elif verdict == "baseline_match":
        state = "match"
        regression_dimensions = []
        text = (
            "当前可比较维度仍处于重复采集的官方 / 可信基准范围内，"
            "本轮没有观察到明显质量退化。"
        )
        label = "质量保持正常"
    else:
        state = "insufficient"
        regression_dimensions = list(raw.get("regression_dimensions") or [])
        warnings = list(raw.get("warnings") or [])
        text = (
            "已找到质量基准，但当前证据不足以判断是否超出正常波动。"
            + ((" " + str(warnings[0])) if warnings else "")
        )
        label = "质量基准证据不足"

    dimensions = []
    raw_dimensions = raw.get("dimensions")
    if isinstance(raw_dimensions, dict):
        for dimension, item in raw_dimensions.items():
            if not isinstance(item, dict):
                continue
            retention = item.get("retention_ratio")
            dimensions.append(
                {
                    "id": dimension,
                    "label": QUALITY_DIMENSION_ZH.get(dimension, dimension),
                    "baseline_mean": item.get("baseline_mean"),
                    "baseline_stddev": item.get("baseline_stddev"),
                    "baseline_runs": item.get("baseline_runs"),
                    "target_score": item.get("target_score"),
                    "delta": item.get("delta"),
                    "retention_ratio": retention,
                    "lower_bound": item.get("lower_bound"),
                    "verdict": item.get("verdict"),
                    "explanation": item.get("explanation"),
                }
            )

    meta = raw.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    return {
        "state": state,
        "label": label,
        "text": text,
        "dimensions": dimensions,
        "regression_dimensions": regression_dimensions,
        "baseline_runs": int(meta.get("baseline_runs") or 0),
        "statistically_evaluable_dimensions": int(
            raw.get("statistically_evaluable_dimensions") or 0
        ),
        "comparable_dimensions": int(raw.get("comparable_dimensions") or 0),
        "suite_version": raw.get("suite_version"),
    }


def build_report_interpretation(report: AuditReport) -> dict[str, Any]:
    verdict = str(report.summary.final_verdict or "insufficient").casefold()
    provider = _provider_summary(report)
    identity = _identity_summary(report)
    quality = _quality_summary(report)

    invalid_target = verdict == "invalid_target"
    policy_violation = provider["state"] == "violation"
    identity_mismatch = identity["state"] == "mismatch"

    if invalid_target:
        decision = "重新检测"
        tone = "bad"
        headline = "检测地址无效：当前请求没有正确命中模型 API。"
    elif policy_violation:
        decision = "拒绝准入"
        tone = "bad"
        headline = "不通过：检测到被禁止的上游 Provider 证据。"
    elif identity_mismatch:
        decision = "拒绝准入"
        tone = "bad"
        headline = "不通过：强模型身份信号与可信参考不一致。"
    elif quality["state"] == "regression":
        decision = "人工复核"
        tone = "warn"
        headline = (
            "检测到相对官方 / 可信基准的质量退化；建议用相同 Suite 复测后，"
            "再排查模型版本、推理档位、部署实现或路由差异。"
        )
    elif verdict in {"pass", "match"}:
        decision = "可通过"
        tone = "good"
        headline = "检测通过：当前证据未发现阻断准入的问题。"
    elif verdict == "review":
        decision = "人工复核"
        tone = "warn"
        headline = (
            "整体基本可用，但仍有异常或身份依据不足，建议查看下方重点风险后再准入。"
        )
    elif verdict == "fail":
        decision = "暂不准入"
        tone = "bad"
        headline = "检测不通过：存在影响兼容性、完整性或稳定性的明确失败项。"
    else:
        decision = "补充证据"
        tone = "muted"
        headline = "当前证据不足，暂时无法给出可靠准入结论。"

    issues = []
    actions: list[str] = []
    abnormal = [
        result for result in report.results
        if result.status in {
            ProbeStatus.FAIL,
            ProbeStatus.ERROR,
            ProbeStatus.WARN,
            ProbeStatus.INSUFFICIENT,
        }
        and result.category not in {"internal", "quality"}
    ]
    abnormal.sort(key=_issue_level)
    for result in abnormal[:12]:
        action = _result_action(result)
        if action and action not in actions:
            actions.append(action)
        issues.append(
            {
                "probe_id": result.probe_id,
                "title": probe_title(result.probe_id),
                "category": category_label(result.category),
                "status": result.status.value,
                "status_label": status_label(result.status),
                "explanation": result_explanation(result),
                "technical_summary": result.summary,
                "action": action,
                "evidence_ids": list(result.evidence_ids),
            }
        )

    if quality["state"] == "regression":
        action = (
            "使用同一个 Reference、同一个 Standard Suite 再跑一次；若退化持续存在，"
            "再检查供应商的模型版本、reasoning 档位、量化/蒸馏配置和后端路由。"
        )
        if action not in actions:
            actions.insert(0, action)
    elif quality["state"] == "insufficient":
        action = (
            "质量基准至少重复采集 3 次且必须与当前检测使用相同 Profile / Suite，"
            "之后才能判断是否超出官方正常波动。"
        )
        if action not in actions:
            actions.insert(0, action)

    if identity["state"] == "missing":
        action = "如果核心目标是判断“是不是官方同模型”，请先创建官方 / 可信 Reference，并启用 Statistical Fingerprint 对比。"
        if action not in actions:
            actions.insert(0, action)
    if not actions:
        actions.append("当前没有必须处理的异常；建议保留报告作为本次准入证据，并定期复测渠道漂移。")

    category_cards = []
    for category in ("identity", "protocol", "integrity", "context", "routing", "capability"):
        score = report.summary.category_scores.get(category)
        covered = bool(report.summary.coverage.get(category))
        category_cards.append(
            {
                "id": category,
                "label": category_label(category),
                "score": score,
                "covered": covered,
                "help": CATEGORY_HELP[category],
            }
        )

    confidence = str(report.summary.confidence or "low").casefold()
    confidence_text = {
        "high": "高：已有较强身份依据且检测覆盖较完整。",
        "medium": "中：覆盖较完整，但身份依据或部分关键证据仍有限。",
        "low": "低：缺少强身份依据或有效检测覆盖不足。",
    }.get(confidence, confidence)

    return {
        "decision": decision,
        "tone": tone,
        "headline": headline,
        "verdict": verdict,
        "verdict_label": verdict_label(verdict),
        "score": report.summary.overall_score,
        "hard_cap": report.summary.hard_cap,
        "confidence": confidence,
        "confidence_label": confidence_label(confidence),
        "confidence_text": confidence_text,
        "identity": identity,
        "provider": provider,
        "quality": quality,
        "issues": issues,
        "actions": actions[:8],
        "categories": category_cards,
        "limitations": [
            "综合分数是审计评分，不是“模型为真”的概率。",
            "Provider / Gateway 指纹来自可观测 Header、Body 和行为证据，不是密码学身份证明。",
            "没有 Trusted Reference / Statistical Fingerprint 时，即使协议和能力全部通过，也不能证明模型身份。",
            "HTTP 429 只代表限流现象，不能单独用来识别 Fireworks 或任何其他 Provider。",
            "质量退化只说明当前黑盒行为低于可信基准范围，不能据此确定 INT4、FP8、AWQ、GPTQ、蒸馏、GPU 型号或具体 Serving Engine。",
            "厂商官网公布的排行榜成绩只有在 Dataset、Harness、Prompt、参数完全一致时才能直接比较；本工具的 Official Baseline 默认使用自己对官方端点的同套件实测。",
        ],
    }
