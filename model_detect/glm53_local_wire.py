"""Capture actual lm-eval outgoing JSON against a loopback fake model endpoint.

This captures the request serialized by lm-eval's HTTP client, NOT a live
provider's server-side interpretation. No official/provider API key is used.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .adapters import lm_eval
from .glm53_benchmark import BENCHMARK_PROFILES


def capture_local_lm_eval_wire(
    level: str, *, reasoning_effort: str = "max",
    max_gen_toks: int = 1024, timeout_seconds: int = 300,
) -> dict[str, Any]:
    if level not in BENCHMARK_PROFILES:
        raise ValueError("unknown benchmark profile")
    if reasoning_effort not in {"low", "high", "max"}:
        raise ValueError("invalid reasoning effort")
    if not 256 <= max_gen_toks <= 32768:
        raise ValueError("invalid max_gen_toks")
    if not 30 <= timeout_seconds <= 600:
        raise ValueError("invalid timeout")

    captures: list[dict[str, Any]] = []
    capture_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 1 or length > 2 * 1024 * 1024:
                self.send_error(413)
                return
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                body = None
            if isinstance(body, dict):
                # Raw messages are held only in short-lived process memory.
                messages = body.get("messages")
                settings = {
                    k: v for k, v in body.items()
                    if k not in {"messages", "api_key", "authorization", "user"}
                }
                record = {
                    "message_sha256": hashlib.sha256(
                        json.dumps(messages, ensure_ascii=False,
                                   sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest(),
                    "settings_sha256": hashlib.sha256(
                        json.dumps(settings, ensure_ascii=False,
                                   sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest(),
                    "model_matches": body.get("model") == "glm-5.3",
                    "reasoning_effort": body.get("reasoning_effort"),
                    "max_tokens": body.get("max_tokens"),
                    "temperature_present": "temperature" in body,
                    "stop_present": "stop" in body,
                    "request_path_matches": self.path.endswith("/chat/completions"),
                }
                with capture_lock:
                    if len(captures) < 32:
                        captures.append(record)
            response = {
                "id": "offline-wire-synthetic", "object": "chat.completion",
                "created": 0, "model": "glm-5.3",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "0"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            encoded = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, fmt: str, *args: object) -> None:
            # Never log request paths, model messages or headers.
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="model-detect-wire-") as directory:
            result = lm_eval.run_endpoint(
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="glm-5.3", api_key="offline-test-key",
                tasks=BENCHMARK_PROFILES[level]["tasks"],
                output_path=Path(directory), limit=1, num_concurrent=1,
                max_retries=0, reasoning_effort=reasoning_effort,
                max_gen_toks=max_gen_toks, timeout_seconds=timeout_seconds,
                local_only=True,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    matching = bool(captures) and all(
        item["model_matches"] and item["reasoning_effort"] == reasoning_effort
        and item["request_path_matches"]
        for item in captures
    )
    return {
        "schema": "glm53-local-wire-capture-v1",
        "harness_returncode": result["returncode"],
        "capture_count": len(captures),
        "parameter_match": matching,
        "requests": captures,
        "offline_synthetic_endpoint": True,
        "external_model_api_calls": 0,
        "server_semantics_verified": False,
        "warning": (
            "Only actual outgoing JSON sent to local synthetic loopback was captured; "
            "this does NOT establish that an official/customer provider honors parameters. "
            "Local third-party task plugins may not honor offline download flags."
        ),
    }
