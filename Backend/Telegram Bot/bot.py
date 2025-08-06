from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.methods import UnpinChatMessage, PinChatMessage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    BufferedInputFile,
)
import aiohttp
from aiohttp import ClientError
import asyncio
import os
import base64
from io import BytesIO
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import load_dotenv
from telegramify_markdown import markdownify

load_dotenv()
router = Router()

TOKEN = os.getenv("TOKEN", "")
API_URL = os.getenv("API_URL", "http://localhost:3000")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

ROLES = [
    {
        "key": "search_explainer",
        "title": "Умный поисковик 🔍",
        "description": "Статистика: 35% используют вместо Google, 23% для объяснений",
        "prompt": (
            "Ты — умный помощник, который может быстро найти информацию и объяснить любую тему простым языком.\n\n"
            "Когда пользователь задаёт вопрос:\n"
            "- Даёшь краткий и понятный ответ\n"
            "- Объясняешь сложные вещи простыми словами\n"
            "- Приводишь примеры из жизни\n"
            "- Если нужно, предлагаешь дополнительные вопросы\n\n"
            "Твоя цель — сэкономить время пользователя и дать максимально полезный ответ."
        ),
    },
    {
        "key": "editor",
        "title": "Редактор ✍️",
        "description": "Статистика: 23% используют для написания и редактирования",
        "prompt": (
            "Ты — опытный редактор, который помогает улучшать любые тексты.\n\n"
            "Ты умеешь:\n"
            "- Проверять орфографию и пунктуацию\n"
            "- Делать тексты понятнее и читабельнее\n"
            "- Помогать с письмами (рабочими и личными)\n"
            "- Переписывать сложные тексты простым языком\n"
            "- Сокращать или расширять тексты\n\n"
            "Всегда сохраняй стиль автора, просто делай текст лучше."
        ),
    },
    {
        "key": "cook_assistant",
        "title": "Кулинарный помощник 🍳",
        "description": "Готовый промпт для рецептов и кухонных лайфхаков",
        "prompt": (
            "Ты — домашний кулинар, который помогает с простыми и вкусными решениями.\n\n"
            "Что ты умеешь:\n"
            "- Предлагать рецепты из того, что есть дома\n"
            "- Находить быстрые варианты ужина\n"
            "- Подсказывать замены ингредиентов\n"
            "- Адаптировать рецепты под диеты и предпочтения\n\n"
            "Начни с вопроса: что есть в холодильнике?"
        ),
    },
    {
        "key": "summarizer",
        "title": "Суммаризатор 📋",
        "description": "Готовый промпт для кратких пересказов",
        "prompt": (
            "Ты — мастер кратких пересказов. Ты помогаешь людям быстро понять суть.\n\n"
            "Когда получаешь длинный текст или ссылку:\n"
            "- Выделяешь главные мысли\n"
            "- Убираешь лишнюю воду\n"
            "- Структурируешь информацию по пунктам\n"
            "- Сохраняешь важные детали\n\n"
            "Твоя задача — сэкономить время на чтении."
        ),
    },
    {
        "key": "planner",
        "title": "Планировщик дел 📅",
        "description": "Готовый промпт для управления задачами",
        "prompt": (
            "Ты — личный помощник по организации времени и задач.\n\n"
            "Помогаешь с:\n"
            "- Составлением списков дел\n"
            "- Планированием дня/недели\n"
            "- Напоминаниями и календарём\n"
            "- Организацией покупок и домашних дел\n\n"
            "Всегда учитываешь реальное время и возможности пользователя."
        ),
    },
    {
        "key": "support_partner",
        "title": "Собеседник для поддержки 🤝",
        "description": "Готовый промпт для эмоциональной поддержки",
        "prompt": (
            "Ты — внимательный собеседник, который всегда готов выслушать.\n\n"
            "Ты можешь:\n"
            "- Выслушать без осуждения\n"
            "- Помочь разобраться в мыслях\n"
            "- Поддержать в сложной ситуации\n"
            "- Помочь с ведением дневника\n\n"
            "Важно: ты НЕ психолог. При серьёзных проблемах советуешь обратиться к специалистам."
        ),
    },
    {
        "key": "custom",
        "title": "Свой промпт ✏️",
        "description": "Введите свой системный промпт вручную",
        "prompt": None,
    },
]


@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    data = {
        "telegramId": message.from_user.id,
        "username": message.from_user.username or "Unknown",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/user", json=data) as resp:
                await message.answer("Привет! Я готов общаться.")
    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка подключения к серверу: {e}")


async def fetch_chats(telegram_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/chats?telegramId={telegram_id}") as resp:
            resp.raise_for_status()
            return await resp.json()


async def delete_chat(chat_id: str):
    async with aiohttp.ClientSession() as session:
        url = f"{API_URL}/chats/{chat_id}"
        async with session.delete(url) as resp:
            resp.raise_for_status()
            return await resp.json()


async def edit_chat(chat_id: str, new_title: str):
    async with aiohttp.ClientSession() as session:
        url = f"{API_URL}/chats/{chat_id}"
        payload = {"id": chat_id, "title": new_title}
        async with session.patch(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


async def show_chats_menu(target, state: FSMContext, mode: str = None):
    data = await state.get_data()
    active_chat = data.get("active_chat")
    telegram_id = target.from_user.id

    try:
        chats = await fetch_chats(telegram_id)
    except Exception as e:
        await target.answer(f"Не удалось получить список чатов: {e}")
        return

    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        label = chat.get("title") or chat["id"][:8]

        if chat["id"] == active_chat:
            label += " ✅"
        if mode == "delete":
            label += " 🗑"
        elif mode == "edit":
            label += " ✏️"

        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"sel_{chat['id']}")]
        )

    if mode is None:
        rows.append(
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data="mode:edit"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data="mode:delete"),
            ]
        )
    else:
        rows.append(
            [InlineKeyboardButton(text="↩️ Отменить", callback_data="mode:cancel")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text_map = {
        None: "Выберите чат:",
        "delete": "Режим удаления. Выберите чат:",
        "edit": "Режим переименования. Выберите чат:",
    }
    text = text_map[mode]

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)

    await state.update_data(mode=mode)


@dp.message(Command(commands=["chats"]))
async def cmd_chats(message: types.Message, state: FSMContext):
    await show_chats_menu(message, state, mode=None)


@dp.callback_query(lambda c: c.data and c.data.startswith("mode:"))
async def cb_mode(query: types.CallbackQuery, state: FSMContext):
    mode = query.data.split(":", 1)[1]
    if mode == "cancel":
        await state.update_data(mode="none")
        await show_chats_menu(query, state, mode=None)
    else:
        await show_chats_menu(query, state, mode=mode)
    await query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("sel_"))
async def cb_selectchat(query: types.CallbackQuery, state: FSMContext):
    chat_id = query.data.split("_", 1)[1]
    data = await state.get_data()
    mode = data.get("mode")

    if mode == "delete":
        await delete_chat(chat_id)
        await query.answer("✅ Чат удалён")
        await show_chats_menu(query, state, mode="delete")

    elif mode == "edit":
        await state.update_data(edit_target=chat_id)
        await query.answer()
        await query.message.edit_text(
            "Напишите новое название чата или нажмите ↩️ Отменить"
        )

    else:
        await state.update_data(active_chat=chat_id)
        await query.answer(f"✅ Активный чат: {chat_id}")


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
    payload = {"telegramId": telegram_id, "defaultModelId": model_id}
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{API_URL}/user", json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


def build_keyboard(
    models: list[dict], selected_id: str | None, user_premium: bool
) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    for m in models:
        label = m["name"]
        if m.get("premium", False) and not user_premium:
            label = f"🔒 {label}"
            callback_data = "disabled"
        else:
            if str(m["id"]) == selected_id:
                label = f"✅ {label}"
            callback_data = f"model_select:{m['id']}"
        buttons.append(InlineKeyboardButton(text=label, callback_data=callback_data))

    info_btn = InlineKeyboardButton(
        text="ℹ️ Информация о моделях", callback_data="models_info"
    )
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([info_btn])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command(commands=["models"]))
async def on_models_command(message: types.Message):
    telegram_id = message.from_user.id
    models, user = await asyncio.gather(fetch_models(), fetch_user(telegram_id))

    current_model_id = str(user.get("defaultModelId", ""))

    kb = build_keyboard(
        models, selected_id=current_model_id, user_premium=user.get("premium", False)
    )

    await message.answer("Выберите модель:", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("model_select:"))
async def on_model_selected(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_id = callback.data.split(":", 1)[1]

    await patch_user_model(telegram_id, selected_id)
    models, user = await asyncio.gather(fetch_models(), fetch_user(telegram_id))
    selected_model = next((m for m in models if m.get("id") == selected_id), None)
    model_title = selected_model["name"]
    kb = build_keyboard(
        models, selected_id=selected_id, user_premium=user.get("premium", False)
    )
    chat_id = callback.message.chat.id
    await callback.message.edit_reply_markup(reply_markup=kb)
    sent = await callback.bot.send_message(
        chat_id=chat_id,
        text=f"📝{model_title}",
        parse_mode="Markdown"
    )
    try:
        await callback.bot.unpin_chat_message(chat_id=chat_id)  
    except Exception:
        print('bad')
    await callback.bot(PinChatMessage(chat_id=chat_id, message_id=sent.message_id))

    await callback.answer(text="✅ Модель обновлена", show_alert=False)


@dp.callback_query(lambda c: c.data == "models_info")
async def on_models_info(callback: CallbackQuery):
    models = await fetch_models()
    info_lines = [
        f"\n*{m['name']}* – {m.get('description', '_без описания_')}" for m in models
    ]
    info_text = "\n".join(info_lines)

    kb = callback.message.reply_markup

    new_text = f"ℹ️ *Список всех моделей:*\n\n{info_text}"
    await callback.message.edit_text(new_text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()


async def patch_user_info(dto: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.patch(f"{API_URL}/user", json=dto) as resp:
            resp.raise_for_status()
            return await resp.json()


async def show_roles_menu(target, state: FSMContext):
    user = await fetch_user(target.from_user.id)
    current_prompt = user.get("systemPrompt", "")
    matched_key = next(
        (r["key"] for r in ROLES if r["prompt"] and r["prompt"] == current_prompt),
        "custom",
    )
    description = next(r["description"] for r in ROLES if r["key"] == matched_key)
    header = f"*Текущий промпт:* {description}\n\n*Выберите роль:*"

    rows = []
    for r in ROLES:
        selected = " ✅" if r["key"] == matched_key else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{r['title']}{selected}", callback_data=f"role_sel:{r['key']}"
                )
            ]
        )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(header, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.answer(header, reply_markup=kb, parse_mode="Markdown")

    await state.update_data(mode=None)


@dp.message(Command(commands=["role"]))
async def cmd_role(message: types.Message, state: FSMContext):
    await show_roles_menu(message, state)


@dp.callback_query(lambda c: c.data and c.data.startswith("role_sel:"))
async def cb_role_select(query: types.CallbackQuery, state: FSMContext):
    key = query.data.split(":", 1)[1]
    role = next(r for r in ROLES if r["key"] == key)

    if key == "custom":
        await state.update_data(mode="role_custom")
        await query.message.edit_text(
            "Введите ваш системный промпт или нажмите /role для отмены"
        )
    else:
        await patch_user_info(
            {"telegramId": query.from_user.id, "systemPrompt": role["prompt"]}
        )
        await query.answer("✅ Системный промпт обновлён")
        await show_roles_menu(query, state)


@dp.message(lambda m: m.text is not None and not m.text.startswith("/"))
async def message_router(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode")
    edit_target = data.get("edit_target")

    if mode == "edit" and edit_target:
        new_title = message.text.strip()
        await edit_chat(edit_target, new_title)
        await message.answer(f"✅ Чат переименован в: {new_title}")
        await state.update_data(edit_target=None)
        await show_chats_menu(message, state, mode="edit")
        return

    if data.get("mode") == "role_custom":
        prompt = message.text.strip()
        await patch_user_info(
            {"telegramId": message.from_user.id, "systemPrompt": prompt}
        )
        await message.answer("✅ Ваш системный промпт сохранён")
        await show_roles_menu(message, state)
        return
    chat_id = data.get("active_chat")
    payload = {
        "telegramId": message.from_user.id,
        "prompt": message.text,
    }
    if chat_id:
        payload["chatId"] = chat_id

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{API_URL}/messages", json=payload) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    try:
                        err = await resp.json()
                        await message.answer(err.get("message", text))
                    except:
                        await message.answer(text)
                    return

                result = await resp.json()
                raw = result.get("content", "")
                if result.get("type") == "image":

                    photo = BufferedInputFile(base64.b64decode(raw), filename="gen.png")
                    await message.answer_photo(photo)
                else:
                    if isinstance(raw, (tuple, list)) and raw:
                        raw = raw[0]
                    safe_md = markdownify(raw)
                    await message.answer(safe_md, parse_mode=ParseMode.MARKDOWN_V2)
        except ClientError as e:
            await message.answer(f"Сетевая ошибка: {e}")


@dp.message(F.photo)
async def on_photo(message: types.Message):
    photo: types.PhotoSize = message.photo[-1]

    bio = BytesIO()
    await bot.download(photo.file_id, destination=bio)
    bio.seek(0)
    file_bytes = bio.read()

    user_text = message.caption or "Игнорируй этот текст, читай только что выше"

    b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "telegramId": message.from_user.id,
        "prompt": user_text,
        "image": b64,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/messages", json=payload) as resp:
                text = await resp.text()

                if resp.status >= 400:
                    try:
                        err = await resp.json()
                        err_msg = err.get("message", text)
                    except Exception:
                        err_msg = text
                    await message.reply(f"Ошибка: {err_msg}")
                    return

                data = await resp.json()
                await message.reply(data.get("content", ""), parse_mode="MarkdownV2")
    except aiohttp.ClientError as e:
        await message.reply(f"Сетевая ошибка: {e}")


@dp.message((F.document & ~F.document.mime_type.contains("image/")) | F.audio | F.voice)
async def handler_doc(message: types.message):
    is_forwarded = bool(
        message.forward_from or message.forward_from_chat or message.forward_sender_name
    )
    doc = message.document or message.audio or message.voice
    data = aiohttp.FormData()
    caption = message.caption or "Игнорируй этот текст,  читай только что выше"
    data.add_field("prompt", caption, content_type="text/plain")
    data.add_field("telegramId", str(message.from_user.id), content_type="text/plain")
    data.add_field("isForwarded", str(is_forwarded), content_type="text/plain")
    if not doc:
        return
    bio = BytesIO()
    await bot.download(doc.file_id, destination=bio)
    bio.seek(0)
    filename = getattr(doc, "file_name", f"{doc.file_id}.ogg")
    content_type = getattr(doc, "mime_type", None) or (
        "audio/ogg" if message.voice else "application/octet-stream"
    )
    data.add_field(
        "file",
        value=bio,
        filename=filename,
        content_type=content_type,
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/messages", data=data) as resp:
                text = await resp.text()

                if resp.status >= 400:
                    try:
                        err = await resp.json()
                        err_msg = err.get("message", text)
                    except Exception:
                        err_msg = text
                    await message.reply(f"Ошибка: {err_msg}")
                    return

                data = await resp.json()
                await message.reply(data.get("content", ""))
    except aiohttp.ClientError as e:
        await message.reply(f"Сетевая ошибка: {e}")


async def main():
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())
