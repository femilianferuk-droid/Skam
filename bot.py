"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL, Crypto Pay API, YooMoney API
Auto-deploy to Bothost.
"""

import asyncio, logging, os, time
from datetime import datetime
from decimal import Decimal
from typing import Optional
from urllib.parse import quote

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
    ForeignKey, select, func, update, delete
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import text

# ═══════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("DATABASE_URL adapted for asyncpg")

if not BOT_TOKEN or not DATABASE_URL:
    logger.error("BOT_TOKEN or DATABASE_URL not set!")
    exit(1)

# ═══════════════════════════════════════════════════════════
# DATABASE MODELS
# ═══════════════════════════════════════════════════════════

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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    user = relationship("User", back_populates="purchases")
    bot = relationship("ShopBot", back_populates="purchases")
    product = relationship("Product", back_populates="purchases")

# ═══════════════════════════════════════════════════════════
# DATABASE ENGINE
# ═══════════════════════════════════════════════════════════

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database ready.")

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str]) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

# ═══════════════════════════════════════════════════════════
# PAYMENT APIS
# ═══════════════════════════════════════════════════════════

class CryptoBotAPI:
    BASE_URL = "https://pay.crypt.bot/api"
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Crypto-Pay-API-Token": token}

    async def create_invoice(self, amount: float, description: str, payload: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/createInvoice", headers=self.headers,
                    json={
                        "currency_type": "fiat", "fiat": "RUB", "amount": str(amount),
                        "description": description, "payload": payload,
                        "paid_btn_name": "callback", "paid_btn_url": "https://t.me/",
                    }
                ) as resp:
                    data = await resp.json()
                    return data["result"] if data.get("ok") else None
        except Exception as e:
            logger.error(f"CryptoBot error: {e}")
            return None

class YooMoneyAPI:
    def __init__(self, wallet: str):
        self.wallet = wallet

    def generate_form_url(self, amount: float, label: str, comment: str) -> str:
        return (
            f"https://yoomoney.ru/quickpay/confirm.xml?"
            f"receiver={self.wallet}&quickpay-form=button"
            f"&targets={quote(comment)}&sum={amount}&label={label}&successURL="
        )

# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛠 Создать бота"), KeyboardButton(text="📋 Мои боты")],
        [KeyboardButton(text="👤 Профиль")],
    ], resize_keyboard=True)

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Купить донат"), KeyboardButton(text="📦 Мои покупки")],
        [KeyboardButton(text="👤 Профиль")],
    ], resize_keyboard=True)

def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📨 Рассылка")],
        [KeyboardButton(text="📋 Управление категориями")],
        [KeyboardButton(text="➕ Выставить товар"), KeyboardButton(text="➖ Удалить товар")],
        [KeyboardButton(text="💳 Платёжные реквизиты")],
        [KeyboardButton(text="👥 Мои покупатели")],
        [KeyboardButton(text="🏠 Выйти из админ-панели")],
    ], resize_keyboard=True)

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])

# ═══════════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════════

class CreateBotFSM(StatesGroup):
    token = State()
    name = State()
    admin_id = State()
    crypto_token = State()
    yoomoney_wallet = State()

class PaymentSettingsFSM(StatesGroup):
    crypto_token = State()
    yoomoney_wallet = State()

class ShopAddCategoryFSM(StatesGroup):
    name = State()

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

# ═══════════════════════════════════════════════════════════
# CONSTRUCTOR BOT ROUTER
# ═══════════════════════════════════════════════════════════

constructor_router = Router()

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать в конструктор магазинов доната!\n\n"
        "Создайте бота для продажи доната в играх Supercell.",
        reply_markup=main_menu_kb()
    )

@constructor_router.message(F.text == "🛠 Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    await state.set_state(CreateBotFSM.token)
    await message.answer("🤖 <b>Шаг 1/5</b> — Токен бота от @BotFather:", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer("❗ Некорректный токен.")
    async with async_session_maker() as session:
        exists = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if exists.scalar_one_or_none():
            return await message.answer("❗ Бот с таким токеном уже есть.")
    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer("📝 <b>Шаг 2/5</b> — Название магазина:")

@constructor_router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    name = message.text.strip()
    if not name:
        return await message.answer("❗ Введите название.")
    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer("👮 <b>Шаг 3/5</b> — Telegram ID администратора:")

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        return await message.answer("❗ Введите числовой ID.")
    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer("💎 <b>Шаг 4/5</b> — Токен Crypto Bot (или «-»):")

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer("💸 <b>Шаг 5/5</b> — Номер ЮMoney (или «-»):")

@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_finish(message: Message, state: FSMContext):
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

        # Auto-create default categories
        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    # Start the created bot
    asyncio.create_task(run_shop_bot(bot_record))

    payments = []
    if bot_record.crypto_bot_token:
        payments.append("Crypto Bot")
    if bot_record.yoomoney_wallet:
        payments.append("YooMoney")

    await message.answer(
        f"✅ <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"Токен: <code>{data['token']}</code>\n"
        f"Admin ID: <code>{data['admin_id']}</code>\n"
        f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"Перейдите в бота и нажмите /start\n"
        f"Админ увидит админ-панель автоматически",
        reply_markup=main_menu_kb()
    )

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id)
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer("У вас пока нет ботов.")

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token:
            payments.append("Crypto Bot")
        if bot.yoomoney_wallet:
            payments.append("YooMoney")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸ Остановить" if bot.is_active else "▶️ Запустить",
                    callback_data=f"toggle_bot:{bot.id}"
                ),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot.id}")
            ],
            [
                InlineKeyboardButton(text="💳 Платежи", callback_data=f"payment_settings:{bot.id}"),
                InlineKeyboardButton(text="🧪 Тест оплаты", callback_data=f"test_payment:{bot.id}")
            ]
        ])
        await message.answer(
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"Статус: {status}\n"
            f"Платежи: {', '.join(payments) or '—'}",
            reply_markup=kb
        )

@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if bot and bot.owner_id == callback.from_user.id:
            bot.is_active = not bot.is_active
            await session.commit()
            await callback.answer(f"Бот {'запущен' if bot.is_active else 'остановлен'}.")

@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
        ]
    ])
    await callback.message.answer("Удалить бота?", reply_markup=kb)

@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(
            delete(ShopBot).where(
                ShopBot.id == bot_id,
                ShopBot.owner_id == callback.from_user.id
            )
        )
        await session.commit()
    await callback.message.answer("🗑 Бот удалён.")

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.answer("Отменено.")

@constructor_router.callback_query(F.data.startswith("payment_settings:"))
async def payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)

    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")

    text = (
        f"💳 <b>Платежи «{bot.bot_name}»</b>\n\n"
        f"Crypto Bot: {'✅' if bot.crypto_bot_token else '❌'}\n"
        f"YooMoney: {'✅' if bot.yoomoney_wallet else '❌'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Crypto Bot токен", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text="💸 YooMoney кошелёк", callback_data=f"edit_yoo:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer("💎 Токен Crypto Bot (или «-»):", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data()
    await state.clear()
    token = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == data["edit_bot_id"])
            .values(crypto_bot_token=token)
        )
        await session.commit()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer("💸 Номер YooMoney (или «-»):", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data()
    await state.clear()
    wallet = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == data["edit_bot_id"])
            .values(yoomoney_wallet=wallet)
        )
        await session.commit()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("test_payment:"))
async def test_payment(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()

    if not cats:
        return await callback.answer("Нет категорий.")

    async with async_session_maker() as session:
        products_result = await session.execute(
            select(Product).where(
                Product.category_id == cats[0].id,
                Product.is_available == True
            )
        )
        products = products_result.scalars().all()

    if not products:
        return await callback.answer("Нет товаров.")

    p = products[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💎 Crypto Bot", callback_data=f"do_crypto:{bot_id}:{p.id}")
        ])
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💸 YooMoney", callback_data=f"do_yoo:{bot_id}:{p.id}")
        ])

    if not kb.inline_keyboard:
        return await callback.answer("Нет платёжных систем!")

    await callback.message.answer(
        f"🧪 <b>Тест оплаты</b>\n\n{p.name} — {p.price} ₽",
        reply_markup=kb
    )

@constructor_router.callback_query(F.data.startswith("do_crypto:"))
async def do_crypto(callback: CallbackQuery):
    _, bot_id, product_id = callback.data.split(":")
    bot_id, product_id = int(bot_id), int(product_id)

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        product = await session.get(Product, product_id)

        if not bot or not bot.crypto_bot_token:
            return await callback.answer("Crypto Bot не настроен!")

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
            float(product.price),
            f"Тест: {product.name}",
            str(purchase.id)
        )

    if not invoice:
        return await callback.message.answer("❌ Ошибка создания счёта!")

    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить", url=pay_url)]
    ])
    await callback.message.answer(
        f"🧾 <b>Счёт создан!</b>\n\n{product.name}\n{product.price} ₽\n\nНажмите «Оплатить» 👇",
        reply_markup=kb
    )

@constructor_router.callback_query(F.data.startswith("do_yoo:"))
async def do_yoo(callback: CallbackQuery):
    _, bot_id, product_id = callback.data.split(":")
    bot_id, product_id = int(bot_id), int(product_id)

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        product = await session.get(Product, product_id)

        if not bot or not bot.yoomoney_wallet:
            return await callback.answer("YooMoney не настроен!")

        label = f"test_{bot_id}_{product_id}_{int(time.time())}"

        purchase = Purchase(
            user_id=callback.from_user.id,
            bot_id=bot_id,
            product_id=product_id,
            amount=product.price,
            status="pending",
            payment_method=f"yoomoney:{label}"
        )
        session.add(purchase)
        await session.commit()

        yoo = YooMoneyAPI(bot.yoomoney_wallet)
        pay_url = yoo.generate_form_url(
            float(product.price),
            label,
            f"Тест: {product.name}"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через YooMoney", url=pay_url)]
    ])
    await callback.message.answer(
        f"🧾 <b>Счёт создан!</b>\n\n{product.name}\n{product.price} ₽\n\nНажмите «Оплатить» 👇",
        reply_markup=kb
    )

@constructor_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Баланс: {user.balance} ₽\n"
        f"Ботов создано: {bots_count}"
    )

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY (ДОЧЕРНИЙ БОТ С ПОЛНОЙ АДМИН-ПАНЕЛЬЮ)
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    shop_router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id == bot_record.admin_id

    # ── /start ─────────────────────────────────────────────

    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)

        if is_admin(message.from_user.id):
            await message.answer(
                f"🎮 <b>Админ-панель</b>\n\n"
                f"Магазин: <b>{bot_record.bot_name}</b>\n"
                f"Выберите действие:",
                reply_markup=admin_menu_kb()
            )
        else:
            await message.answer(
                f"🎮 Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
                f"Здесь можно купить донат для игр Supercell.",
                reply_markup=shop_menu_kb()
            )

    # ── Выход из админ-панели ─────────────────────────────

    @shop_router.message(F.text == "🏠 Выйти из админ-панели")
    async def exit_admin(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("Вы вышли из админ-панели.", reply_markup=shop_menu_kb())

    # ── Купить донат (для обычных пользователей) ──────────

    @shop_router.message(F.text == "🛒 Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = result.scalars().all()

        if not cats:
            return await message.answer("😔 Пока нет доступных категорий.")

        await message.answer(
            "🎮 Выберите игру:",
            reply_markup=inline_kb([(c.name, f"shop_cat:{c.id}") for c in cats])
        )

    @shop_router.callback_query(F.data.startswith("shop_cat:"))
    async def show_products(callback: CallbackQuery):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            products_result = await session.execute(
                select(Product).where(
                    Product.category_id == cat_id,
                    Product.is_available == True
                )
            )
            products = products_result.scalars().all()
            cat = await session.get(Category, cat_id)

        if not products:
            return await callback.answer("В этой категории пока нет товаров.", show_alert=True)

        await callback.message.answer(
            f"📦 <b>{cat.name}</b>:",
            reply_markup=inline_kb([
                (f"{p.name} — {p.price} ₽", f"shop_product:{p.id}") for p in products
            ])
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("shop_product:"))
    async def product_detail(callback: CallbackQuery):
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

        btns = []
        if bot_record.crypto_bot_token:
            btns.append(("💎 Crypto Bot", f"pay_crypto:{product_id}"))
        if bot_record.yoomoney_wallet:
            btns.append(("💸 ЮMoney", f"pay_yoo:{product_id}"))

        if not btns:
            return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")

        await callback.message.answer(
            text + "\n\n💳 Выберите способ оплаты:",
            reply_markup=inline_kb(btns)
        )
        await callback.answer()

    # ── Crypto Bot оплата ─────────────────────────────────

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.")

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
                float(product.price),
                f"Покупка: {product.name}",
                str(purchase.id)
            )

        if not invoice:
            return await callback.message.answer("❌ Ошибка создания счёта!")

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Оплатить", url=pay_url)]
        ])
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price} ₽\n\n"
            f"Нажмите «Оплатить» 👇",
            reply_markup=kb
        )
        await callback.answer()

    # ── ЮMoney оплата ─────────────────────────────────────

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.")

            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"

            purchase = Purchase(
                user_id=callback.from_user.id,
                bot_id=bot_record.id,
                product_id=product_id,
                amount=product.price,
                status="pending",
                payment_method=f"yoomoney:{label}"
            )
            session.add(purchase)
            await session.commit()

            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(
                float(product.price),
                label,
                f"Покупка: {product.name}"
            )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)]
        ])
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price} ₽\n\n"
            f"Нажмите «Оплатить» 👇",
            reply_markup=kb
        )
        await callback.answer()

    # ── Мои покупки ───────────────────────────────────────

    @shop_router.message(F.text == "📦 Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Purchase, Product)
                .join(Product)
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id
                )
                .order_by(Purchase.created_at.desc())
                .limit(20)
            )
            rows = result.all()

        if not rows:
            return await message.answer("У вас пока нет покупок.")

        text = "📦 <b>Ваши покупки:</b>\n\n"
        status_map = {"pending": "⏳ Ожидает", "completed": "✅ Завершена"}
        for purchase, product in rows:
            text += (
                f"🛍 {product.name} — {purchase.amount} ₽ | "
                f"{status_map.get(purchase.status, purchase.status)}\n"
            )
        await message.answer(text)

    # ── Профиль в магазине ────────────────────────────────

    @shop_router.message(F.text == "👤 Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(
                session, message.from_user.id, message.from_user.username
            )
            total = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id,
                    Purchase.status == "completed"
                )
            )
        await message.answer(
            f"👤 <b>Профиль</b>\n\n"
            f"ID: <code>{message.from_user.id}</code>\n"
            f"Баланс: {user.balance} ₽\n"
            f"Потрачено: {total} ₽"
        )

    # ═══════════════════════════════════════════════════════
    # АДМИН-ПАНЕЛЬ
    # ═══════════════════════════════════════════════════════

    # ── Статистика ────────────────────────────────────────

    @shop_router.message(F.text == "📊 Статистика")
    async def admin_stats(message: Message):
        if not is_admin(message.from_user.id):
            return
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
            products_count = await session.scalar(
                select(func.count(Product.id))
                .where(Product.category_id.in_(
                    select(Category.id).where(Category.bot_id == bot_record.id)
                ))
            )

        await message.answer(
            f"📊 <b>Статистика магазина</b>\n\n"
            f"👥 Уникальных покупателей: {users_count or 0}\n"
            f"📦 Товаров: {products_count}\n"
            f"🛒 Продаж: {purchases_count or 0}\n"
            f"💰 Выручка: {revenue or 0} ₽"
        )

    # ── Мои покупатели ────────────────────────────────────

    @shop_router.message(F.text == "👥 Мои покупатели")
    async def admin_buyers(message: Message):
        if not is_admin(message.from_user.id):
            return
        async with async_session_maker() as session:
            result = await session.execute(
                select(
                    User.telegram_id,
                    User.username,
                    func.count(Purchase.id),
                    func.sum(Purchase.amount)
                )
                .join(Purchase, User.telegram_id == Purchase.user_id)
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed")
                .group_by(User.telegram_id, User.username)
                .order_by(func.sum(Purchase.amount).desc())
                .limit(20)
            )
            buyers = result.all()

        if not buyers:
            return await message.answer("Пока нет покупателей.")

        text = "👥 <b>Топ покупателей:</b>\n\n"
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            text += f"{i}. @{username or tid} — {count} пок. на {total} ₽\n"
        await message.answer(text)

    # ── Управление категориями ────────────────────────────

    @shop_router.message(F.text == "📋 Управление категориями")
    async def admin_categories(message: Message):
        if not is_admin(message.from_user.id):
            return
        async with async_session_maker() as session:
            cats_result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = cats_result.scalars().all()
            products_counts = {}
            for cat in cats:
                products_counts[cat.id] = await session.scalar(
                    select(func.count(Product.id)).where(Product.category_id == cat.id)
                )

        text = "📋 <b>Категории:</b>\n\n"
        for cat in cats:
            text += f"• {cat.name} ({products_counts.get(cat.id, 0)} товаров)\n"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="add_category")],
            [InlineKeyboardButton(text="🗑 Удалить категорию", callback_data="del_category_menu")],
        ])
        await message.answer(text, reply_markup=kb)

    @shop_router.callback_query(F.data == "add_category")
    async def add_category_start(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return await callback.answer("Нет доступа.")
        await state.set_state(ShopAddCategoryFSM.name)
        await callback.message.answer(
            "✏️ Введите название новой категории:",
            reply_markup=cancel_kb()
        )
        await callback.answer()

    @shop_router.message(StateFilter(ShopAddCategoryFSM.name))
    async def add_category_save(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        name = message.text.strip()
        if not name:
            return await message.answer("❗ Введите название.")
        await state.clear()
        async with async_session_maker() as session:
            session.add(Category(bot_id=bot_record.id, name=name))
            await session.commit()
        await message.answer(f"✅ Категория «{name}» добавлена!", reply_markup=admin_menu_kb())

    @shop_router.callback_query(F.data == "del_category_menu")
    async def del_category_menu(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer("Нет доступа.")
        async with async_session_maker() as session:
            cats_result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = cats_result.scalars().all()
        if not cats:
            return await callback.answer("Нет категорий.")
        await callback.message.answer(
            "Выберите категорию для удаления:",
            reply_markup=inline_kb([(c.name, f"del_category:{c.id}") for c in cats])
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("del_category:"))
    async def del_category_confirm(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return await callback.answer("Нет доступа.")
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            cat = await session.get(Category, cat_id)
            name = cat.name if cat else "Категория"
            await session.execute(
                delete(Category).where(
                    Category.id == cat_id,
                    Category.bot_id == bot_record.id
                )
            )
            await session.commit()
        await callback.message.answer(
            f"🗑 Категория «{name}» удалена.",
            reply_markup=admin_menu_kb()
        )
        await callback.answer()

    # ── Выставить товар ───────────────────────────────────

    @shop_router.message(F.text == "➕ Выставить товар")
    async def admin_add_product_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        async with async_session_maker() as session:
            cats_result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = cats_result.scalars().all()

        if not cats:
            return await message.answer(
                "Нет категорий. Создайте категорию в «📋 Управление категориями»."
            )

        await state.set_state(ShopAddProductFSM.category)
        await message.answer(
            "Выберите категорию:",
            reply_markup=inline_kb([(c.name, f"addcat:{c.id}") for c in cats])
        )

    @shop_router.callback_query(
        StateFilter(ShopAddProductFSM.category),
        F.data.startswith("addcat:")
    )
    async def add_product_name(callback: CallbackQuery, state: FSMContext):
        await state.update_data(category_id=int(callback.data.split(":")[1]))
        await state.set_state(ShopAddProductFSM.name)
        await callback.message.answer("✏️ Введите название товара:", reply_markup=cancel_kb())
        await callback.answer()

    @shop_router.message(StateFilter(ShopAddProductFSM.name))
    async def add_product_desc(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        await state.update_data(name=message.text.strip())
        await state.set_state(ShopAddProductFSM.description)
        await message.answer("📝 Введите описание товара (или «-» пропустить):")

    @shop_router.message(StateFilter(ShopAddProductFSM.description))
    async def add_product_price(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        desc = None if message.text.strip() == "-" else message.text.strip()
        await state.update_data(description=desc)
        await state.set_state(ShopAddProductFSM.price)
        await message.answer("💰 Введите цену в рублях (например: 299.00):")

    @shop_router.message(StateFilter(ShopAddProductFSM.price))
    async def add_product_save(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        try:
            price = Decimal(message.text.strip().replace(",", "."))
            if price <= 0:
                raise ValueError
        except (ValueError, Exception):
            return await message.answer("❗ Некорректная цена. Пример: 299.00")

        data = await state.get_data()
        await state.clear()

        async with async_session_maker() as session:
            product = Product(
                category_id=data["category_id"],
                name=data["name"],
                description=data.get("description"),
                price=price
            )
            session.add(product)
            await session.commit()

        await message.answer(
            f"✅ Товар «{data['name']}» добавлен за {price} ₽!",
            reply_markup=admin_menu_kb()
        )

    # ── Удалить товар ─────────────────────────────────────

    @shop_router.message(F.text == "➖ Удалить товар")
    async def admin_del_product_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        async with async_session_maker() as session:
            cats_result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = cats_result.scalars().all()

        if not cats:
            return await message.answer("Нет категорий.")

        await state.set_state(ShopDeleteProductFSM.category)
        await message.answer(
            "Выберите категорию:",
            reply_markup=inline_kb([(c.name, f"delcat:{c.id}") for c in cats])
        )

    @shop_router.callback_query(
        StateFilter(ShopDeleteProductFSM.category),
        F.data.startswith("delcat:")
    )
    async def del_product_select(callback: CallbackQuery, state: FSMContext):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            products_result = await session.execute(
                select(Product).where(Product.category_id == cat_id)
            )
            products = products_result.scalars().all()

        if not products:
            await callback.answer("Нет товаров.", show_alert=True)
            await state.clear()
            return

        await state.set_state(ShopDeleteProductFSM.product)
        await callback.message.answer(
            "Выберите товар:",
            reply_markup=inline_kb([
                (f"{p.name} ({p.price} ₽)", f"delprod:{p.id}") for p in products
            ])
        )
        await callback.answer()

    @shop_router.callback_query(
        StateFilter(ShopDeleteProductFSM.product),
        F.data.startswith("delprod:")
    )
    async def del_product_confirm(callback: CallbackQuery, state: FSMContext):
        product_id = int(callback.data.split(":")[1])
        await state.clear()
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            name = product.name if product else "Товар"
            await session.execute(delete(Product).where(Product.id == product_id))
            await session.commit()
        await callback.message.answer(
            f"🗑 Товар «{name}» удалён.",
            reply_markup=admin_menu_kb()
        )
        await callback.answer()

    # ── Рассылка ──────────────────────────────────────────

    @shop_router.message(F.text == "📨 Рассылка")
    async def broadcast_start(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.set_state(ShopBroadcastFSM.message_text)
        await message.answer("✍️ Введите текст рассылки:", reply_markup=cancel_kb())

    @shop_router.message(StateFilter(ShopBroadcastFSM.message_text))
    async def broadcast_send(message: Message, state: FSMContext):
        if message.text == "❌ Отмена":
            await state.clear()
            return await message.answer("Отменено.", reply_markup=admin_menu_kb())
        await state.clear()
        async with async_session_maker() as session:
            result = await session.execute(
                select(Purchase.user_id.distinct())
                .where(Purchase.bot_id == bot_record.id)
            )
            user_ids = [row[0] for row in result.all()]

        sent = 0
        for uid in user_ids:
            try:
                await message.bot.send_message(uid, message.text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass

        await message.answer(
            f"📨 Рассылка завершена!\n✅ Отправлено: {sent}",
            reply_markup=admin_menu_kb()
        )

    # ── Платёжные реквизиты ───────────────────────────────

    @shop_router.message(F.text == "💳 Платёжные реквизиты")
    async def admin_payment_settings(message: Message):
        if not is_admin(message.from_user.id):
            return
        text = (
            f"💳 <b>Платежи «{bot_record.bot_name}»</b>\n\n"
            f"💎 Crypto Bot: {'✅' if bot_record.crypto_bot_token else '❌'}\n"
            f"💸 YooMoney: {'✅' if bot_record.yoomoney_wallet else '❌'}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💎 Crypto Bot токен",
                callback_data=f"edit_crypto:{bot_record.id}"
            )],
            [InlineKeyboardButton(
                text="💸 YooMoney кошелёк",
                callback_data=f"edit_yoo:{bot_record.id}"
            )],
        ])
        await message.answer(text, reply_markup=kb)

    return shop_router

# ═══════════════════════════════════════════════════════════
# RUNNING BOTS
# ═══════════════════════════════════════════════════════════

running_tasks: dict[int, asyncio.Task] = {}

async def run_shop_bot(bot_record: ShopBot):
    """Запускает одного shop-бота."""
    if bot_record.id in running_tasks:
        logger.warning(f"Bot {bot_record.id} already running")
        return

    bot = Bot(
        token=bot_record.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(create_shop_router(bot_record))

    async def polling():
        logger.info(f"Shop bot '{bot_record.bot_name}' (id={bot_record.id}) started")
        try:
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        except Exception as e:
            logger.error(f"Shop bot {bot_record.id} error: {e}")
        finally:
            await bot.session.close()

    task = asyncio.create_task(polling())
    running_tasks[bot_record.id] = task

async def start_all_active_bots():
    """Запускает все активные shop-боты из БД."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.is_active == True)
        )
        bots = result.scalars().all()

    for bot_record in bots:
        await run_shop_bot(bot_record)
        await asyncio.sleep(0.5)

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    await init_db()

    # Запускаем конструктор
    constructor_bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(constructor_router)

    # Запускаем все активные shop-боты
    await start_all_active_bots()

    logger.info("Constructor bot starting...")
    try:
        await dp.start_polling(
            constructor_bot,
            allowed_updates=["message", "callback_query"]
        )
    finally:
        await constructor_bot.session.close()
        for task in running_tasks.values():
            task.cancel()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
