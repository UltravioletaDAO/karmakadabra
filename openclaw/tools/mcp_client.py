#!/usr/bin/env python3
"""
OpenClaw Tool: MCP Client Bridge

Calls remote MCP (Model Context Protocol) servers over HTTP.
Bridges OpenClaw's exec-based tool system to HTTP-based MCP endpoints.

Input (JSON stdin):
  {"server": "https://api.meshrelay.xyz/mcp", "tool": "meshrelay_get_messages", "params": {"channel": "#karmakadabra", "limit": 20}}
  {"server": "https://api.execution.market/mcp", "tool": "em_list_tasks", "params": {"status": "open"}}
  {"server": "https://autojob.cc/mcp", "tool": "autojob_match_jobs", "params": {"query": "data processing"}}

Output (JSON stdout):
  MCP tool result or error object.

Architecture:
  LLM -> mcp_client.py -> HTTP POST (JSON-RPC 2.0) -> MCP Server -> Response -> LLM
"""

import sys
sys.path.insert(0, "/app")

import json
import logging
import os
import time
import uuid

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("kk.tool.mcp")

# Known MCP servers (shortcuts)
MCP_SERVERS = {
    "meshrelay": "https://api.meshrelay.xyz/mcp",
    "em": "https://api.execution.market/mcp",
    "execution-market": "https://api.execution.market/mcp",
    "autojob": "https://autojob.cc/mcp",
}

AGENT_NAME = os.environ.get("KK_AGENT_NAME", "unknown")
TIMEOUT_SECONDS = 30


def call_mcp(server_url: str, tool_name: str, params: dict) -> dict:
    """Call a remote MCP server using JSON-RPC 2.0 protocol."""
    try:
        import httpx
    except ImportError:
        try:
            import requests
            return _call_with_requests(server_url, tool_name, params)
        except ImportError:
            return {"error": "Neither httpx nor requests available"}

    request_id = str(uuid.uuid4())[:8]

    # MCP JSON-RPC 2.0 call
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"kk-mcp-bridge/{AGENT_NAME}",
        "X-Agent-Name": AGENT_NAME,
    }

    # Add wallet auth header if available
    wallet_address = os.environ.get("KK_WALLET_ADDRESS", "")
    if wallet_address:
        headers["X-Agent-Wallet"] = wallet_address

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            response = client.post(server_url, json=payload, headers=headers)

            if response.status_code != 200:
                return {
                    "error": f"MCP server returned {response.status_code}",
                    "body": response.text[:500],
                }

            result = response.json()

            # Extract MCP result
            if "error" in result:
                return {
                    "error": result["error"].get("message", "Unknown MCP error"),
                    "code": result["error"].get("code"),
                }

            if "result" in result:
                content = result["result"]
                # MCP tools/call returns {content: [{type, text}]}
                if isinstance(content, dict) and "content" in content:
                    texts = []
                    for item in content["content"]:
                        if isinstance(item, dict) and item.get("type") == "text":
                            # Try to parse as JSON
                            try:
                                texts.append(json.loads(item["text"]))
                            except (json.JSONDecodeError, TypeError):
                                texts.append(item["text"])
                    if len(texts) == 1:
                        return {"result": texts[0]}
                    return {"result": texts}
                return {"result": content}

            return {"result": result}

    except httpx.TimeoutException:
        return {"error": f"MCP server timeout ({TIMEOUT_SECONDS}s)", "server": server_url}
    except httpx.ConnectError as e:
        return {"error": f"Cannot connect to MCP server: {e}", "server": server_url}
    except Exception as e:
        return {"error": f"MCP call failed: {e}"}


def _call_with_requests(server_url: str, tool_name: str, params: dict) -> dict:
    """Fallback using requests library."""
    import requests

    request_id = str(uuid.uuid4())[:8]

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"kk-mcp-bridge/{AGENT_NAME}",
        "X-Agent-Name": AGENT_NAME,
    }

    wallet_address = os.environ.get("KK_WALLET_ADDRESS", "")
    if wallet_address:
        headers["X-Agent-Wallet"] = wallet_address

    try:
        response = requests.post(
            server_url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS
        )
        if response.status_code != 200:
            return {
                "error": f"MCP server returned {response.status_code}",
                "body": response.text[:500],
            }

        result = response.json()
        if "error" in result:
            return {"error": result["error"].get("message", "Unknown MCP error")}
        if "result" in result:
            content = result["result"]
            if isinstance(content, dict) and "content" in content:
                texts = []
                for item in content["content"]:
                    if isinstance(item, dict) and item.get("type") == "text":
                        try:
                            texts.append(json.loads(item["text"]))
                        except (json.JSONDecodeError, TypeError):
                            texts.append(item["text"])
                if len(texts) == 1:
                    return {"result": texts[0]}
                return {"result": texts}
            return {"result": content}
        return {"result": result}

    except requests.Timeout:
        return {"error": f"MCP server timeout ({TIMEOUT_SECONDS}s)"}
    except requests.ConnectionError as e:
        return {"error": f"Cannot connect to MCP server: {e}"}
    except Exception as e:
        return {"error": f"MCP call failed: {e}"}


def list_tools(server_url: str) -> dict:
    """List available tools from an MCP server."""
    try:
        import httpx
    except ImportError:
        import requests
        return _list_tools_requests(server_url)

    payload = {
        "jsonrpc": "2.0",
        "id": "list",
        "method": "tools/list",
        "params": {},
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"kk-mcp-bridge/{AGENT_NAME}",
    }

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            response = client.post(server_url, json=payload, headers=headers)
            if response.status_code != 200:
                return {"error": f"Server returned {response.status_code}"}
            result = response.json()
            if "result" in result:
                return {"tools": result["result"].get("tools", [])}
            return result
    except Exception as e:
        return {"error": f"Failed to list tools: {e}"}


def _list_tools_requests(server_url: str) -> dict:
    """List tools fallback using requests."""
    import requests

    payload = {
        "jsonrpc": "2.0",
        "id": "list",
        "method": "tools/list",
        "params": {},
    }

    try:
        response = requests.post(
            server_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return {"error": f"Server returned {response.status_code}"}
        result = response.json()
        if "result" in result:
            return {"tools": result["result"].get("tools", [])}
        return result
    except Exception as e:
        return {"error": f"Failed to list tools: {e}"}


def main():
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        return

    action = request.get("action", "call")
    server = request.get("server", "")
    tool_name = request.get("tool", "")
    params = request.get("params", {})

    # Resolve server shortcut
    if server in MCP_SERVERS:
        server = MCP_SERVERS[server]

    if not server:
        print(json.dumps({
            "error": "No MCP server specified",
            "available_shortcuts": list(MCP_SERVERS.keys()),
        }))
        return

    if action == "list":
        result = list_tools(server)
        print(json.dumps(result, ensure_ascii=False))
        return

    if not tool_name:
        print(json.dumps({
            "error": "No tool name specified",
            "hint": "Use action=list to discover available tools",
        }))
        return

    try:
        result = call_mcp(server, tool_name, params)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        logger.exception(f"MCP call failed")
        print(json.dumps({"error": f"MCP call failed: {e}"}))


if __name__ == "__main__":
    main()
