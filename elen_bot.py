import telebot
import random
from aiogram.filters import Command
from aiogram import F
from aiogram.types.input_file import FSInputFile
import uvicorn
import os
import logging
import json
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from flask import Flask, request

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TOKEN = "5800571745:AAFr-8QqNzgD35f9kFtqjg4Nq8wzW8SpY7Q"
WEBHOOK_URL = f"https://telebot-production-dde9.up.railway.app/webhook/{TOKEN}"
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
    logger.debug(f"Обработчик вызван: {callback_query.data}")
    category = "cats" if callback_query.data == "subscribe_cats" else "tarot"

    subscriptions = load_subscriptions()
    subscriptions[user_id] = category
    save_subscriptions(subscriptions)

    image_path = get_random_image(category)
    if image_path:
        caption = "Твой кот дня!" if category == "cats" else "Твоя карта Таро на сегодня))"

        # Отправляем фотографию без промежуточной переменной
        await bot.send_photo(user_id, FSInputFile(image_path), caption=caption)
        await bot.send_message(user_id, "Теперь я буду присылать тебе новую картинку каждый день))", reply_markup=subscription_menu())
    else:
        await bot.send_message(user_id, "Картинки закончились..")

# Рассылка утренних картинок
async def send_daily_images():
    subscriptions = load_subscriptions()
    for user_id, category in subscriptions.items():
        image_path = get_random_image(category)
        if image_path:
            try:
                caption = "Такой ты сегодня дурацкий кот" if category == "cats" else "Твоя карта таро на сегодня"
                
                # Отправляем фотографию без промежуточной переменной
                await bot.send_photo(user_id, FSInputFile(image_path), caption=caption)
            except Exception as e:
                logger.error(f"Ошибка при отправке пользователю {user_id}: {e}")


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
@server.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200

@server.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook_update():
    try:
        json_str = request.get_data().decode("utf-8")
        update = types.Update.model_validate_json(json_str)

        logger.debug(f"Webhook получил update: {update}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Добавляем try-except, чтобы ловить ошибки
        try:
            loop.run_until_complete(dp.feed_update(bot, update))  # Передаем bot явно!
        except Exception as e:
            logger.error(f"Error while processing update: {e}")

        return "OK", 200
    except Exception as e:
        logger.error(f"Critical error in webhook: {e}")
        return "Internal Server Error", 500
        
# Установка вебхука
async def set_webhook():
    await bot.set_webhook(url=WEBHOOK_URL)
    logger.info("Webhook установлен!")

async def main():
    scheduler.start()
    await set_webhook()

    port = int(os.getenv("PORT", 5000))
    config = uvicorn.Config("main:server", host="0.0.0.0", port=port)
    server_task = asyncio.create_task(uvicorn.Server(config).serve())

    logger.info("Бот запущен!")
    await server_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

