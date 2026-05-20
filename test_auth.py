import asyncio
import sys
sys.path.insert(0, '.')

from backend.database import init_db, create_user, get_user_by_username
import hashlib

async def test():
    await init_db()
    print("[OK] Database initialized")

    password_hash = hashlib.sha256("test123456".encode()).hexdigest()
    try:
        user_id = await create_user("testuser2", password_hash)
        print(f"[OK] Register success, user_id: {user_id}")
    except Exception as e:
        print(f"[FAIL] Register failed: {e}")
        return

    user = await get_user_by_username("testuser2")
    if user:
        print(f"[OK] Login query success: {user['username']}")
        if user['password_hash'] == password_hash:
            print("[OK] Password verified")
        else:
            print("[FAIL] Password mismatch")
    else:
        print("[FAIL] User not found")

asyncio.run(test())
