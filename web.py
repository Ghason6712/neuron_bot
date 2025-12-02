from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from contextlib import asynccontextmanager
import asyncio
from config import BOT_TOKEN, APP_URL
import bot

bot_instance = Bot(token=BOT_TOKEN)
dp = bot.dp

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Установка вебхука при запуске
    if APP_URL:
        webhook_url = f"{APP_URL}/webhook"
        await bot_instance.set_webhook(webhook_url)
        print(f"✅ Webhook установлен: {webhook_url}")
    else:
        print("⚠ APP_URL не установлен, работаю в режиме поллинга")
    yield
    
    # Очистка при остановке
    if APP_URL:
        await bot_instance.delete_webhook()
        print("🛑 Webhook удален")

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        update = types.Update(**await request.json())
        await dp.feed_update(bot_instance, update)
        return {"status": "ok"}
    except Exception as e:
        print(f"❌ Ошибка в webhook: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/")
async def root():
    return {
        "status": "Bot is alive!",
        "mode": "webhook" if APP_URL else "polling"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}