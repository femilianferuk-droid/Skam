"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL, Crypto Pay API, YooMoney API
Auto-deploy to Bothost — reads BOT_TOKEN & DATABASE_URL from env, starts immediately.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, Numeric, String, Text,
    ForeignKey, select, func, update, delete, inspect
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import text

# ───────────────────────── Logging ─────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ───────────────────────── Config ─────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Bothost даёт postgresql://, SQLAlchemy ждёт postgresql+asyncpg://
if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("DATABASE_URL → adapted for asyncpg")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set in environment!")
    exit(1)
if not DATABASE_URL:
    logger.error("DATABASE_URL not set in environment!")
    exit(1)

# ───────────────────────── Database Models ─────────────────

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    bots = relationship("ShopBot", back_populates="owner", foreign_keys="ShopBot.owner_id")
    purchases = relationship("Purchase", back_populates="user")


class ShopBot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    owner = relationship("User", back_populates="bots", foreign_keys=[owner_id])
    categories = relationship("Category", back_populates="bot", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="bot")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    bot = relationship("ShopBot", back_populates="categories")
    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

    category = relationship("Category", back_populates="products")
    purchases = relationship("Purchase", back_populates="product")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="purchases")
    bot = relationship("ShopBot", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")


# ───────────────────────── DB Engine ───────────────────────

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create tables and add missing columns automatically."""
    async with engine.begin() as conn:
        # Create all tables if not exist
        await conn.run_sync(Base.metadata.create_all)
        
        # Add missing columns for existing tables
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='bots' AND column_name='yoomoney_token') THEN
                    ALTER TABLE bots ADD COLUMN yoomoney_token VARCHAR(255);
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='purchases' AND column_name='payment_label') THEN
                    ALTER TABLE purchases ADD COLUMN payment_label VARCHAR(255);
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='purchases' AND column_name='invoice_id') THEN
                    ALTER TABLE purchases ADD COLUMN invoice_id BIGINT;
                END IF;
            END $$;
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='purchases' AND column_name='paid_at') THEN
                    ALTER TABLE purchases ADD COLUMN paid_at TIMESTAMP;
                END IF;
            END $$;
        """))
    
    logger.info("Database tables ready with all columns.")


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str]) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


# ───────────────────────── Payment APIs ────────────────────

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
                    logger.error(f"CryptoBot invoice error: {data}")
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

    async def check_payment(self, label: str) -> Optional[dict]:
        if not self.token:
            logger.warning("YooMoney token not set, cannot check payment")
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/operation-history",
                    headers={"Authorization": f"Bearer {self.token}"},
                    json={"label": label, "records": 10, "type": "deposition"}
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"YooMoney API error: {data}")
                        return None
                    operations = data.get("operations", [])
                    for op in operations:
                        if op.get("label") == label and op.get("status") == "success":
                            return op
                    return None
        except Exception as e:
            logger.error(f"YooMoney check error: {e}")
            return None


# ───────────────────────── Keyboards ───────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Создать бота"), KeyboardButton(text="📋 Мои боты")],
            [KeyboardButton(text="👤 Профиль")],
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


# ───────────────────────── FSM States ──────────────────────

class CreateBotFSM(StatesGroup):
    token = State()
    name = State()
    admin_id = State()
    crypto_token = State()
    yoomoney_wallet = State()
    yoomoney_token = State()


class PaymentSettingsFSM(StatesGroup):
    crypto_token = State()
    yoomoney_wallet = State()
    yoomoney_token = State()


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


# ───────────────────────── Constructor Router ──────────────

router = Router()


# ── /start ─────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать в конструктор магазинов доната!\n\n"
        "Здесь вы можете создать собственного Telegram-бота для продажи доната "
        "в играх Supercell (Brawl Stars, Clash of Clans, Clash Royale).",
        reply_markup=main_menu_kb()
    )


# ── Создать бота ───────────────────────────────────────────

@router.message(F.text == "🛠 Создать бота")
async def start_create_bot(message: Message, state: FSMContext):
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        "🤖 <b>Шаг 1/6</b> — Введите токен бота.\n"
        "Получите его у @BotFather командой /newbot",
        reply_markup=cancel_kb()
    )


@router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer("❗ Некорректный токен. Попробуйте ещё раз.")

    async with async_session_maker() as session:
        existing = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if existing.scalar_one_or_none():
            return await message.answer("❗ Бот с таким токеном уже существует.")

    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer("✅ Токен принят.\n\n📝 <b>Шаг 2/6</b> — Введите название магазина:")


@router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer("❗ Название должно быть от 1 до 255 символов.")

    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer("✅ Название принято.\n\n👮 <b>Шаг 3/6</b> — Введите Telegram ID администратора:")


@router.message(StateFilter(CreateBotFSM.admin_id))
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
        "✅ Admin ID принят.\n\n💎 <b>Шаг 4/6</b> — Введите токен Crypto Bot (от @CryptoBot).\n"
        "Или отправьте <b>-</b> чтобы пропустить."
    )


@router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer(
        "💸 <b>Шаг 5/6</b> — Введите номер кошелька ЮMoney (например: 410011234567890).\n"
        "Или отправьте <b>-</b> чтобы пропустить."
    )


@router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_yoomoney_wallet(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    yoo_wallet = message.text.strip()
    await state.update_data(yoomoney_wallet=None if yoo_wallet == "-" else yoo_wallet)
    
    if yoo_wallet != "-":
        await state.set_state(CreateBotFSM.yoomoney_token)
        await message.answer(
            "🔑 <b>Шаг 6/6</b> — Введите OAuth-токен ЮMoney для проверки платежей.\n"
            "Получить: https://yoomoney.ru/api/oauth\n"
            "Или отправьте <b>-</b> чтобы пропустить."
        )
    else:
        await finalize_bot_creation(message, state)


@router.message(StateFilter(CreateBotFSM.yoomoney_token))
async def create_bot_yoomoney_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    yoo_token = message.text.strip()
    await state.update_data(yoomoney_token=None if yoo_token == "-" else yoo_token)
    await finalize_bot_creation(message, state)


async def finalize_bot_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        bot_record = ShopBot(
            owner_id=message.from_user.id,
            bot_token=data["token"],
            bot_name=data["name"],
            admin_id=data["admin_id"],
            crypto_bot_token=data.get("crypto_token"),
            yoomoney_wallet=data.get("yoomoney_wallet"),
            yoomoney_token=data.get("yoomoney_token"),
            is_active=True
        )
        session.add(bot_record)
        await session.commit()
        await session.refresh(bot_record)

        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    payments = []
    if bot_record.crypto_bot_token:
        payments.append("Crypto Bot ✅")
    if bot_record.yoomoney_wallet:
        payments.append(f"ЮMoney ✅")
    
    await message.answer(
        f"✅ <b>Бот «{data['name']}» создан!</b>\n\n"
        f"🔑 Токен: <code>{data['token']}</code>\n"
        f"👮 Admin ID: <code>{data['admin_id']}</code>\n"
        f"💳 Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"Для управления зайдите в админ-панель созданного бота.",
        reply_markup=main_menu_kb()
    )


# ── Мои боты ───────────────────────────────────────────────

@router.message(F.text == "📋 Мои боты")
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

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="⏸ Остановить" if bot.is_active else "▶️ Запустить",
                callback_data=f"toggle_bot:{bot.id}"
            ),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot.id}"),
        ], [
            InlineKeyboardButton(text="💳 Платежи", callback_data=f"payment_settings:{bot.id}"),
            InlineKeyboardButton(text="🧪 Тест оплаты", callback_data=f"test_payment:{bot.id}"),
        ]])
        await message.answer(
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"Статус: {status}\n"
            f"Оплата: {', '.join(payments) or '—'}\n"
            f"ID: <code>{bot.id}</code>",
            reply_markup=kb
        )


@router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            return await callback.answer("Бот не найден.")
        bot.is_active = not bot.is_active
        await session.commit()
    await callback.answer(f"Бот {'запущен' if bot.is_active else 'остановлен'}.")
    await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete"),
    ]])
    await callback.message.answer("Удалить бота?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(
            delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id)
        )
        await session.commit()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🗑 Бот удалён.")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено.")


# ── Платёжные реквизиты ──────────────────────────────────

@router.callback_query(F.data.startswith("payment_settings:"))
async def show_payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
    
    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")

    crypto_status = "✅ Настроен" if bot.crypto_bot_token else "❌ Не настроен"
    yoo_status = "✅ Настроен" if bot.yoomoney_wallet else "❌ Не настроен"
    yoo_token_status = "✅ Настроен" if bot.yoomoney_token else "❌ Не настроен"

    text = (
        f"💳 <b>Платёжные реквизиты бота «{bot.bot_name}»</b>\n\n"
        f"💎 Crypto Bot: {crypto_status}\n"
        f"💸 ЮMoney кошелёк: {yoo_status}\n"
        f"🔑 ЮMoney токен: {yoo_token_status}\n\n"
        f"Выберите действие:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Изменить Crypto Bot токен", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text="💸 Изменить ЮMoney кошелёк", callback_data=f"edit_yoo_wallet:{bot_id}")],
        [InlineKeyboardButton(text="🔑 Изменить ЮMoney токен", callback_data=f"edit_yoo_token:{bot_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_token_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer(
        "💎 Введите новый токен Crypto Bot:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_token_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    await state.clear()

    token = None if message.text.strip() == "-" else message.text.strip()

    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot).where(ShopBot.id == bot_id).values(crypto_bot_token=token)
        )
        await session.commit()

    await message.answer("✅ Токен Crypto Bot обновлён!", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("edit_yoo_wallet:"))
async def edit_yoo_wallet_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer(
        "💸 Введите номер кошелька ЮMoney:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_wallet_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    await state.clear()

    wallet = None if message.text.strip() == "-" else message.text.strip()

    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot).where(ShopBot.id == bot_id).values(yoomoney_wallet=wallet)
        )
        await session.commit()

    await message.answer("✅ Кошелёк ЮMoney обновлён!", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("edit_yoo_token:"))
async def edit_yoo_token_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_token)
    await callback.message.answer(
        "🔑 Введите OAuth-токен ЮMoney:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(StateFilter(PaymentSettingsFSM.yoomoney_token))
async def edit_yoo_token_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    await state.clear()

    token = None if message.text.strip() == "-" else message.text.strip()

    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot).where(ShopBot.id == bot_id).values(yoomoney_token=token)
        )
        await session.commit()

    await message.answer("✅ Токен ЮMoney обновлён!", reply_markup=main_menu_kb())


# ── Тестовая оплата ────────────────────────────────────────

@router.callback_query(F.data.startswith("test_payment:"))
async def test_payment_menu(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        categories_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        categories = categories_result.scalars().all()

    if not categories:
        return await callback.answer("Нет категорий. Создайте товары!", show_alert=True)

    cat = categories[0]
    
    async with async_session_maker() as session:
        products_result = await session.execute(
            select(Product).where(Product.category_id == cat.id, Product.is_available == True)
        )
        products = products_result.scalars().all()

    if not products:
        return await callback.answer("Нет товаров в категории.", show_alert=True)

    product = products[0]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💎 Оплатить через Crypto Bot", callback_data=f"do_crypto:{bot_id}:{product.id}")
        ])
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💸 Оплатить через ЮMoney", callback_data=f"do_yoomoney:{bot_id}:{product.id}")
        ])
    
    if not kb.inline_keyboard:
        return await callback.answer("Нет настроенных платёжных систем!", show_alert=True)

    await callback.message.answer(
        f"🧪 <b>Тестовая оплата</b>\n\n"
        f"Товар: {product.name}\n"
        f"Цена: {product.price} ₽\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_crypto:"))
async def test_crypto_payment(callback: CallbackQuery):
    _, bot_id, product_id = callback.data.split(":")
    bot_id, product_id = int(bot_id), int(product_id)

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        product = await session.get(Product, product_id)

        if not bot.crypto_bot_token:
            return await callback.answer("Crypto Bot не настроен!", show_alert=True)

        purchase = Purchase(
            user_id=callback.from_user.id,
            bot_id=bot_id,
            product_id=product_id,
            amount=product.price,
            status="pending",
            payment_method="crypto_bot"
        )
        session.add(purchase)
        await session.commit()
        await session.refresh(purchase)

        api = CryptoBotAPI(bot.crypto_bot_token)
        invoice = await api.create_invoice(
            amount=float(product.price),
            description=f"Тестовая покупка: {product.name}",
            payload=f"test_{purchase.id}"
        )

    if not invoice:
        return await callback.message.answer("❌ Ошибка создания счёта!")

    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
    invoice_id = invoice.get("invoice_id")

    async with async_session_maker() as session:
        await session.execute(
            update(Purchase).where(Purchase.id == purchase.id).values(invoice_id=invoice_id)
        )
        await session.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_crypto_pay:{purchase.id}:{invoice_id}")],
    ])

    await callback.message.answer(
        f"🧾 <b>Счёт создан!</b>\n\n"
        f"Товар: {product.name}\n"
        f"Сумма: {product.price} ₽\n"
        f"ID платежа: <code>{purchase.id}</code>\n\n"
        f"1. Нажмите «Оплатить»\n"
        f"2. Оплатите через Crypto Bot\n"
        f"3. Вернитесь и нажмите «Проверить оплату»",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_crypto_pay:"))
async def check_crypto_payment_status(callback: CallbackQuery):
    _, purchase_id, invoice_id = callback.data.split(":")
    purchase_id, invoice_id = int(purchase_id), int(invoice_id)

    async with async_session_maker() as session:
        purchase = await session.get(Purchase, purchase_id)
        bot = await session.get(ShopBot, purchase.bot_id)
        api = CryptoBotAPI(bot.crypto_bot_token)
        invoices = await api.get_invoices([invoice_id])

    if not invoices:
        return await callback.answer("Не удалось проверить статус.", show_alert=True)

    invoice_data = invoices[0]
    if invoice_data.get("status") == "paid":
        async with async_session_maker() as session:
            await session.execute(
                update(Purchase).where(Purchase.id == purchase_id).values(
                    status="completed",
                    paid_at=datetime.now()
                )
            )
            await session.commit()

        await callback.message.answer("✅ <b>Оплата подтверждена!</b>\n\nПлатёж прошёл успешно! 🎉")
    else:
        await callback.answer("⏳ Оплата ещё не получена.", show_alert=True)


@router.callback_query(F.data.startswith("do_yoomoney:"))
async def test_yoomoney_payment(callback: CallbackQuery):
    _, bot_id, product_id = callback.data.split(":")
    bot_id, product_id = int(bot_id), int(product_id)

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        product = await session.get(Product, product_id)

        if not bot.yoomoney_wallet:
            return await callback.answer("ЮMoney не настроен!", show_alert=True)

        label = f"test_{bot_id}_{product_id}_{int(time.time())}"
        
        purchase = Purchase(
            user_id=callback.from_user.id,
            bot_id=bot_id,
            product_id=product_id,
            amount=product.price,
            status="pending",
            payment_method="yoomoney",
            payment_label=label
        )
        session.add(purchase)
        await session.commit()
        await session.refresh(purchase)

        yoo = YooMoneyAPI(bot.yoomoney_wallet, bot.yoomoney_token or "")
        pay_url = yoo.generate_form_url(
            amount=float(product.price),
            label=label,
            comment=f"Тестовая покупка: {product.name}"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)],
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_yoo_pay:{purchase.id}:{label}")],
    ])

    await callback.message.answer(
        f"🧾 <b>Счёт создан!</b>\n\n"
        f"Товар: {product.name}\n"
        f"Сумма: {product.price} ₽\n"
        f"Метка: <code>{label}</code>\n\n"
        f"1. Нажмите «Оплатить»\n"
        f"2. Оплатите через ЮMoney\n"
        f"3. Вернитесь и нажмите «Проверить оплату»",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_yoo_pay:"))
async def check_yoomoney_payment_status(callback: CallbackQuery):
    _, purchase_id, label = callback.data.split(":")
    purchase_id = int(purchase_id)

    async with async_session_maker() as session:
        purchase = await session.get(Purchase, purchase_id)
        bot = await session.get(ShopBot, purchase.bot_id)
        yoo = YooMoneyAPI(bot.yoomoney_wallet, bot.yoomoney_token or "")
        result = await yoo.check_payment(label)

    if result:
        async with async_session_maker() as session:
            await session.execute(
                update(Purchase).where(Purchase.id == purchase_id).values(
                    status="completed",
                    paid_at=datetime.now()
                )
            )
            await session.commit()

        await callback.message.answer(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"Сумма: {result.get('amount')} ₽\n"
            f"Платёж прошёл успешно! 🎉"
        )
    else:
        await callback.answer("⏳ Оплата не найдена. Оплатите и попробуйте снова.", show_alert=True)


# ── Профиль ────────────────────────────────────────────────

@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
    
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"Баланс: {user.balance} ₽\n"
        f"Ботов создано: {bots_count}"
    )


# ───────────────────────── Main ────────────────────────────

async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
