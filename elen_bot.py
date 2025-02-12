import telebot
import random
from aiogram.filters import Command
from aiogram import F
from aiogram.types.input_file import FSInputFile

import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = f"https://{os.getenv('RAILWAY_APP_NAME')}.up.railway.app/{TOKEN}"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

server = Flask(__name__)

# Файл с подписками пользователей
USER_FILE = "users.json"

# Папка с картинками
CAT_DIR = "коты"
TAROT_DIR = "таро"

# Загружаем подписки
def load_subscriptions():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Сохраняем подписки
def save_subscriptions(data):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Получаем рандомную картинку
def get_random_image(category):
    category_dir = CAT_DIR if category == "cats" else TAROT_DIR
    if os.path.exists(category_dir):
        images = [f for f in os.listdir(category_dir) if f.endswith(".png")]
        if images:
            return os.path.join(category_dir, random.choice(images))
    return None

# Главное меню выбора рассылки
def main_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="твой кот дня", callback_data="subscribe_cats"),
                InlineKeyboardButton(text="твоя карта дня", callback_data="subscribe_tarot")
            ]
        ]
    )
    return keyboard

# Кнопки для отмены или смены подписки
def subscription_menu():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Отменить рассылку", callback_data="unsubscribe"),
                InlineKeyboardButton(text="Выбрать другую рассылку", callback_data="change_subscription")
            ]
        ]
    )
    return keyboard
# Обработчик команды /start
@router.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "приветик, я могу стать твоим интернет другом или просто быть рядом тогда, когда тебе это будет нужно. с помощью меня ты можешь получить предсказание на день, услышать случайный жизненный совет или увидеть какой котенок ты сегодня. ну что, уже решил что хочешь?", 
        reply_markup=main_menu()
    )

# Обработка выбора подписки
@router.callback_query(F.data.startswith("subscribe_"))
async def process_subscription(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    category = "cats" if callback_query.data == "subscribe_cats" else "tarot"

    subscriptions = load_subscriptions()
    subscriptions[user_id] = category
    save_subscriptions(subscriptions)

    image_path = get_random_image(category)
    if image_path:
        caption = "Твой кот дня!" if category == "cats" else "твоя карта Таро на сегодня))"

        # Используем InputFile, правильно передавая путь к файлу
        photo = FSInputFile(image_path)
        
        # Отправляем фотографию
        await bot.send_photo(user_id, photo=photo, caption=caption)
        await bot.send_message(user_id, "теперь я буду присылать тебе новую картинку каждый день))", reply_markup=subscription_menu())
    else:
        await bot.send_message(user_id, "картинки закончились..")

# Рассылка утренних картинок
async def send_daily_images():
    subscriptions = load_subscriptions()
    for user_id, category in subscriptions.items():
        image_path = get_random_image(category)
        if image_path:
            try:
                caption = "такой ты сегодня дурацкий кот" if category == "cats" else "твоя карта таро на сегодня"
                photo = FSInputFile(image_path)
                await bot.send_photo(user_id, photo=photo, caption=caption)
            except Exception as e:
                print(f"Ошибка при отправке пользователю {user_id}: {e}")
# Отписка от рассылки
@router.callback_query(F.data == "unsubscribe")
async def unsubscribe(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    subscriptions = load_subscriptions()

    if user_id in subscriptions:
        del subscriptions[user_id]
        save_subscriptions(subscriptions)
        await bot.send_message(user_id, "ты отписался от меня тварь(()) если передумаешь, введи /start.")
    else:
        await bot.send_message(user_id, "но ты не подписан ни на что дуралей")

# Смена подписки
@router.callback_query(F.data == "change_subscription")
async def change_subscription(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    subscriptions = load_subscriptions()

    if user_id in subscriptions:
        del subscriptions[user_id]
        save_subscriptions(subscriptions)

    await bot.send_message(user_id, "Выбери новую рассылку:", reply_markup=main_menu())
    

# Запуск планировщика
scheduler = AsyncIOScheduler()
scheduler.add_job(send_daily_images, "cron", hour=8, minute=0)


# Вебхук Telegram
@server.route(f"/{TOKEN}", methods=["POST"])
async def webhook_update():
    json_str = await request.get_data()
    update = types.Update.model_validate_json(json_str)
    await dp.process_update(update)
    return "!", 200

# Установка вебхука при запуске
@server.route("/")
async def set_webhook():
    await bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook установлен", 200

# Основная функция запуска
async def main():
    scheduler.start()
    await set_webhook()
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# Запуск бота
if __name__ == "__main__":
    asyncio.run(main())
