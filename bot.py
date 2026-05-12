"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL, Crypto Pay API, YooMoney API
Auto-deploy to Bothost — reads BOT_TOKEN & DATABASE_URL from env, starts immediately.
Constructor bot = full management (categories, products, payments, stats, broadcast).
Shop bots = buying only (catalog + payment).
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

def bot_management_kb(bot_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления ботом из конструктора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Категории", callback_data=f"manage_cats:{bot_id}")],
        [InlineKeyboardButton(text="🛍 Товары", callback_data=f"manage_products:{bot_id}")],
        [InlineKeyboardButton(text="💳 Платежи", callback_data=f"payment_settings:{bot_id}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"bot_stats:{bot_id}")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data=f"bot_broadcast:{bot_id}")],
        [InlineKeyboardButton(text="👥 Покупатели", callback_data=f"bot_buyers:{bot_id}")],
        [InlineKeyboardButton(text="⏸ Остановить" if True else "▶️ Запустить", callback_data=f"toggle_bot:{bot_id}"),
         InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot_id}")],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к управлению", callback_data=f"back_to_bot:{bot_id}")]
    ])

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

class AddCategoryFSM(StatesGroup):
    bot_id = State()
    name = State()

class AddProductFSM(StatesGroup):
    bot_id = State()
    category = State()
    name = State()
    description = State()
    price = State()

class EditProductFSM(StatesGroup):
    product_id = State()
    field = State()
    value = State()

class DeleteProductFSM(StatesGroup):
    bot_id = State()
    category = State()
    product = State()

class BroadcastFSM(StatesGroup):
    bot_id = State()
    message_text = State()

# ═══════════════════════════════════════════════════════════
# CONSTRUCTOR BOT ROUTER
# ═══════════════════════════════════════════════════════════

constructor_router = Router()

# ── /start ─────────────────────────────────────────────────

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 Добро пожаловать в конструктор магазинов доната!\n\n"
        "Создайте бота для продажи доната в играх Supercell.\n"
        "После создания вы сможете управлять товарами, категориями и платежами.",
        reply_markup=main_menu_kb()
    )

# ── Создать бота ───────────────────────────────────────────

@constructor_router.message(F.text == "🛠 Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        "🤖 <b>Шаг 1/5</b> — Введите токен бота.\n"
        "Получите его у @BotFather командой /newbot\n\n"
        "Формат: <code>123456:ABC-DEF1234ghikl</code>",
        reply_markup=cancel_kb()
    )

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer("❗ Некорректный токен. Должен быть вида: 123456:ABC-DEF")
    
    async with async_session_maker() as session:
        exists = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if exists.scalar_one_or_none():
            return await message.answer("❗ Бот с таким токеном уже существует в системе.")
    
    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer(
        "✅ Токен принят.\n\n"
        "📝 <b>Шаг 2/5</b> — Введите название магазина:\n"
        "Например: «Донат Brawl Stars 24/7»"
    )

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
    await message.answer(
        "✅ Название принято.\n\n"
        "👮 <b>Шаг 3/5</b> — Введите Telegram ID администратора:\n"
        "Этот пользователь будет управлять ботом из конструктора.\n"
        "Получить ID: @getmyid_bot"
    )

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("❗ Введите корректный числовой Telegram ID.")
    
    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer(
        "✅ Admin ID принят.\n\n"
        "💎 <b>Шаг 4/5</b> — Введите токен Crypto Bot (от @CryptoBot):\n"
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
        "💸 <b>Шаг 5/5</b> — Введите номер кошелька ЮMoney:\n"
        "Например: 410011234567890\n"
        "Или отправьте <b>-</b> чтобы пропустить."
    )

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

        # Auto-create default Supercell categories
        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    # Launch the created bot
    asyncio.create_task(run_shop_bot(bot_record))

    payments = []
    if bot_record.crypto_bot_token:
        payments.append("Crypto Bot")
    if bot_record.yoomoney_wallet:
        payments.append("ЮMoney")

    text = (
        f"✅ <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"🔑 Токен: <code>{data['token']}</code>\n"
        f"👮 Admin ID: <code>{data['admin_id']}</code>\n"
        f"💳 Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"📋 <b>Управление ботом доступно в разделе «📋 Мои боты»</b>\n"
        f"Там вы можете: добавлять товары, настраивать категории, делать рассылки и смотреть статистику.\n\n"
        f"🛒 Сам бот уже работает — перейдите в него и нажмите /start"
    )
    await message.answer(text, reply_markup=main_menu_kb())

# ── Мои боты (список с кнопками управления) ─────────────────

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id)
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer(
            "У вас пока нет созданных ботов.\n"
            "Нажмите «🛠 Создать бота» чтобы начать!"
        )

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token:
            payments.append("Crypto Bot")
        if bot.yoomoney_wallet:
            payments.append("ЮMoney")

        # Count products
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(
                    select(Category.id).where(Category.bot_id == bot.id)
                )
            )
        )

        text = (
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"▸ Статус: {status}\n"
            f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"▸ Товаров: {products_count}\n"
            f"▸ ID: <code>{bot.id}</code>"
        )
        await message.answer(text, reply_markup=bot_management_kb(bot.id))

# ── Навигация "Назад к управлению" ─────────────────────────

@constructor_router.callback_query(F.data.startswith("back_to_bot:"))
async def back_to_bot_management(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        payments = []
        if bot.crypto_bot_token: payments.append("Crypto Bot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(
                    select(Category.id).where(Category.bot_id == bot.id)
                )
            )
        )

    status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
    text = (
        f"🤖 <b>{bot.bot_name}</b>\n"
        f"▸ Статус: {status}\n"
        f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"▸ Товаров: {products_count}\n"
        f"▸ ID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id))
    await callback.answer()

# ── Управление категориями ──────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_cats:"))
async def manage_categories(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id).order_by(Category.id)
        )
        cats = cats_result.scalars().all()

    text = f"📋 <b>Категории бота «{bot.bot_name}»</b>\n\n"
    if cats:
        for i, cat in enumerate(cats, 1):
            products_count = await session.scalar(
                select(func.count(Product.id)).where(Product.category_id == cat.id)
            )
            text += f"{i}. {cat.name} ({products_count} товаров)\n"
    else:
        text += "Категорий пока нет.\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data=f"add_cat:{bot_id}")],
    ])
    if cats:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"del_cat_menu:{bot_id}")
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Добавить категорию ──────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("add_cat:"))
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddCategoryFSM.name)
    await callback.message.answer(
        "✏️ Введите название новой категории:\n"
        "Например: «🎁 Акции» или «🔥 Хиты продаж»",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AddCategoryFSM.name))
async def add_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer("❗ Название должно быть от 1 до 255 символов.")
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()

    async with async_session_maker() as session:
        session.add(Category(bot_id=bot_id, name=name))
        await session.commit()

    await message.answer(
        f"✅ Категория «{name}» добавлена!",
        reply_markup=main_menu_kb()
    )

# ── Удалить категорию ───────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("del_cat_menu:"))
async def del_category_menu(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()

    if not cats:
        return await callback.answer("Нет категорий для удаления.", show_alert=True)

    await callback.message.edit_text(
        "🗑 Выберите категорию для удаления:",
        reply_markup=inline_kb([(cat.name, f"confirm_del_cat:{cat.id}") for cat in cats])
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_del_cat:"))
async def confirm_del_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cat = await session.get(Category, cat_id)
        if not cat:
            return await callback.answer("Категория не найдена.")
        bot_id = cat.bot_id
        name = cat.name
        await session.execute(delete(Category).where(Category.id == cat_id))
        await session.commit()

    await callback.message.edit_text(
        f"🗑 Категория «{name}» удалена.",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()

# ── Управление товарами ─────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_products:"))
async def manage_products(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

    text = f"🛍 <b>Управление товарами — «{bot.bot_name}»</b>\n\nВыберите действие:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_product:{bot_id}")],
        [InlineKeyboardButton(text="📋 Список товаров", callback_data=f"list_products:{bot_id}:0")],
        [InlineKeyboardButton(text="➖ Удалить товар", callback_data=f"del_product_menu:{bot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Добавить товар ──────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("add_product:"))
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()

    if not cats:
        return await callback.answer("Сначала создайте категорию!", show_alert=True)

    await state.update_data(bot_id=bot_id)
    await state.set_state(AddProductFSM.category)
    await callback.message.answer(
        "📂 Выберите категорию для товара:",
        reply_markup=inline_kb([(cat.name, f"prod_cat:{cat.id}") for cat in cats])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(AddProductFSM.category), F.data.startswith("prod_cat:"))
async def add_product_name(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductFSM.name)
    await callback.message.answer(
        "✏️ Введите название товара:\nНапример: «1000 гемов»",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name:
        return await message.answer("❗ Введите название товара.")
    
    await state.update_data(name=name)
    await state.set_state(AddProductFSM.description)
    await message.answer(
        "📝 Введите описание товара:\n"
        "Или отправьте <b>-</b> чтобы оставить без описания."
    )

@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    desc = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductFSM.price)
    await message.answer(
        "💰 Введите цену товара в рублях:\n"
        "Например: 299.00 или 150"
    )

@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except (ValueError, Exception):
        return await message.answer("❗ Некорректная цена. Пример: 299.00")

    data = await state.get_data()
    bot_id = data["bot_id"]
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
        f"✅ Товар «{data['name']}» добавлен!\nЦена: {price} ₽",
        reply_markup=main_menu_kb()
    )

# ── Список товаров ──────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("list_products:"))
async def list_products(callback: CallbackQuery):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()

    text = f"📦 <b>Товары бота «{bot.bot_name}»</b>\n\n"
    all_products = []

    for cat in cats:
        async with async_session_maker() as session:
            prod_result = await session.execute(
                select(Product).where(Product.category_id == cat.id).order_by(Product.id)
            )
            products = prod_result.scalars().all()
        for p in products:
            all_products.append((cat.name, p))

    if not all_products:
        text += "Товаров пока нет."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"add_product:{bot_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
        ])
        return await callback.message.edit_text(text, reply_markup=kb)

    per_page = 10
    total_pages = (len(all_products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page

    for i, (cat_name, p) in enumerate(all_products[start:end], start + 1):
        status = "✅" if p.is_available else "❌"
        text += f"{i}. {status} {p.name} — {p.price} ₽ [{cat_name}]\n"

    text += f"\nСтраница {page + 1}/{total_pages}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"list_products:{bot_id}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"list_products:{bot_id}:{page + 1}"))
    if nav:
        kb.inline_keyboard.append(nav)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 К управлению", callback_data=f"back_to_bot:{bot_id}")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Удалить товар ───────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("del_product_menu:"))
async def del_product_menu(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()

    if not cats:
        return await callback.answer("Нет категорий.", show_alert=True)

    await state.update_data(bot_id=bot_id)
    await state.set_state(DeleteProductFSM.category)
    await callback.message.answer(
        "📂 Выберите категорию:",
        reply_markup=inline_kb([(cat.name, f"del_prod_cat:{cat.id}") for cat in cats])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.category), F.data.startswith("del_prod_cat:"))
async def del_product_select(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        prod_result = await session.execute(
            select(Product).where(Product.category_id == cat_id)
        )
        products = prod_result.scalars().all()

    if not products:
        await callback.answer("В этой категории нет товаров.", show_alert=True)
        await state.clear()
        return

    await state.set_state(DeleteProductFSM.product)
    await callback.message.answer(
        "🗑 Выберите товар для удаления:",
        reply_markup=inline_kb([(f"{p.name} ({p.price} ₽)", f"confirm_del_prod:{p.id}") for p in products])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.product), F.data.startswith("confirm_del_prod:"))
async def confirm_del_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()

    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        name = product.name if product else "Товар"
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.commit()

    await callback.message.edit_text(
        f"🗑 Товар «{name}» удалён.",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()

# ── Платёжные реквизиты ─────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("payment_settings:"))
async def payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)

    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")

    text = (
        f"💳 <b>Платёжные реквизиты — «{bot.bot_name}»</b>\n\n"
        f"💎 Crypto Bot: {'✅ Настроен' if bot.crypto_bot_token else '❌ Не настроен'}\n"
        f"💸 ЮMoney: {'✅ Настроен' if bot.yoomoney_wallet else '❌ Не настроен'}\n\n"
        f"Выберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Изменить Crypto Bot токен", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text="💸 Изменить ЮMoney кошелёк", callback_data=f"edit_yoo:{bot_id}")],
        [InlineKeyboardButton(text="🧪 Тестовая оплата", callback_data=f"test_payment:{bot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer(
        "💎 Введите новый токен Crypto Bot:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
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

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer(
        "💸 Введите новый номер кошелька ЮMoney:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
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

# ── Статистика бота ─────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_stats:"))
async def bot_stats(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

        users_count = await session.scalar(
            select(func.count(Purchase.user_id.distinct())).where(Purchase.bot_id == bot_id)
        )
        purchases_total = await session.scalar(
            select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed")
        )
        purchases_pending = await session.scalar(
            select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "pending")
        )
        revenue = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
            .where(Purchase.bot_id == bot_id, Purchase.status == "completed")
        )
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(select(Category.id).where(Category.bot_id == bot_id))
            )
        )
        categories_count = await session.scalar(
            select(func.count(Category.id)).where(Category.bot_id == bot_id)
        )

    text = (
        f"📊 <b>Статистика — «{bot.bot_name}»</b>\n\n"
        f"👥 Уникальных покупателей: {users_count or 0}\n"
        f"📦 Категорий: {categories_count}\n"
        f"🛍 Товаров: {products_count}\n"
        f"🛒 Продаж (завершено): {purchases_total or 0}\n"
        f"⏳ Продаж (ожидает): {purchases_pending or 0}\n"
        f"💰 Общая выручка: {revenue or 0} ₽"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Покупатели ──────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_buyers:"))
async def bot_buyers(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

        result = await session.execute(
            select(User.telegram_id, User.username, func.count(Purchase.id), func.sum(Purchase.amount))
            .join(Purchase, User.telegram_id == Purchase.user_id)
            .where(Purchase.bot_id == bot_id, Purchase.status == "completed")
            .group_by(User.telegram_id, User.username)
            .order_by(func.sum(Purchase.amount).desc())
            .limit(20)
        )
        buyers = result.all()

    text = f"👥 <b>Покупатели — «{bot.bot_name}»</b>\n\n"
    if buyers:
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            display = f"@{username}" if username else f"ID:{tid}"
            text += f"{i}. {display} — {count} покупок на {total} ₽\n"
    else:
        text += "Покупателей пока нет."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Рассылка ─────────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_broadcast:"))
async def bot_broadcast_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

    await state.update_data(broadcast_bot_id=bot_id)
    await state.set_state(BroadcastFSM.message_text)
    await callback.message.answer(
        "📨 Введите текст рассылки (поддерживается HTML):\n\n"
        "<b>жирный</b>, <i>курсив</i>, <code>моно</code>\n\n"
        "Сообщение получат все, кто делал покупки в этом боте.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(BroadcastFSM.message_text))
async def broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())

    data = await state.get_data()
    bot_id = data["broadcast_bot_id"]
    await state.clear()

    async with async_session_maker() as session:
        result = await session.execute(
            select(Purchase.user_id.distinct()).where(Purchase.bot_id == bot_id)
        )
        user_ids = [row[0] for row in result.all()]

        bot_record = await session.get(ShopBot, bot_id)

    if not user_ids:
        return await message.answer("Нет пользователей для рассылки.", reply_markup=main_menu_kb())

    sent, failed = 0, 0
    await message.answer(f"📨 Начинаю рассылку на {len(user_ids)} пользователей...")

    for uid in user_ids:
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(
        f"📨 <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        reply_markup=main_menu_kb()
    )

# ── Тестовая оплата ─────────────────────────────────────────

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
        return await callback.answer("Нет категорий. Создайте товары!", show_alert=True)

    async with async_session_maker() as session:
        products_result = await session.execute(
            select(Product).where(
                Product.category_id == cats[0].id,
                Product.is_available == True
            )
        )
        products = products_result.scalars().all()

    if not products:
        return await callback.answer("Нет товаров в категории.", show_alert=True)

    p = products[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💎 Crypto Bot", callback_data=f"do_crypto:{bot_id}:{p.id}")
        ])
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💸 ЮMoney", callback_data=f"do_yoo:{bot_id}:{p.id}")
        ])

    if not kb.inline_keyboard:
        return await callback.answer("Нет настроенных платёжных систем!", show_alert=True)

    await callback.message.answer(
        f"🧪 <b>Тестовая оплата</b>\n\n"
        f"Товар: {p.name}\n"
        f"Цена: {p.price} ₽\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb
    )
    await callback.answer()

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
        f"🧾 <b>Тестовый счёт создан!</b>\n\n"
        f"Товар: {product.name}\n"
        f"Сумма: {product.price} ₽\n"
        f"ID: <code>{purchase.id}</code>\n\n"
        f"Нажмите «Оплатить» 👇",
        reply_markup=kb
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("do_yoo:"))
async def do_yoo(callback: CallbackQuery):
    _, bot_id, product_id = callback.data.split(":")
    bot_id, product_id = int(bot_id), int(product_id)

    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        product = await session.get(Product, product_id)

        if not bot or not bot.yoomoney_wallet:
            return await callback.answer("ЮMoney не настроен!")

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
        [InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)]
    ])
    await callback.message.answer(
        f"🧾 <b>Тестовый счёт создан!</b>\n\n"
        f"Товар: {product.name}\n"
        f"Сумма: {product.price} ₽\n"
        f"Метка: <code>{label}</code>\n\n"
        f"Нажмите «Оплатить» 👇",
        reply_markup=kb
    )
    await callback.answer()

# ── Toggle/Delete бота ──────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if bot and bot.owner_id == callback.from_user.id:
            bot.is_active = not bot.is_active
            await session.commit()
            status = "запущен" if bot.is_active else "остановлен"
            await callback.answer(f"Бот {status}.")
        else:
            await callback.answer("Ошибка.")

@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")]
    ])
    await callback.message.answer("🗑 Вы уверены, что хотите удалить бота? Все данные будут потеряны.", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(
            delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id)
        )
        await session.commit()
    await callback.message.edit_text("🗑 Бот удалён.")
    await callback.answer()

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()

# ── Профиль ─────────────────────────────────────────────────

@constructor_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
        total_purchases = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.user_id == message.from_user.id,
                Purchase.status == "completed"
            )
        )

    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"Баланс: {user.balance} ₽\n"
        f"Ботов создано: {bots_count}\n"
        f"Всего покупок: {total_purchases}"
    )

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY (ТОЛЬКО ПОКУПКИ, БЕЗ АДМИНКИ)
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    shop_router = Router()

    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        await message.answer(
            f"🎮 Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат для игр Supercell.\n"
            f"Выберите действие:",
            reply_markup=shop_menu_kb()
        )

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
            reply_markup=inline_kb([(f"{p.name} — {p.price} ₽", f"shop_product:{p.id}") for p in products])
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
        await callback.message.answer(text + "\n\n💳 Выберите способ оплаты:", reply_markup=inline_kb(btns))
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.")
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method="crypto_bot"
            )
            session.add(purchase); await session.commit(); await session.refresh(purchase)
            api = CryptoBotAPI(bot_record.crypto_bot_token)
            invoice = await api.create_invoice(float(product.price), f"Покупка: {product.name}", str(purchase.id))
        if not invoice:
            return await callback.message.answer("❌ Ошибка создания счёта!")
        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оплатить", url=pay_url)]])
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить» 👇",
            reply_markup=kb
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.")
            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"yoomoney:{label}"
            )
            session.add(purchase); await session.commit()
            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(float(product.price), label, f"Покупка: {product.name}")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)]])
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить» 👇",
            reply_markup=kb
        )
        await callback.answer()

    @shop_router.message(F.text == "📦 Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            rows = (await session.execute(
                select(Purchase, Product).join(Product)
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id)
                .order_by(Purchase.created_at.desc()).limit(20)
            )).all()
        if not rows:
            return await message.answer("У вас пока нет покупок.")
        text = "📦 <b>Ваши покупки:</b>\n\n"
        status_map = {"pending": "⏳ Ожидает", "completed": "✅ Завершена"}
        for purchase, product in rows:
            text += f"🛍 {product.name} — {purchase.amount} ₽ | {status_map.get(purchase.status, purchase.status)}\n"
        await message.answer(text)

    @shop_router.message(F.text == "👤 Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            total = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id, Purchase.status == "completed")
            )
        await message.answer(f"👤 <b>Профиль</b>\n\nID: <code>{message.from_user.id}</code>\nБаланс: {user.balance} ₽\nПотрачено: {total} ₽")

    return shop_router

# ═══════════════════════════════════════════════════════════
# RUNNING BOTS
# ═══════════════════════════════════════════════════════════

running_tasks: dict[int, asyncio.Task] = {}

async def run_shop_bot(bot_record: ShopBot):
    if bot_record.id in running_tasks:
        logger.warning(f"Bot {bot_record.id} already running")
        return
    bot = Bot(token=bot_record.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    async with async_session_maker() as session:
        result = await session.execute(select(ShopBot).where(ShopBot.is_active == True))
        bots = result.scalars().all()
    for bot_record in bots:
        await run_shop_bot(bot_record)
        await asyncio.sleep(0.5)

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    await init_db()
    constructor_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(constructor_router)
    await start_all_active_bots()
    logger.info("Constructor bot starting...")
    try:
        await dp.start_polling(constructor_bot, allowed_updates=["message", "callback_query"])
    finally:
        await constructor_bot.session.close()
        for task in running_tasks.values():
            task.cancel()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
