"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL, Crypto Pay API, YooMoney API
"""

import asyncio
import logging
import os
import threading
import hashlib
import hmac
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, Numeric, String, Text,
    ForeignKey, select, func, update, delete
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import text

# ─────────────────────────── Logging ────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────── Config ─────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/dbname")

# ── ИСПРАВЛЕНИЕ ДЛЯ BOTHOST ────────────────────────────────────────────────
# Bothost выдаёт URL в формате postgresql://, но SQLAlchemy требует postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info(f"DATABASE_URL адаптирован для asyncpg")
# ───────────────────────────────────────────────────────────────────────────

# ─────────────────────────── Database Models ────────────────────────────────

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    bots: Mapped[list["ShopBot"]] = relationship("ShopBot", back_populates="owner", foreign_keys="ShopBot.owner_id")
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user")


class ShopBot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    owner: Mapped["User"] = relationship("User", back_populates="bots", foreign_keys=[owner_id])
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="bot", cascade="all, delete-orphan")
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="bot")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    bot: Mapped["ShopBot"] = relationship("ShopBot", back_populates="categories")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    category: Mapped["Category"] = relationship("Category", back_populates="products")
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="product")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    user: Mapped["User"] = relationship("User", back_populates="purchases")
    bot: Mapped["ShopBot"] = relationship("ShopBot", back_populates="purchases")
    product: Mapped["Product"] = relationship("Product", back_populates="purchases")


# ─────────────────────────── DB Engine ──────────────────────────────────────

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str]) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


# ─────────────────────────── Payment APIs ───────────────────────────────────

class CryptoBotAPI:
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": token}

    async def create_invoice(self, amount: float, description: str, payload: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/createInvoice",
                    headers=self.headers,
                    json={
                        "currency_type": "fiat",
                        "fiat": "RUB",
                        "amount": str(amount),
                        "description": description,
                        "payload": payload,
                        "paid_btn_name": "callback",
                        "paid_btn_url": "https://t.me/",
                    }
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]
                    logger.error(f"CryptoBot create_invoice error: {data}")
                    return None
        except Exception as e:
            logger.error(f"CryptoBot API error: {e}")
            return None

    async def get_invoices(self, invoice_ids: list[int]) -> Optional[list]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/getInvoices",
                    headers=self.headers,
                    params={"invoice_ids": ",".join(map(str, invoice_ids))}
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]["items"]
                    return None
        except Exception as e:
            logger.error(f"CryptoBot getInvoices error: {e}")
            return None


class YooMoneyAPI:
    BASE_URL = "https://yoomoney.ru/api"

    def __init__(self, wallet: str, token: str = ""):
        self.wallet = wallet
        self.token = token

    def generate_form_url(self, amount: float, label: str, comment: str) -> str:
        return (
            f"https://yoomoney.ru/quickpay/confirm.xml?"
            f"receiver={self.wallet}&quickpay-form=button"
            f"&targets={comment}&sum={amount}&label={label}&successURL="
        )

    async def check_payment(self, label: str) -> bool:
        if not self.token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/operation-history",
                    headers={"Authorization": f"Bearer {self.token}"},
                    data={"label": label, "records": 10}
                ) as resp:
                    data = await resp.json()
                    ops = data.get("operations", [])
                    for op in ops:
                        if op.get("label") == label and op.get("status") == "success":
                            return True
                    return False
        except Exception as e:
            logger.error(f"YooMoney check error: {e}")
            return False


# ─────────────────────────── Keyboard Helpers ────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Создать бота"), KeyboardButton(text="📋 Мои боты")],
            [KeyboardButton(text="👤 Профиль")],
        ],
        resize_keyboard=True
    )


def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Купить донат"), KeyboardButton(text="📦 Мои покупки")],
            [KeyboardButton(text="👤 Профиль")],
        ],
        resize_keyboard=True
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📨 Рассылка")],
            [KeyboardButton(text="➕ Выставить товар"), KeyboardButton(text="➖ Удалить товар")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d)] for t, d in buttons]
    )


# ─────────────────────────── FSM States ─────────────────────────────────────

class CreateBotFSM(StatesGroup):
    token = State()
    name = State()
    admin_id = State()
    crypto_token = State()
    yoomoney_wallet = State()


class AddProductFSM(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()


class DeleteProductFSM(StatesGroup):
    category = State()
    product = State()


class BroadcastFSM(StatesGroup):
    message = State()


class PaymentFSM(StatesGroup):
    waiting_confirm = State()


# ─────────────────────────── Constructor Bot ─────────────────────────────────

constructor_router = Router()


@constructor_router.message(CommandStart())
async def cmd_start_constructor(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать в конструктор магазинов доната!\n\n"
        "Здесь вы можете создать собственного Telegram-бота для продажи доната "
        "в играх Supercell (Brawl Stars, Clash of Clans, Clash Royale).",
        reply_markup=main_menu_kb()
    )


# ── Создать бота ─────────────────────────────────────────────────────────────

@constructor_router.message(F.text == "🛠 Создать бота")
async def start_create_bot(message: Message, state: FSMContext):
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        "🤖 <b>Шаг 1/5</b> — Введите токен бота.\n"
        "Получите его у @BotFather командой /newbot",
        reply_markup=cancel_kb()
    )


@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer("❗ Некорректный токен. Попробуйте ещё раз.")

    # Check uniqueness
    async with async_session_maker() as session:
        existing = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if existing.scalar_one_or_none():
            return await message.answer("❗ Бот с таким токеном уже существует.")

    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer("✅ Токен принят.\n\n📝 <b>Шаг 2/5</b> — Введите название магазина:")


@constructor_router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer("❗ Название должно быть от 1 до 255 символов.")

    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer("✅ Название принято.\n\n👮 <b>Шаг 3/5</b> — Введите Telegram ID администратора магазина:")


@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    try:
        admin_id = int(message.text.strip())
    except ValueError:
        return await message.answer("❗ Введите числовой Telegram ID.")

    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer(
        "✅ Admin ID принят.\n\n💎 <b>Шаг 4/5</b> — Введите токен Crypto Bot (от @CryptoBot).\n"
        "Или отправьте <b>-</b> чтобы пропустить."
    )


@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer(
        "💸 <b>Шаг 5/5</b> — Введите номер кошелька ЮMoney.\n"
        "Или отправьте <b>-</b> чтобы пропустить."
    )


@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_yoomoney(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    yoo = message.text.strip()
    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        bot_record = ShopBot(
            owner_id=message.from_user.id,
            bot_token=data["token"],
            bot_name=data["name"],
            admin_id=data["admin_id"],
            crypto_bot_token=data.get("crypto_token"),
            yoomoney_wallet=None if yoo == "-" else yoo,
            is_active=True
        )
        session.add(bot_record)
        await session.commit()
        await session.refresh(bot_record)

        # Auto-create default Supercell categories
        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    await message.answer(
        f"✅ <b>Бот '{data['name']}' создан!</b>\n\n"
        f"🔑 Токен: <code>{data['token']}</code>\n"
        f"👮 Admin ID: <code>{data['admin_id']}</code>\n\n"
        f"📋 Для запуска добавьте бота на сервер и установите переменные:\n"
        f"<code>SHOP_BOT_TOKEN={data['token']}</code>\n"
        f"<code>DATABASE_URL=ваша_строка_подключения</code>\n\n"
        f"Используйте команду: <code>python bot.py --shop {bot_record.id}</code>",
        reply_markup=main_menu_kb()
    )


# ── Мои боты ─────────────────────────────────────────────────────────────────

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id)
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer("У вас пока нет созданных ботов.\nНажмите «🛠 Создать бота»!")

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token:
            payments.append("Crypto Bot")
        if bot.yoomoney_wallet:
            payments.append("ЮMoney")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⏸ Остановить" if bot.is_active else "▶️ Запустить",
                                     callback_data=f"toggle_bot:{bot.id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot.id}"),
            ]
        ])
        await message.answer(
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"Статус: {status}\n"
            f"Оплата: {', '.join(payments) or '—'}\n"
            f"ID: <code>{bot.id}</code>",
            reply_markup=kb
        )


@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        result = await session.execute(select(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id))
        bot = result.scalar_one_or_none()
        if not bot:
            return await callback.answer("Бот не найден.")
        bot.is_active = not bot.is_active
        await session.commit()
        status = "запущен" if bot.is_active else "остановлен"
    await callback.answer(f"Бот {status}.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"✅ Бот {'🟢 запущен' if not bot.is_active else '🔴 остановлен'}.")


@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete"),
    ]])
    await callback.message.answer("Вы уверены, что хотите удалить бота?", reply_markup=kb)
    await callback.answer()


@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id))
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🗑 Бот удалён.")
    await callback.answer()


@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено.")


# ── Профиль ──────────────────────────────────────────────────────────────────

@constructor_router.message(F.text == "👤 Профиль")
async def profile_constructor(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
        total_spent = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
            .where(Purchase.user_id == message.from_user.id, Purchase.status == "completed")
        )

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"💰 Баланс: {user.balance} ₽\n"
        f"🤖 Ботов создано: {bots_count}\n"
        f"🛒 Всего потрачено: {total_spent} ₽\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y')}"
    )


# ─────────────────────────── Shop Bot Factory ────────────────────────────────

def create_shop_bot(bot_record: ShopBot) -> tuple[Bot, Dispatcher]:
    """Create a shop bot instance for a given bot record."""
    shop_bot = Bot(
        token=bot_record.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    shop_router = Router()

    # ── FSM States for this shop ─────────────────────────────────────────────
    class ShopPaymentFSM(StatesGroup):
        select_payment = State()
        waiting_crypto = State()
        waiting_yoomoney = State()

    class ShopAddProductFSM(StatesGroup):
        category = State()
        name = State()
        description = State()
        price = State()

    class ShopDeleteProductFSM(StatesGroup):
        category = State()
        product = State()

    class ShopBroadcastFSM(StatesGroup):
        message_text = State()

    # ── /start ───────────────────────────────────────────────────────────────
    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        is_admin = (message.from_user.id == bot_record.admin_id)
        kb = admin_menu_kb() if is_admin else shop_menu_kb()
        await message.answer(
            f"🎮 Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат для игр Supercell:\n"
            f"🔵 Brawl Stars | ⚔️ Clash of Clans | 👑 Clash Royale",
            reply_markup=kb
        )

    @shop_router.message(F.text == "🏠 Главное меню")
    async def shop_home(message: Message, state: FSMContext):
        await state.clear()
        is_admin = (message.from_user.id == bot_record.admin_id)
        kb = admin_menu_kb() if is_admin else shop_menu_kb()
        await message.answer("Главное меню:", reply_markup=kb)

    # ── 🛒 Купить донат ──────────────────────────────────────────────────────
    @shop_router.message(F.text == "🛒 Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            categories = result.scalars().all()

        if not categories:
            return await message.answer("😔 Пока нет доступных категорий. Обратитесь к администратору.")

        buttons = [(cat.name, f"cat:{cat.id}") for cat in categories]
        await message.answer("🎮 Выберите игру:", reply_markup=inline_kb(buttons))

    @shop_router.callback_query(F.data.startswith("cat:"))
    async def show_products(callback: CallbackQuery):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            result = await session.execute(
                select(Product).where(Product.category_id == cat_id, Product.is_available == True)
            )
            products = result.scalars().all()
            cat = await session.get(Category, cat_id)

        if not products:
            return await callback.answer("В этой категории пока нет товаров.", show_alert=True)

        buttons = [(f"{p.name} — {p.price} ₽", f"product:{p.id}") for p in products]
        await callback.message.answer(
            f"📦 Товары в категории <b>{cat.name}</b>:",
            reply_markup=inline_kb(buttons)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("product:"))
    async def show_product_detail(callback: CallbackQuery, state: FSMContext):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)

        if not product:
            return await callback.answer("Товар не найден.", show_alert=True)

        text = (
            f"🛍 <b>{product.name}</b>\n\n"
            f"{product.description or ''}\n\n"
            f"💰 Цена: <b>{product.price} ₽</b>"
        )

        payment_buttons = []
        if bot_record.crypto_bot_token:
            payment_buttons.append(("💎 Crypto Bot", f"pay_crypto:{product_id}"))
        if bot_record.yoomoney_wallet:
            payment_buttons.append(("💸 ЮMoney", f"pay_yoomoney:{product_id}"))

        if not payment_buttons:
            return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")

        await callback.message.answer(text + "\n\n💳 Выберите способ оплаты:", reply_markup=inline_kb(payment_buttons))
        await callback.answer()

    # ── Crypto Bot Payment ───────────────────────────────────────────────────
    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_with_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.", show_alert=True)

            purchase = Purchase(
                user_id=callback.from_user.id,
                bot_id=bot_record.id,
                product_id=product_id,
                amount=product.price,
                status="pending",
                payment_method="crypto_bot"
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)

        api = CryptoBotAPI(bot_record.crypto_bot_token)
        invoice = await api.create_invoice(
            amount=float(product.price),
            description=f"Покупка: {product.name}",
            payload=str(purchase.id)
        )

        if not invoice:
            return await callback.message.answer("❌ Ошибка создания счёта. Попробуйте позже.")

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        invoice_id = invoice.get("invoice_id")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_crypto:{purchase.id}:{invoice_id}")],
        ])
        await callback.message.answer(
            f"🧾 Счёт создан!\n\n"
            f"Товар: <b>{product.name}</b>\n"
            f"Сумма: <b>{product.price} ₽</b>\n\n"
            f"Нажмите кнопку ниже для оплаты, затем проверьте статус.",
            reply_markup=kb
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("check_crypto:"))
    async def check_crypto_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        purchase_id, invoice_id = int(parts[1]), int(parts[2])

        api = CryptoBotAPI(bot_record.crypto_bot_token)
        invoices = await api.get_invoices([invoice_id])

        if not invoices:
            return await callback.answer("Не удалось проверить статус. Попробуйте позже.", show_alert=True)

        invoice_data = invoices[0]
        if invoice_data.get("status") == "paid":
            async with async_session_maker() as session:
                await session.execute(
                    update(Purchase).where(Purchase.id == purchase_id).values(status="completed")
                )
                await session.commit()
                purchase = await session.get(Purchase, purchase_id)
                product = await session.get(Product, purchase.product_id)

            try:
                await shop_bot.send_message(
                    bot_record.admin_id,
                    f"✅ <b>Новая покупка!</b>\n"
                    f"Товар: {product.name}\n"
                    f"Сумма: {purchase.amount} ₽\n"
                    f"Пользователь: {callback.from_user.id}\n"
                    f"Способ: Crypto Bot"
                )
            except Exception:
                pass

            await callback.message.answer(
                f"✅ <b>Оплата прошла успешно!</b>\n\nТовар: {product.name}\nСпасибо за покупку! 🎉"
            )
        else:
            await callback.answer("⏳ Оплата ещё не получена. Попробуйте чуть позже.", show_alert=True)

    # ── YooMoney Payment ─────────────────────────────────────────────────────
    @shop_router.callback_query(F.data.startswith("pay_yoomoney:"))
    async def pay_with_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.", show_alert=True)

            purchase = Purchase(
                user_id=callback.from_user.id,
                bot_id=bot_record.id,
                product_id=product_id,
                amount=product.price,
                status="pending",
                payment_method="yoomoney"
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)

        label = f"purchase_{purchase.id}_{int(time.time())}"
        yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
        pay_url = yoo.generate_form_url(
            amount=float(product.price),
            label=label,
            comment=f"Покупка: {product.name}"
        )

        # Store label for verification
        async with async_session_maker() as session:
            await session.execute(
                update(Purchase).where(Purchase.id == purchase.id)
                .values(payment_method=f"yoomoney:{label}")
            )
            await session.commit()

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_yoomoney:{purchase.id}:{label}")],
        ])
        await callback.message.answer(
            f"🧾 Счёт на оплату\n\n"
            f"Товар: <b>{product.name}</b>\n"
            f"Сумма: <b>{product.price} ₽</b>\n\n"
            f"Нажмите «Оплатить», затем «Проверить оплату».",
            reply_markup=kb
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("check_yoomoney:"))
    async def check_yoomoney_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        purchase_id, label = int(parts[1]), parts[2]

        yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
        paid = await yoo.check_payment(label)

        if paid:
            async with async_session_maker() as session:
                await session.execute(
                    update(Purchase).where(Purchase.id == purchase_id).values(status="completed")
                )
                await session.commit()
                purchase = await session.get(Purchase, purchase_id)
                product = await session.get(Product, purchase.product_id)

            try:
                await shop_bot.send_message(
                    bot_record.admin_id,
                    f"✅ <b>Новая покупка!</b>\n"
                    f"Товар: {product.name}\n"
                    f"Сумма: {purchase.amount} ₽\n"
                    f"Пользователь: {callback.from_user.id}\n"
                    f"Способ: ЮMoney"
                )
            except Exception:
                pass

            await callback.message.answer(f"✅ <b>Оплата подтверждена!</b>\n\nТовар: {product.name}\nСпасибо! 🎉")
        else:
            await callback.answer("⏳ Оплата не найдена. Убедитесь, что оплатили и попробуйте снова.", show_alert=True)

    # ── 📦 Мои покупки ───────────────────────────────────────────────────────
    @shop_router.message(F.text == "📦 Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Purchase, Product)
                .join(Product, Purchase.product_id == Product.id)
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id)
                .order_by(Purchase.created_at.desc())
                .limit(20)
            )
            rows = result.all()

        if not rows:
            return await message.answer("У вас пока нет покупок в этом магазине.")

        text = "📦 <b>Ваши покупки:</b>\n\n"
        status_map = {"pending": "⏳ Ожидает", "completed": "✅ Завершена", "cancelled": "❌ Отменена"}
        for purchase, product in rows:
            method = purchase.payment_method.split(":")[0] if ":" in purchase.payment_method else purchase.payment_method
            text += (
                f"🛍 <b>{product.name}</b>\n"
                f"💰 {purchase.amount} ₽ | {status_map.get(purchase.status, purchase.status)}\n"
                f"💳 {method} | 📅 {purchase.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        await message.answer(text)

    # ── 👤 Профиль (shop) ────────────────────────────────────────────────────
    @shop_router.message(F.text == "👤 Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            total = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(Purchase.user_id == message.from_user.id,
                       Purchase.bot_id == bot_record.id,
                       Purchase.status == "completed")
            )
            count = await session.scalar(
                select(func.count(Purchase.id))
                .where(Purchase.user_id == message.from_user.id,
                       Purchase.bot_id == bot_record.id,
                       Purchase.status == "completed")
            )

        await message.answer(
            f"👤 <b>Ваш профиль</b>\n\n"
            f"ID: <code>{message.from_user.id}</code>\n"
            f"Username: @{message.from_user.username or '—'}\n"
            f"🛒 Покупок: {count}\n"
            f"💰 Потрачено: {total} ₽"
        )

    # ─────────────────────────── ADMIN PANEL ─────────────────────────────────

    def is_admin(user_id: int) -> bool:
        return user_id == bot_record.admin_id

    @shop_router.message(F.text == "📊 Статистика")
    async def admin_stats(message: Message):
        if not is_admin(message.from_user.id):
            return await message.answer("⛔ Нет доступа.")
        async with async_session_maker() as session:
            users_count = await session.scalar(
                select(func.count(Purchase.user_id.distinct()))
                .where(Purchase.bot_id == bot_record.id)
            )
            purchases_count = await session.scalar(
                select(func.count(Purchase.id))
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed")
            )
            revenue = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed")
            )

        await message.answer(
            f"📊 <b>Статистика магазина</b>\n\n"
            f"👥 Уникальных покупателей: {users_count or 0}\n"
            f"🛒 Завершённых покупок: {purchases_count or 0}\n"
            f"💰 Общая выручка: {revenue or 0} ₽"
        )

    @shop_router.message(F.text == "📨 Рассылка")
    async def admin_broadcast_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return await message.answer("⛔ Нет доступа.")
        await state.set_state(ShopBroadcastFSM.message_text)
        await message.answer("✍️ Введите текст рассылки (поддерживается HTML):", reply_markup=cancel_kb())

    @shop_router.message(StateFilter(ShopBroadcastFSM.message_text))
    async def admin_broadcast_send(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())

        await state.clear()
        text = message.text

        async with async_session_maker() as session:
            result = await session.execute(
                select(Purchase.user_id.distinct()).where(Purchase.bot_id == bot_record.id)
            )
            user_ids = [row[0] for row in result.all()]

        sent, failed = 0, 0
        for uid in user_ids:
            try:
                await shop_bot.send_message(uid, text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await message.answer(
            f"📨 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
            reply_markup=admin_menu_kb()
        )

    @shop_router.message(F.text == "➕ Выставить товар")
    async def admin_add_product_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return await message.answer("⛔ Нет доступа.")
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            categories = result.scalars().all()

        if not categories:
            return await message.answer("Нет категорий. Создайте категорию через базу данных.")

        buttons = [(cat.name, f"addcat:{cat.id}") for cat in categories]
        await state.set_state(ShopAddProductFSM.category)
        await message.answer("Выберите категорию:", reply_markup=inline_kb(buttons))

    @shop_router.callback_query(StateFilter(ShopAddProductFSM.category), F.data.startswith("addcat:"))
    async def admin_add_product_name(callback: CallbackQuery, state: FSMContext):
        cat_id = int(callback.data.split(":")[1])
        await state.update_data(category_id=cat_id)
        await state.set_state(ShopAddProductFSM.name)
        await callback.message.answer("✏️ Введите название товара:", reply_markup=cancel_kb())
        await callback.answer()

    @shop_router.message(StateFilter(ShopAddProductFSM.name))
    async def admin_add_product_desc(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        await state.update_data(name=message.text.strip())
        await state.set_state(ShopAddProductFSM.description)
        await message.answer("📝 Введите описание товара (или «-» без описания):")

    @shop_router.message(StateFilter(ShopAddProductFSM.description))
    async def admin_add_product_price(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        desc = None if message.text.strip() == "-" else message.text.strip()
        await state.update_data(description=desc)
        await state.set_state(ShopAddProductFSM.price)
        await message.answer("💰 Введите цену в рублях (например: 299.00):")

    @shop_router.message(StateFilter(ShopAddProductFSM.price))
    async def admin_add_product_save(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        try:
            price = Decimal(message.text.strip().replace(",", "."))
            if price <= 0:
                raise ValueError
        except (ValueError, Exception):
            return await message.answer("❗ Введите корректную цену (число больше 0).")

        data = await state.get_data()
        await state.clear()

        async with async_session_maker() as session:
            product = Product(
                category_id=data["category_id"],
                name=data["name"],
                description=data.get("description"),
                price=price,
                is_available=True
            )
            session.add(product)
            await session.commit()

        await message.answer(
            f"✅ Товар <b>{data['name']}</b> добавлен по цене {price} ₽",
            reply_markup=admin_menu_kb()
        )

    @shop_router.message(F.text == "➖ Удалить товар")
    async def admin_delete_product_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return await message.answer("⛔ Нет доступа.")
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            categories = result.scalars().all()

        buttons = [(cat.name, f"delcat:{cat.id}") for cat in categories]
        await state.set_state(ShopDeleteProductFSM.category)
        await message.answer("Выберите категорию:", reply_markup=inline_kb(buttons))

    @shop_router.callback_query(StateFilter(ShopDeleteProductFSM.category), F.data.startswith("delcat:"))
    async def admin_delete_product_select(callback: CallbackQuery, state: FSMContext):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            result = await session.execute(
                select(Product).where(Product.category_id == cat_id)
            )
            products = result.scalars().all()

        if not products:
            await callback.answer("В этой категории нет товаров.", show_alert=True)
            await state.clear()
            return

        buttons = [(f"{p.name} ({p.price} ₽)", f"delprod:{p.id}") for p in products]
        await state.set_state(ShopDeleteProductFSM.product)
        await callback.message.answer("Выберите товар для удаления:", reply_markup=inline_kb(buttons))
        await callback.answer()

    @shop_router.callback_query(StateFilter(ShopDeleteProductFSM.product), F.data.startswith("delprod:"))
    async def admin_delete_product_confirm(callback: CallbackQuery, state: FSMContext):
        product_id = int(callback.data.split(":")[1])
        await state.clear()
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            name = product.name if product else "Товар"
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.commit()

        await callback.message.answer(f"🗑 Товар <b>{name}</b> удалён.", reply_markup=admin_menu_kb())
        await callback.answer()

    dp.include_router(shop_router)
    return shop_bot, dp


# ─────────────────────────── Running Bots ────────────────────────────────────

running_bots: dict[int, asyncio.Task] = {}


async def run_shop_bot(bot_record: ShopBot):
    """Run a single shop bot."""
    bot, dp = create_shop_bot(bot_record)
    logger.info(f"Starting shop bot '{bot_record.bot_name}' (id={bot_record.id})")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"Shop bot {bot_record.id} error: {e}")
    finally:
        await bot.session.close()


async def start_all_active_bots():
    """Load and start all active shop bots from DB."""
    async with async_session_maker() as session:
        result = await session.execute(select(ShopBot).where(ShopBot.is_active == True))
        bots = result.scalars().all()

    for bot_record in bots:
        task = asyncio.create_task(run_shop_bot(bot_record))
        running_bots[bot_record.id] = task
        logger.info(f"Scheduled shop bot {bot_record.id}: {bot_record.bot_name}")


# ─────────────────────────── Main Entry Point ────────────────────────────────

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    await init_db()

    # Start constructor bot
    constructor_bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(constructor_router)

    # Start all active shop bots
    await start_all_active_bots()

    logger.info("Constructor bot starting...")
    try:
        await dp.start_polling(constructor_bot, allowed_updates=["message", "callback_query"])
    finally:
        await constructor_bot.session.close()
        for task in running_bots.values():
            task.cancel()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
