from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_IMAGES = {
    "python": os.getenv("MODEL_DETECT_PYTHON_IMAGE", "python:3.12-alpine"),
    "go": os.getenv("MODEL_DETECT_GO_IMAGE", "golang:1.24-alpine"),
}


@dataclass
class SandboxLimits:
    memory: str = "256m"
    cpus: str = "1.0"
    pids_limit: int = 64
    timeout_seconds: float = 12.0
    max_output_bytes: int = 128 * 1024
    tmpfs_size: str = "128m"


@dataclass
class SandboxResult:
    status: str
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    output_limited: bool = False
    duration_ms: float = 0.0
    image: str | None = None
    command: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass" and self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "output_limited": self.output_limited,
            "duration_ms": self.duration_ms,
            "image": self.image,
            "command": self.command,
            "error": self.error,
        }


def availability() -> dict[str, Any]:
    binary = shutil.which("docker")
    return {
        "available": bool(binary),
        "binary": binary,
        "images": DEFAULT_IMAGES.copy(),
        "security": "docker-isolated-only",
    }


class DockerSandbox:
    def __init__(
        self,
        *,
        limits: SandboxLimits | None = None,
        auto_pull: bool = True,
    ) -> None:
        self.binary = shutil.which("docker")
        self.limits = limits or SandboxLimits()
        self.auto_pull = auto_pull

    def _require(self) -> str:
        if not self.binary:
            raise RuntimeError("Docker is not installed or not on PATH")
        return self.binary

    def _image_present(self, image: str) -> bool:
        binary = self._require()
        proc = subprocess.run(
            [binary, "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        return proc.returncode == 0

    def _ensure_image(self, image: str) -> None:
        if self._image_present(image):
            return
        if not self.auto_pull:
            raise RuntimeError(
                f"Docker image {image!r} is not available locally and auto-pull is disabled"
            )
        binary = self._require()
        proc = subprocess.run(
            [binary, "pull", image],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"failed to pull Docker image {image!r}: {(proc.stdout or '')[-1500:]}"
            )

    def _docker_command(
        self,
        *,
        container_name: str,
        workspace: Path,
        image: str,
        command: list[str],
        language: str,
    ) -> list[str]:
        binary = self._require()
        env_args: list[str] = []
        if language == "python":
            env_args = ["-e", "PYTHONDONTWRITEBYTECODE=1"]
        elif language == "go":
            env_args = [
                "-e", "GOCACHE=/tmp/go-build",
                "-e", "GOMODCACHE=/tmp/go-mod",
                "-e", "GOTMPDIR=/tmp",
            ]

        return [
            binary,
            "run",
            "--name", container_name,
            "--rm",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", self.limits.memory,
            "--cpus", self.limits.cpus,
            "--pids-limit", str(self.limits.pids_limit),
            "--user", "65534:65534",
            "--tmpfs", f"/tmp:rw,nosuid,nodev,size={self.limits.tmpfs_size},mode=1777",
            "--mount", f"type=bind,src={workspace.resolve()},dst=/workspace,readonly",
            "--workdir", "/workspace",
            *env_args,
            image,
            *command,
        ]

    def run(
        self,
        *,
        language: str,
        files: dict[str, str],
        command: list[str],
    ) -> SandboxResult:
        started = time.perf_counter()
        image = DEFAULT_IMAGES.get(language)
        if not image:
            return SandboxResult(status="error", exit_code=None, error=f"unsupported language: {language}")
        if not self.binary:
            return SandboxResult(
                status="unavailable",
                exit_code=None,
                image=image,
                error="Docker unavailable; untrusted code was not executed",
            )

        try:
            self._ensure_image(image)
        except Exception as exc:
            return SandboxResult(
                status="unavailable",
                exit_code=None,
                image=image,
                error=f"{type(exc).__name__}: {exc}",
            )

        with tempfile.TemporaryDirectory(prefix="model-detect-code-") as tmp:
            workspace = Path(tmp)
            for name, content in files.items():
                path = workspace / name
                if path.parent != workspace:
                    return SandboxResult(
                        status="error",
                        exit_code=None,
                        image=image,
                        error=f"unsafe sandbox filename rejected: {name}",
                    )
                path.write_text(content, encoding="utf-8")

            container_name = "model-detect-" + uuid.uuid4().hex[:12]
            docker_cmd = self._docker_command(
                container_name=container_name,
                workspace=workspace,
                image=image,
                command=command,
                language=language,
            )
            stdout_path = workspace / "_stdout.txt"
            stderr_path = workspace / "_stderr.txt"
            timed_out = False
            output_limited = False
            proc: subprocess.Popen[Any] | None = None
            try:
                with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
                    proc = subprocess.Popen(docker_cmd, stdout=out, stderr=err)
                    deadline = time.monotonic() + self.limits.timeout_seconds
                    while proc.poll() is None:
                        if time.monotonic() >= deadline:
                            timed_out = True
                            break
                        total_output = sum(
                            p.stat().st_size if p.exists() else 0
                            for p in (stdout_path, stderr_path)
                        )
                        if total_output > self.limits.max_output_bytes:
                            output_limited = True
                            break
                        time.sleep(0.05)

                    if timed_out or output_limited:
                        subprocess.run(
                            [self.binary, "rm", "-f", container_name],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=10,
                            check=False,
                        )
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        try:
                            proc.wait(timeout=3)
                        except Exception:
                            pass
                    else:
                        proc.wait(timeout=2)
            except Exception as exc:
                try:
                    subprocess.run(
                        [self.binary, "rm", "-f", container_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        check=False,
                    )
                except Exception:
                    pass
                return SandboxResult(
                    status="error",
                    exit_code=proc.returncode if proc else None,
                    image=image,
                    command=_redact_mount_source(docker_cmd),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    error=f"{type(exc).__name__}: {exc}",
                )

            stdout = _read_capped(stdout_path, self.limits.max_output_bytes // 2)
            stderr = _read_capped(stderr_path, self.limits.max_output_bytes // 2)
            exit_code = proc.returncode if proc is not None else None
            if timed_out:
                status = "timeout"
            elif output_limited:
                status = "output_limit"
            elif exit_code == 0:
                status = "pass"
            else:
                status = "fail"
            return SandboxResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
                output_limited=output_limited,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                image=image,
                command=_redact_mount_source(docker_cmd),
            )


def _read_capped(path: Path, limit: int) -> str:
    try:
        data = path.read_bytes()[:limit]
    except OSError:
        return ""
    text = data.decode("utf-8", errors="replace")
    if path.exists() and path.stat().st_size > limit:
        text += "\n...[truncated]"
    return text


def _redact_mount_source(command: list[str]) -> list[str]:
    out = []
    for item in command:
        if item.startswith("type=bind,src="):
            parts = item.split(",")
            out.append(",".join(
                "src=<temporary-workspace>" if p.startswith("src=") else p
                for p in parts
            ))
        else:
            out.append(item)
    return out
