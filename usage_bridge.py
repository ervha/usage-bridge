#!/usr/bin/env python3
"""usage-bridge: PC-side relay that exposes OpenTokenUsage's local API as MCP.

Runs on your PC (stdlib only, no pip installs).
- Reads http://127.0.0.1:6736/v1/usage (OpenTokenUsage local HTTP API)
- Serves MCP Streamable HTTP at POST /mcp with tools:
    usage_all       -> snapshots for all enabled providers
    usage_provider  -> one provider by id (e.g. "claude", "codex", "antigravity", "grok")
- Also serves GET /health and GET /usage (plain JSON, for local debugging)
- Auth: bearer token from OS secure storage (DPAPI / Keychain / Secret
  Service), env USAGE_BRIDGE_TOKEN, or ./token.txt — see --init-token
- Cache: 300s. On upstream error, serves the last good snapshot marked stale.

Usage:
    python usage_bridge.py [--port 8787] [--host 127.0.0.1]
Bind to 127.0.0.1 by default; expose it only through a tunnel (Tailscale /
Cloudflare Tunnel) — never port-forward it directly to the internet.
"""
import argparse, hashlib, hmac, json, os, secrets, subprocess, sys, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ.get("USAGE_BRIDGE_UPSTREAM", "http://127.0.0.1:6736")
CACHE_TTL = 300

_cache = {"at": 0.0, "data": None}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_TXT = os.path.join(BASE_DIR, "token.txt")
TOKEN_DPAPI = os.path.join(BASE_DIR, "token.dpapi")

# --- Token storage ----------------------------------------------------------
# The token survives restarts, but preferably not as plain text on disk:
#   Windows: a DPAPI-encrypted file (token.dpapi) — only this Windows user
#            can decrypt it.
#   macOS:   a Keychain entry ("usage-bridge") via the `security` CLI.
#   Linux:   the Secret Service via `secret-tool`, when available.
# Fallback: token.txt with owner-only permissions. A failure in the secure
# store always falls back instead of locking you out. Set
# USAGE_BRIDGE_EPHEMERAL=1 to skip storage entirely (memory-only token that
# changes on every restart; agents then pair again after each restart).

def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    fn = (ctypes.windll.crypt32.CryptProtectData if protect
          else ctypes.windll.crypt32.CryptUnprotectData)
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

def _secure_load():
    try:
        if sys.platform == "win32" and os.path.exists(TOKEN_DPAPI):
            return _dpapi(open(TOKEN_DPAPI, "rb").read(), False).decode("utf-8").strip()
        if sys.platform == "darwin":
            r = subprocess.run(["security", "find-generic-password", "-s", "usage-bridge",
                                "-a", "token", "-w"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
        if sys.platform.startswith("linux"):
            r = subprocess.run(["secret-tool", "lookup", "service", "usage-bridge",
                                "account", "token"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
    except Exception:
        return None
    return None

def _secure_save(tok):
    """Store tok in the OS-protected store. Returns a label, or None."""
    try:
        if sys.platform == "win32":
            with open(TOKEN_DPAPI, "wb") as f:
                f.write(_dpapi(tok.encode("utf-8"), True))
            return "Windows DPAPI (token.dpapi)"
        if sys.platform == "darwin":
            r = subprocess.run(["security", "add-generic-password", "-s", "usage-bridge",
                                "-a", "token", "-w", tok, "-U"],
                               capture_output=True, text=True, timeout=10)
            return "macOS Keychain" if r.returncode == 0 else None
        if sys.platform.startswith("linux"):
            r = subprocess.run(["secret-tool", "store", "--label=usage-bridge",
                                "service", "usage-bridge", "account", "token"],
                               input=tok, capture_output=True, text=True, timeout=10)
            return "Linux Secret Service" if r.returncode == 0 else None
    except Exception:
        return None
    return None

def _file_save(tok):
    with open(TOKEN_TXT, "w", encoding="utf-8") as f:
        f.write(tok + "\n")
    try:
        os.chmod(TOKEN_TXT, 0o600)
    except Exception:
        pass
    return "token.txt (owner-only permissions)"

def load_token():
    if os.environ.get("USAGE_BRIDGE_EPHEMERAL", "") == "1":
        return secrets.token_urlsafe(32), "memory only (ephemeral)"
    tok = os.environ.get("USAGE_BRIDGE_TOKEN", "").strip()
    if tok:
        return tok, "environment variable"
    tok = _secure_load()
    if tok:
        return tok, "OS secure storage"
    if os.path.exists(TOKEN_TXT):
        return open(TOKEN_TXT, encoding="utf-8").read().strip(), "token.txt"
    return "", "none"

TOKEN, TOKEN_SOURCE = load_token()

# --- Secure token handover (pairing) ---------------------------------------
# The long-lived token never has to travel through chat or email. Someone on
# this PC creates a short-lived, single-use pairing code (POST /pair/create,
# loopback only, or `usage_bridge.py --pair`); the agent redeems it once via
# POST /pair/redeem from inside the tailnet and stores the token in its own
# secret store. Codes expire in PAIR_TTL seconds and burn after
# PAIR_MAX_ATTEMPTS wrong guesses.
PAIR_TTL = 600
PAIR_MAX_ATTEMPTS = 5
PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no ambiguous characters
_pair = {"digest": None, "expires": 0.0, "attempts": 0}
_pair_lock = threading.Lock()

def _new_pair_code():
    code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(8))
    with _pair_lock:
        _pair["digest"] = hashlib.sha256(code.encode()).hexdigest()
        _pair["expires"] = time.time() + PAIR_TTL
        _pair["attempts"] = 0
    return code

def _redeem_pair_code(code):
    digest = hashlib.sha256((code or "").strip().upper().encode()).hexdigest()
    with _pair_lock:
        if not _pair["digest"] or time.time() > _pair["expires"]:
            return None
        if _pair["attempts"] >= PAIR_MAX_ATTEMPTS:
            return None
        if hmac.compare_digest(digest, _pair["digest"]):
            _pair["digest"] = None  # single use
            return TOKEN
        _pair["attempts"] += 1
        return None

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
        # Under pythonw.exe sys.stderr is None; writing there would kill the
        # handler before the response is sent (client sees an empty reply).
        if sys.stderr is not None:
            try:
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))
            except Exception:
                pass

    def _authed(self):
        if not TOKEN:
            return True  # local-only mode when no token configured
        return hmac.compare_digest(
            self.headers.get("Authorization", ""), f"Bearer {TOKEN}")

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
        if self.path == "/pair/create":
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                return self._send(403, json.dumps(
                    {"error": "pairing codes can only be created on this PC"}))
            if not TOKEN:
                return self._send(400, json.dumps(
                    {"error": "no token configured on the server"}))
            code = _new_pair_code()
            return self._send(200, json.dumps(
                {"code": code, "expiresInSeconds": PAIR_TTL}))
        if self.path == "/pair/redeem":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return self._send(400, json.dumps({"error": "bad request"}))
            token = _redeem_pair_code(body.get("code", ""))
            if token:
                return self._send(200, json.dumps({"token": token}))
            return self._send(401, json.dumps(
                {"error": "invalid or expired pairing code"}))
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
    # pythonw.exe leaves std streams as None; give the process real sinks.
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--pair", action="store_true",
                    help="create a one-time pairing code on the running server and exit")
    ap.add_argument("--init-token", action="store_true",
                    help="create the token in OS secure storage (or migrate token.txt into it) and exit")
    a = ap.parse_args()
    if a.init_token:
        if TOKEN and TOKEN_SOURCE == "token.txt":
            where = _secure_save(TOKEN)
            if where:
                os.remove(TOKEN_TXT)
                print(f"Existing token moved into secure storage: {where}. token.txt deleted.")
            else:
                print("Secure storage is not available on this system; "
                      "the token stays in token.txt.")
            return
        if TOKEN:
            print(f"A token already exists ({TOKEN_SOURCE}); nothing to do.")
            return
        new_tok = secrets.token_urlsafe(32)
        where = _secure_save(new_tok) or _file_save(new_tok)
        print(f"Token created and stored in: {where}")
        print("The token itself is never printed. Hand it to your agent with "
              "pairing: run this file with --pair while the server is running.")
        return
    if a.pair:
        req = urllib.request.Request(
            f"http://127.0.0.1:{a.port}/pair/create", data=b"", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                out = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            sys.stderr.write(f"Could not create a pairing code: {e}\n"
                             "Is usage-bridge running on this PC?\n")
            return
        print(f"Pairing code: {out['code']}")
        print(f"Valid for {out['expiresInSeconds'] // 60} minutes, single use.")
        print("Give this code to your agent (not the token). "
              "The agent redeems it for the token and stores the token in its secret store.")
        return
    if not TOKEN:
        sys.stderr.write("WARNING: no token configured. Run with --init-token to create one. "
                         "Auth is disabled — keep the bind on 127.0.0.1.\n")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    sys.stderr.write(f"usage-bridge listening on {a.host}:{a.port} (upstream {UPSTREAM})\n")
    sys.stderr.write(f"token source: {TOKEN_SOURCE}\n")
    srv.serve_forever()

if __name__ == "__main__":
    main()
