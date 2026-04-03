#!/usr/bin/env python3
"""
Claude OAuth Proxy — Docker-adapted version.
Uses curl-cffi with Chrome TLS fingerprint and injects required cloaking headers
to enable sonnet/opus access with OAuth tokens on api.anthropic.com.

Token source priority:
  1. ANTHROPIC_OAUTH_KEY env var (primary for Docker deployment)
  2. ~/.claude/.credentials.json with auto-refresh (fallback)

Endpoints:
  POST /v1/messages          (Anthropic native format)
  POST /v1/chat/completions  (OpenAI-compat -> Anthropic)
  GET  /v1/models
  GET  /health
  GET  /
"""

from __future__ import annotations

import json
import os
import time
import threading
from pathlib import Path
from typing import Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.request

try:
    from curl_cffi import requests as cffi_requests
    CFFI_AVAILABLE = True
except ImportError:
    CFFI_AVAILABLE = False

# -- Config -------------------------------------------------------------------
PORT = int(os.getenv("PROXY_PORT", "8319"))
HOST = "0.0.0.0"
CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
ANTHROPIC_API = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "claude-code-20250219,oauth-2025-04-20,interleaved-thinking-2025-05-14,context-management-2025-06-27,prompt-caching-scope-2026-01-05"
TOKEN_REFRESH_URL = "https://api.anthropic.com/v1/oauth/token"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

# In Docker, allow all container traffic (no subnet restriction)
ALLOWED_PREFIX = os.getenv("ALLOWED_PREFIX", "")

# Cloaking string required to unlock sonnet/opus model access
BILLING_HEADER = "x-anthropic-billing-header: cc_version=2.1.63.e4d; cc_entrypoint=cli; cch=ce2dd;"

# -- Token management ---------------------------------------------------------
_lock = threading.Lock()


def _load_credentials() -> dict:
    return json.loads(CREDENTIALS_PATH.read_text())


def _save_credentials(creds: dict) -> None:
    CREDENTIALS_PATH.write_text(json.dumps(creds, indent=2))


def _oauth_refresh(refresh_tok: str):
    payload = json.dumps({
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": OAUTH_CLIENT_ID,
    }).encode()
    req = urllib.request.Request(
        TOKEN_REFRESH_URL, data=payload,
        headers={"Content-Type": "application/json", "anthropic-version": ANTHROPIC_VERSION},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data.get("access_token"), data.get("refresh_token"), data.get("expires_in")


def get_token() -> str:
    # Primary: env var (Docker deployment)
    env_token = os.getenv("ANTHROPIC_OAUTH_KEY", "").strip()
    if env_token:
        return env_token

    # Fallback: credentials.json with auto-refresh
    with _lock:
        creds = _load_credentials()
        oauth = creds["claudeAiOauth"]
        expires_at = oauth.get("expiresAt", 0)
        if expires_at < (time.time() + 300) * 1000:
            refresh_tok = oauth.get("refreshToken", "")
            if refresh_tok:
                try:
                    new_access, new_refresh, expires_in = _oauth_refresh(refresh_tok)
                    if new_access:
                        oauth["accessToken"] = new_access
                        if new_refresh:
                            oauth["refreshToken"] = new_refresh
                        if expires_in:
                            oauth["expiresAt"] = int((time.time() + expires_in) * 1000)
                        creds["claudeAiOauth"] = oauth
                        _save_credentials(creds)
                        print(f"[proxy] Token refreshed: {new_access[:25]}...")
                except Exception as e:
                    print(f"[proxy] Token refresh failed: {e}")
        return oauth["accessToken"]


# -- Request builder ----------------------------------------------------------
def _build_headers(token: str, stream: bool = False) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": OAUTH_BETA,
        "Anthropic-Dangerous-Direct-Browser-Access": "true",
        "X-App": "cli",
        "X-Stainless-Arch": "x86_64",
        "X-Stainless-Lang": "js",
        "X-Stainless-Os": "Linux",
        "X-Stainless-Package-Version": "0.74.0",
        "X-Stainless-Retry-Count": "0",
        "X-Stainless-Runtime": "node",
        "X-Stainless-Runtime-Version": "v22.22.1",
        "X-Stainless-Timeout": "600",
        "User-Agent": "claude-cli/2.1.85 (external, sdk-cli)",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }
    if stream:
        h["Accept"] = "text/event-stream"
        h["Accept-Encoding"] = "identity"
    else:
        h["Accept"] = "application/json"
        h["Accept-Encoding"] = "gzip, deflate, br, zstd"
    return h


def _inject_cloaking(body: dict) -> dict:
    body = dict(body)
    existing_system = body.get("system")
    cloaking_block = {"type": "text", "text": BILLING_HEADER}
    if existing_system is None:
        body["system"] = [cloaking_block,
                          {"type": "text", "text": "You are a helpful assistant.",
                           "cache_control": {"type": "ephemeral"}}]
    elif isinstance(existing_system, str):
        body["system"] = [cloaking_block,
                          {"type": "text", "text": existing_system,
                           "cache_control": {"type": "ephemeral"}}]
    elif isinstance(existing_system, list):
        body["system"] = [cloaking_block] + existing_system
    return body


def _normalize_messages(body: dict) -> dict:
    body = dict(body)
    msgs = []
    for m in body.get("messages", []):
        m = dict(m)
        content = m.get("content")
        if isinstance(content, str):
            m["content"] = [{"type": "text", "text": content}]
        msgs.append(m)
    body["messages"] = msgs
    return body


# -- Model catalog ------------------------------------------------------------
MODELS = [
    "claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101",
    "claude-opus-4-1-20250805", "claude-opus-4-20250514",
    "claude-sonnet-4-20250514", "claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022",
]

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-6", "claude-sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6", "claude-opus": "claude-opus-4-6",
    "haiku": "claude-haiku-4-5-20251001", "claude-haiku": "claude-haiku-4-5-20251001",
}


def _resolve_model(name: str) -> str:
    base = name.split(":")[0].strip()
    return MODEL_ALIASES.get(base, base)


def models_response() -> dict:
    now = int(time.time())
    return {"object": "list",
            "data": [{"id": m, "object": "model", "created": now, "owned_by": "anthropic"} for m in MODELS]}


# -- Format converters --------------------------------------------------------
def openai_to_anthropic(body: dict) -> dict:
    messages = body.get("messages", [])
    system = None
    filtered = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            system = m.get("content", "")
            continue
        if role == "tool":
            tool_result: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", "unknown"),
                "content": m.get("content", ""),
            }
            if filtered and filtered[-1]["role"] == "user" and isinstance(filtered[-1].get("content"), list):
                filtered[-1]["content"].append(tool_result)
            else:
                filtered.append({"role": "user", "content": [tool_result]})
            continue
        if role == "assistant" and m.get("tool_calls"):
            content: list[dict] = []
            text = m.get("content") or ""
            if text:
                content.append({"type": "text", "text": text})
            for tc in m.get("tool_calls", []):
                args = tc.get("function", {}).get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"toolu_{len(content)}"),
                    "name": tc.get("function", {}).get("name", "unknown"),
                    "input": args,
                })
            filtered.append({"role": "assistant", "content": content})
            continue
        content = m.get("content", "")
        if role == "assistant" and not content:
            continue
        filtered.append({"role": role, "content": content})

    result: dict[str, Any] = {
        "model": _resolve_model(body.get("model", "claude-sonnet-4-6")),
        "messages": filtered,
        "max_tokens": body.get("max_tokens", 8192),
        "stream": body.get("stream", False),
    }
    if system:
        result["system"] = system
    if "temperature" in body:
        result["temperature"] = body["temperature"]
    if body.get("tools"):
        anthropic_tools = []
        for t in body["tools"]:
            if t.get("type") == "function":
                f = t["function"]
                anthropic_tools.append({
                    "name": f.get("name", ""),
                    "description": f.get("description", ""),
                    "input_schema": f.get("parameters", {"type": "object", "properties": {}}),
                })
        if anthropic_tools:
            result["tools"] = anthropic_tools
    return result


def anthropic_to_openai(body: dict, model: str) -> dict:
    content_blocks = body.get("content", [])
    text = " ".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
    usage = body.get("usage", {})
    tool_calls = []
    for i, b in enumerate(content_blocks):
        if b.get("type") == "tool_use":
            tool_calls.append({
                "id": b.get("id", f"call_{i}"),
                "type": "function",
                "function": {
                    "name": b.get("name", ""),
                    "arguments": json.dumps(b.get("input", {})),
                },
            })
    finish_reason = "tool_calls" if tool_calls else body.get("stop_reason", "stop")
    message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": body.get("id", ""),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": usage.get("input_tokens", 0),
                  "completion_tokens": usage.get("output_tokens", 0),
                  "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)},
    }


def anthropic_stream_to_openai(chunk: bytes, model: str, state: dict | None = None) -> bytes | None:
    if state is None:
        state = {}
    line = chunk.decode(errors="ignore").strip()
    if not line.startswith("data:"):
        return None
    data_str = line[5:].strip()
    if data_str == "[DONE]":
        return b"data: [DONE]\n\n"
    try:
        data = json.loads(data_str)
    except Exception:
        return None
    etype = data.get("type", "")
    now = int(time.time())

    if etype == "content_block_start":
        cb = data.get("content_block", {})
        if cb.get("type") == "tool_use":
            idx = data.get("index", 0)
            state.setdefault("tool_calls", {})[idx] = {
                "id": cb.get("id", ""), "name": cb.get("name", ""), "arguments": "",
            }
            out = {"id": "", "object": "chat.completion.chunk", "created": now, "model": model,
                   "choices": [{"index": 0, "delta": {"tool_calls": [{
                       "index": idx, "id": cb.get("id", ""), "type": "function",
                       "function": {"name": cb.get("name", ""), "arguments": ""},
                   }]}, "finish_reason": None}]}
            return f"data: {json.dumps(out)}\n\n".encode()

    elif etype == "content_block_delta":
        delta = data.get("delta", {})
        idx = data.get("index", 0)
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            out = {"id": "", "object": "chat.completion.chunk", "created": now, "model": model,
                   "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]}
            return f"data: {json.dumps(out)}\n\n".encode()
        elif delta.get("type") == "input_json_delta":
            partial = delta.get("partial_json", "")
            tc = state.get("tool_calls", {}).get(idx)
            if tc:
                tc["arguments"] += partial
            out = {"id": "", "object": "chat.completion.chunk", "created": now, "model": model,
                   "choices": [{"index": 0, "delta": {
                       "tool_calls": [{"index": idx, "function": {"arguments": partial}}]
                   }, "finish_reason": None}]}
            return f"data: {json.dumps(out)}\n\n".encode()

    elif etype == "message_delta":
        stop_reason = data.get("delta", {}).get("stop_reason", "end_turn")
        finish_reason = "tool_calls" if stop_reason == "tool_use" else "stop"
        state["finish_reason"] = finish_reason
        out = {"id": "", "object": "chat.completion.chunk", "created": now, "model": model,
               "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]}
        return f"data: {json.dumps(out)}\n\n".encode()

    elif etype == "message_stop":
        if "finish_reason" not in state:
            out = {"id": "", "object": "chat.completion.chunk", "created": now, "model": model,
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            return f"data: {json.dumps(out)}\n\ndata: [DONE]\n\n".encode()
        return b"data: [DONE]\n\n"

    return None


# -- Core request function ----------------------------------------------------
def _call_anthropic(body: dict, stream: bool) -> tuple[int, Any]:
    if not CFFI_AVAILABLE:
        raise RuntimeError("curl-cffi not installed. Run: pip install curl-cffi")

    token = get_token()
    body = _inject_cloaking(body)
    body = _normalize_messages(body)
    body["model"] = _resolve_model(body.get("model", "claude-sonnet-4-6"))

    payload = json.dumps(body).encode()
    headers = _build_headers(token, stream=stream)
    url = f"{ANTHROPIC_API}/v1/messages?beta=true"

    resp = cffi_requests.post(url, headers=headers, data=payload,
                               impersonate="chrome", timeout=300, stream=stream)
    return resp.status_code, resp


# -- HTTP Handler -------------------------------------------------------------
class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} {fmt % args}")

    def _allowed(self) -> bool:
        if not ALLOWED_PREFIX:
            return True
        client = self.client_address[0]
        return client.startswith(ALLOWED_PREFIX) or client in ("127.0.0.1", "::1")

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def do_GET(self):
        if not self._allowed():
            self._send_json(403, {"error": "Access denied"})
            return
        if self.path in ("/", "/v1"):
            self._send_json(200, {"message": "Claude OAuth Proxy",
                                  "cffi": CFFI_AVAILABLE,
                                  "endpoints": ["POST /v1/messages", "POST /v1/chat/completions", "GET /v1/models"]})
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "cffi": CFFI_AVAILABLE,
                                  "token_source": "env" if os.getenv("ANTHROPIC_OAUTH_KEY") else "credentials"})
        elif self.path.startswith("/v1/models"):
            self._send_json(200, models_response())
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._allowed():
            self._send_json(403, {"error": "Access denied"})
            return
        raw = self._read_body()
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self._send_json(400, {"error": "Invalid JSON"})
            return

        if self.path.startswith("/v1/messages"):
            self._handle_messages(body)
        elif self.path.startswith("/v1/chat/completions"):
            self._handle_chat_completions(body)
        else:
            self._send_json(404, {"error": "Not found"})

    def _handle_messages(self, body: dict) -> None:
        stream = body.get("stream", False)
        try:
            status, resp = _call_anthropic(body, stream)
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for chunk in resp.iter_lines():
                self.wfile.write(chunk + b"\n")
                self.wfile.flush()
        else:
            data = resp.content
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def _handle_chat_completions(self, body: dict) -> None:
        model = _resolve_model(body.get("model", "claude-sonnet-4-6"))
        stream = body.get("stream", False)
        anthropic_body = openai_to_anthropic(body)
        try:
            status, resp = _call_anthropic(anthropic_body, stream)
        except Exception as e:
            self._send_json(500, {"error": str(e)})
            return

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            state: dict = {}
            for chunk in resp.iter_lines():
                converted = anthropic_stream_to_openai(chunk + b"\n", model, state)
                if converted:
                    self.wfile.write(converted)
                    self.wfile.flush()
        else:
            try:
                d = resp.json()
                out = json.dumps(anthropic_to_openai(d, model)).encode()
            except Exception:
                out = resp.content
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)


# -- Entry point --------------------------------------------------------------
if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    tok = get_token()
    source = "ANTHROPIC_OAUTH_KEY env" if os.getenv("ANTHROPIC_OAUTH_KEY") else "credentials.json"
    print(f"[proxy] Token source: {source}")
    print(f"[proxy] Token: {tok[:25]}...")
    print(f"[proxy] curl-cffi: {'YES' if CFFI_AVAILABLE else 'NO — pip install curl-cffi'}")
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer((HOST, port), ProxyHandler)
    print(f"[proxy] Listening on {HOST}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[proxy] Shutting down")
