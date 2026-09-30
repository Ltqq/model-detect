from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model TEXT,
                    base_url TEXT,
                    profile TEXT,
                    progress REAL NOT NULL DEFAULT 0,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    report_path TEXT,
                    error TEXT,
                    meta_json TEXT
                )
                """
            )
            conn.commit()

    def create(
        self,
        *,
        job_id: str,
        kind: str,
        model: str,
        base_url: str,
        profile: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created_at = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs
                (id, kind, status, model, base_url, profile, progress, detail, created_at, meta_json)
                VALUES (?, ?, 'queued', ?, ?, ?, 0, 'queued', ?, ?)
                """,
                (
                    job_id,
                    kind,
                    model,
                    base_url,
                    profile,
                    created_at,
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
        return self.get(job_id)

    def update(self, job_id: str, **values: Any) -> dict[str, Any]:
        allowed = {
            "status",
            "progress",
            "detail",
            "finished_at",
            "report_path",
            "error",
            "meta_json",
        }
        payload = {k: v for k, v in values.items() if k in allowed}
        if not payload:
            return self.get(job_id)
        parts = ", ".join(f"{k}=?" for k in payload)
        args = list(payload.values()) + [job_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {parts} WHERE id=?", args)
            conn.commit()
        return self.get(job_id)

    def finish(
        self,
        job_id: str,
        *,
        report_path: str | None = None,
        detail: str = "done",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.update(
            job_id,
            status="done",
            progress=1.0,
            detail=detail,
            finished_at=_now(),
            report_path=report_path,
            meta_json=json.dumps(meta or {}, ensure_ascii=False),
        )

    def fail(self, job_id: str, error: str) -> dict[str, Any]:
        return self.update(
            job_id,
            status="failed",
            detail="failed",
            finished_at=_now(),
            error=error,
        )

    def get(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._row(row)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._row(row) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        out = dict(row)
        try:
            out["meta"] = json.loads(out.pop("meta_json") or "{}")
        except Exception:
            out["meta"] = {}
            out.pop("meta_json", None)
        return out
