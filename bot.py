from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
import asyncio
import os
import tempfile
from config import BOT_TOKEN
from utils import file_manager, get_file_type
import processor

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для обработки геофизических данных.\n\n"
        "📁 Отправьте мне 3 файла в ЛЮБОМ порядке:\n"
        "• roH.obl (горизонтальные сопротивления)\n"
        "• roV.obl (вертикальные сопротивления)\n"
        "• z.ini (глубины)\n\n"
        "⚡ Я запущу обработку и пришлю вам файл с результатами.\n\n"
        "📝 Как это работает:\n"
        "1. Отправляйте файлы по одному\n"
        "2. Бот сам определит тип каждого файла\n"
        "3. Когда будут все 3 файла - начнётся обработка\n\n"
        "🔧 Команды:\n"
        "/clear - удалить мои файлы\n"
        "/status - что я уже отправил\n"
        "/help - эта инструкция"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await cmd_start(message)

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Очистить файлы пользователя."""
    user_id = message.from_user.id
    file_manager.clear_user_files(user_id)
    await message.answer("✅ Все ваши файлы удалены. Можно отправлять новые.")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Показать статус."""
    user_id = message.from_user.id
    user_files = file_manager.get_user_files(user_id)
    
    if not user_files:
        await message.answer("📭 У вас нет загруженных файлов.")
        return
    
    file_info = []
    for file_path in user_files:
        filename = os.path.basename(file_path)
        file_type = get_file_type(filename)
        file_info.append(f"• {filename} ({file_type})")
    
    file_list = "\n".join(file_info)
    await message.answer(
        f"📁 Ваши файлы ({len(user_files)}/3):\n\n"
        f"{file_list}\n\n"
        f"Отправьте остальные файлы или дождитесь автоматической обработки."
    )

@dp.message(F.document)
async def handle_document(message: types.Message):
    """Обработка загружаемых документов."""
    user_id = message.from_user.id
    document = message.document
    
    # Проверяем расширение файла
    allowed_extensions = ['.obl', '.ini', '.txt', '.dat']
    file_ext = os.path.splitext(document.file_name)[1].lower()
    
    if file_ext not in allowed_extensions:
        await message.answer(f"❌ Формат {file_ext} не поддерживается.")
        return
    
    # Проверяем размер файла (максимум 10 MB)
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой. Максимум 10 MB.")
        return
    
    try:
        # Создаём временную папку для пользователя
        temp_dir = os.path.join(tempfile.gettempdir(), f"tg_bot_{user_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Скачиваем файл
        file_path = os.path.join(temp_dir, document.file_name)
        
        await message.answer(f"📥 Загружаю {document.file_name}...")
        await bot.download(document, destination=file_path)
        
        # Сохраняем информацию о файле
        file_manager.add_file(user_id, file_path)
        
        # Проверяем количество файлов
        user_files = file_manager.get_user_files(user_id)
        file_type = get_file_type(document.file_name)
        
        await message.answer(
            f"✅ Файл сохранён: {document.file_name}\n"
            f"📊 Тип: {file_type}\n"
            f"📁 Загружено файлов: {len(user_files)}/3"
        )
        
        # Если есть 3 файла - начинаем обработку
        if len(user_files) == 3:
            await process_user_files(user_id, message)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке файла: {str(e)}")

async def process_user_files(user_id, message):
    """Обработка файлов пользователя."""
    user_files = file_manager.get_user_files(user_id)
    
    if len(user_files) != 3:
        return
    
    try:
        # Определяем тип каждого файла
        roh_file = None
        rov_file = None
        z_file = None
        
        for file_path in user_files:
            filename = os.path.basename(file_path)
            file_type = get_file_type(filename)
            
            if file_type == 'roh' and roh_file is None:
                roh_file = file_path
            elif file_type == 'rov' and rov_file is None:
                rov_file = file_path
            elif file_type == 'z' and z_file is None:
                z_file = file_path
        
        # Проверяем, что нашли все три типа
        if not (roh_file and rov_file and z_file):
            # Если не определили автоматически, берём в порядке загрузки
            roh_file, rov_file, z_file = user_files[0], user_files[1], user_files[2]
            await message.answer(
                "⚠ Не удалось определить типы файлов автоматически.\n"
                "Буду использовать порядок загрузки:\n"
                f"1. {os.path.basename(roh_file)} → roH\n"
                f"2. {os.path.basename(rov_file)} → roV\n"
                f"3. {os.path.basename(z_file)} → z"
            )
        
        await message.answer("⚙ Начинаю обработку файлов... Это может занять несколько секунд.")
        
        # Запускаем обработку в отдельном потоке
        output_file = await asyncio.to_thread(
            processor.process_files,
            roh_file, rov_file, z_file
        )
        
        # Отправляем результат
        await message.answer("📤 Отправляю результат...")
        document = FSInputFile(output_file, filename="all_predictions.dat")
        await message.answer_document(document)
        await message.answer("✅ Обработка завершена!")
        
        # Очищаем временные файлы
        file_manager.clear_user_files(user_id)
        if os.path.exists(output_file):
            os.remove(output_file)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки: {str(e)}")
        file_manager.clear_user_files(user_id)

@dp.message()
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений."""
    await message.answer(
        "Отправьте мне 3 файла для обработки:\n"
        "1. roH.obl\n2. roV.obl\n3. z.ini\n\n"
        "Или используйте команды:\n"
        "/start - инструкция\n"
        "/clear - удалить мои файлы\n"
        "/status - проверить статус"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())