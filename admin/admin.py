from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from config import ADMIN_ID
router = Router()


class AdminState(StatesGroup):
    waiting_for_user_id_to_add = State()
    waiting_for_user_id_to_remove = State()


def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Выдать доступ", callback_data="give_access")],
        [InlineKeyboardButton(text="📤 Забрать доступ", callback_data="remove_access")],
        [InlineKeyboardButton(text="📋 Статистика доступа", callback_data="list_users")]
    ])
    return keyboard


# Вход в админ-панель
@router.message(Command("adminqibix"))
async def enter_admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔑 <b>Админка</b>\n\nВыберите нужное действие:", reply_markup=get_admin_keyboard())
    else:
        return


# Обработчик кнопок админки
@router.callback_query()
async def handle_admin_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("🚫 У вас нет доступа!", show_alert=True)
        return

    if callback_query.data == "give_access":
        await callback_query.message.answer("Введите ID пользователя, которому нужно выдать доступ (в формате: 123456789)")
        await state.set_state(AdminState.waiting_for_user_id_to_add)
        await callback_query.answer()

    elif callback_query.data == "remove_access":
        await callback_query.message.answer("Введите ID пользователя, у которого нужно забрать доступ (в формате: 123456789)")
        await state.set_state(AdminState.waiting_for_user_id_to_remove)
        await callback_query.answer()

    elif callback_query.data == "list_users":
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE access = 1")
        access_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE access = 0")
        no_access_count = cursor.fetchone()[0]

        conn.close()

        await callback_query.message.answer(
            f"✅ Пользователей с доступом: {access_count}\n🚫 Пользователей без доступа: {no_access_count}"
        )
        await callback_query.answer()


# Выдача доступа (ожидание ID)
@router.message(AdminState.waiting_for_user_id_to_add)
async def process_add_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        
        cursor.execute("UPDATE users SET access = 1 WHERE telegram_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Доступ пользователю {user_id} выдан.")

        # Уведомление пользователя о том, что ему выдали доступ
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text="✅ Вам выдали доступ к боту! Пожалуйста, напишите команду /start для использования."
            )
        except:
            pass
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()


# Удаление доступа (ожидание ID)
@router.message(AdminState.waiting_for_user_id_to_remove)
async def process_remove_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET access = 0 WHERE telegram_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Доступ пользователю {user_id} отозван.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()
