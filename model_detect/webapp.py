from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .adapters import fingerprint, lm_eval
from .lmeval_run_import import load_revision_manifest
from .audit import run_audit
from .baseline_collection import collect_quality_baseline
from .config import AuditConfig, RegressionAuditConfig, UpstreamPolicyConfig
from .models import AuditTarget
from .interpretation import build_report_interpretation
from .references import ReferenceRegistry
from .probes.provider import load_provider_rule_set
from .rules import match_model_rule
from .reporting import write_report
from .evaluation_batch_report import (
    compare_directories, compare_kimi_official_protocol_summaries,
    write_comparison_report,
)
from .storage import JobStore


class WebAuditRequest(BaseModel):
    base_url: str
    api_key: str = Field(min_length=1)
    model: str
    profile: str = "standard"
    reference_id: str | None = None
    declared_context_tokens: int | None = None
    proxy_sleuth: bool = False
    coding_sandbox: bool = False
    benchmark_profile: str | None = None
    retain_benchmark_reference: bool = False
    benchmark_revisions_file: str | None = None
    regression_suites: list[str] = Field(default_factory=list)
    disallowed_upstreams: list[str] = Field(default_factory=list)


class WebReferenceRequest(BaseModel):
    id: str
    base_url: str
    api_key: str = Field(min_length=1)
    model: str
    provider: str = "trusted"
    fingerprint: bool = True
    quality_baseline: bool = True
    baseline_runs: int = Field(default=3, ge=1, le=5)
    benchmark_profile: str | None = None
    overwrite: bool = False



class WebComparisonRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    official_snapshots_dir: str | None = None
    vendor_snapshots_dir: str | None = None
    kimi_official_summary: str | None = None
    kimi_vendor_summary: str | None = None


def _validated_benchmark_profile(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value not in {"smoke", "standard", "deep"}:
        raise ValueError("Benchmark 档位只能是 smoke、standard、deep")
    return value


def _list_regression_suites(root: Path) -> list[str]:
    if not root.exists():
        return []
    out: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
            continue
        out.append(path.relative_to(root).as_posix())
    return out


def _resolve_regression_suites(
    root: Path,
    selected: list[str],
) -> list[str]:
    catalog = set(_list_regression_suites(root))
    unknown = sorted(set(selected) - catalog)
    if unknown:
        raise ValueError(f"存在未允许的回归规则: {unknown}")
    return [
        str((root / name).resolve())
        for name in dict.fromkeys(selected)
    ]


def _provider_provenance(
    provider_ids: list[str],
) -> list[dict[str, Any]]:
    ruleset = load_provider_rule_set()
    sources = {source.id: source for source in ruleset.sources}
    out: list[dict[str, Any]] = []
    for provider_id in provider_ids:
        rule = ruleset.providers.get(provider_id)
        if rule is None:
            continue
        out.append(
            {
                "provider": provider_id,
                "label": rule.label,
                "source_refs": list(rule.source_refs),
                "sources": [
                    sources[ref].model_dump(mode="json")
                    for ref in rule.source_refs
                    if ref in sources
                ],
                "false_positive_notes": list(rule.false_positive_notes),
                "confidence_calibration": dict(rule.confidence_calibration),
            }
        )
    return out


def create_app(
    *,
    state_dir: str | Path = ".model-detect",
    reference_dir: str | Path = "references",
    output_dir: str | Path = "model-detect-output",
    regression_dir: str | Path = "regressions",
) -> FastAPI:
    app = FastAPI(title="model-detect", version="0.2.0")
    state_root = Path(state_dir)
    state_root.mkdir(parents=True, exist_ok=True)
    store = JobStore(state_root / "jobs.sqlite3")
    registry = ReferenceRegistry(reference_dir)
    regression_root = Path(regression_dir)
    regression_root.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    app.state.store = store
    app.state.registry = registry
    app.state.output_dir = Path(output_dir)
    app.state.state_dir = state_root
    app.state.regression_dir = regression_root

    @app.get("/", response_class=HTMLResponse)
    async def index(
        request: Request,
        model: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "jobs": store.list(
                    50,
                    model=model,
                    status=status,
                    kind=kind,
                ),
                "references": registry.list(),
                "regression_suites": _list_regression_suites(regression_root),
                "history_filters": {
                    "model": model or "",
                    "status": status or "",
                    "kind": kind or "",
                },
            },
        )

    @app.get("/references", response_class=HTMLResponse)
    async def references_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="references.html",
            context={
                "references": registry.list(),
                "jobs": [x for x in store.list(100) if x["kind"] == "reference"],
            },
        )

    @app.get("/api/knowledge/model")
    async def model_knowledge(model: str):
        rule = match_model_rule(model)
        return {"rule": rule.model_dump(mode="json")}

    @app.get("/api/knowledge/providers")
    async def provider_knowledge():
        ruleset = load_provider_rule_set()
        return ruleset.model_dump(mode="json")

    @app.get("/api/regression-suites")
    async def regression_suites():
        return {
            "suites": _list_regression_suites(app.state.regression_dir)
        }

    @app.get("/api/jobs")
    async def jobs(
        model: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ):
        return {
            "jobs": store.list(
                100,
                model=model,
                status=status,
                kind=kind,
            )
        }

    @app.get("/api/jobs/{job_id}")
    async def job(job_id: str):
        try:
            return store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")

    @app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")

        if item["status"] in {"queued", "running"}:
            raise HTTPException(409, "运行中的任务不能删除")

        if item["kind"] in {"audit", "comparison"}:
            report_root = (app.state.output_dir / job_id).resolve()
            output_root = app.state.output_dir.resolve()
            if report_root.is_relative_to(output_root) and report_root.exists():
                shutil.rmtree(report_root, ignore_errors=True)

        if item["kind"] == "audit":
            root = (app.state.state_dir / "benchmark-runs").resolve()
            archived_run = (root / job_id).resolve()
            if archived_run.is_relative_to(root) and archived_run.is_dir():
                shutil.rmtree(archived_run, ignore_errors=True)
        archive = app.state.state_dir / f"{job_id}-report.zip"
        if archive.exists():
            archive.unlink()

        regression_work = (
            app.state.state_dir / "regression-runs" / job_id
        )
        if regression_work.exists():
            shutil.rmtree(regression_work, ignore_errors=True)

        if not store.delete(job_id):
            raise HTTPException(404, "任务不存在")
        return {"ok": True, "id": job_id}

    @app.post("/api/comparisons")
    async def create_comparison_job(payload: WebComparisonRequest):
        """Import local, previously saved evidence into existing SQLite history."""
        if not payload.model.strip():
            raise HTTPException(400, "模型 ID 不能为空")
        benchmark = bool(payload.official_snapshots_dir and payload.vendor_snapshots_dir)
        kimi = bool(payload.kimi_official_summary and payload.kimi_vendor_summary)
        if (
            not (benchmark or kimi)
            or bool(payload.official_snapshots_dir) != bool(payload.vendor_snapshots_dir)
            or bool(payload.kimi_official_summary) != bool(payload.kimi_vendor_summary)
        ):
            raise HTTPException(400, "请提供官方与供应商的成对结果目录或 Kimi 测试汇总")

        try:
            # No model API calls. Paths are for the server's local filesystem;
            # never echo the paths, source files, or parser errors to clients.
            if benchmark:
                comparison = await asyncio.to_thread(
                    compare_directories,
                    Path(payload.official_snapshots_dir),
                    Path(payload.vendor_snapshots_dir),
                    expected_model=payload.model.strip(),
                )
            else:
                comparison = {
                    "schema": "evaluation-batch-report-v1",
                    "tasks": [], "total_tasks": 0, "comparable_tasks": 0,
                    "unknown_or_incompatible_tasks": 0,
                    "official_provenance_attested": False,
                    "model_identity_proven": False,
                }
            if kimi:
                comparison["kimi_official_protocol"] = await asyncio.to_thread(
                    compare_kimi_official_protocol_summaries,
                    Path(payload.kimi_official_summary),
                    Path(payload.kimi_vendor_summary),
                    expected_model=payload.model.strip(),
                )
        except (OSError, ValueError, TypeError, KeyError):
            raise HTTPException(400, "本地评测文件缺失、格式错误或版本不兼容") from None

        job_id = "compare_" + uuid.uuid4().hex[:12]
        root = app.state.output_dir / job_id
        try:
            await asyncio.to_thread(write_comparison_report, comparison, root)
        except (OSError, ValueError, TypeError):
            raise HTTPException(400, "本地对照报告生成失败") from None
        store.create(
            job_id=job_id, kind="comparison", model=payload.model.strip(),
            base_url="", profile="offline", meta={
                "comparable_tasks": comparison["comparable_tasks"],
                "unknown_or_incompatible_tasks": comparison["unknown_or_incompatible_tasks"],
                "kimi_protocol_status": comparison.get("kimi_official_protocol", {}).get("status"),
                "source_attested": False,
                "model_identity_proven": False,
            },
        )
        return store.finish(
            job_id, report_path=str(root / "comparison.html"),
            detail=f"离线对照：{comparison['comparable_tasks']} 项可比",
            meta={
                "comparable_tasks": comparison["comparable_tasks"],
                "unknown_or_incompatible_tasks": comparison["unknown_or_incompatible_tasks"],
                "kimi_protocol_status": comparison.get("kimi_official_protocol", {}).get("status"),
                "source_attested": False,
                "model_identity_proven": False,
            },
        )

    @app.post("/api/audits")
    async def create_audit_job(payload: WebAuditRequest):
        if payload.coding_sandbox:
            raise HTTPException(
                400, "内置 Docker Coding Sandbox 已移除；代码能力请使用开源 lm-eval 深入评测"
            )
        if payload.profile not in {"quick", "standard", "deep"}:
            raise HTTPException(400, "检测档位只能是 quick、standard 或 deep")
        try:
            _validated_benchmark_profile(payload.benchmark_profile)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        if payload.retain_benchmark_reference:
            if not payload.benchmark_profile or not payload.benchmark_revisions_file:
                raise HTTPException(400, "要保存可对照的 Benchmark，请选择测试档位并提供本地版本清单")
            try:
                selected = lm_eval.resolve_builtin_profile(
                    payload.benchmark_profile, include_native_overlap=True
                )
                load_revision_manifest(
                    Path(payload.benchmark_revisions_file),
                    expected_tasks=list(selected["tasks"]),
                )
            except (OSError, ValueError, TypeError):
                raise HTTPException(400, "本地 Benchmark 版本清单无效或任务不匹配") from None
        elif payload.benchmark_revisions_file:
            raise HTTPException(400, "版本清单只能用于保存 Benchmark Reference")
        try:
            regression_paths = _resolve_regression_suites(
                app.state.regression_dir,
                payload.regression_suites,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        job_id = "audit_" + uuid.uuid4().hex[:12]
        store.create(
            job_id=job_id,
            kind="audit",
            model=payload.model,
            base_url=payload.base_url,
            profile=payload.profile,
            meta={
                "reference_id": payload.reference_id,
                "coding_sandbox": payload.coding_sandbox,
                "benchmark_profile": payload.benchmark_profile,
                "retain_benchmark_reference": payload.retain_benchmark_reference,
                "regression_suites": list(payload.regression_suites),
                "regression_status": (
                    "queued" if payload.regression_suites else "not_configured"
                ),
                "disallowed_upstreams": list(payload.disallowed_upstreams),
            },
        )
        asyncio.create_task(
            _run_audit_job(
                app,
                job_id,
                payload,
                regression_paths,
            )
        )
        return store.get(job_id)

    @app.post("/api/references")
    async def create_reference_job(payload: WebReferenceRequest):
        try:
            _validated_benchmark_profile(payload.benchmark_profile)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        if payload.benchmark_profile and not payload.quality_baseline:
            raise HTTPException(400, "Benchmark 需要同时开启质量 Baseline")
        if registry.exists(payload.id) and not payload.overwrite:
            raise HTTPException(409, "Reference 已存在；如需替换请启用覆盖")
        job_id = "ref_" + uuid.uuid4().hex[:12]
        store.create(
            job_id=job_id,
            kind="reference",
            model=payload.model,
            base_url=payload.base_url,
            profile="standard",
            meta={"reference_id": payload.id, "provider": payload.provider},
        )
        asyncio.create_task(_run_reference_job(app, job_id, payload))
        return store.get(job_id)

    @app.delete("/api/references/{reference_id}")
    async def delete_reference(reference_id: str):
        if not registry.delete(reference_id):
            raise HTTPException(404, "Reference 不存在")
        return {"ok": True}

    @app.get("/api/references")
    async def list_references():
        return {
            "references": [x.model_dump(mode="json") for x in registry.list()]
        }

    @app.get("/reports/{job_id}", response_class=HTMLResponse)
    async def report_html(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")
        if not item.get("report_path"):
            raise HTTPException(404, "报告尚未生成")
        path = Path(item["report_path"])
        if not path.exists():
            raise HTTPException(404, "报告文件不存在")
        content = path.read_text(encoding="utf-8")
        content = re.sub(
            r'href="evidence/(ev_[A-Za-z0-9_-]+)\\.json"',
            lambda m: f'href="/api/audits/{job_id}/evidence/{m.group(1)}"',
            content,
        )
        content = re.sub(
            r'href="regression/([^"]+)"',
            lambda m: (
                f'href="/api/audits/{job_id}/regression/{m.group(1)}"'
            ),
            content,
        )
        return HTMLResponse(content)

    @app.get("/api/audits/{job_id}/report")
    async def report_json(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")
        if not item.get("report_path"):
            raise HTTPException(404, "报告尚未生成")
        report_name = "comparison.json" if item["kind"] == "comparison" else "report.json"
        path = Path(item["report_path"]).with_name(report_name)
        if not path.exists():
            raise HTTPException(404, "报告 JSON 不存在")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/audits/{job_id}/evidence/{evidence_id}")
    async def evidence(job_id: str, evidence_id: str):
        if not evidence_id.startswith("ev_"):
            raise HTTPException(400, "Evidence ID 无效")
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")
        if not item.get("report_path"):
            raise HTTPException(404, "报告尚未生成")
        path = Path(item["report_path"]).parent / "evidence" / f"{evidence_id}.json"
        if not path.exists():
            raise HTTPException(404, "Evidence 不存在")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/audits/{job_id}/regression/{artifact_path:path}")
    async def regression_artifact(job_id: str, artifact_path: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")
        if not item.get("report_path"):
            raise HTTPException(404, "报告尚未生成")

        root = (
            Path(item["report_path"]).parent / "regression"
        ).resolve()
        candidate = (root / artifact_path).resolve()
        if not candidate.is_relative_to(root):
            raise HTTPException(400, "回归结果路径无效")
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(404, "回归结果文件不存在")
        return FileResponse(candidate)

    @app.get("/api/audits/{job_id}/download")
    async def download_report(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "任务不存在")
        if not item.get("report_path"):
            raise HTTPException(404, "报告尚未生成")
        root = Path(item["report_path"]).parent
        if not root.exists():
            raise HTTPException(404, "报告目录不存在")
        archive_base = app.state.state_dir / f"{job_id}-report"
        archive = Path(
            shutil.make_archive(str(archive_base), "zip", root_dir=str(root))
        )
        return FileResponse(
            archive,
            filename=f"{job_id}-report.zip",
            media_type="application/zip",
        )

    return app


def _safe_job_error(exc: Exception) -> str:
    """Safe status for SQLite, JSON and HTML; never serialize exception messages.

    External transports, subprocesses and parsers may include credentials,
    request bodies, model output or private local paths in str(exc).
    """
    if isinstance(exc, TimeoutError):
        return "任务超时，错误详情已隐藏"
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return "任务所需文件或访问权限不可用，错误详情已隐藏"
    if isinstance(exc, (ValueError, TypeError)):
        return "任务配置或结果数据无效，错误详情已隐藏"
    return "后台任务执行失败，错误详情已隐藏"


def _progress_label(name: str) -> str:
    if name.startswith("protocol:"):
        return "正在检查协议兼容"
    return {
        "integrity-suite": "正在检查参数完整性",
        "context-suite": "正在检查上下文能力",
        "routing-suite": "正在检查路由一致性",
        "capability-suite": "正在进行能力抽检",
        "coding-sandbox": "正在进行代码能力抽检",
        "fingerprint-reference": "正在对比统计指纹",
        "proxy-sleuth": "正在运行开源增强检测",
        "regression-suite": "正在运行回归规则",
        "strong-benchmark": "正在运行标准能力 Benchmark",
    }.get(name, "正在检测")


def _progress_value(name: str, current: int, total: int) -> float:
    if name.startswith("protocol:"):
        return min(0.38, 0.03 + 0.35 * (current / max(total, 1)))
    phase = {
        "integrity-suite": 0.45,
        "context-suite": 0.58,
        "routing-suite": 0.68,
        "capability-suite": 0.76,
        "coding-sandbox": 0.84,
        "fingerprint-reference": 0.89,
        "proxy-sleuth": 0.94,
        "regression-suite": 0.97,
        "strong-benchmark": 0.82,
    }
    return phase.get(name, 0.5)


async def _run_audit_job(
    app: FastAPI,
    job_id: str,
    payload: WebAuditRequest,
    regression_paths: list[str] | None = None,
) -> None:
    store: JobStore = app.state.store
    registry: ReferenceRegistry = app.state.registry
    try:
        store.update(job_id, status="running", progress=0.01, detail="正在准备检测")
        cfg = AuditConfig(
            target=AuditTarget(
                base_url=payload.base_url,
                model=payload.model,
                api_key_env="WEB_API_KEY_NOT_STORED",
                protocol="openai",
            ),
            profile=payload.profile,
            output_dir=str(app.state.output_dir),
            reference_id=payload.reference_id,
            reference_dir=str(registry.root),
            declared_context_tokens=payload.declared_context_tokens,
            proxy_sleuth_enabled=payload.proxy_sleuth,
            coding_sandbox_enabled=payload.coding_sandbox,
            benchmark_profile=payload.benchmark_profile,
            benchmark_evidence_dir=(
                str(app.state.state_dir / "benchmark-runs" / job_id)
                if payload.retain_benchmark_reference else None
            ),
            benchmark_revisions_file=(
                payload.benchmark_revisions_file
                if payload.retain_benchmark_reference else None
            ),
            regression=RegressionAuditConfig(
                suites=list(regression_paths or []),
            ),
            upstream_policy=UpstreamPolicyConfig(
                disallowed=list(payload.disallowed_upstreams),
            ),
        )

        def progress(name: str, current: int, total: int) -> None:
            store.update(
                job_id,
                status="running",
                progress=_progress_value(name, current, total),
                detail=_progress_label(name),
            )

        regression_work_dir = (
            app.state.state_dir / "regression-runs" / job_id
        )
        report = await run_audit(
            cfg,
            progress=progress,
            api_key_override=payload.api_key,
            regression_output_dir=regression_work_dir,
        )
        root = app.state.output_dir / job_id
        write_report(report, root)
        if regression_work_dir.exists():
            shutil.rmtree(regression_work_dir, ignore_errors=True)

        human = build_report_interpretation(report)
        regression_adapter = report.adapters.get("promptfoo_regression")
        regression_status = (
            regression_adapter.get("status")
            if isinstance(regression_adapter, dict)
            else "not_configured"
        )
        benchmark_meta = report.adapters.get("lm_eval_benchmark") or {}
        imported = benchmark_meta.get("snapshot_import") if isinstance(benchmark_meta, dict) else None
        benchmark_snapshots_dir = (
            str(app.state.state_dir / "benchmark-runs" / job_id / "snapshots")
            if isinstance(imported, dict) and imported.get("status") == "completed"
            else None
        )
        model_rule = report.adapters.get("model_rule")
        provider_provenance = _provider_provenance(
            [item.provider for item in report.provider_hypotheses[:5]]
        )

        store.finish(
            job_id,
            report_path=str(root / "report.html"),
            detail="检测已结束，请查看逐项结果和证据（模型身份未独立认证）",
            meta={
                "verdict": report.summary.final_verdict,
                "score": report.summary.overall_score,
                "provider_hypotheses": [
                    x.model_dump(mode="json") for x in report.provider_hypotheses
                ],
                "model_rule": model_rule,
                "provider_provenance": provider_provenance,
                "regression_suites": list(payload.regression_suites),
                "regression_status": regression_status,
                "benchmark_snapshots_dir": benchmark_snapshots_dir,
                "benchmark_snapshot_status": imported.get("status") if isinstance(imported, dict) else "not_requested",
                "upstream_policy": report.adapters.get("upstream_policy"),
                "human_summary": {
                    "decision": human["decision"],
                    "headline": human["headline"],
                    "tone": human["tone"],
                    "verdict_label": human["verdict_label"],
                    "confidence_label": human["confidence_label"],
                    "identity_state": human["identity"]["label"],
                    "provider_state": human["provider"]["label"],
                    "quality_state": human["quality"]["label"],
                    "quality_regressions": list(
                        human["quality"].get("regression_dimensions") or []
                    ),
                    "issue_count": len(human["issues"]),
                    "http_429_count": human["provider"]["http_429_count"],
                },
            },
        )
    except Exception as exc:
        store.fail(job_id, _safe_job_error(exc))


async def _run_reference_job(
    app: FastAPI,
    job_id: str,
    payload: WebReferenceRequest,
) -> None:
    store: JobStore = app.state.store
    registry: ReferenceRegistry = app.state.registry
    try:
        store.update(
            job_id,
            status="running",
            progress=0.05,
            detail="正在准备可信基准采集",
        )
        if payload.overwrite and registry.exists(payload.id):
            registry.delete(payload.id)

        target = AuditTarget(
            base_url=payload.base_url,
            model=payload.model,
            api_key_env="WEB_API_KEY_NOT_STORED",
            protocol="openai",
        )

        baseline = None
        if payload.quality_baseline:
            def baseline_progress(
                current: int,
                total: int,
                phase: str,
            ) -> None:
                progress_value = 0.08 + 0.47 * (
                    (current - (0 if phase == "completed" else 1))
                    / max(total, 1)
                )
                if phase == "completed":
                    progress_value = 0.08 + 0.47 * (
                        current / max(total, 1)
                    )
                store.update(
                    job_id,
                    status="running",
                    progress=max(0.08, min(0.55, progress_value)),
                    detail=(
                        f"官方/可信基准采集 {current}/{total}"
                        if phase == "running"
                        else f"基准第 {current}/{total} 次采集完成"
                    ),
                )

            reports, baseline = await collect_quality_baseline(
                target=target,
                api_key=payload.api_key,
                runs=payload.baseline_runs,
                profile="standard",
                coding_sandbox_enabled=False,
                benchmark_profile=payload.benchmark_profile,
                progress=baseline_progress,
            )
            report = reports[0]
        else:
            cfg = AuditConfig(
                target=target,
                profile="standard",
                capability_enabled=False,
                proxy_sleuth_enabled=False,
            )
            report = await run_audit(
                cfg,
                use_proxy_sleuth=False,
                api_key_override=payload.api_key,
            )

        store.update(
            job_id,
            progress=0.58,
            detail="基础基准已采集，正在处理统计指纹",
        )

        fp_path = None
        fp_meta = None
        if payload.fingerprint and fingerprint.availability().get("available"):
            fp_path = registry.path_for(payload.id) / "fingerprint.json"
            store.update(job_id, progress=0.62, detail="正在采集统计指纹")
            collected = await asyncio.to_thread(
                fingerprint.collect,
                base_url=payload.base_url,
                model=payload.model,
                api_key=payload.api_key,
                output=fp_path,
            )
            fp_meta = {
                **(collected.get("fingerprint") or {}),
                "collection": {
                    "split_half_jsd": collected.get("split_half_jsd"),
                    "adapter": collected.get("adapter"),
                    "warnings": collected.get("warnings") or [],
                },
            }

        store.update(
            job_id,
            progress=0.90,
            detail="正在保存可信 Reference 与质量基准",
        )
        manifest = registry.create_from_report(
            reference_id=payload.id,
            model=payload.model,
            provider=payload.provider,
            protocol="openai",
            report=report,
            fingerprint_path=fp_path,
            fingerprint_metadata=fp_meta,
            fingerprint_source="collected" if fp_path else None,
            baseline=baseline,
        )
        report_root = registry.path_for(payload.id) / "baseline-report"
        write_report(report, report_root)
        store.finish(
            job_id,
            report_path=str(report_root / "report.html"),
            detail=(
                f"Reference {manifest.id} 已保存"
                + (
                    f" · 质量基准 {manifest.baseline_runs} 次"
                    if manifest.baseline_artifact
                    else ""
                )
            ),
            meta={
                "reference_id": manifest.id,
                "baseline_runs": manifest.baseline_runs,
                "baseline_suite_version": manifest.baseline_suite_version,
                "benchmark_profile": payload.benchmark_profile,
                "fingerprint": bool(manifest.fingerprint_reference),
            },
        )
    except Exception as exc:
        store.fail(job_id, _safe_job_error(exc))
