import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
import os
import logging
from mail.mail_handler import router as mail_router
from config import BOT_TOKEN, CONTACT

logging.basicConfig(level=logging.INFO)

#отрисовка
from otrisovka.main import generate_image_with_amounts
#админка
from admin.admin import router as admin_router


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(mail_router)
dp.include_router(router)
dp.include_router(admin_router)


# Пути
MENU_IMAGE_PATH = "./assets/menu.png"
OTRIS_IMAGE_PATH = "./assets/otris.png"
ZAPRET_IMAGE_PATH = "./assets/zapret.png"
ABOUT_IMAGE_PATH = "./assets/obot.png"

last_message_id = {}

async def delete_current_message(callback_query: types.CallbackQuery):
    if isinstance(callback_query.message, types.Message): 
        try:
            await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")


async def delete_previous_message(user_id: int, chat_id: int):
    if user_id in last_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_message_id[user_id])
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
        finally:
            last_message_id.pop(user_id, None)


class DrawState(StatesGroup):
    waiting_for_amounts = State()


def add_user_to_db(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            access INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def has_access(user_id: int) -> bool:
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT access FROM users WHERE telegram_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None and result[0] == 1


def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸Отрисовка", callback_data="draw"), InlineKeyboardButton(text="ℹ️О боте", callback_data="about_bot")],
            [InlineKeyboardButton(text="📩Почта", callback_data="generate_mail_intro"), InlineKeyboardButton(text="🤖ChatGPT", url="https://t.me/Free_ChatGPTAI_bot")],
        ]
    )
    return keyboard



@dp.message(CommandStart())
async def cmd_start(message: Message):
    add_user_to_db(message.from_user.id)

    if has_access(message.from_user.id):
        photo = FSInputFile(MENU_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=message.chat.id, photo=photo,
                                   caption=
                                    "👋 <b>Добро пожаловать!</b>\n"
                                    "<b>Это вспомогательный бот.</b>\n\n"
                                    "<i>Выберите нужный раздел ниже:</i>",
                                   reply_markup=get_main_menu_keyboard())
        last_message_id[message.from_user.id] = msg.message_id
    else:
        photo = FSInputFile(ZAPRET_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=message.chat.id, photo=photo,
                                   caption="🚫 У вас нет доступа к этому боту.")
        last_message_id[message.from_user.id] = msg.message_id

@router.callback_query(F.data == "draw")
async def handle_draw_button(callback_query: types.CallbackQuery, state: FSMContext):
    if has_access(callback_query.from_user.id):
        photo = FSInputFile(OTRIS_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo,
                                   caption="Введите 3 суммы через запятую (например: 1000,2000,3000)")
        last_message_id[callback_query.from_user.id] = msg.message_id
        await state.set_state(DrawState.waiting_for_amounts)
    await callback_query.answer()

@router.callback_query(F.data == "draw_again")
async def handle_draw_again(callback_query: types.CallbackQuery, state: FSMContext):
    if has_access(callback_query.from_user.id):
        photo = FSInputFile(OTRIS_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo,
                                   caption="Введите 3 суммы через запятую (например: 1000,2000,3000)")
        
        # Сохраняем ID нового сообщения, чтобы оно могло быть удалено позже
        last_message_id[callback_query.from_user.id] = msg.message_id
        
        await state.set_state(DrawState.waiting_for_amounts)

    await callback_query.answer()



@router.message(DrawState.waiting_for_amounts)
async def handle_amounts_input(message: Message, state: FSMContext):
    if not has_access(message.from_user.id):
        photo = FSInputFile(ZAPRET_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=message.chat.id, photo=photo,
                                   caption="🚫 У вас нет доступа к этому боту.")
        last_message_id[message.from_user.id] = msg.message_id
        return

    parts = message.text.split(",")
    if len(parts) != 3:
        msg = await message.answer("❗ Введите *ровно три* суммы через запятую.")
        last_message_id[message.from_user.id] = msg.message_id
        return

    try:
        generate_image_with_amounts(parts)
        photo = FSInputFile("otrisovka/output.png")
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔁Отрисовать ещё", callback_data="draw_again")],
                [InlineKeyboardButton(text="⬅️В меню", callback_data="to_menu")]
            ]
        )
        
        msg = await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="✅ Готово",
            reply_markup=keyboard
        )
        last_message_id[message.from_user.id] = msg.message_id
    except Exception as e:
        msg = await message.answer(f"Ошибка при генерации изображения: {e}")
        last_message_id[message.from_user.id] = msg.message_id

    await state.clear()

@router.callback_query(F.data == "draw")
async def handle_draw_button(callback_query: types.CallbackQuery, state: FSMContext):
    await delete_current_message(callback_query)

    if has_access(callback_query.from_user.id):
        photo = FSInputFile(OTRIS_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo,
                                   caption="Введите 3 суммы через запятую (например: 1000,2000,3000)")
        last_message_id[callback_query.from_user.id] = msg.message_id
        await state.set_state(DrawState.waiting_for_amounts)

    await callback_query.answer()


@router.callback_query(F.data == "to_menu")
async def handle_to_menu(callback_query: types.CallbackQuery):
    await delete_current_message(callback_query)

    if has_access(callback_query.from_user.id):
        photo = FSInputFile(MENU_IMAGE_PATH)
        msg = await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo,
                                   caption=
                                    "👋 <b>Добро пожаловать!</b>\n"
                                    "<b>Это вспомогательный бот.</b>\n\n"
                                    "<i>Выберите нужный раздел ниже:</i>",
                                   reply_markup=get_main_menu_keyboard())
        last_message_id[callback_query.from_user.id] = msg.message_id

    await callback_query.answer()

@router.callback_query(F.data == "generate_mail_intro")
async def handle_get_mail_intro(callback_query: types.CallbackQuery):
    await delete_current_message(callback_query)
    
    text = (
        "📬 <b>Одноразовая почта</b>\n\n"
        "Эта функция позволяет вам создать одноразовый почтовый ящик для быстрой регистрации на сайтах или получения сообщений, "
        "не раскрывая ваш основной адрес. Почта автоматически удаляется через некоторое время.\n\n"
        "Нажмите на кнопку ниже, чтобы получить новый почтовый адрес."
    )
    
    keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📨Получить почту", callback_data="generate_mail")],
        [InlineKeyboardButton(text="⬅️В меню", callback_data="to_menu")]
        ]
    )
    
    photo = FSInputFile("./assets/pocht.png")
    await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo, caption=text, reply_markup=keyboard)
    await callback_query.answer()




@router.callback_query(F.data == "about_bot")
async def handle_about_bot(callback_query: types.CallbackQuery):
    await delete_current_message(callback_query)
    
    text = (
        "🔍 <b>О боте</b>\n\n"
        "Этот бот является вспомогательным инструментом, предоставляющим несколько полезных функций. 📊\n\n"
        "✅ <b>Возможности бота:</b>\n"
        "- Отрисовка изображений с указанными суммами.\n"
        "- Одноразовая почта - для быстрой регистрации и защиты приватности.\n"
        "- Задать вопрос ChatGPT - для наших пользователей также сделан бесплатный бот для получения нужной информации @Free_ChatGPTAI_bot.\n\n"
        "📲 Свяжитесь с администратором для получения доступа.\n\n"
        "🔧 Функционал будет постоянно дополняться и улучшаться."
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧙‍♂️Связь", url=CONTACT)],
            [InlineKeyboardButton(text="⬅️В меню", callback_data="to_menu")]
        ]
    )
    
    photo = FSInputFile(ABOUT_IMAGE_PATH)
    await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo, caption=text, reply_markup=keyboard)
    await callback_query.answer()


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
