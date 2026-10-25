#!/usr/bin/env python3
"""OpenAI-compatible plan/execute proxy for the 262k local champion stack."""
from __future__ import annotations

import copy
import http.client
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "127.0.0.1"
PORT = int(os.environ.get("CHAMPION_PORT", "7870"))
UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = int(os.environ.get("SPLASH_PORT", "18796"))
CHAMPION_MODEL = "qwen3.8-27b-champion-262k"
UPSTREAM_MODEL = "incoai/Qwen3.8-27B-Splash"
PLAN_MAX_TOKENS = 128
PLAN_MAX_CHARS = 1_200
CONTEXT_WINDOW = 262_144


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                parts.append(str(item.get("text") or ""))
        return "\n".join(parts)
    return ""


def build_plan_prompt(request: dict[str, Any]) -> str:
    messages = request.get("messages") or []
    system_parts = [_text(m.get("content")) for m in messages if m.get("role") in {"system", "developer"}]
    user_parts = [_text(m.get("content")) for m in messages if m.get("role") == "user"]
    tools = []
    for tool in request.get("tools") or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            tools.append(str(fn["name"]))
    context = "\n".join(system_parts[-2:] + user_parts[-3:])[-12_000:]
    tool_text = ", ".join(tools) if tools else "none"
    prompt = (
        "Create an ultra-concise execution plan for another pass of the same Qwen model. "
        "Prioritize correctness, constraints, failure modes, and verification. Do not write the final answer.\n\n"
        f"Available tools: {tool_text}\n\nTask context:\n{context}"
    )
    return prompt[:16_000]


def should_plan(request: dict[str, Any]) -> bool:
    max_tokens = int(request.get("max_tokens") or request.get("max_completion_tokens") or 0)
    if 0 < max_tokens <= 512:
        return False
    messages = request.get("messages") or []
    last_user = next((_text(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), "")
    return len(last_user.strip()) >= 48 or max_tokens > 512


def build_executor_request(request: dict[str, Any], plan: str) -> dict[str, Any]:
    out = copy.deepcopy(request)
    out["model"] = UPSTREAM_MODEL
    out["reasoning_effort"] = "none"
    messages = list(out.get("messages") or [])
    messages.append({"role": "assistant", "reasoning_content": plan[:PLAN_MAX_CHARS], "content": ""})
    messages.append(
        {
            "role": "user",
            "content": "Execute the previous request now using the internal plan. Return the final answer only; do not repeat the plan.",
        }
    )
    out["messages"] = messages
    return out


def _headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    result = {"Content-Type": "application/json"}
    for key in ("Authorization", "x-api-key", "anthropic-version"):
        value = handler.headers.get(key)
        if value:
            result[key] = value
    return result


def _request_json(path: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 21_600):
    body = json.dumps(payload).encode()
    conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=timeout)
    conn.request("POST", path, body=body, headers={**headers, "Content-Length": str(len(body))})
    response = conn.getresponse()
    raw = response.read()
    status = response.status
    response_headers = dict(response.getheaders())
    conn.close()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"error": {"message": raw.decode("utf-8", "replace"), "type": "upstream_error"}}
    return status, response_headers, data


def _extract_plan(response: dict[str, Any]) -> str:
    message = ((response.get("choices") or [{}])[0].get("message") or {})
    plan = message.get("content") or message.get("reasoning_content") or ""
    return str(plan).strip()[:PLAN_MAX_CHARS]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[champion] {self.address_string()} {fmt % args}", flush=True)

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/health", "/ready"}:
            self._send_json(200, {"status": "ok", "model": CHAMPION_MODEL, "context_window": CONTEXT_WINDOW})
            return
        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": CHAMPION_MODEL,
                            "object": "model",
                            "owned_by": "local-champion",
                            "context_window": CONTEXT_WINDOW,
                            "max_model_len": CONTEXT_WINDOW,
                        }
                    ],
                },
            )
            return
        self._proxy_raw("GET", self.path, None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "invalid JSON", "type": "invalid_request_error"}})
            return
        if self.path == "/v1/chat/completions" and not self.headers.get("X-Champion-Bypass"):
            self._champion_chat(payload)
            return
        if isinstance(payload, dict) and payload.get("model") == CHAMPION_MODEL:
            payload["model"] = UPSTREAM_MODEL
        self._proxy_payload(self.path, payload)

    def _champion_chat(self, payload: dict[str, Any]) -> None:
        if not should_plan(payload):
            direct = copy.deepcopy(payload)
            direct["model"] = UPSTREAM_MODEL
            direct["reasoning_effort"] = "none"
            self._proxy_payload("/v1/chat/completions", direct)
            return
        headers = _headers(self)
        planner = {
            "model": UPSTREAM_MODEL,
            "messages": [{"role": "user", "content": build_plan_prompt(payload)}],
            "max_tokens": PLAN_MAX_TOKENS,
            "temperature": 0,
            "stream": False,
            "reasoning_effort": "medium",
        }
        status, _, response = _request_json("/v1/chat/completions", planner, headers, timeout=600)
        if status >= 400:
            self._send_json(status, response)
            return
        plan = _extract_plan(response)
        if not plan:
            self._send_json(502, {"error": {"message": "planner returned no plan", "type": "planner_error"}})
            return
        self._proxy_payload("/v1/chat/completions", build_executor_request(payload, plan))

    def _proxy_payload(self, path: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=21_600)
        conn.request("POST", path, body=body, headers={**_headers(self), "Content-Length": str(len(body))})
        response = conn.getresponse()
        stream = bool(payload.get("stream"))
        self.send_response(response.status)
        content_type = response.getheader("Content-Type") or "application/json"
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", response.getheader("Cache-Control") or "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        if stream:
            while chunk := response.read(8192):
                self.wfile.write(chunk)
                self.wfile.flush()
        else:
            self.wfile.write(response.read())
        conn.close()
        self.close_connection = True

    def _proxy_raw(self, method: str, path: str, body: bytes | None) -> None:
        conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=60)
        conn.request(method, path, body=body, headers=_headers(self))
        response = conn.getresponse()
        raw = response.read()
        self.send_response(response.status)
        self.send_header("Content-Type", response.getheader("Content-Type") or "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        conn.close()


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Champion proxy ready on http://{HOST}:{PORT}/v1 ({CHAMPION_MODEL})", flush=True)
    server.serve_forever()
