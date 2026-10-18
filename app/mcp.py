"""SIDE EFFECTS as an MCP server, so any AI agent (Gemini CLI, ADK, Claude, ChatGPT) can use the same tools.

A minimal Model Context Protocol server over Streamable HTTP: one POST endpoint that speaks JSON-RPC 2.0
and answers with plain JSON. It offers the tools in app/tools.py; the gate stays deterministic, so an agent
calling gate_check gets the same verdict the checkout enforces.
"""
from __future__ import annotations

import inspect
import json
import logging
import types
import typing

from . import bq, tools

log = logging.getLogger("side_effects.mcp")
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "side-effects", "title": "SIDE EFFECTS", "version": "1.0"}
INSTRUCTIONS = ("Side effects of credit products from real complaint data. Before an agent signs a person up for "
                "credit, call gate_check and show the person every required disclosure; a human_review verdict means "
                "the person must confirm. Complaints are unverified reports, not proof.")


def _schema(fn) -> dict:
    hints = typing.get_type_hints(fn)
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        t = hints.get(name, str)
        if typing.get_origin(t) in (typing.Union, types.UnionType):  # list[str] | None
            t = next(a for a in typing.get_args(t) if a is not type(None))
        props[name] = {"type": "array", "items": {"type": "string"}} if typing.get_origin(t) is list else {"type": "string"}
        if name == "product_type":
            props[name]["enum"] = list(tools.PRODUCT_TYPES)
        if p.default is inspect.Parameter.empty:
            required.append(name)
        elif p.default is not None:
            props[name]["default"] = p.default
    return {"type": "object", "properties": props, "required": required}


def tool_list() -> list[dict]:
    return [{"name": f.__name__, "description": inspect.cleandoc(f.__doc__ or ""), "inputSchema": _schema(f)}
            for f in tools.MCP_TOOLS]


def _ok(rid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle(msg: dict) -> dict | None:
    """Answer one JSON-RPC message; notifications (no id) get no answer."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
        return _err(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid request")
    rid, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg:
        return None
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _ok(rid, {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                         "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS})
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": tool_list()})
    if method == "tools/call":
        fn = {f.__name__: f for f in tools.MCP_TOOLS}.get(params.get("name"))
        if not fn:
            return _err(rid, -32602, f"Unknown tool: {params.get('name')}")
        args = params.get("arguments") or {}
        try:
            out = fn(**args)
        except TypeError as e:
            return _ok(rid, {"content": [{"type": "text", "text": f"Bad arguments: {e}"}], "isError": True})
        except Exception as e:
            log.warning("MCP tool %s failed: %s", fn.__name__, e)
            return _ok(rid, {"content": [{"type": "text", "text": "The data source could not be reached."}], "isError": True})
        if fn is tools.gate_check:
            bq.log_decision("mcp", args.get("issuer", ""), args.get("product_type", "credit_card"),
                            args.get("applicant_profile") or [], out)
        return _ok(rid, {"content": [{"type": "text", "text": json.dumps(out, default=str)}], "structuredContent": out,
                         "isError": False})
    return _err(rid, -32601, f"Method not found: {method}")
