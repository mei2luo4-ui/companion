import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .database import (
    init_db,
    get_profile,
    update_profile,
    get_recent_messages,
    get_pending_events,
    dismiss_event,
    add_diary,
    get_diary_list,
    get_mood_history,
)
from .companion import chat_stream
from .events import event_scheduler_loop
from .models import ChatRequest, DiaryRequest, ProfileRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(event_scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="情感陪伴体", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def generate():
        try:
            async for kind, data in chat_stream(req.message):
                if kind == "text":
                    payload = json.dumps({"type": "text", "content": data}, ensure_ascii=False)
                else:
                    payload = json.dumps({"type": "emotion", "data": data}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/history")
async def history(limit: int = 30):
    messages = await get_recent_messages(limit)
    return {"messages": messages}


@app.get("/events/pending")
async def pending_events():
    events = await get_pending_events()
    return {"events": events}


@app.post("/events/{event_id}/dismiss")
async def dismiss(event_id: int):
    await dismiss_event(event_id)
    return {"ok": True}


@app.post("/diary")
async def create_diary(req: DiaryRequest):
    entry_id = await add_diary(req.content, req.mood_score, req.tags)
    return {"id": entry_id}


@app.get("/diary")
async def list_diary(limit: int = 30):
    entries = await get_diary_list(limit)
    return {"entries": entries}


@app.get("/mood/history")
async def mood_history(days: int = 14):
    data = await get_mood_history(days)
    return {"data": data}


@app.get("/profile")
async def profile():
    return await get_profile()


@app.post("/profile")
async def save_profile(req: ProfileRequest):
    await update_profile(req.name, req.personality, req.speaking_style, req.avatar_emoji)
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
