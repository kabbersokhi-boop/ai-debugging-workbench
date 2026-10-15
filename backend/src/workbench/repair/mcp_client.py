"""Actual official-SDK JSON-RPC stdio client. Transport and discovery evidence are saved."""

import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class RepairTools:
    def __init__(self, session: ClientSession):
        self.session = session
        self.events: list[dict[str, Any]] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        record = {"method": "tools/call", "name": name, "arguments": arguments}
        self.events.append(record)
        result = await self.session.call_tool(name, arguments, read_timeout_seconds=None)
        text = "\n".join(block.text for block in result.content if block.type == "text")
        if len(text.encode()) > 60000:
            raise ValueError("MCP result exceeds retained-output budget")
        record["is_error"] = result.isError
        if result.isError:
            record["error"] = text[:1500]
            raise ValueError(f"MCP {name} rejected the request: {text[:800]}")
        # FastMCP's structured content is authoritative when available.
        data = result.structuredContent or json.loads(text)
        record["result"] = data
        if "tool_error" in data:
            record["is_error"] = True
            raise RuntimeError(data["tool_error"]["message"])
        return data


@asynccontextmanager
async def connect_tools(repair_id: UUID, snapshot_id: str, broker_url: str):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "workbench.repair.mcp_server"],
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "REPAIR_ID": str(repair_id),
            "SNAPSHOT_ID": snapshot_id,
            "REPAIR_BROKER_URL": broker_url,
        },
    )
    failure: BaseException | None = None
    async with stdio_client(params) as streams, ClientSession(*streams) as session:
        initialized = await session.initialize()
        tools = RepairTools(session)
        tools.events.append(
            {
                "method": "initialize",
                "protocol_version": initialized.protocolVersion,
                "server": initialized.serverInfo.model_dump(),
            }
        )
        discovery = await session.list_tools()
        tools.events.append(
            {"method": "tools/list", "tools": [t.model_dump() for t in discovery.tools]}
        )
        try:
            yield tools
        except BaseException as error:
            failure = error
    if failure is not None:
        raise failure
