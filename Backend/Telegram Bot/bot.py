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

bot = Bot(token=TOKEN)
dp = Dispatcher()

ROLES = [
    {
        "key": "search_explainer",
        "title": "Умный поисковик 🔍",
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
                await message.answer("Привет! Я готов общаться.", parse_mode=None)
                resp.raise_for_status()
                user_info = await resp.json()
                chat_id = message.chat.id
                user_model = user_info["defaultModelId"]
                message_to_pin = await message.bot.send_message(
                    chat_id=chat_id, text=f"📝{user_model}"
                )
                await bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=message_to_pin.message_id,
                    disable_notification=True,
                )
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
        await target.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await target.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

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
    telegram_id = query.from_user.id

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
        try:
            chats = await fetch_chats(telegram_id)
        except Exception as e:
            await query.answer(
                f"Не удалось получить список чатов: {e}", show_alert=True
            )
            return

        selected = next((c for c in chats if c["id"] == chat_id), None)
        chat_title = (
            selected.get("title") if selected and selected.get("title") else chat_id[:8]
        )

        chat: types.Chat = await bot.get_chat(query.message.chat.id)
        pinned: types.Message | None = chat.pinned_message

        # if not pinned:
        #    return await query.message.reply("В чате нет закреплённого сообщения.")

        original = pinned.text or pinned.caption or ""
        if "|" not in original:
            new_text = f"{original} | 💭{chat_title}"

            try:
                await bot.edit_message_text(
                    text=new_text,
                    chat_id=query.message.chat.id,
                    message_id=pinned.message_id,
                )
                return
            except Exception as e:
                return 'bad'
        else:
            base = original.split("|", 1)[0]
            new_text = f"{base}| 💭{chat_title}"

            try:
                await bot.edit_message_text(
                    text=new_text,
                    chat_id=query.message.chat.id,
                    message_id=pinned.message_id,
                )
            except Exception as e:
                return print(e)

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


def is_user_premium(user: dict) -> bool:
    subscription = user.get("subscription")
    if not subscription:
        return False
    status = subscription.get("status")
    if status != "ACTIVE":
        return False
    else:
        return True

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
        models, selected_id=current_model_id, user_premium=is_user_premium(user)
    )

    await message.answer("Выберите модель:", reply_markup=kb)
async def fetch_shortcuts(telegram_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/shortcuts?telegramId={telegram_id}") as resp:
            resp.raise_for_status()
            return await resp.json()

@dp.message(Command(commands=["shortcuts"]))
async def shortcuts_command(message: types.Message, state: FSMContext):
    try:
        user_shortcuts = await fetch_shortcuts(message.from_user.id)
    except Exception as e:
        await message.answer(f"Не удалось получить список шорткатов: {e}")
        return
    data = await state.get_data()
    shortcut_mode = data.get("shortcut_mode")
    rows: list[list[InlineKeyboardButton]] = []
    for shortcut in user_shortcuts:
        label = shortcut.get("command") or shortcut["id"][:8]

        if shortcut_mode == "delete":
            label += " 🗑"
        elif shortcut_mode == "edit":
            label += " ✏️"

        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"shortcut_sel:{shortcut["id"]}")]
        )

    #if shortcut_mode is None:
    #    rows.append(
    #        [
    #            InlineKeyboardButton(text="✏️ Редактировать", callback_data="shortcut_mode:edit"),
    #            InlineKeyboardButton(text="🗑 Удалить", callback_data="shortcut_mode:delete"),
    #        ]
    #    )
    #else:
    #    rows.append(
    #        [InlineKeyboardButton(text="↩️ Отменить", callback_data="shortcut_mode:cancel")]
    #    )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text_map = {
        None: "Выберите шорткат:",
        "delete": "Режим удаления. Выберите шорткат:",
        "edit": "Режим переименования. Выберите шорткат:",
    }
    text = text_map[shortcut_mode]

    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    await state.update_data(shortcut_mode='edit')

@dp.callback_query(lambda c: c.data and c.data.startswith("model_select:"))
async def on_model_selected(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    selected_id = callback.data.split(":", 1)[1]

    await patch_user_model(telegram_id, selected_id)
    models, user = await asyncio.gather(fetch_models(), fetch_user(telegram_id))
    selected_model = next((m for m in models if m.get("id") == selected_id), None)
    model_title = selected_model["name"]
    kb = build_keyboard(
        models, selected_id=selected_id, user_premium=is_user_premium(user)
    )
    chat_id = callback.message.chat.id
    await callback.message.edit_reply_markup(reply_markup=kb)
    chat = await bot.get_chat(chat_id)
    pinned = chat.pinned_message
    original = pinned.text or pinned.caption or ""
    if not pinned:
        message_to_pin = await callback.bot.send_message(
            chat_id=chat_id, text=f"📝{model_title}"
        )
        await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_to_pin.message_id,
            disable_notification=True,
        )
    else:
        base = original.split("|", 1)[1]
        await bot.edit_message_text(
            text=f"📝{model_title} |{base}",
            chat_id=callback.message.chat.id,
            message_id=pinned.message_id,
        )
    await callback.answer(text="✅ Модель обновлена", show_alert=False)


ORIGINAL_TEXT = "Выберите модель:"


def toggle_button(markup: InlineKeyboardMarkup, show: bool) -> InlineKeyboardMarkup:
    rows = [row[:] for row in markup.inline_keyboard]
    rows = [
        r
        for r in rows
        if not any(b.callback_data in ("models_info", "models_hide") for b in r)
    ]
    text = "Скрыть модели" if show else "ℹ️ Показать модели"
    data = "models_hide" if show else "models_info"
    rows.append([InlineKeyboardButton(text=text, callback_data=data)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(lambda c: c.data in ("models_info", "models_hide"))
async def on_models_toggle(callback: CallbackQuery):
    kb_old = callback.message.reply_markup
    if callback.data == "models_info":
        models = await fetch_models()
        info_lines = [
            f"*{m['name']}* – {m.get('description', '_без описания_')}\n"
            for m in models
        ]
        new_text = f"ℹ️ *Список всех моделей:*\n\n" + "\n".join(info_lines)
        kb_new = toggle_button(kb_old, show=True)
    else:
        new_text = ORIGINAL_TEXT
        kb_new = toggle_button(kb_old, show=False)

    await callback.message.edit_text(
        new_text, parse_mode="Markdown", reply_markup=kb_new
    )
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
    role = next(r for r in ROLES if r["key"] == matched_key)
    if role["key"] == "custom":
        header = f"*Текущий промпт:* {role['title']} \n\n{current_prompt} \n\n*Выберите роль:*"
    else:
        header = f"*Текущий промпт:* {role['title']} \n\n  {role['prompt']} \n\n*Выберите роль:*"

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
            "Введите ваш системный промпт или напишите /role для отмены"
        )
    else:
        await patch_user_info(
            {"telegramId": query.from_user.id, "systemPrompt": role["prompt"]}
        )
        await query.answer("✅ Системный промпт обновлён")
        await show_roles_menu(query, state)

import re

def extract_and_strip_think(text: str) -> tuple[str, str]:
    think_blocks = re.findall(r"<think\b[^>]*>([\s\S]*?)</think\s*>", text, flags=re.IGNORECASE)
    think_text = ("\n\n".join(tb.strip() for tb in think_blocks)).strip()
    visible_text = re.sub(r"<think\b[^>]*>[\s\S]*?</think\s*>", "", text, flags=re.IGNORECASE).strip()
    return visible_text, think_text

def is_blank_simple(s: str) -> bool:
    if s is None:
        return True
    s = str(s)
    cleaned = re.sub(r'[\s\u00A0\u200B\u200C\u200D\u200E\u200F\uFEFF]+', '', s)
    return cleaned == ''

def escape_markdown_v2(text: str) -> str:
    if text is None:
        return ''
    text = text.replace('\\', r'\\')
    return re.sub(r'([_\*\[\]\(\)~`>#+\-=|{}.!])', r'\\\\\1', text)
forbidden_commands = {"/chats","/models","/role","/start", "/pro","/suppport","/shortcuts"}
@dp.message(lambda m: m.text is not None and m.text not in forbidden_commands)
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
    if data.get("is_locked") == True:
        await message.answer("Дождитесь пожалуйста ответа модели")
        return
    await state.update_data(is_locked=True)
    target = await message.answer(
        "Нейросеть думает🤔", parse_mode=ParseMode.MARKDOWN_V2
    )
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
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

                try:
                    result = await resp.json()
                    response_chat_id = result.get("chatId","0")
                    await state.update_data(active_chat=response_chat_id)
                    raw = result.get("content", "")

                    if isinstance(raw, (tuple, list)):
                        raw = raw[0] if raw else "" 
                    if not isinstance(raw, str):
                        raw = str(raw) or "" 

                    if result.get("type") == "image":
                        photo = BufferedInputFile(base64.b64decode(raw), filename="gen.png")
                        await message.answer_photo(photo)
                    else:
                        raw_visible, think_text = extract_and_strip_think(raw)
                        clean = markdownify(raw_visible)

                        if not is_blank_simple(think_text):
                            try:
                                final_text = make_final_text_by_truncating_hidden(clean, think_text, max_len=4096)
                            except ValueError:
                                final_text = clean[:4096]

                            kb = toggle_think_buttons(InlineKeyboardMarkup(inline_keyboard=[]), show=False)
                            await target.delete()
                            await message.reply(final_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
                        else:
                            final_text = clean
                            await target.delete()
                            await message.reply(final_text, parse_mode=ParseMode.MARKDOWN_V2)
                except Exception as e:
                    await target.delete()
                    await message.answer(f"Ошибка обработки ответа: {e}. Попробуйте позже.")
        except ClientError as e:
            await target.delete()
            await message.answer(f"Сетевая ошибка: {e}")
        finally:
            await state.update_data(is_locked=False)



import zlib
import base64
import html
import json
import binascii

_ZW_MARKER = "\u2063\u2063\u2063"  
_ZW_ZERO = "\u200B"  
_ZW_ONE = "\u200C"   

def _pack_bytes_to_zw(data: bytes) -> str:
    comp = zlib.compress(data, level=6)
    crc = binascii.crc32(data).to_bytes(4, "big")
    full = crc + comp
    b85 = base64.b85encode(full)
    bits = "".join(f"{byte:08b}" for byte in b85)
    return "".join(_ZW_ZERO if b == "0" else _ZW_ONE for b in bits)

def _unpack_zw_to_bytes(s: str) -> bytes | None:
    filtered = "".join(ch for ch in s if ch in (_ZW_ZERO, _ZW_ONE))
    if not filtered:
        return None
    bits = "".join("0" if ch == _ZW_ZERO else "1" for ch in filtered)
    if len(bits) % 8 != 0:
        return None
    byte_arr = bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))
    try:
        raw = base64.b85decode(byte_arr)
        crc_recv = raw[:4]
        comp = raw[4:]
        data = zlib.decompress(comp)
        if crc_recv != binascii.crc32(data).to_bytes(4, "big"):
            return None
        return data
    except Exception:
        return None

def _embed_hidden(visible_text: str, hidden_bytes: bytes) -> str:
    return visible_text + _ZW_MARKER + _pack_bytes_to_zw(hidden_bytes)

def _extract_hidden(full_text: str):
    if _ZW_MARKER not in full_text:
        return full_text, None
    visible, zw_part = full_text.split(_ZW_MARKER, 1)
    return visible, zw_part

def _make_hidden_payload(clean_text: str, think_text: str) -> bytes:
    obj = {"clean": clean_text, "think": think_text}
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")

def toggle_think_buttons(kb: InlineKeyboardMarkup, show: bool) -> InlineKeyboardMarkup:
    kb.inline_keyboard = [[
        InlineKeyboardButton(text="Скрыть размышления модели 💡" if show else "Показать размышления модели 💡", callback_data="think_hide" if show else "think_info")
    ]]
    return kb

@dp.callback_query(lambda c: c.data in ("think_info", "think_hide"))
async def on_think_toggle(callback: CallbackQuery):
    msg = callback.message
    if not msg or not msg.text:
        await callback.answer("Нет текста сообщения.", show_alert=True)
        return

    visible, zw_part = _extract_hidden(msg.text)
    hidden_obj = None
    raw_bytes = _unpack_zw_to_bytes(zw_part) if zw_part else None
    if raw_bytes:
        try:
            hidden_obj = json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            hidden_obj = None

    if callback.data == "think_info":
        if not hidden_obj:
            await callback.answer("Размышления не найдены или повреждены.", show_alert=True)
            return
        clean = hidden_obj.get("clean", visible) or ""
        think = hidden_obj.get("think", "") or ""
        new_text = f"{clean}\n\n💡 Размышления модели:\n{think}"
        try:
            new_text_with_hidden = make_final_text_by_truncating_hidden(new_text, think, max_len=4096)
        except ValueError:
            new_text_with_hidden = new_text[:4096]
        kb_new = toggle_think_buttons(msg.reply_markup or InlineKeyboardMarkup(), show=True)
        await msg.edit_text(new_text_with_hidden, reply_markup=kb_new)
        await callback.answer()
    else:
        clean = (hidden_obj.get("clean", "") if hidden_obj else visible) or ""
        think_part = hidden_obj.get("think", "") if hidden_obj else ""
        try:
            new_text_with_hidden = make_final_text_by_truncating_hidden(clean, think_part, max_len=4096)
        except ValueError:
            new_text_with_hidden = clean[:4096]
        kb_new = toggle_think_buttons(msg.reply_markup or InlineKeyboardMarkup(), show=False)
        await msg.edit_text(new_text_with_hidden, reply_markup=kb_new)
        await callback.answer()

def make_final_text_by_truncating_hidden(visible_text: str, think_text: str, max_len: int = 4096) -> str:

    marker = _ZW_MARKER
    space_for_zw = max_len - len(visible_text) - len(marker)
    if space_for_zw <= 0:
        raise ValueError("Нет места для невидимого блока.")

    whole_bytes = _make_hidden_payload(visible_text, think_text)
    whole_zw = _pack_bytes_to_zw(whole_bytes)
    if len(whole_zw) <= space_for_zw:
        return visible_text + marker + whole_zw

    s = think_text or ""
    lo, hi = 0, len(s)
    best_zw = None
    while lo <= hi:
        mid = (lo + hi) // 2
        cand_think = s[:mid]
        cand_bytes = _make_hidden_payload(visible_text, cand_think)
        try:
            cand_zw = _pack_bytes_to_zw(cand_bytes)
        except Exception:
            cand_zw = None

        if cand_zw is not None and len(cand_zw) <= space_for_zw:
            best_zw = cand_zw
            lo = mid + 1
        else:
            hi = mid - 1

    if best_zw is not None:
        return visible_text + marker + best_zw

    empty_bytes = _make_hidden_payload(visible_text, "")
    empty_zw = _pack_bytes_to_zw(empty_bytes)
    if len(empty_zw) <= space_for_zw:
        return visible_text + marker + empty_zw

    raise ValueError("Hidden payload too large even after truncation.")


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


from aiogram.utils.keyboard import InlineKeyboardBuilder


def payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить 1 ⭐️", pay=True)

    return builder.as_markup()


from aiogram.types import LabeledPrice, Message


async def send_invoice_handler(message: Message):
    prices = [LabeledPrice(label="XTR", amount=1)]
    await message.answer_invoice(
        title="Поддержка канала",
        description="Поддержать канал на 1 звёзд!",
        prices=prices,
        provider_token="",
        payload="channel_support",
        currency="XTR",
        reply_markup=payment_keyboard(),
    )


from aiogram.types import PreCheckoutQuery


async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


async def success_payment_handler(message: Message):
    payment = message.successful_payment

    telegram_charge_id = payment.telegram_payment_charge_id
    provider_charge_id = payment.provider_payment_charge_id

    user = await fetch_user(message.from_user.id)
    payment_info = {
        "userId": user.get("id", ""),
        "telegramPaymentId": telegram_charge_id,
        "providerPaymentId": provider_charge_id,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/subscriptions", json=payment_info
            ) as resp:
                resp.raise_for_status()
                await message.answer(
                    text="🥳Спасибо за вашу поддержку!🤗", parse_mode=None
                )
    except Exception as e:
        safe_error = str(e).replace("=", "\\=").replace("_", "\\_")
        await message.answer(
            text=f"❗ Проблема при оплате: `{safe_error}`\nОбратитесь в поддержку: /paysupport",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def pay_support_handler(message: Message):
    await message.answer(
        text="Добровольные пожертвования не подразумевают возврат средств, "
        "однако, если вы очень хотите вернуть средства - свяжитесь с нами."
    )


dp.message.register(send_invoice_handler, Command(commands="pro"))
dp.pre_checkout_query.register(pre_checkout_handler)
dp.message.register(success_payment_handler, F.successful_payment)
dp.message.register(pay_support_handler, Command(commands="paysupport"))


async def main():
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    asyncio.run(main())
