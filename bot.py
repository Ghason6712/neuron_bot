from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import asyncio
import os
import tempfile
from config import BOT_TOKEN
from utils import file_manager, get_file_type
import processor

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    """Основная клавиатура с кнопками."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 Отправить файлы"), KeyboardButton(text="📊 Статус")],
            [KeyboardButton(text="🧹 Очистить файлы"), KeyboardButton(text="ℹ️ Помощь")],
            [KeyboardButton(text="🔄 Перезапустить"), KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard

def get_file_type_keyboard():
    """Клавиатура для выбора типа файла (если нужно уточнить)."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="roH.obl"), KeyboardButton(text="roV.obl"), KeyboardButton(text="z.ini")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_confirmation_keyboard():
    """Клавиатура для подтверждения действий."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, начать обработку"), KeyboardButton(text="❌ Нет, отправить ещё файлы")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_inline_file_actions():
    """Инлайн-кнопки для действий с файлом."""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="📊 Показать первые строки", callback_data="show_preview"),
        InlineKeyboardButton(text="🗑 Удалить файл", callback_data="delete_file"),
        InlineKeyboardButton(text="📝 Переименовать", callback_data="rename_file")
    )
    builder.adjust(1)
    return builder.as_markup()

# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработка команды /start."""
    welcome_text = (
        "👋 *Добро пожаловать!*\n\n"
        "Я бот для обработки геофизических данных.\n\n"
        "📁 *Как работать с ботом:*\n"
        "1. Нажмите '📤 Отправить файлы'\n"
        "2. Отправьте 3 файла в любом порядке:\n"
        "   • *roH.obl* - горизонтальные сопротивления\n"
        "   • *roV.obl* - вертикальные сопротивления\n"
        "   • *z.ini* - глубины\n"
        "3. После загрузки всех файлов начнётся обработка\n"
        "4. Получите результат в виде файла\n\n"
        "✨ *Особенности:*\n"
        "• Бот сам определит тип каждого файла\n"
        "• Поддерживаются файлы .obl, .ini, .txt\n"
        "• Максимальный размер файла: 10 МБ\n"
        "• Обработка занимает несколько секунд\n\n"
        "📌 Используйте кнопки ниже для управления:"
    )
    
    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработка команды /help."""
    help_text = (
        "🆘 *Справка*\n\n"
        "📁 *Необходимые файлы:*\n"
        "1. *roH.obl* - файл горизонтальных сопротивлений\n"
        "2. *roV.obl* - файл вертикальных сопротивлений\n"
        "3. *z.ini* - файл глубин\n\n"
        "🎯 *Как использовать:*\n"
        "• Нажмите '📤 Отправить файлы'\n"
        "• Отправляйте файлы по одному\n"
        "• Бот покажет прогресс загрузки\n"
        "• После 3 файлов начнётся обработка\n\n"
        "⚙️ *Команды:*\n"
        "/start - Главное меню\n"
        "/clear - Удалить все файлы\n"
        "/status - Показать загруженные файлы\n"
        "/help - Эта справка\n\n"
        "⚠️ *Ограничения:*\n"
        "• Максимум 10 МБ на файл\n"
        "• Только .obl, .ini, .txt форматы\n"
        "• Таймаут обработки: 60 секунд\n\n"
        "📞 *Поддержка:*\n"
        "При возникновении проблем обратитесь к разработчику."
    )
    await message.answer(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Обработка команды /clear."""
    user_id = message.from_user.id
    file_manager.clear_user_files(user_id)
    await message.answer(
        "✅ Все ваши файлы удалены.\n\n"
        "Теперь вы можете начать заново.",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Обработка команды /status."""
    await show_status(message)

# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@dp.message(F.text == "📤 Отправить файлы")
async def handle_send_files(message: types.Message):
    """Обработка нажатия кнопки 'Отправить файлы'."""
    user_id = message.from_user.id
    user_files = file_manager.get_user_files(user_id)
    
    if len(user_files) >= 3:
        await message.answer(
            "⚠️ У вас уже загружено 3 файла.\n\n"
            "Выберите действие:",
            reply_markup=get_confirmation_keyboard()
        )
    else:
        await message.answer(
            f"📤 *Отправьте файлы*\n\n"
            f"Загружено: *{len(user_files)}/3*\n\n"
            f"📋 *Инструкция:*\n"
            f"1. Нажмите на скрепку 📎\n"
            f"2. Выберите 'Файл'\n"
            f"3. Отправьте нужный файл\n\n"
            f"📁 *Поддерживаемые форматы:*\n"
            f"• .obl (roH, roV)\n"
            f"• .ini (z)\n"
            f"• .txt\n\n"
            f"📏 *Максимальный размер:* 10 МБ",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )

@dp.message(F.text == "📊 Статус")
async def handle_status(message: types.Message):
    """Обработка нажатия кнопки 'Статус'."""
    await show_status(message)

@dp.message(F.text == "🧹 Очистить файлы")
async def handle_clear(message: types.Message):
    """Обработка нажатия кнопки 'Очистить файлы'."""
    user_id = message.from_user.id
    user_files = file_manager.get_user_files(user_id)
    
    if not user_files:
        await message.answer(
            "📭 У вас нет загруженных файлов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    file_list = "\n".join([f"• {os.path.basename(f)}" for f in user_files])
    
    # Создаем временную клавиатуру для подтверждения
    confirm_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, удалить всё"), KeyboardButton(text="❌ Нет, оставить")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"🗑 *Подтверждение удаления*\n\n"
        f"У вас загружено *{len(user_files)}* файлов:\n"
        f"{file_list}\n\n"
        f"Вы действительно хотите удалить все файлы?",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard
    )

@dp.message(F.text == "✅ Да, удалить всё")
async def handle_confirm_clear(message: types.Message):
    """Подтверждение удаления файлов."""
    user_id = message.from_user.id
    file_manager.clear_user_files(user_id)
    await message.answer(
        "✅ Все файлы успешно удалены!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "❌ Нет, оставить")
async def handle_cancel_clear(message: types.Message):
    """Отмена удаления файлов."""
    await message.answer(
        "✅ Файлы сохранены.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "ℹ️ Помощь")
async def handle_help(message: types.Message):
    """Обработка нажатия кнопки 'Помощь'."""
    await cmd_help(message)

@dp.message(F.text == "🔄 Перезапустить")
async def handle_restart(message: types.Message):
    """Обработка нажатия кнопки 'Перезапустить'."""
    user_id = message.from_user.id
    file_manager.clear_user_files(user_id)
    await cmd_start(message)

@dp.message(F.text == "❌ Отмена")
async def handle_cancel(message: types.Message):
    """Обработка нажатия кнопки 'Отмена'."""
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "✅ Да, начать обработку")
async def handle_start_processing(message: types.Message):
    """Начало обработки файлов."""
    user_id = message.from_user.id
    await process_user_files(user_id, message)

@dp.message(F.text == "❌ Нет, отправить ещё файлы")
async def handle_more_files(message: types.Message):
    """Пользователь хочет отправить больше файлов."""
    await message.answer(
        "❌ Обработка отменена.\n\n"
        "Вы можете отправить другие файлы.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "🔙 Главное меню")
async def handle_back_to_main(message: types.Message):
    """Возврат в главное меню."""
    await cmd_start(message)

@dp.message(F.text == "🔙 Назад")
async def handle_back(message: types.Message):
    """Возврат на шаг назад."""
    await message.answer(
        "Возвращаюсь...",
        reply_markup=get_main_keyboard()
    )

# ==================== ФУНКЦИИ ====================

async def show_status(message: types.Message):
    """Показать статус пользователя."""
    user_id = message.from_user.id
    user_files = file_manager.get_user_files(user_id)
    
    if not user_files:
        await message.answer(
            "📭 *Статус:* Нет загруженных файлов\n\n"
            "Нажмите '📤 Отправить файлы' чтобы начать.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    file_info = []
    for i, file_path in enumerate(user_files, 1):
        filename = os.path.basename(file_path)
        file_type = get_file_type(filename)
        size = os.path.getsize(file_path) / 1024  # размер в КБ
        
        file_info.append(
            f"{i}. *{filename}*\n"
            f"   Тип: {file_type} | Размер: {size:.1f} КБ"
        )
    
    file_list = "\n\n".join(file_info)
    
    status_text = (
        f"📊 *Статус загрузки*\n\n"
        f"📁 Загружено файлов: *{len(user_files)}/3*\n\n"
        f"{file_list}\n\n"
    )
    
    if len(user_files) == 3:
        status_text += "✅ *Все файлы загружены!*\nНажмите '✅ Да, начать обработку' или отправьте команду /process"
    
    await message.answer(
        status_text,
        parse_mode="Markdown",
        reply_markup=get_confirmation_keyboard() if len(user_files) == 3 else get_main_keyboard()
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
        await message.answer(
            f"❌ Формат *{file_ext}* не поддерживается.\n\n"
            f"Поддерживаемые форматы: {', '.join(allowed_extensions)}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем размер файла (максимум 10 MB)
    if document.file_size and document.file_size > 10 * 1024 * 1024:
        await message.answer(
            "❌ Файл слишком большой. Максимальный размер: *10 МБ*.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    try:
        # Создаём временную папку для пользователя
        temp_dir = os.path.join(tempfile.gettempdir(), f"tg_bot_{user_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Скачиваем файл
        file_path = os.path.join(temp_dir, document.file_name)
        
        await message.answer(f"📥 *Загружаю {document.file_name}...*", parse_mode="Markdown")
        await bot.download(document, destination=file_path)
        
        # Сохраняем информацию о файле
        file_manager.add_file(user_id, file_path)
        
        # Проверяем количество файлов
        user_files = file_manager.get_user_files(user_id)
        file_type = get_file_type(document.file_name)
        
        await message.answer(
            f"✅ *Файл успешно загружен!*\n\n"
            f"📝 *Информация:*\n"
            f"• Имя: {document.file_name}\n"
            f"• Тип: {file_type}\n"
            f"• Размер: {document.file_size / 1024:.1f} КБ\n\n"
            f"📊 *Прогресс:* {len(user_files)}/3 файлов",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
        # Если есть 3 файла - предлагаем начать обработку
        if len(user_files) == 3:
            await message.answer(
                "🎯 *Все файлы загружены!*\n\n"
                "Хотите начать обработку?",
                reply_markup=get_confirmation_keyboard()
            )
            
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка при загрузке файла:*\n\n{str(e)}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def process_user_files(user_id, message):
    """Обработка файлов пользователя."""
    user_files = file_manager.get_user_files(user_id)
    
    if len(user_files) != 3:
        await message.answer(
            "❌ Недостаточно файлов для обработки.",
            reply_markup=get_main_keyboard()
        )
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
                "⚠ *Внимание:* Не удалось определить типы файлов автоматически.\n"
                "Использую порядок загрузки:\n"
                f"1. {os.path.basename(roh_file)} → roH\n"
                f"2. {os.path.basename(rov_file)} → roV\n"
                f"3. {os.path.basename(z_file)} → z",
                parse_mode="Markdown"
            )
        
        # Создаём клавиатуру с индикатором процесса
        processing_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⏳ Обработка...")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "⚙ *Начинаю обработку файлов...*\n\n"
            "⏳ Это может занять несколько секунд.\n"
            "Пожалуйста, подождите...",
            parse_mode="Markdown",
            reply_markup=processing_keyboard
        )
        
        # Запускаем обработку в отдельном потоке
        output_file = await asyncio.to_thread(
            processor.process_files,
            roh_file, rov_file, z_file
        )
        
        # Отправляем результат
        await message.answer("📤 *Отправляю результат...*", parse_mode="Markdown")
        
        # Отправляем файл
        document = FSInputFile(output_file, filename="all_predictions.dat")
        await message.answer_document(
            document,
            caption="✅ *Обработка завершена!*\n\n"
                   "📄 Файл с результатами готов.\n"
                   "Вы можете начать новую обработку.",
            parse_mode="Markdown"
        )
        
        # Очищаем временные файлы
        file_manager.clear_user_files(user_id)
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Возвращаем основную клавиатуру
        await message.answer(
            "✨ *Готово!* Вы можете начать новую обработку.",
            reply_markup=get_main_keyboard()
        )
            
    except Exception as e:
        await message.answer(
            f"❌ *Ошибка обработки:*\n\n{str(e)}\n\n"
            "Пожалуйста, проверьте файлы и попробуйте снова.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        file_manager.clear_user_files(user_id)

@dp.message()
async def handle_other_messages(message: types.Message):
    """Обработка всех остальных сообщений."""
    if message.text.startswith('/'):
        # Если команда не обработана, покажем помощь
        await cmd_help(message)
    else:
        # Если текст не команда и не кнопка, покажем главное меню
        await message.answer(
            "🤔 Не понял ваше сообщение.\n\n"
            "Используйте кнопки ниже или команды:\n"
            "/start - Главное меню\n"
            "/help - Справка",
            reply_markup=get_main_keyboard()
        )

async def main():
    """Основная функция запуска бота."""
    print("🤖 Бот запущен...")
    print("✨ Используйте Ctrl+C для остановки")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        print("🛑 Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())