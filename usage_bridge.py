#!/usr/bin/env python3
"""usage-bridge: PC-side relay that exposes OpenTokenUsage's local API as MCP.

Runs on your PC (stdlib only, no pip installs).
- Reads http://127.0.0.1:6736/v1/usage (OpenTokenUsage local HTTP API)
- Serves MCP Streamable HTTP at POST /mcp with tools:
    usage_all       -> snapshots for all enabled providers
    usage_provider  -> one provider by id (e.g. "claude", "codex", "antigravity", "grok")
- Also serves GET /health and GET /usage (plain JSON, for local debugging)
- Auth: bearer token from env USAGE_BRIDGE_TOKEN or ./token.txt next to this file
- Cache: 300s. On upstream error, serves the last good snapshot marked stale.

Usage:
    python usage_bridge.py [--port 8787] [--host 127.0.0.1]
Bind to 127.0.0.1 by default; expose it only through a tunnel (Tailscale /
Cloudflare Tunnel) — never port-forward it directly to the internet.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("USAGE_BRIDGE_UPSTREAM", "http://127.0.0.1:6736")
CACHE_TTL = 300

_cache = {"at": 0.0, "data": None}

def load_token():
    tok = os.environ.get("USAGE_BRIDGE_TOKEN", "").strip()
    if tok:
        return tok
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return ""

TOKEN = load_token()

def fetch_usage(provider=None, force=False):
    now = time.time()
    key = provider or "__all__"
    store = _cache.setdefault("by", {})
    ent = store.get(key)
    if not force and ent and now - ent["at"] < CACHE_TTL:
        return ent["data"], False, ent["at"]
    url = UPSTREAM + "/v1/usage" + ("/" + provider if provider else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "usage-bridge/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        store[key] = {"at": now, "data": data}
        return data, False, now
    except Exception as e:
        if ent:
            return ent["data"], True, ent["at"]
        raise RuntimeError(
            f"OpenTokenUsage local API unreachable at {url}: {e}. "
            "Is OpenTokenUsage running on this PC?")

def summarize(data, stale, at):
    return {"fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(at)),
            "stale": stale, "source": "OpenTokenUsage local API via usage-bridge",
            "providers": data}

TOOLS = [
    {"name": "usage_all",
     "description": "Usage snapshots for all enabled providers (Claude, Codex, Antigravity, Grok, ...) from OpenTokenUsage on your PC.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "usage_provider",
     "description": "Usage snapshot for one provider id, e.g. claude, codex, antigravity, grok.",
     "inputSchema": {"type": "object",
                     "properties": {"provider": {"type": "string"}},
                     "required": ["provider"]}},
]

def call_tool(name, args):
    if name == "usage_all":
        data, stale, at = fetch_usage()
        return summarize(data, stale, at)
    if name == "usage_provider":
        data, stale, at = fetch_usage(provider=args.get("provider", ""))
        return summarize(data, stale, at)
    raise RuntimeError(f"unknown tool: {name}")

def handle_rpc(msg):
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "usage-bridge", "version": "1.0.0"}}}
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            result = call_tool(params.get("name", ""), params.get("arguments", {}) or {})
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": str(e)}], "isError": True}}
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _authed(self):
        if not TOKEN:
            return True  # local-only mode when no token configured
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def _send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, json.dumps({"ok": True, "service": "usage-bridge"}))
        if self.path == "/usage":
            if not self._authed():
                return self._send(401, json.dumps({"error": "unauthorized"}))
            try:
                data, stale, at = fetch_usage()
                return self._send(200, json.dumps(summarize(data, stale, at), ensure_ascii=False))
            except Exception as e:
                return self._send(502, json.dumps({"error": str(e)}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/mcp":
            return self._send(404, json.dumps({"error": "not found"}))
        if not self._authed():
            return self._send(401, json.dumps({"error": "unauthorized"}))
        try:
            length = int(self.headers.get("Content-Length", "0"))
            msg = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            return self._send(400, json.dumps({"error": f"bad request: {e}"}))
        resp = handle_rpc(msg)
        if resp is None:
            return self._send(202, b"")
        return self._send(200, json.dumps(resp, ensure_ascii=False))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    if not TOKEN:
        sys.stderr.write("WARNING: no token configured (USAGE_BRIDGE_TOKEN or token.txt). "
                         "Auth is disabled — keep the bind on 127.0.0.1.\n")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    sys.stderr.write(f"usage-bridge listening on {a.host}:{a.port} (upstream {UPSTREAM})\n")
    srv.serve_forever()

if __name__ == "__main__":
    main()
