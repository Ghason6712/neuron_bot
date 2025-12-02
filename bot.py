from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
from config import BOT_TOKEN

# Проверяем токен
if not BOT_TOKEN:
    print("ОШИБКА: BOT_TOKEN не установлен! Создайте файл .env с токеном")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Я тестовый бот. Если видишь это сообщение - бот работает!")

@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    await message.answer("✅ Тест пройден! Бот отвечает.")

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Вы написали: {message.text}")

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())