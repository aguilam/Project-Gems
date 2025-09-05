from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
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
from aiogram.enums import ParseMode

from dotenv import load_dotenv
from telegramify_markdown import markdownify
import re
import uuid
from aiogram.types import (
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import zlib
import base64
import html
import json
import binascii
from datetime import datetime
import time

from aiohttp import web
import logging
from typing import Optional, Any

import logging

logging.basicConfig(level=logging.DEBUG)
import sentry_sdk

_RETRIES = 3
_BACKOFF_BASE = 0.5
_TIMEOUT_SECONDS = 15


async def handle_root(request):
    return web.json_response({"status": "ok"})


async def handle_healthz(request):
    return web.json_response({"status": "healthy"})


async def _start_health_server(port: int) -> web.AppRunner:
    app = web.Application()
    app.add_routes([web.get("/", handle_root), web.get("/healthz", handle_healthz)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    return runner


async def change_pin(chat_id, model_title, chat_name, bot):
    try:
        chat: types.Chat = await bot.get_chat(chat_id)
        pinned: types.Message | None = getattr(chat, "pinned_message", None)
    except Exception as e:
        logging.warning("Не удалось получить чат/закреплённое сообщение: %s", e)
        pinned = None
    original = ""
    if pinned:
        original = (
            getattr(pinned, "text", None) or getattr(pinned, "caption", None) or ""
        ).strip()
    if not pinned:
        if model_title is not None:
            message_to_pin = await bot.send_message(
                chat_id=chat_id, text=f"📝{model_title}"
            )
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message_to_pin.message_id,
                disable_notification=True,
            )
        elif chat_name is not None:
            message_to_pin = await bot.send_message(
                chat_id=chat_id, text=f"💭{chat_name}"
            )
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message_to_pin.message_id,
                disable_notification=True,
            )
    else:
        if "|" in original:
            if chat_name is not None:
                first_part = original.split("|", 1)[0].strip()
                try:
                    await bot.edit_message_text(
                        text=f"{first_part} | 💭{chat_name}",
                        chat_id=chat_id,
                        message_id=pinned.message_id,
                    )
                    return
                except Exception:
                    return "bad"
            elif model_title is not None:
                first_part = original.split("|", 1)[1].strip()
                await bot.edit_message_text(
                    text=f"📝{model_title} | {first_part}",
                    chat_id=chat_id,
                    message_id=pinned.message_id,
                )
        elif "|" not in original:
            if chat_name is not None:
                try:
                    await bot.edit_message_text(
                        text=f"{original} | 💭{chat_name}",
                        chat_id=chat_id,
                        message_id=pinned.message_id,
                    )
                    return
                except Exception:
                    return "bad"
            elif model_title is not None:
                try:
                    await bot.edit_message_text(
                        text=f"📝{model_title} | {original}",
                        chat_id=chat_id,
                        message_id=pinned.message_id,
                    )
                    return
                except Exception:
                    return "bad"


async def _shutdown_health_server(runner: web.AppRunner):
    try:
        await runner.cleanup()
    except Exception:
        pass


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
                await message.answer(
                    "Привет! Вот основные команды: \n\n /profile — информация о профиле и оставшихся вопросах \n /models — переключиться на другую ИИ-модель \n /role — сменить роль (системный промпт) для ИИ \n /chats — открыть другой чат или создать новый \n /shortcuts — создать или редактировать шорткат \n /support — сообщить об ошибке, баге или предложении \n /pro - не хватает текущих возможностей и моделей? Попробуйте pro подписку \n\n <b>Чтобы начать — просто напишите ваш запрос!</b>",
                    parse_mode=ParseMode.HTML,
                )
                resp.raise_for_status()
                response = await resp.json()
                chat_id = message.chat.id
                user = response["user"]
                user_model = user["defaultModel"]
                model_name = user_model["name"]
                user_existing = response["existing"]
                await change_pin(chat_id, model_name, None, message.bot)
                if user_existing == False:
                    await message.bot.send_message(
                        chat_id=chat_id,
                        text=f"Как новому пользователю мы предлагаем вам 14 дневный пробный  pro период.",
                        reply_markup=trial_invoice_keyboard(),
                    )
                return

    except aiohttp.ClientError as e:
        await message.answer(f"Ошибка подключения к серверу: {e}")
        return


def trial_invoice_keyboard():
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="Активировать пробную подписку", callback_data="activate_trial"
            )
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


@dp.message(Command(commands=["trial"]))
async def cmd_trial(msg: types.message):
    await msg.answer(
        "Нажми кнопку, чтобы активировать пробную подписку:",
        reply_markup=trial_invoice_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "activate_trial")
async def on_activate_trial(query: CallbackQuery):
    await query.answer(text="Активирую...", show_alert=False)
    await success_trial_handler(query.from_user.id, query.message.chat.id)


async def success_trial_handler(user_telegram_id: int, chat_id: int):
    user = await fetch_user(user_telegram_id)
    backend_user_id = (user or {}).get("id")
    if not backend_user_id:
        await bot.send_message(
            chat_id=chat_id,
            text="❗ Не удалось определить пользователя. Нажмите /start и попробуйте снова.",
        )
        return
    payment_info = {"userId": backend_user_id}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/subscriptions/trial", json=payment_info
            ) as resp:
                resp.raise_for_status()
        await bot.send_message(
            chat_id=chat_id,
            text="🥳 Спасибо! Подписка оформлена — вы получили доступ к Pro.",
        )
    except Exception as e:
        safe_error = str(e).replace("=", "\\=").replace("_", "\\_")
        await bot.send_message(
            chat_id=chat_id,
            text=f"❗ Проблема при записи подписки: `{safe_error}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def fetch_chats(telegram_id: int, chat_page: int) -> list:
    url = f"{API_URL}/chats?telegramId={telegram_id}&page={chat_page}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    logging.info("fetch_chats GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "fetch_chats HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return []
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_chats network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_chats failed after retries: %s", url)
    return []


async def fetch_chat(telegram_id: int, chat_id: int) -> list:
    url = f"{API_URL}/chats/{chat_id}?telegramId={telegram_id}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    logging.info("fetch_chats GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "fetch_chats HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return []
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_chats network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_chats failed after retries: %s", url)
    return []


async def delete_chat(chat_id: str) -> dict | None:
    url = f"{API_URL}/chats/{chat_id}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.delete(url) as resp:
                    logging.info("delete_chat DELETE %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "delete_chat HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "delete_chat network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("delete_chat failed after retries: %s", url)
    return None


async def edit_chat(chat_id: str, new_title: str) -> dict | None:
    url = f"{API_URL}/chats/{chat_id}"
    payload = {"id": chat_id, "title": new_title}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.patch(url, json=payload) as resp:
                    logging.info("edit_chat PATCH %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "edit_chat HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "edit_chat network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("edit_chat failed after retries: %s", url)
    return None


PROVIDER_TOKEN = ""
CURRENCY = "XTR"
PRICE_PRO_UNITS = 500
PRICE_GO_UNITS = 350


def offer_keyboard():
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([
        types.InlineKeyboardButton(text="Оформить GO подписку", callback_data="buy_go"),
        types.InlineKeyboardButton(text="Оформить PRO подписку", callback_data="buy_pro"),
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb

def invoice_pro_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить 500 ⭐️", pay=True)
    return kb.as_markup()

def invoice_go_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Оплатить 350 ⭐️", pay=True)
    return kb.as_markup()
@dp.callback_query(lambda c: c.data == "buy_pro")
async def callback_buy_pro(callback: CallbackQuery):
    if callback.data != "buy_pro":
        return

    await callback.answer()

    try:
        await callback.message.edit_text(
            callback.message.text + "\n\nПереходим к оплате…"
        )
    except Exception:
        pass

    order_id = str(uuid.uuid4())
    payload = json.dumps({
        "order_id": order_id,
        "plan": "PRO",
    }, ensure_ascii=False)
    amount_smallest = int(PRICE_PRO_UNITS)
    prices = [LabeledPrice(label="Pro подписка", amount=amount_smallest)]

    short_description = (
        "Pro подписка — 1000 обычных + 120 премиум вопросов и огромное множество дополнительных функций, которые выведут взаимодействие с ботом на новый уровень."
    )

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Pro подписка",
        description=short_description,
        payload=payload,
        provider_token="",  
        currency=CURRENCY,
        prices=prices,
        reply_markup=invoice_pro_keyboard(),
    )


@dp.callback_query(lambda c: c.data == "buy_go")
async def callback_buy_go(callback: CallbackQuery):
    if callback.data != "buy_go":
        return

    await callback.answer()

    try:
        await callback.message.edit_text(
            callback.message.text + "\n\nПереходим к оплате…"
        )
    except Exception:
        pass

    order_id = str(uuid.uuid4())
    payload = json.dumps({
        "order_id": order_id,
        "plan": "GO",
    }, ensure_ascii=False)
    amount_smallest = int(PRICE_GO_UNITS)
    prices = [LabeledPrice(label="Go подписка", amount=amount_smallest)]

    short_description = (
        "Go подписка — 1000 обычных + 120 премиум вопросов и много много чего ещё."
    )

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Go подписка",
        description=short_description,
        payload=payload,
        provider_token="",
        currency=CURRENCY,
        prices=prices,
        reply_markup=invoice_go_keyboard(),
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def success_payment_handler(message: types.message):
    payment = message.successful_payment
    invoice_payload_raw = payment.invoice_payload or ""
    try:
        order_payload = json.loads(invoice_payload_raw) if invoice_payload_raw else {}
    except Exception:
        order_payload = {"raw_payload": invoice_payload_raw}
    user = await fetch_user(message.from_user.id)
    payment_info = {
        "userId": user.get("id", ""),
        "telegramPaymentId": payment.telegram_payment_charge_id,
        "providerPaymentId": payment.provider_payment_charge_id,
        "orderPayload": order_payload,
        "plan": order_payload.get("plan") if isinstance(order_payload, dict) else None
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/subscriptions", json=payment_info
            ) as resp:
                resp.raise_for_status()
        await message.answer(
            "🥳 Спасибо! Подписка оформлена — вы получили доступ к морю возможностей."
        )
    except Exception as e:
        safe_error = str(e).replace("=", "\\=").replace("_", "\\_")
        await message.answer(
            text=f"❗ Проблема при записи подписки: `{safe_error}`",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


@dp.message(Command(commands=["pro", "premium", "go"]))
async def send_offer(message: types.message):
    text = (
        "⭐ Go — для тех, кто хочет работать быстрее и умнее\n\n"
        "Что вы получаете:\n"
        "• 1000 обычных и 120 премиум-вопросов — задавайте больше и сложнее\n"
        "• Доступ к премиум-моделям генерации текста и изображений — лучшие результаты без лишних усилий\n"
        "• Ускорение Llama в 3 раза — экономия времени при обработке запросов\n\n"
        "✨ Pro — для продвинутых задач и автоматизации:\n"
        "• Всё из Go, плюс расширенные возможности LLM\n"
        "• Доступ к интернет-поиску — модель использует свежую информацию из сети\n"
        "• Улучшенная память между чатами — важные детали сохраняются и используются в будущем\n"
        "• Выполнение кода в Python-окружении — автоматизация, проверки сценариев, запуск агентов\n"
        "• WolframAlpha — точные вычисления, графики и научные расчёты\n"
        "• Новые функции в приоритете для подписчиков\n\n"
        "Выберите план и нажмите кнопку, чтобы активировать доступ и начать пользоваться всеми преимуществами."
    )
    await message.answer(text=text, reply_markup=offer_keyboard())


async def show_chats_menu(target, state: FSMContext, mode: str = None):
    data = await state.get_data()
    active_chat = data.get("active_chat")
    chat_page = data.get("chat_page") or 1
    telegram_id = target.from_user.id

    try:
        chats_response = await fetch_chats(telegram_id, chat_page)
        chats = chats_response["chats"]
        pages_count = chats_response["pagesCount"]
    except Exception as e:
        await target.answer(f"Не удалось получить список чатов: {e}")
        return

    rows: list[list[InlineKeyboardButton]] = []
    if chat_page >= 2 and pages_count > chat_page:
        rows.append(
            [
                InlineKeyboardButton(text="⬅️", callback_data="chat:prev"),
                InlineKeyboardButton(
                    text=f"{chat_page} / {pages_count}", callback_data="de"
                ),
                InlineKeyboardButton(text="➡️", callback_data="chat:next"),
            ]
        )
    elif pages_count <= chat_page and chat_page != 1:
        rows.append(
            [
                InlineKeyboardButton(text="⬅️", callback_data="chat:prev"),
                InlineKeyboardButton(
                    text=f"{chat_page} / {pages_count}", callback_data="de"
                ),
            ]
        )
    elif chat_page <= 1 and pages_count != 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{chat_page} / {pages_count}", callback_data="de"
                ),
                InlineKeyboardButton(text="➡️", callback_data="chat:next"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Новый чат", callback_data="mode:new")])

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
    await state.update_data(chat_page=1)
    await show_chats_menu(message, state, mode=None)


@dp.callback_query(lambda c: c.data and c.data.startswith("mode:"))
async def cb_mode(query: types.CallbackQuery, state: FSMContext):
    mode = query.data.split(":", 1)[1]
    if mode == "cancel":
        await state.update_data(mode="none")
        await show_chats_menu(query, state, mode=None)
    if mode == "new":
        await state.update_data(mode="none")
        await state.update_data(active_chat="0")
        await query.message.answer(
            text="Введите своё первое сообщение для начала нового чата:"
        )
    else:
        await show_chats_menu(query, state, mode=mode)
    await query.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("chat:"))
async def cb_mode(query: types.CallbackQuery, state: FSMContext):
    mode = query.data.split(":", 1)[1]
    data = await state.get_data()
    chat_page = data.get("chat_page")
    if mode == "prev":
        await state.update_data(chat_page=chat_page - 1)
        await show_chats_menu(query, state, mode=None)
    if mode == "next":
        await state.update_data(chat_page=chat_page + 1)
        await show_chats_menu(query, state, mode=None)
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
            selected = await fetch_chat(telegram_id, chat_id)
        except Exception as e:
            await query.answer(
                f"Не удалось получить список чатов: {e}", show_alert=True
            )
            return
        chat_title = (
            selected.get("title") if selected and selected.get("title") else chat_id[:8]
        )

        await state.update_data(active_chat=chat_id)
        await show_chats_menu(query, state, mode=None)
        await change_pin(query.message.chat.id, None, chat_title, query.message.bot)
        await query.answer(f"✅ Активный чат: {chat_title}")


async def fetch_models() -> list:
    url = f"{API_URL}/models"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    logging.info("fetch_models GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "fetch_models HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return []
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_models network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_models failed after retries: %s", url)
    return []


async def fetch_user(telegram_id: int) -> dict | None:
    url = f"{API_URL}/user/{telegram_id}"
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    logging.info("fetch_user GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientResponseError as e:
                logging.warning(
                    "fetch_user HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    getattr(e, "status", e),
                )
                if 500 <= getattr(e, "status", 500) < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_user network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_user failed after retries: %s", url)
    return None


async def patch_user_model(telegram_id: int, model_id: str) -> Optional[dict]:
    url = f"{API_URL}/user"
    payload = {"telegramId": telegram_id, "defaultModelId": model_id}
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.patch(url, json=payload) as resp:
                    logging.info("patch_user_model PATCH %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "patch_user_model HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    status,
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "patch_user_model network/timeout %s (attempt %d): %s",
                    url,
                    attempt,
                    e,
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("patch_user_model failed after retries: %s", url)
    return None


def is_user_premium(user: dict) -> bool:
    subscriptions = user.get("subscription", [])
    if not subscriptions:
        return False
    active_subscription = next(
        (sub for sub in subscriptions if sub.get("status") == "ACTIVE"), None
    )
    return active_subscription is not None


def build_keyboard(
    models: list[dict], selected_id: str | None, user_premium: bool
) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    for m in models:

        model_name = m["name"]
        icons = ""
        callback_data = f"model_select:{m['id']}"
        if m.get("premium", False) and not user_premium:
            icons = f"🔒{icons}"
            callback_data = "disabled"
        if str(m["id"]) == selected_id:
            icons = f"✅{icons}"
            callback_data = "disabled"
        if "reasoning" in m["tags"]:
            icons = f"🧠{icons}"
        if "image" in m["tags"]:
            icons = f"🖼️{icons}"
        if m["premium"] == True:
            icons = f"⭐ {icons}"
        label = f"{icons} {model_name}"
        buttons.append(InlineKeyboardButton(text=label, callback_data=callback_data))

    info_btn = InlineKeyboardButton(
        text="ℹ️ Информация о моделях", callback_data="models_info"
    )
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([info_btn])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command(commands=["models", "model"]))
async def on_models_command(message: types.Message):
    telegram_id = message.from_user.id
    models, user = await asyncio.gather(fetch_models(), fetch_user(telegram_id))

    current_model_id = str(user.get("defaultModelId", ""))

    kb = build_keyboard(
        models, selected_id=current_model_id, user_premium=is_user_premium(user)
    )

    await message.answer("Выберите модель:", reply_markup=kb)


async def fetch_user_shortcuts(telegram_id: int) -> list:
    url = f"{API_URL}/shortcuts?telegramId={telegram_id}"
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    text = await resp.text()
                    logging.info("fetch_user_shortcuts GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return []
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "fetch_user_shortcuts HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    status,
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return []
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_user_shortcuts network/timeout %s (attempt %d): %s",
                    url,
                    attempt,
                    e,
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_user_shortcuts failed after retries: %s", url)
    return []


async def add_shortcuts(data: dict) -> Optional[dict]:
    url = f"{API_URL}/shortcuts"
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.post(url, json=data) as resp:
                    text = await resp.text()
                    logging.info("add_shortcuts POST %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "add_shortcuts HTTP error %s (attempt %d): %s", url, attempt, status
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "add_shortcuts network/timeout %s (attempt %d): %s", url, attempt, e
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("add_shortcuts failed after retries: %s", url)
    return None


async def delete_shortcuts(id: int) -> Optional[dict]:
    url = f"{API_URL}/shortcuts/{id}"
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.delete(url) as resp:
                    logging.info("delete_shortcuts DELETE %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "delete_shortcuts HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    status,
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "delete_shortcuts network/timeout %s (attempt %d): %s",
                    url,
                    attempt,
                    e,
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("delete_shortcuts failed after retries: %s", url)
    return None


async def patch_shortcuts(id: str, payload: dict | None = None) -> Optional[dict]:
    url = f"{API_URL}/shortcuts/{id}"
    body = {"id": id, **(payload or {})}
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.patch(url, json=body) as resp:
                    logging.info("patch_shortcuts PATCH %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "patch_shortcuts HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    status,
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "patch_shortcuts network/timeout %s (attempt %d): %s",
                    url,
                    attempt,
                    e,
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("patch_shortcuts failed after retries: %s", url)
    return None


@dp.message(Command(commands=["shortcuts"]))
async def shortcuts_command(message: types.Message, state: FSMContext):
    try:
        user_shortcuts = await fetch_user_shortcuts(message.from_user.id)
    except Exception as e:
        await message.answer(f"Не удалось получить список шорткатов: {e}")
        return

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="➕ Создать новый шорткат", callback_data="shortcut-create"
            )
        ],
    ]
    for shortcut in user_shortcuts:
        label = shortcut.get("command") or shortcut["id"][:8]
        id = shortcut.get("id")

        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"shortcut-sel_{id}")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text = "<b>Шорткаты — это быстрые шаблоны, чтобы не вводить одно и то же по сто раз.</b> \n\nПри использовании шортката его инструкция автоматически добавится в начало вашего запроса, а ответ придёт от выбранной вами модели. \n\nВыберите или создайте шорткат и ускорьте работу."

    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def fetch_shortcut(id: int) -> Optional[dict]:
    url = f"{API_URL}/shortcuts/{id}"
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, _RETRIES + 1):
            try:
                async with session.get(url) as resp:
                    logging.info("fetch_shortcut GET %s -> %s", url, resp.status)
                    resp.raise_for_status()
                    try:
                        return await resp.json()
                    except Exception:
                        return {}
            except aiohttp.ClientResponseError as e:
                status = getattr(e, "status", None)
                logging.warning(
                    "fetch_shortcut HTTP error %s (attempt %d): %s",
                    url,
                    attempt,
                    status,
                )
                if status and 500 <= status < 600:
                    await asyncio.sleep(_BACKOFF_BASE * attempt)
                    continue
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logging.warning(
                    "fetch_shortcut network/timeout %s (attempt %d): %s",
                    url,
                    attempt,
                    e,
                )
                await asyncio.sleep(_BACKOFF_BASE * attempt)
                continue
    logging.error("fetch_shortcut failed after retries: %s", url)
    return None


@dp.message(Command(commands=["help", "paysupport", "suggestion", "bug", "support"]))
async def help_form(message: types.Message):
    text = (
        "*Есть предложение\, проблема или может нашли баг?*\n\n"
        "О них вы можете сообщить\, заполнив форму ниже\:\n\n"
        "https://forms\.gle/Cwb4PJMnSJ8ZeEgo7\n"
    )
    await message.answer(text=text, parse_mode=ParseMode.MARKDOWN_V2)


@dp.message(Command(commands=["profile"]))
async def help_form(message: types.Message):
    user = await fetch_user(message.from_user.id)
    user_is_premium = is_user_premium(user)

    subscription_name = "Free"
    subscription_expired = None
    subscription_expired_normalized_time = "-"

    user_id = user.get("telegramId", "Unknown")

    if user_is_premium:
        try:
            subscriptions = user.get("subscription", [])
            active_subscription = next(
                (sub for sub in subscriptions if sub.get("status") == "ACTIVE"), None
            )
            valid_until = (
                active_subscription.get("validUntil") if active_subscription else None
            )
            plan = (
                active_subscription.get("plan") if active_subscription else None
            )
            if valid_until:
                subscription_expired = datetime.fromisoformat(valid_until)
                subscription_expired_normalized_time = subscription_expired.strftime(
                    "%d.%m.%Y"
                )
            else:
                subscription_expired_normalized_time = "-"
            subscription_name = plan
        except Exception:
            subscription_expired = None
            subscription_expired_normalized_time = "-"
            subscription_name = plan

    user_model = user.get("defaultModel") or {}
    user_model_name = user_model.get("name", "Unknown")
    user_free_questions = user.get("freeQuestions", 0)
    user_premium_questions = user.get("premiumQuestions", 0)

    text = (
        f"<b>👤ID:</b> {user_id} \n"
        f" <b>⭐️Тип подписки:</b> {subscription_name} \n"
        f" <b>📆Действует до:</b> {subscription_expired_normalized_time} \n\n"
        " ———————————————— \n\n"
        f" <b>🤖Текущая модель:</b> {user_model_name} \n"
        f" <b>✨Премиум вопросы:</b> {user_premium_questions} \n"
        f" <b>❔Обычные вопросы:</b> {user_free_questions} "
    )
    await message.answer(text=text, parse_mode=ParseMode.HTML)


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-sel_"))
async def cb_select_shortcut(query: types.CallbackQuery, state: FSMContext):
    await query.answer()

    shortcut_id = query.data.split("_", 1)[1].lstrip(":")

    shortcut = await fetch_shortcut(shortcut_id)
    if not shortcut:
        await query.message.answer("Шорткат не найден.")
        return

    command = shortcut.get("command", "")
    instruction = shortcut.get("instruction", "")
    ai_model = shortcut.get("model") or {}
    ai_model_name = ai_model.get("name", "(unknown)")

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="✏️Изменить команду",
                callback_data=f"shortcut-edit_cmd_{shortcut_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️Изменить инструкцию",
                callback_data=f"shortcut-edit_instr_{shortcut_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️Изменить модель",
                callback_data=f"shortcut-edit_model_{shortcut_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑Удалить шорткат", callback_data=f"shortcut-delete_{shortcut_id}"
            )
        ],
        [InlineKeyboardButton(text="↩️Назад", callback_data="shortcut-back")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    short_cut_info = (
        f"<b>Команда</b> - {html.escape(str(command))}\n"
        f"<b>Инструкция</b> - {html.escape(str(instruction))}\n"
        f"<b>ИИ-модель</b> - {html.escape(str(ai_model_name))}"
    )

    await query.message.edit_text(
        short_cut_info, parse_mode=ParseMode.HTML, reply_markup=kb
    )


@dp.callback_query(lambda c: c.data == "shortcut-create")
async def cb_create_shortcut(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(shortcut_mode="create")
    await state.update_data(shortcut_step="command")

    rows = [[InlineKeyboardButton(text="↩️ Назад", callback_data="shortcut-back")]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await query.message.edit_text(
        "Создание нового шортката\n\nВведите команду для шортката (например: /image):",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@dp.callback_query(lambda c: c.data == "shortcut-back")
async def cb_shortcut_back(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    await state.update_data(shortcut_mode=None)
    await shortcuts_edit_answer(query.message, state, query.from_user.id)


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-edit_cmd_"))
async def cb_edit_shortcut_command(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    shortcut_id = query.data.replace("shortcut-edit_cmd_", "")
    await state.update_data(shortcut_mode="edit")
    await state.update_data(shortcut_step="command")
    await state.update_data(shortcut_id=shortcut_id)

    rows = [
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=f"shortcut-sel_{shortcut_id}"
            )
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await query.message.edit_text(
        "Введите новую команду для шортката:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-edit_instr_"))
async def cb_edit_shortcut_instruction(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    shortcut_id = query.data.replace("shortcut-edit_instr_", "")
    await state.update_data(shortcut_mode="edit")
    await state.update_data(shortcut_step="instruction")
    await state.update_data(shortcut_id=shortcut_id)

    rows = [
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=f"shortcut-sel_{shortcut_id}"
            )
        ]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await query.message.edit_text(
        "Введите новую инструкцию для шортката:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-edit_model_"))
async def cb_edit_shortcut_model(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    shortcut_id = query.data.replace("shortcut-edit_model_", "")
    await state.update_data(shortcut_mode="edit")
    await state.update_data(shortcut_step="model")
    await state.update_data(shortcut_id=shortcut_id)

    models = await fetch_models()
    user = await fetch_user(query.from_user.id)
    user_premium = is_user_premium(user)

    buttons: list[InlineKeyboardButton] = []
    for m in models:
        model_name = m["name"]
        icons = ""
        if m.get("premium", False) and not user_premium:
            icons = f"🔒{icons}"
            continue
        if "reasoning" in m["tags"]:
            icons = f"🧠{icons}"
        if "image" in m["tags"]:
            icons = f"🖼️{icons}"
        if m["premium"] == True:
            icons = f"⭐ {icons}"

        label = f"{icons} {model_name}"
        buttons.append(
            InlineKeyboardButton(
                text=label,
                callback_data=f"shortcut-model_select_{shortcut_id}_{m['id']}",
            )
        )

    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(
                text="↩️Отмена", callback_data=f"shortcut-sel_{shortcut_id}"
            )
        ]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await query.message.edit_text(
        "Выберите модель для шортката:", reply_markup=kb, parse_mode=ParseMode.HTML
    )


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-model_select_"))
async def cb_select_shortcut_model(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    parts = query.data.split("_")
    shortcut_id = parts[2]
    model_id = parts[3]

    try:
        await patch_shortcuts(shortcut_id, {"modelId": model_id})
        await query.answer("✅ Модель обновлена", show_alert=True)
        await shortcuts_edit_answer(query.message, state, user_id=query.from_user.id)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


async def shortcuts_edit_answer(
    message: types.Message, state: FSMContext, user_id: int
):
    try:
        user_shortcuts = await fetch_user_shortcuts(user_id)
    except Exception as e:
        await message.answer(f"Не удалось получить список шорткатов: {e}")
        return

    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text="➕ Создать новый шорткат", callback_data="shortcut-create"
            )
        ],
    ]
    for shortcut in user_shortcuts:
        label = shortcut.get("command") or shortcut["id"][:8]
        id = shortcut.get("id")

        rows.append(
            [InlineKeyboardButton(text=label, callback_data=f"shortcut-sel_{id}")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text = "<b>Шорткаты — это быстрые шаблоны, чтобы не вводить одно и то же по сто раз.</b> \n\n При использовании шортката его инструкция автоматически добавится в начало вашего запроса, а ответ придёт от выбранной вами модели. \n\n Выберите или создайте шорткат и ускорьте работу."

    await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-delete_"))
async def cb_delete_shortcut(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    shortcut_id = query.data.replace("shortcut-delete_", "")

    try:
        await delete_shortcuts(shortcut_id)
        await query.answer("✅ Шорткат удалён", show_alert=True)
        await shortcuts_edit_answer(query.message, state, query.from_user.id)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


@dp.callback_query(lambda c: c.data and c.data.startswith("shortcut-create_model_"))
async def cb_create_shortcut_final(query: types.CallbackQuery, state: FSMContext):
    await query.answer()
    parts = query.data.split("_")
    model_id = parts[2]

    data = await state.get_data()
    command = data.get("shortcut_command")
    instruction = data.get("shortcut_instruction")

    try:
        shortcut_data = {
            "telegramId": query.from_user.id,
            "command": command,
            "instruction": instruction,
            "modelId": model_id,
        }

        result = await add_shortcuts(shortcut_data)
        if result:
            await query.answer("✅ Шорткат создан!", show_alert=True)
            await state.update_data(
                shortcut_mode=None,
                shortcut_step=None,
                shortcut_command=None,
                shortcut_instruction=None,
            )
            await shortcuts_edit_answer(query.message, state, query.from_user.id)
        else:
            await query.answer("❌ Ошибка при создании шортката", show_alert=True)
    except Exception as e:
        await query.answer(f"❌ Ошибка: {e}", show_alert=True)


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
    await callback.message.edit_reply_markup(reply_markup=kb)
    await change_pin(callback.message.chat.id, model_title, None, callback.bot)
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
        new_text = f"{new_text} \n\n ✅ - выбранная вами модель \n 🧠 - модель обладающая возможностью рассуждения \n 🖼️ - модель вместо текстового ответа создёт картинки \n ⭐ - премиум модель"
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
from typing import Tuple


def extract_and_strip_think(text: str) -> Tuple[str, str]:
    m = re.search(r"<think\b[^>]*>([\s\S]*?)</think\s*>", text, flags=re.IGNORECASE)
    if m:
        think_text = m.group(1).strip()
        visible_text = (text[: m.start()] + text[m.end() :]).strip()
        return visible_text, think_text

    m_close = re.search(r"</think\s*>", text, flags=re.IGNORECASE)
    if m_close:
        think_text = text[: m_close.start()].strip()
        visible_text = text[m_close.end() :].strip()
        return visible_text, think_text

    return text.strip(), ""


def is_blank_simple(s: str) -> bool:
    if s is None:
        return True
    s = str(s)
    cleaned = re.sub(r"[\s\u00A0\u200B\u200C\u200D\u200E\u200F\uFEFF]+", "", s)
    return cleaned == ""


def escape_markdown_v2(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("\\", r"\\")
    return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}.!])", r"\\\\\1", text)


forbidden_commands = {
    "/chats",
    "/models",
    "/role",
    "/start",
    "/pro",
    "/support",
    "/shortcuts",
}


@dp.message()
async def message_router(message: types.Message, state: FSMContext):
    txt = (message.text or message.caption or "").strip()
    if message.text is None and message.caption is None and message.voice is None:
        return
    if any(txt.startswith(cmd) for cmd in forbidden_commands):
        return
    data = await state.get_data()
    mode = data.get("mode")
    edit_target = data.get("edit_target")
    payload = None
    form_data = None

    if data.get("is_locked") == True:
        await message.answer("Дождитесь пожалуйста ответа модели")
        return

    chat_id = data.get("active_chat", "0")

    target = None

    async def safe_delete_target(t):
        if not t:
            return
        try:
            await t.delete()
        except Exception:
            pass

    if message.text is not None and message.text not in forbidden_commands:
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

        shortcut_mode = data.get("shortcut_mode")
        if shortcut_mode in ["create", "edit"]:
            shortcut_step = data.get("shortcut_step")
            shortcut_id = data.get("shortcut_id")

            if shortcut_mode == "create":
                if shortcut_step == "command":
                    command = message.text.strip()
                    if not command.startswith("/"):
                        command = "/" + command

                    await state.update_data(shortcut_command=command)
                    await state.update_data(shortcut_step="instruction")
                    rows = [
                        [
                            InlineKeyboardButton(
                                text="↩️ Назад", callback_data=f"shortcut-back"
                            )
                        ]
                    ]
                    kb = InlineKeyboardMarkup(inline_keyboard=rows)
                    await message.answer(
                        "Введите инструкцию для шортката:",
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb,
                    )

                    return
                elif shortcut_step == "instruction":
                    command = data.get("shortcut_command")
                    instruction = message.text.strip()

                    models = await fetch_models()
                    user = await fetch_user(message.from_user.id)
                    user_premium = is_user_premium(user)

                    buttons: list[InlineKeyboardButton] = []
                    for m in models:
                        model_name = m["name"]
                        icons = ""
                        if m.get("premium", False) and not user_premium:
                            icons = f"🔒{icons}"
                            continue
                        if "reasoning" in m["tags"]:
                            icons = f"🧠{icons}"
                        if "image" in m["tags"]:
                            icons = f"🖼️{icons}"
                        if m["premium"] == True:
                            icons = f"⭐ {icons}"

                        label = f"{icons} {model_name}"
                        buttons.append(
                            InlineKeyboardButton(
                                text=label,
                                callback_data=f"shortcut-create_model_{m['id']}",
                            )
                        )

                    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
                    rows.append(
                        [
                            InlineKeyboardButton(
                                text="↩️Отмена", callback_data="shortcut-back"
                            )
                        ]
                    )
                    kb = InlineKeyboardMarkup(inline_keyboard=rows)

                    await state.update_data(
                        shortcut_command=command, shortcut_instruction=instruction
                    )

                    await message.answer(
                        "Выберите модель для шортката:",
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML,
                    )
                    return

            elif shortcut_mode == "edit":
                if shortcut_step == "command":
                    command = message.text.strip()
                    if not command.startswith("/"):
                        command = "/" + command

                    try:
                        await patch_shortcuts(shortcut_id, {"command": command})
                        await message.answer("✅ Команда обновлена")
                        await state.update_data(
                            shortcut_mode=None, shortcut_step=None, shortcut_id=None
                        )
                        await shortcuts_command(message, state)
                    except Exception as e:
                        await message.answer(f"❌ Ошибка: {e}")
                    return
                elif shortcut_step == "instruction":
                    try:
                        await patch_shortcuts(
                            shortcut_id, {"instruction": message.text.strip()}
                        )
                        await message.answer("✅ Инструкция обновлена")
                        await state.update_data(
                            shortcut_mode=None, shortcut_step=None, shortcut_id=None
                        )
                        await shortcuts_command(message, state)
                    except Exception as e:
                        await message.answer(f"❌ Ошибка: {e}")
                    return

        payload = {"telegramId": message.from_user.id, "prompt": message.text}
        if chat_id:
            payload["chatId"] = chat_id
        await state.update_data(is_locked=True)

        try:
            target = await message.answer(
                "Нейросеть думает🤔", parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception:
            try:
                target = await message.reply("Нейросеть думает🤔")
            except Exception:
                target = None
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    if message.photo:
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
        if chat_id:
            payload["chatId"] = chat_id
        if target is None:
            try:
                target = await message.answer(
                    "Нейросеть думает🤔", parse_mode=ParseMode.MARKDOWN_V2
                )
            except Exception:
                try:
                    target = await message.reply("Нейросеть думает🤔")
                except Exception:
                    target = None
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    if (
        (
            message.document
            and not (message.document.mime_type or "").startswith("image/")
        )
        or message.audio
        or message.voice
    ):
        is_forwarded = bool(
            message.forward_from
            or message.forward_from_chat
            or message.forward_sender_name
        )
        doc = message.document or message.audio or message.voice
        form_data = aiohttp.FormData()
        caption = message.caption or "Игнорируй этот текст,  читай только что выше"
        form_data.add_field("prompt", caption, content_type="text/plain")
        form_data.add_field(
            "telegramId", str(message.from_user.id), content_type="text/plain"
        )
        form_data.add_field("chatId", str(chat_id), content_type="text/plain")
        form_data.add_field("isForwarded", str(is_forwarded), content_type="text/plain")
        if not doc:
            return
        bio = BytesIO()
        await bot.download(doc.file_id, destination=bio)
        bio.seek(0)
        filename = getattr(doc, "file_name", f"{doc.file_id}.ogg")
        content_type = getattr(doc, "mime_type", None) or (
            "audio/ogg" if message.voice else "application/octet-stream"
        )
        form_data.add_field(
            "file",
            value=bio,
            filename=filename,
            content_type=content_type,
        )

    async with aiohttp.ClientSession() as session:
        try:
            if isinstance(form_data, aiohttp.FormData):
                async with session.post(f"{API_URL}/messages", data=form_data) as resp:
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
                        response_chat_id = result.get("chatId", "0")
                        actual_chat_id = data.get("active_chat")
                        if response_chat_id != actual_chat_id:
                            try:
                                selected = await fetch_chat(
                                    message.from_user.id, response_chat_id
                                )
                            except Exception as e:
                                await message.answer(
                                    f"Не удалось получить список чатов: {e}",
                                    show_alert=True,
                                )
                                return
                            chat_title = (
                                selected.get("title")
                                if selected and selected.get("title")
                                else response_chat_id[:8]
                            )
                            await change_pin(
                                message.chat.id, None, chat_title, message.bot
                            )
                        await state.update_data(active_chat=response_chat_id)
                        raw = result.get("content", "")

                        if isinstance(raw, (tuple, list)):
                            raw = raw[0] if raw else ""
                        if not isinstance(raw, str):
                            raw = str(raw) or ""

                        if result.get("type") == "image":
                            photo = BufferedInputFile(
                                base64.b64decode(raw), filename="gen.png"
                            )
                            await message.answer_photo(photo)
                        else:
                            raw_visible, think_text = extract_and_strip_think(raw)
                            clean = markdownify(raw_visible)
                            final_text = clean[:4096]
                            if not is_blank_simple(think_text):
                                try:
                                    byte_text = make_final_text_by_truncating_hidden(
                                        think_text, max_len=4096
                                    )
                                except ValueError:
                                    pass
                                kb = toggle_think_buttons(
                                    InlineKeyboardMarkup(inline_keyboard=[]), show=False
                                )
                                await safe_delete_target(target)
                                await message.answer(text=byte_text, reply_markup=kb)
                                await message.reply(
                                    final_text, parse_mode=ParseMode.MARKDOWN_V2
                                )
                            else:
                                final_text = clean
                                await safe_delete_target(target)
                                await message.reply(
                                    final_text, parse_mode=ParseMode.MARKDOWN_V2
                                )
                    except Exception as e:
                        await safe_delete_target(target)
                        await message.answer(
                            f"Ошибка обработки ответа: {e}. Попробуйте позже."
                        )
            else:
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

                        logging.info("result: %s", result)

                        response_chat_id = result.get("chatId", "0")
                        actual_chat_id = data.get("active_chat")
                        if response_chat_id != actual_chat_id:
                            try:
                                selected = await fetch_chat(
                                    message.from_user.id, response_chat_id
                                )
                            except Exception as e:
                                await message.answer(
                                    f"Не удалось получить список чатов: {e}",
                                    show_alert=True,
                                )
                                return

                            chat_title = (
                                selected.get("title")
                                if selected and selected.get("title")
                                else response_chat_id[:8]
                            )
                            await change_pin(
                                message.chat.id, None, chat_title, message.bot
                            )
                        await state.update_data(active_chat=response_chat_id)
                        raw = result.get("content", "")
                        if not raw:
                            await safe_delete_target(target)
                            await message.answer(
                                "Произошла непредвиденная ошибка: сервер вернул пустой ответ. "
                                "Попробуйте сменить модель или повторить запрос."
                            )
                            return
                        if isinstance(raw, (tuple, list)):
                            raw = raw[0] if raw else ""
                        if not isinstance(raw, str):
                            raw = str(raw) or ""
                        if result.get("type") == "image":
                            photo = BufferedInputFile(
                                base64.b64decode(raw), filename="gen.png"
                            )
                            await message.answer_photo(photo)
                        else:
                            raw_visible, think_text = extract_and_strip_think(raw)
                            clean = markdownify(raw_visible)
                            final_text = clean[:4096]
                            if not is_blank_simple(think_text):
                                try:
                                    byte_text = make_final_text_by_truncating_hidden(
                                        think_text, max_len=4096
                                    )
                                except ValueError:
                                    pass
                                kb = toggle_think_buttons(
                                    InlineKeyboardMarkup(inline_keyboard=[]), show=False
                                )
                                await safe_delete_target(target)
                                await message.answer(text=byte_text, reply_markup=kb)
                                await message.reply(
                                    final_text, parse_mode=ParseMode.MARKDOWN_V2
                                )
                            else:
                                final_text = clean
                                await safe_delete_target(target)
                                await message.reply(
                                    final_text, parse_mode=ParseMode.MARKDOWN_V2
                                )
                    except Exception as e:
                        await safe_delete_target(target)
                        await message.answer(
                            f"Ошибка обработки ответа: {e}. Попробуйте позже."
                        )
        except ClientError as e:
            await safe_delete_target(target)
            await message.answer(f"Сетевая ошибка: {e}")
        finally:
            await state.update_data(is_locked=False)


_ZW_MARKER = "\u2063\u2063\u2063"
_ZW_ZERO = "\u200b"
_ZW_ONE = "\u200c"


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
    byte_arr = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
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


def _extract_hidden(full_text: str):
    if _ZW_MARKER not in full_text:
        return full_text, None
    visible, zw_part = full_text.split(_ZW_MARKER, 1)
    return visible, zw_part


def _make_hidden_payload(think_text: str) -> bytes:
    obj = {"think": think_text}
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def toggle_think_buttons(kb: InlineKeyboardMarkup, show: bool) -> InlineKeyboardMarkup:
    kb.inline_keyboard = [
        [
            InlineKeyboardButton(
                text=(
                    "Скрыть размышления модели 💡"
                    if show
                    else "Показать размышления модели 💡"
                ),
                callback_data="think_hide" if show else "think_info",
            )
        ]
    ]
    return kb


@dp.callback_query(lambda c: c.data in ("think_info", "think_hide"))
async def on_think_toggle(callback: CallbackQuery):
    msg = callback.message
    if not msg or not (msg.text or msg.caption):
        await callback.answer("Нет текста сообщения.", show_alert=True)
        return

    full_text = msg.text or msg.caption or ""
    visible, zw_part = _extract_hidden(full_text)
    raw_bytes = _unpack_zw_to_bytes(zw_part) if zw_part else None
    hidden_obj = None
    if raw_bytes:
        try:
            hidden_obj = json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            hidden_obj = None

    if callback.data == "think_info":
        if not hidden_obj:
            await callback.answer(
                "Размышления не найдены или повреждены.", show_alert=True
            )
            return

        clean = hidden_obj.get("clean", visible) or ""
        think = hidden_obj.get("think", "") or ""
        visible_text = f"{clean}\n\n💡 Размышления модели:\n{think}"

        try:
            zw_for_visible = make_final_text_by_truncating_hidden(
                think, max_len=4096 - len(visible_text)
            )
            new_text = visible_text + zw_for_visible
        except ValueError:
            new_text = visible_text[:4096]

        kb_new = toggle_think_buttons(
            msg.reply_markup or InlineKeyboardMarkup(), show=True
        )
        await msg.edit_text(new_text, reply_markup=kb_new, parse_mode=ParseMode.HTML)
        await callback.answer()

    else:
        clean = (hidden_obj.get("clean", "") if hidden_obj else visible) or ""
        think_part = hidden_obj.get("think", "") if hidden_obj else ""
        visible_text = clean

        try:
            zw_for_visible = make_final_text_by_truncating_hidden(
                think_part, max_len=4096 - len(visible_text)
            )
            new_text = visible_text + zw_for_visible
        except ValueError:
            new_text = visible_text[:4096]

        kb_new = toggle_think_buttons(
            msg.reply_markup or InlineKeyboardMarkup(), show=False
        )
        await msg.edit_text(new_text, reply_markup=kb_new, parse_mode=ParseMode.HTML)
        await callback.answer()


def make_final_text_by_truncating_hidden(think_text: str, max_len: int = 4096) -> str:

    marker = _ZW_MARKER
    space_for_zw = max_len - len(marker)
    if space_for_zw <= 0:
        raise ValueError("Нет места для невидимого блока.")

    whole_bytes = _make_hidden_payload(think_text)
    whole_zw = _pack_bytes_to_zw(whole_bytes)
    if len(whole_zw) <= space_for_zw:
        return marker + whole_zw

    s = think_text or ""
    lo, hi = 0, len(s)
    best_zw = None
    while lo <= hi:
        mid = (lo + hi) // 2
        cand_think = s[:mid]
        cand_bytes = _make_hidden_payload(cand_think)
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
        return marker + best_zw

    empty_bytes = _make_hidden_payload("")
    empty_zw = _pack_bytes_to_zw(empty_bytes)
    if len(empty_zw) <= space_for_zw:
        return marker + empty_zw

    raise ValueError("Hidden payload too large even after truncation.")


import socket


async def _wait_port_up(port: int, timeout: float = 10.0) -> bool:
    def _check(port, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                s = socket.create_connection(("127.0.0.1", port), timeout=1)
                s.close()
                return True
            except Exception:
                time.sleep(0.2)
        return False

    return await asyncio.to_thread(_check, port, timeout)


async def main():
    sentry_sdk.init(
        dsn="https://e8b7b18ddf5122642e1be46af0e0af02@o4509825102708736.ingest.de.sentry.io/4509920637812816",
        send_default_pii=True,
    )
    port = int(os.environ.get("PORT", 8000))

    print(f"[boot] starting health server on 0.0.0.0:{port} ...", flush=True)
    health_runner = await _start_health_server(port)
    print(
        "[boot] health server started, waiting for port to accept connections...",
        flush=True,
    )

    ok = await _wait_port_up(port, timeout=10.0)
    if not ok:
        print(
            f"[boot][WARN] port {port} is not accepting connections after wait; continuing anyway.",
            flush=True,
        )
    else:
        print(f"[boot] port {port} is reachable (self-check OK).", flush=True)

    polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    print("[boot] started polling task", flush=True)

    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print("Polling error:", e, flush=True)
    finally:
        print("[shutdown] shutting down dp and bot", flush=True)
        try:
            await dp.shutdown()
        except Exception:
            pass
        try:
            await bot.session.close()
        except Exception:
            pass

        await _shutdown_health_server(health_runner)
        print("[shutdown] health server stopped. Shutdown complete.", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user")
