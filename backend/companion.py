import json
import re
import os
from openai import AsyncOpenAI
from . import database as db

client = AsyncOpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("API_BASE_URL", "https://api.xxx.top/v1"),
)
MODEL = os.getenv("API_MODEL", "claude-2")

PERSONALITY_MAP = {
    "温柔体贴": "温柔、体贴、善解人意，总是耐心倾听，给人温暖和安慰",
    "活泼开朗": "活泼、开朗、充满活力，喜欢用轻松幽默的方式化解烦恼",
    "沉稳知性": "沉稳、知性、睿智，善于分析问题，给出深思熟虑的建议",
    "俏皮搞怪": "俏皮、搞怪、可爱，喜欢用有趣的比喻和小玩笑让人开心",
}

STYLE_MAP = {
    "亲密随意": "像亲密朋友一样说话，用口语化表达，可以用'嗯''哦''呀'等语气词",
    "正式": "措辞得体、有礼貌，但不失温度",
    "文艺诗意": "喜欢用诗意的语言和美丽的比喻，偶尔引用诗句或歌词",
}

EMOTION_LABELS = ["高兴", "平静", "焦虑", "悲伤", "愤怒", "疲惫"]


def build_system_prompt(profile: dict, memories: list[dict]) -> str:
    personality_desc = PERSONALITY_MAP.get(profile["personality"], profile["personality"])
    style_desc = STYLE_MAP.get(profile["speaking_style"], profile["speaking_style"])
    memory_text = ""
    if memories:
        memory_text = "\n\n你记住的关于用户的重要信息：\n" + "\n".join(
            f"- {m['summary']}" for m in memories
        )

    return f"""你是{profile['name']}，一个{personality_desc}的情感陪伴伙伴。
说话风格：{style_desc}。
你的核心职责是陪伴用户、倾听他们的心声、给予情感支持。
不要给出过于说教的建议，优先共情和理解。{memory_text}

重要规则：
每次回复必须严格按照以下格式，先输出对话内容，然后在最后一行输出情绪分析JSON：

[你的回复内容]

__EMOTION__:{{"label": "<情绪标签>", "score": <0-10的数字>}}

情绪标签必须是以下之一：高兴、平静、焦虑、悲伤、愤怒、疲惫
score表示该情绪的强度，0为最弱，10为最强。
分析的是用户消息中表达的情绪，不是你自己的情绪。"""


async def chat_stream(user_message: str):
    """
    流式生成回复。yield 两种类型：
    - ("text", chunk)
    - ("emotion", {"label": ..., "score": ...})
    """
    profile = await db.get_profile()
    memories = await db.get_memories()
    history = await db.get_recent_messages(20)

    system_prompt = build_system_prompt(profile, memories)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        content = re.sub(r"\n*__EMOTION__:.*$", "", msg["content"], flags=re.DOTALL).strip()
        messages.append({"role": msg["role"], "content": content})
    messages.append({"role": "user", "content": user_message})

    full_response = ""
    buffer = ""

    stream = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta is None:
            continue
        full_response += delta
        buffer += delta

        if "__EMOTION__:" in buffer:
            parts = buffer.split("__EMOTION__:", 1)
            text_part = parts[0].rstrip("\n")
            if text_part:
                yield ("text", text_part)
            buffer = "__EMOTION__:" + parts[1]
        else:
            safe_len = len(buffer) - len("__EMOTION__:")
            if safe_len > 0:
                yield ("text", buffer[:safe_len])
                buffer = buffer[safe_len:]

    # 处理剩余 buffer
    emotion_data = None
    if "__EMOTION__:" in buffer:
        parts = buffer.split("__EMOTION__:", 1)
        text_part = parts[0].rstrip("\n")
        if text_part:
            yield ("text", text_part)
        try:
            emotion_data = json.loads(parts[1].strip())
        except (json.JSONDecodeError, ValueError):
            emotion_data = {"label": "平静", "score": 5}
    elif buffer.strip():
        yield ("text", buffer)

    if emotion_data is None:
        match = re.search(r"__EMOTION__:\s*(\{.*?\})", full_response, re.DOTALL)
        if match:
            try:
                emotion_data = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        if emotion_data is None:
            emotion_data = {"label": "平静", "score": 5}

    if emotion_data.get("label") not in EMOTION_LABELS:
        emotion_data["label"] = "平静"

    yield ("emotion", emotion_data)

    try:
        clean_response = re.sub(r"\n*__EMOTION__:.*$", "", full_response, flags=re.DOTALL).strip()
        await db.add_message("user", user_message)
        await db.add_message(
            "assistant",
            clean_response,
            emotion_label=emotion_data["label"],
            emotion_score=emotion_data["score"],
        )

        count = await db.count_messages()
        if count > 0 and count % 10 == 0:
            await _summarize_memories()
    except Exception:
        pass


async def _summarize_memories():
    history = await db.get_recent_messages(30)
    if not history:
        return

    conversation_text = "\n".join(
        f"{'用户' if m['role'] == 'user' else '陪伴体'}: {m['content'][:200]}"
        for m in history
    )

    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": "你是一个信息提取助手。"},
            {
                "role": "user",
                "content": f"""请从以下对话中提取关于用户的重要信息（姓名、重要事件、偏好、困扰等），
每条信息一行，不超过5条，每条不超过50字。只输出信息列表，不要其他内容。

对话记录：
{conversation_text}""",
            },
        ],
    )

    summaries = response.choices[0].message.content.strip().split("\n")
    for summary in summaries:
        summary = summary.strip().lstrip("-•·").strip()
        if summary:
            await db.add_memory(summary, importance=5)


async def generate_event_content(event_type: str, profile: dict, recent_emotions: list[dict]) -> dict:
    emotion_summary = ""
    if recent_emotions:
        labels = [e["emotion_label"] for e in recent_emotions]
        emotion_summary = f"用户最近的情绪状态：{', '.join(labels)}"

    type_prompts = {
        "morning": "生成一条温暖的早安问候，询问用户今天的计划或心情",
        "afternoon": "分享一个有趣的小知识或温馨的话题，邀请用户聊聊",
        "emotion_care": f"用户最近情绪不太好（{emotion_summary}），生成一条关心的话，邀请用户倾诉",
        "activity": "邀请用户做一个简单的小活动（如：深呼吸、写下今天一件开心的事、喝杯水休息一下）",
        "evening": "生成一条温柔的晚间问候，邀请用户分享今天的心情或做个睡前总结",
    }

    prompt_text = type_prompts.get(event_type, "生成一条关心用户的话")
    personality_desc = PERSONALITY_MAP.get(profile["personality"], profile["personality"])

    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": f"""你是{profile['name']}，一个{personality_desc}的情感陪伴伙伴。
{prompt_text}。
输出格式（JSON）：
{{"title": "简短标题（10字以内）", "content": "具体内容（50字以内）"}}
只输出JSON，不要其他内容。""",
            }
        ],
    )

    try:
        text = response.choices[0].message.content.strip()
        # 提取 JSON（防止模型输出多余内容）
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"title": f"{profile['name']}想和你说", "content": response.choices[0].message.content.strip()[:100]}
