"""
JARVIS v2 — api/mcp.py

Model Context Protocol server.
Exposes Jarvis skills as MCP tools for:
- Claude Desktop
- Cursor
- VS Code
- Any MCP-compatible client

Run: python api/mcp.py
Or:  uvicorn api.mcp:app --port 8001

Configure in Claude Desktop:
{
  "mcpServers": {
    "jarvis": {
      "command": "python",
      "args": ["/home/12zse/jarvis/api/mcp.py"]
    }
  }
}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config.settings import Settings
from router import Router

app = FastAPI(title="JARVIS MCP Server")
settings = Settings()
router_engine = Router(settings)


@app.get("/mcp/tools")
async def list_tools():
    """List all available tools (skills) in MCP format."""
    tools = []
    for skill in router_engine.skills[:500]:  # Limit for performance
        tools.append({
            "name": skill["name"],
            "description": skill.get("description", "")[:200],
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": f"Your request for the {skill['name']} skill"
                    }
                },
                "required": ["query"]
            }
        })
    return {"tools": tools}


@app.post("/mcp/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Execute a tool (skill) and return result."""
    body = await request.json()
    query = body.get("query", body.get("input", ""))

    skill = router_engine.skill_info(tool_name)
    if not skill:
        return JSONResponse(
            {"error": f"Tool '{tool_name}' not found"},
            status_code=404
        )

    # Load SKILL.md for context
    skill_md = settings.SKILLS_DIR / tool_name / "SKILL.md"
    instructions = ""
    if skill_md.exists():
        instructions = skill_md.read_text(errors="ignore")[:3000]

    from brain import BrainClient
    from context_injector import build_messages
    from memory.memory import Memory

    brain = BrainClient(settings)
    memory = Memory(window=5, db_path=settings.MEMORY_DB)

    msgs = build_messages(
        query, memory, settings.PERSONA,
        skill=skill, settings=settings
    )

    # Collect full response
    result = ""
    async for token in brain.stream(msgs):
        result += token

    memory.add("user", query, skill=tool_name, outcome="success")
    memory.add("assistant", result)

    return {
        "content": [{"type": "text", "text": result}],
        "skill": tool_name,
        "category": skill.get("category", "general"),
    }


@app.get("/mcp/categories")
async def list_categories():
    """List skill categories."""
    return router_engine.get_categories()


@app.get("/mcp/search")
async def search_tools(q: str, k: int = 5):
    """Search for tools by query."""
    results = router_engine.search_skills(q, k=k)
    return [{
        "name": r["name"],
        "score": r["score"],
        "category": r.get("category", ""),
        "description": r.get("description", "")[:100],
    } for r in results]


# JSON-RPC 2.0 endpoint (standard MCP protocol)
@app.post("/mcp/jsonrpc")
async def jsonrpc(request: Request):
    """Handle JSON-RPC 2.0 requests (standard MCP protocol)."""
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id", 1)

    if method == "tools/list":
        tools_response = await list_tools()
        return {"jsonrpc": "2.0", "id": req_id, "result": tools_response}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        # Create a mock request
        class MockReq:
            async def json(self_inner):
                return args

        result = await call_tool(tool_name, MockReq())
        if isinstance(result, JSONResponse):
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -1, "message": "Tool not found"}}
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    elif method == "resources/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}

    elif method == "prompts/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32601, "message": f"Method not found: {method}"
        }}


if __name__ == "__main__":
    import uvicorn
    print("JARVIS MCP Server starting on port 8001...")
    print("Add to Claude Desktop config:")
    print(json.dumps({
        "mcpServers": {
            "jarvis": {
                "url": "http://localhost:8001/mcp/jsonrpc"
            }
        }
    }, indent=2))
    uvicorn.run(app, host="0.0.0.0", port=8001)
