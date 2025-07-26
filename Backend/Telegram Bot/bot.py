from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BufferedInputFile
import aiohttp
import asyncio
import os
import base64

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN", "")
API_URL = os.getenv("API_URL", "http://localhost:3000")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    data = {
        "telegramId": message.from_user.id,
        "username": message.from_user.username or "Unknown"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/user", json=data) as resp:
                await message.answer("Привет! Я готов общаться.")
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка подключения к серверу: {e}")


@dp.message(Command(commands=["system_prompt"]))
async def on_system_prompt(message: types.Message):
    args = message.get_full_command()[1:]
    if not args:
        await message.answer("Укажите новый системный промпт после команды.")
        return

    data = {
        "telegramId": message.from_user.id,
        "systemPrompt": " ".join(args)
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(f"{API_URL}/user", json=data) as resp:
                if resp.status != 200 or 201:
                    text = await resp.text()
                    await message.answer(f"Ошибка обновления: {resp.status}\n{text}")
                    return
                result = await resp.json()
                await message.answer(
                    f"✅ Системный промпт обновлён:\n`{result.get('systemPrompt')}`",
                    parse_mode="Markdown"
                )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

async def fetch_models() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/models") as resp:
            resp.raise_for_status()
            return await resp.json()

async def fetch_user(telegram_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/user/{telegram_id}") as resp:
            resp.raise_for_status()
            return await resp.json()

async def patch_user_model(telegram_id: int, model_id: str) -> dict:
    payload = {
        "telegramId": telegram_id,
        "defaultModel": model_id
    }
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{API_URL}/user", json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()

def build_keyboard(models: list[dict], selected_id: str | None) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    for m in models:
        label = m['name']
        if str(m['id']) == selected_id:
            label = f"✅ {label}"
        buttons.append(
            InlineKeyboardButton(text=label, callback_data=f"model_select:{m['id']}")
        )
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command(commands=["models"]))
async def on_models_command(message: types.Message):
    telegram_id = message.from_user.id
    models, user = await asyncio.gather(
        fetch_models(),
        fetch_user(telegram_id)
    )
    current_model = str(user.get("defaultModel", ""))
    kb = build_keyboard(models, selected_id=current_model)
    await message.answer("Выберите модель:", reply_markup=kb)

@dp.callback_query(lambda c: c.data and c.data.startswith("model_select:"))
async def on_model_selected(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_id = callback.data.split(":", 1)[1]
    await patch_user_model(telegram_id, selected_id)
    models = await fetch_models()
    new_kb = build_keyboard(models, selected_id=selected_id)
    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer(text="✅ Модель обновлена", show_alert=False)

@dp.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def message_to_llm(message: types.Message):
    data = {
        "telegramId": message.from_user.id,
        "prompt": message.text,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/messages", json=data) as resp:
                data = await resp.json()
                msg_type = data.get("type")
                content  = data.get("content", "")
                if msg_type == 'image':
                    img_bytes = await resp.read()  
                    photo = BufferedInputFile(img_bytes, filename="gen.png")
                    await bot.send_photo(message.chat.id, photo)
                return await message.answer(content)
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка подключения к серверу: {e}")



async def main():
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())
