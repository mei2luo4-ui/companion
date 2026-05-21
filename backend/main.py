import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from pathlib import Path

import hashlib
import hmac
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

from .database import (
    init_db,
    get_profile,
    update_profile,
    get_recent_messages,
    clear_messages,
    get_pending_events,
    dismiss_event,
    add_diary,
    get_diary_list,
    get_mood_history,
    create_user,
    get_user_by_username,
    add_moment,
    get_moments,
    like_moment,
    add_moment_comment,
    get_moment_comments,
)
from .companion import chat_stream
from .events import event_scheduler_loop
from .models import ChatRequest, DiaryRequest, ProfileRequest, RegisterRequest, LoginRequest, MomentRequest

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _create_token(user_id: int) -> str:
    expire = datetime.now() + timedelta(days=30)
    payload = f"{user_id}:{expire.isoformat()}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def _verify_token(token: str) -> int:
    try:
        parts = token.rsplit(":", 1)
        payload, sig = parts[0], parts[1]
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError
        user_id_str, expire_str = payload.split(":", 1)
        if datetime.fromisoformat(expire_str) < datetime.now():
            raise ValueError
        return int(user_id_str)
    except Exception:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


bearer = HTTPBearer()


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    return _verify_token(creds.credentials)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(event_scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="情感陪伴体", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
AVATARS_DIR = FRONTEND_DIR / "avatars"
AVATARS_DIR.mkdir(exist_ok=True)

BUILTIN_AVATARS = ["/avatars/cyber1.svg", "/avatars/cyber2.svg", "/avatars/cyber3.svg"]


@app.post("/auth/register")
async def register(req: RegisterRequest):
    if len(req.username) < 2 or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="用户名至少2位，密码至少6位")
    existing = await get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user_id = await create_user(req.username, _hash_password(req.password))
    return {"token": _create_token(user_id)}


@app.post("/auth/login")
async def login(req: LoginRequest):
    user = await get_user_by_username(req.username)
    if not user or user["password_hash"] != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": _create_token(user["id"])}


@app.post("/chat")
async def chat(req: ChatRequest, user_id: int = Depends(get_current_user)):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def generate():
        try:
            async for kind, data in chat_stream(user_id, req.message, req.display_message):
                if kind == "text":
                    payload = json.dumps({"type": "text", "content": data}, ensure_ascii=False)
                else:
                    payload = json.dumps({"type": "emotion", "data": data}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            logger.exception("chat_stream error user_id=%s", user_id)
            payload = json.dumps({"type": "text", "content": "连接出了点问题，稍后再试试？"}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/history")
async def history(limit: int = 30, user_id: int = Depends(get_current_user)):
    profile = await get_profile(user_id)
    messages = await get_recent_messages(user_id, limit, character_name=profile["name"])
    return {"messages": messages}


@app.delete("/history")
async def delete_history(user_id: int = Depends(get_current_user)):
    await clear_messages(user_id)
    return {"ok": True}


@app.get("/events/pending")
async def pending_events(user_id: int = Depends(get_current_user)):
    events = await get_pending_events(user_id)
    return {"events": events}


@app.post("/events/{event_id}/dismiss")
async def dismiss(event_id: int, user_id: int = Depends(get_current_user)):
    await dismiss_event(user_id, event_id)
    return {"ok": True}


@app.post("/diary")
async def create_diary(req: DiaryRequest, user_id: int = Depends(get_current_user)):
    entry_id = await add_diary(user_id, req.content, req.mood_score, req.tags)
    return {"id": entry_id}


@app.get("/diary")
async def list_diary(limit: int = 30, user_id: int = Depends(get_current_user)):
    entries = await get_diary_list(user_id, limit)
    return {"entries": entries}


@app.get("/mood/history")
async def mood_history(days: int = 14, user_id: int = Depends(get_current_user)):
    data = await get_mood_history(user_id, days)
    return {"data": data}


@app.get("/profile")
async def profile(user_id: int = Depends(get_current_user)):
    return await get_profile(user_id)


@app.post("/profile")
async def save_profile(req: ProfileRequest, user_id: int = Depends(get_current_user)):
    await update_profile(user_id, req.name, req.personality, req.speaking_style, req.avatar_emoji)
    return {"ok": True}


@app.get("/avatar/list")
async def list_avatars(user_id: int = Depends(get_current_user)):
    uploaded = sorted(AVATARS_DIR.glob(f"u{user_id}_*"), key=lambda p: p.stat().st_mtime)
    return {"uploaded": [f"/avatars/{p.name}" for p in uploaded]}


@app.post("/avatar/upload")
async def upload_avatar(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp/gif")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")

    # 统计用户已上传数量
    existing = sorted(AVATARS_DIR.glob(f"u{user_id}_*"))
    if len(existing) >= 3:
        existing[0].unlink()  # 删除最旧的

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    import time
    fname = f"u{user_id}_{int(time.time())}.{ext}"
    (AVATARS_DIR / fname).write_bytes(data)
    return {"url": f"/avatars/{fname}"}


@app.get("/")
async def root():
    return RedirectResponse(url="/login.html")


@app.post("/moments")
async def create_moment(req: MomentRequest, user_id: int = Depends(get_current_user)):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(req.content) > 500:
        raise HTTPException(status_code=400, detail="内容不能超过500字")
    entry_id = await add_moment(user_id, req.content)
    return {"id": entry_id}


@app.get("/moments")
async def list_moments(limit: int = 30, user_id: int = Depends(get_current_user)):
    entries = await get_moments(user_id, limit)
    return {"moments": entries}


@app.post("/moments/{moment_id}/like")
async def like_moment_route(moment_id: int, user_id: int = Depends(get_current_user)):
    likes = await like_moment(moment_id)
    return {"likes": likes}


@app.get("/moments/{moment_id}/comments")
async def list_moment_comments(moment_id: int, user_id: int = Depends(get_current_user)):
    return {"comments": await get_moment_comments(moment_id)}


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")
