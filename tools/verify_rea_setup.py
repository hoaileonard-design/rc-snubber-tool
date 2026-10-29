"""Verify exact registered runtime and a real MCP initialize/tools-list exchange."""

import json
import queue
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path


def verify():
    root = Path(__file__).resolve().parents[1]
    home = Path.home()
    cfg = home / ".codex" / "config.toml"
    codex = tomllib.loads(cfg.read_text(encoding="utf-8-sig"))
    codex_before = tomllib.loads(cfg.with_suffix(".toml.rea.backup").read_text(encoding="utf-8-sig"))
    registration = codex["mcp_servers"]["rea"]
    stripped = dict(codex)
    stripped["mcp_servers"] = dict(codex["mcp_servers"])
    stripped["mcp_servers"].pop("rea")
    if not stripped["mcp_servers"] and "mcp_servers" not in codex_before:
        stripped.pop("mcp_servers")
    assert stripped == codex_before, "Unrelated Codex settings changed"
    claude_path = home / ".claude.json"
    claude = json.loads(claude_path.read_text(encoding="utf-8-sig"))
    claude_before = json.loads(claude_path.with_name(".claude.json.rea.backup").read_text(encoding="utf-8-sig"))
    claude_copy = dict(claude)
    claude_copy["mcpServers"] = dict(claude_copy["mcpServers"])
    claude_rea = claude_copy["mcpServers"].pop("rea")
    if not claude_copy["mcpServers"] and "mcpServers" not in claude_before:
        claude_copy.pop("mcpServers")
    assert claude_copy == claude_before, "Unrelated Claude settings changed"
    assert registration["command"] == claude_rea["command"] and registration["args"] == claude_rea["args"]
    process = subprocess.Popen([registration["command"], *registration["args"]],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8")
    replies = queue.Queue()
    def read_replies():
        for line in process.stdout:
            try:
                replies.put(json.loads(line))
            except ValueError:
                replies.put({"parse_error": line[:100]})
    threading.Thread(target=read_replies, daemon=True).start()
    def request(identity, method, params):
        process.stdin.write(json.dumps(dict(jsonrpc="2.0", id=identity, method=method, params=params)) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            value = replies.get(timeout=max(.1, deadline - time.monotonic()))
            if value.get("id") == identity:
                if "error" in value:
                    raise ValueError(value["error"])
                return value["result"]
        raise TimeoutError(method)
    try:
        initialize = request(1, "initialize", dict(protocolVersion="2025-11-25", capabilities={},
                                                   clientInfo=dict(name="Snubber REA install check", version="1")))
        process.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        process.stdin.flush()
        tool_list = request(2, "tools/list", {})
        names = [tool["name"] for tool in tool_list["tools"]]
        assert "analyze_javascript_application" in names and "binary_session" in names
        assert not tool_list.get("nextCursor"), "Unverified additional tools page"
        result = dict(status="passed", server=initialize["serverInfo"], protocol=initialize["protocolVersion"],
                      tools=len(names), same_runtime_for_both=True, unrelated_settings_preserved=True,
                      clients=["Codex", "Claude Code"], runtime=registration["command"],
                      entry=registration["args"][0],
                      scope="Actual MCP stdio startup checked; running agent sessions must reload registration")
        out = root / "verification" / "rea_falstad"
        out.mkdir(parents=True, exist_ok=True)
        (out / "installation_verified.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    verify()
