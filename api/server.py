"""
JARVIS v2 — api/server.py
FastAPI backend + WebSocket streaming.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from config.settings import Settings
from brain import BrainClient
from router import Router
from memory.memory import Memory
from context_injector import build_messages

app = FastAPI(title="JARVIS v2")
settings = Settings()
brain = BrainClient(settings)
router_engine = Router(settings)
memory = Memory(window=settings.MEMORY_WINDOW, db_path=settings.MEMORY_DB)


@app.get("/api/skills")
async def list_skills(category: str = None):
    skills = router_engine.list_skills(category=category)
    return [{"name": s["name"], "category": s.get("category", ""),
             "description": s.get("description", "")[:80]} for s in skills[:200]]


@app.get("/api/skills/{name}")
async def get_skill(name: str):
    skill = router_engine.skill_info(name)
    if not skill:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return skill


@app.get("/api/categories")
async def get_categories():
    return router_engine.get_categories()


@app.get("/api/history")
async def get_history(n: int = 20):
    rows = memory.get_history(n)
    return [{"ts": r[0], "task": r[1], "skill": r[2], "outcome": r[3]} for r in rows]


@app.get("/api/stats")
async def get_stats():
    return memory.get_stats()


@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            query = data.strip()
            if not query:
                continue

            # Classify and route
            try:
                cls = await brain.classify(query)
                hint = cls.get("category_hint", "general")
            except Exception:
                hint = "general"

            match = router_engine.route(query, category_hint=hint)

            # Send skill match info
            if match:
                await ws.send_json({
                    "type": "skill_match",
                    "name": match["name"],
                    "category": match.get("category", "general"),
                    "score": match.get("score", 0),
                })

            # Build messages and stream
            msgs = build_messages(query, memory, settings.PERSONA,
                                 skill=match, settings=settings)

            full_response = ""
            async for token in brain.stream(msgs):
                full_response += token
                await ws.send_json({"type": "token", "content": token})

            await ws.send_json({"type": "done"})

            # Save to memory
            memory.add("user", query,
                      skill=match["name"] if match else None,
                      outcome="success")
            memory.add("assistant", full_response)

    except WebSocketDisconnect:
        pass


# Serve the web UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
