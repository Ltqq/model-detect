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

from .adapters import fingerprint
from .audit import run_audit
from .config import AuditConfig
from .models import AuditTarget
from .references import ReferenceRegistry
from .reporting import write_report
from .storage import JobStore


class WebAuditRequest(BaseModel):
    base_url: str
    api_key: str = Field(min_length=1)
    model: str
    profile: str = "standard"
    reference_id: str | None = None
    declared_context_tokens: int | None = None
    proxy_sleuth: bool = True


class WebReferenceRequest(BaseModel):
    id: str
    base_url: str
    api_key: str = Field(min_length=1)
    model: str
    provider: str = "trusted"
    fingerprint: bool = True
    overwrite: bool = False


def create_app(
    *,
    state_dir: str | Path = ".model-detect",
    reference_dir: str | Path = "references",
    output_dir: str | Path = "model-detect-output",
) -> FastAPI:
    app = FastAPI(title="model-detect", version="0.2.0")
    state_root = Path(state_dir)
    state_root.mkdir(parents=True, exist_ok=True)
    store = JobStore(state_root / "jobs.sqlite3")
    registry = ReferenceRegistry(reference_dir)
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    app.state.store = store
    app.state.registry = registry
    app.state.output_dir = Path(output_dir)
    app.state.state_dir = state_root

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "jobs": store.list(50),
                "references": registry.list(),
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

    @app.get("/api/jobs")
    async def jobs():
        return {"jobs": store.list(100)}

    @app.get("/api/jobs/{job_id}")
    async def job(job_id: str):
        try:
            return store.get(job_id)
        except KeyError:
            raise HTTPException(404, "job not found")

    @app.post("/api/audits")
    async def create_audit_job(payload: WebAuditRequest):
        if payload.profile not in {"quick", "standard", "deep"}:
            raise HTTPException(400, "profile must be quick, standard or deep")
        job_id = "audit_" + uuid.uuid4().hex[:12]
        store.create(
            job_id=job_id,
            kind="audit",
            model=payload.model,
            base_url=payload.base_url,
            profile=payload.profile,
            meta={"reference_id": payload.reference_id},
        )
        asyncio.create_task(
            _run_audit_job(
                app,
                job_id,
                payload,
            )
        )
        return store.get(job_id)

    @app.post("/api/references")
    async def create_reference_job(payload: WebReferenceRequest):
        if registry.exists(payload.id) and not payload.overwrite:
            raise HTTPException(409, "reference already exists; set overwrite=true to replace it")
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
            raise HTTPException(404, "reference not found")
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
            raise HTTPException(404, "job not found")
        if not item.get("report_path"):
            raise HTTPException(404, "report not ready")
        path = Path(item["report_path"])
        if not path.exists():
            raise HTTPException(404, "report file missing")
        content = path.read_text(encoding="utf-8")
        content = re.sub(
            r'href="evidence/(ev_[A-Za-z0-9_-]+)\\.json"',
            lambda m: f'href="/api/audits/{job_id}/evidence/{m.group(1)}"',
            content,
        )
        return HTMLResponse(content)

    @app.get("/api/audits/{job_id}/report")
    async def report_json(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "job not found")
        if not item.get("report_path"):
            raise HTTPException(404, "report not ready")
        path = Path(item["report_path"]).with_name("report.json")
        if not path.exists():
            raise HTTPException(404, "report JSON missing")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/audits/{job_id}/evidence/{evidence_id}")
    async def evidence(job_id: str, evidence_id: str):
        if not evidence_id.startswith("ev_"):
            raise HTTPException(400, "invalid evidence id")
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "job not found")
        if not item.get("report_path"):
            raise HTTPException(404, "report not ready")
        path = Path(item["report_path"]).parent / "evidence" / f"{evidence_id}.json"
        if not path.exists():
            raise HTTPException(404, "evidence not found")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/audits/{job_id}/download")
    async def download_report(job_id: str):
        try:
            item = store.get(job_id)
        except KeyError:
            raise HTTPException(404, "job not found")
        if not item.get("report_path"):
            raise HTTPException(404, "report not ready")
        root = Path(item["report_path"]).parent
        if not root.exists():
            raise HTTPException(404, "report directory missing")
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


def _progress_value(name: str, current: int, total: int) -> float:
    if name.startswith("protocol:"):
        return min(0.38, 0.03 + 0.35 * (current / max(total, 1)))
    phase = {
        "integrity-suite": 0.45,
        "context-suite": 0.58,
        "routing-suite": 0.68,
        "capability-suite": 0.80,
        "fingerprint-reference": 0.88,
        "proxy-sleuth": 0.94,
    }
    return phase.get(name, 0.5)


async def _run_audit_job(
    app: FastAPI,
    job_id: str,
    payload: WebAuditRequest,
) -> None:
    store: JobStore = app.state.store
    registry: ReferenceRegistry = app.state.registry
    try:
        store.update(job_id, status="running", progress=0.01, detail="starting")
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
        )

        def progress(name: str, current: int, total: int) -> None:
            store.update(
                job_id,
                status="running",
                progress=_progress_value(name, current, total),
                detail=name,
            )

        report = await run_audit(
            cfg,
            progress=progress,
            api_key_override=payload.api_key,
        )
        root = app.state.output_dir / job_id
        write_report(report, root)
        store.finish(
            job_id,
            report_path=str(root / "report.html"),
            detail=f"{report.summary.final_verdict} / {report.summary.overall_score}",
            meta={
                "verdict": report.summary.final_verdict,
                "score": report.summary.overall_score,
                "provider_hypotheses": [
                    x.model_dump(mode="json") for x in report.provider_hypotheses
                ],
            },
        )
    except Exception as exc:
        store.fail(job_id, f"{type(exc).__name__}: {exc}")


async def _run_reference_job(
    app: FastAPI,
    job_id: str,
    payload: WebReferenceRequest,
) -> None:
    store: JobStore = app.state.store
    registry: ReferenceRegistry = app.state.registry
    try:
        store.update(job_id, status="running", progress=0.05, detail="collecting protocol baseline")
        if payload.overwrite and registry.exists(payload.id):
            registry.delete(payload.id)

        cfg = AuditConfig(
            target=AuditTarget(
                base_url=payload.base_url,
                model=payload.model,
                api_key_env="WEB_API_KEY_NOT_STORED",
                protocol="openai",
            ),
            profile="standard",
            capability_enabled=False,
            proxy_sleuth_enabled=False,
        )
        report = await run_audit(
            cfg,
            use_proxy_sleuth=False,
            api_key_override=payload.api_key,
        )
        store.update(job_id, progress=0.55, detail="protocol baseline collected")

        fp_path = None
        if payload.fingerprint and fingerprint.availability().get("available"):
            fp_path = registry.path_for(payload.id) / "fingerprint.json"
            store.update(job_id, progress=0.60, detail="collecting statistical fingerprint")
            await asyncio.to_thread(
                fingerprint.collect,
                base_url=payload.base_url,
                model=payload.model,
                api_key=payload.api_key,
                output=fp_path,
            )

        manifest = registry.create_from_report(
            reference_id=payload.id,
            model=payload.model,
            provider=payload.provider,
            protocol="openai",
            report=report,
            fingerprint_path=fp_path,
        )
        report_root = registry.path_for(payload.id) / "baseline-report"
        write_report(report, report_root)
        store.finish(
            job_id,
            report_path=str(report_root / "report.html"),
            detail=f"reference {manifest.id} saved",
            meta={"reference_id": manifest.id},
        )
    except Exception as exc:
        store.fail(job_id, f"{type(exc).__name__}: {exc}")
