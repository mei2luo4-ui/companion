from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str


class DiaryRequest(BaseModel):
    content: str
    mood_score: Optional[float] = None
    tags: Optional[str] = None


class ProfileRequest(BaseModel):
    name: str
    personality: str
    speaking_style: str
    avatar_emoji: str
