import requests
import random
import string
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging
import os
from aiogram.types import InputFile
from aiogram.types import FSInputFile

logging.basicConfig(level=logging.INFO)

router = Router()

# URL API Mail.tm
BASE_URL = "https://api.mail.tm"

def generate_random_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

def generate_random_password():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def get_available_domains():
    try:
        response = requests.get(f"{BASE_URL}/domains")
        response.raise_for_status()
        domains = response.json().get("hydra:member", [])
        if domains:
            return [domain['domain'] for domain in domains]
        else:
            logging.error("Нет доступных доменов.")
            return []
    except Exception as e:
        logging.error(f"Ошибка при получении доступных доменов: {e}")
        return []

def create_account():
    domains = get_available_domains()
    if not domains:
        return None, None

    email = f"{generate_random_username()}@{random.choice(domains)}"
    password = generate_random_password()

    response = requests.post(f"{BASE_URL}/accounts", json={"address": email, "password": password})
    
    if response.status_code == 201:
        return email, password
    else:
        logging.error(f"Ошибка при создании аккаунта: {response.json()}")
        return None, None

def get_token(email, password):
    response = requests.post(f"{BASE_URL}/token", json={"address": email, "password": password})
    
    if response.status_code == 200:
        return response.json().get("token")
    else:
        logging.error(f"Ошибка при получении токена: {response.json()}")
        return None

async def check_inbox(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/messages", headers=headers)
    
    if response.status_code == 200:
        return response.json().get("hydra:member", [])
    else:
        logging.error(f"Ошибка при проверке почты: {response.json()}")
        return None

async def read_message(token, message_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/messages/{message_id}", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Ошибка при чтении письма: {response.json()}")
        return None

@router.callback_query(lambda callback_query: callback_query.data == "generate_mail")
async def handle_get_mail(callback_query: types.CallbackQuery, state: FSMContext):
    logging.info("Кнопка 'Почта' нажата.")
    
    email, password = create_account()

    if not email or not password:
        await callback_query.message.answer("❌ Ошибка при создании почтового адреса. Попробуйте снова.")
        return

    token = get_token(email, password)

    if not token:
        await callback_query.message.answer("❌ Ошибка при получении токена. Попробуйте снова.")
        return

    await state.update_data(email=email, token=token)
    logging.info(f"Сохранённый email: {email}")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Проверить почту", callback_data="check_inbox")]
        ]
    )
    
    await callback_query.message.answer(
        f"✅ Ваш одноразовый почтовый адрес:\n<b>{email}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback_query.answer()

@router.callback_query(lambda callback_query: callback_query.data == "check_inbox")
async def handle_check_inbox(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    token = data.get("token")
    email = data.get("email")
    previous_message_id = data.get("last_check_message_id")  # Получаем ID предыдущего сообщения

    # Удаляем предыдущее сообщение, если оно есть
    if previous_message_id:
        try:
            await callback_query.message.bot.delete_message(chat_id=callback_query.message.chat.id, message_id=previous_message_id)
        except Exception as e:
            logging.error(f"Ошибка при удалении предыдущего сообщения: {e}")

    if not token or not email:
        msg = await callback_query.message.answer("❌ Почтовый ящик не найден. Попробуйте снова получить почту.")
        await state.update_data(last_check_message_id=msg.message_id)  # Сохраняем ID сообщения
        return

    messages = await check_inbox(token)

    if messages:
        for message in messages:
            subject = message.get("subject", "Без темы")
            message_id = message.get("id")
            sender = message.get("from", {}).get("address", "Неизвестный отправитель")
            msg = await callback_query.message.answer(
                f"📧 <b>Новое письмо:</b>\n<b>Отправитель:</b> {sender}\n<b>Тема:</b> {subject}\n<b>ID:</b> {message_id}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Читать письмо", callback_data=f"read_message_{message_id}")]
                    ]
                )
            )
            await state.update_data(last_check_message_id=msg.message_id)  # Сохраняем ID сообщения
    else:
        msg = await callback_query.message.answer("📭 В почтовом ящике пока нет писем.")
        await state.update_data(last_check_message_id=msg.message_id)  # Сохраняем ID сообщения

    await callback_query.answer()


@router.callback_query(lambda callback_query: callback_query.data.startswith("read_message_"))
async def handle_read_message(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    token = data.get("token")

    if not token:
        await callback_query.message.answer("❌ Токен не найден. Попробуйте снова получить почту.")
        return

    message_id = callback_query.data.split("_")[-1]
    message_data = await read_message(token, message_id)

    if message_data:
        sender = message_data.get("from", {}).get("address", "Неизвестный отправитель")
        subject = message_data.get("subject", "Без темы")
        html_content = message_data.get("html", [])
        text_content = message_data.get("text", "Нет текста")

        if html_content:
            html_content = html_content[0]
        elif text_content:
            html_content = f"<pre>{text_content}</pre>"
        else:
            html_content = "<p>Сообщение пустое.</p>"

        # Генерация имени файла
        filename = f"email_{message_id}.html"
        file_path = os.path.join(os.getcwd(), filename)

        # Сохранение HTML-содержимого в файл
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(html_content)

        # 📌 Исправление: Использование FSInputFile для отправки файла
        file_to_send = FSInputFile(file_path)
        await callback_query.message.answer_document(
            document=file_to_send,
            caption=f"📩 <b>Сообщение от:</b> {sender}\n<b>Тема:</b> {subject}",
            parse_mode="HTML"
        )
        
        # Удаление файла после отправки
        os.remove(file_path)
    else:
        await callback_query.message.answer("❌ Ошибка при чтении письма.")

    await callback_query.answer()