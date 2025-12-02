from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from contextlib import asynccontextmanager
import asyncio
from config import BOT_TOKEN, APP_URL
import bot  # импортируем ваш файл с логикой бота

bot_instance = Bot(token=BOT_TOKEN)
dp = bot.dp  # берем диспетчер из bot.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot_instance.set_webhook(f"{APP_URL}/webhook")
    yield
    await bot_instance.delete_webhook()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update(**await request.json())
    await dp.feed_update(bot_instance, update)

@app.get("/")
async def root():
    return {"status": "Bot is alive!"}