"""Exercise the ORIGINAL lm-eval scorer over a loopback-only fake model.

No vendor account, official API, HF dataset download, or model billing.
Validates upstream task loading, local-chat API transport, scoring and result JSON.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from model_detect.adapters.lm_eval import (
    build_command, parse_result_payload, _validate_profile_run_results,
)


class FakeChatHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert payload.get("model") == "offline-smoke"
        answer = {
            "id": "offline-chat", "object": "chat.completion",
            "model": "offline-smoke", "choices": [{
                "index": 0, "message": {"role": "assistant", "content": "42"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
        }
        body = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        return


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="md-real-harness-") as tmp:
        root = Path(tmp)
        tasks = root / "tasks"
        tasks.mkdir()
        (tasks / "samples.jsonl").write_text(
            json.dumps({"question": "What is six times seven? Answer with digits only.", "answer": "42"}) + "\n",
            encoding="utf-8",
        )
        task_cfg = {
            "task": "md_offline_harness_smoke",
            "dataset_path": "json",
            "dataset_kwargs": {"data_files": {"test": str(tasks / "samples.jsonl")}},
            "test_split": "test",
            "output_type": "generate_until",
            "doc_to_text": "{{question}}",
            "doc_to_target": "{{answer}}",
            "generation_kwargs": {"until": ["\\n"], "max_gen_toks": 16},
            "metric_list": [{"metric": "exact_match", "aggregation": "mean", "higher_is_better": True}],
        }
        import yaml
        (tasks / "md_offline_harness_smoke.yaml").write_text(
            yaml.safe_dump(task_cfg, allow_unicode=True), encoding="utf-8"
        )

        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeChatHandler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            cmd = build_command(
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                model="offline-smoke", tasks=["md_offline_harness_smoke"],
                output_path=root / "results", limit=1, max_retries=0,
            )
            cmd += ["--include_path", str(tasks)]
            env = dict(os.environ)
            env["OPENAI_API_KEY"] = "offline-test-placeholder"
            env["HF_HUB_OFFLINE"] = "1"
            env["HF_DATASETS_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
            if proc.returncode:
                print(proc.stdout[-1500:])
                print(proc.stderr[-4000:])
                raise SystemExit(f"Original upstream lm-eval failed (exit {proc.returncode})")

            candidates = list((root / "results").rglob("results*.json"))
            if not candidates:
                raise AssertionError("Original upstream did not emit results JSON")
            payload = json.loads(candidates[0].read_text(encoding="utf-8"))
            # Validate the exact same reportability contract on a real run of
            # the original upstream scorer, not just on synthetic parsed JSON.
            _validate_profile_run_results(
                parse_result_payload(payload),
                requested_tasks=["md_offline_harness_smoke"],
                output_path=root / "results",
                log_samples=False,
            )
            scores = payload["results"]["md_offline_harness_smoke"]
            exact_values = [v for k, v in scores.items() if k.startswith("exact_match") and isinstance(v, (float, int))]
            assert exact_values and max(exact_values) == 1.0, scores
            print(json.dumps({
                "original_upstream_scorer_executed": True,
                "task": "md_offline_harness_smoke",
                "metric": "exact_match",
                "score": max(exact_values),
                "external_model_api_calls": 0,
                "note": "synthetic harness/transport smoke, NOT vendor model capability evidence",
            }))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
