"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL, Crypto Pay API, YooMoney API, RollyPay API
Auto-deploy to Bothost — reads BOT_TOKEN & DATABASE_URL from env, starts immediately.
Constructor bot = full management (categories, products, payments, stats, broadcast, subscriptions).
Shop bots = buying only (catalog + payment).
Premium emoji support, subscription system (Free/Pro/Premium).
"""

import asyncio, logging, os, time, uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from urllib.parse import quote

import aiohttp
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter, Command
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

ADMIN_IDS = [7973988177]

# ═══════════════════════════════════════════════════════════
# PREMIUM EMOJI IDs
# ═══════════════════════════════════════════════════════════

EMOJI = {
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "people": "5870772616305839506",
    "person_check": "5891207662678317861",
    "person_cross": "5893192487324880883",
    "file": "5870528606328852614",
    "smile": "5870764288364252592",
    "chart_up": "5870930636742595124",
    "chart_stats": "5870921681735781843",
    "home": "5873147866364514353",
    "lock_closed": "6037249452824072506",
    "lock_open": "6037496202990194718",
    "megaphone": "6039422865189638057",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "pencil": "5870676941614354370",
    "trash": "5870875489362513438",
    "down": "5893057118545646106",
    "paperclip": "6039451237743595514",
    "link": "5769289093221454192",
    "info": "6028435952299413210",
    "bot": "6030400221232501136",
    "eye": "6037397706505195857",
    "eye_hidden": "6037243349675544634",
    "send": "5963103826075456248",
    "download": "6039802767931871481",
    "bell": "6039486778597970865",
    "gift": "6032644646587338669",
    "clock": "5983150113483134607",
    "party": "6041731551845159060",
    "font": "5870801517140775623",
    "write": "5870753782874246579",
    "media": "6035128606563241721",
    "geo": "6042011682497106307",
    "wallet": "5769126056262898415",
    "box": "5884479287171485878",
    "cryptobot": "5260752406890711732",
    "calendar": "5890937706803894250",
    "tag": "5886285355279193209",
    "time_past": "5775896410780079073",
    "apps": "5778672437122045013",
    "brush": "6050679691004612757",
    "add_text": "5771851822897566479",
    "format": "5778479949572738874",
    "coin": "5904462880941545555",
    "send_money": "5890848474563352982",
    "receive_money": "5879814368572478751",
    "code": "5940433880585605708",
    "loading": "5345906554510012647",
    "back": "5345906554510012647",
    "star": "5774022692642492953",
    "subscribe": "6039450962865688331",
    "broadcast": "5370599459661045441",
    "blue": "5373141891321699086",
    "red": "5370810157871667232",
    "green": "5471984997361523302",
}

def em(name: str) -> str:
    emoji_id = EMOJI.get(name, EMOJI["smile"])
    return f'<tg-emoji emoji-id="{emoji_id}">⚙</tg-emoji>'

def em_text(name: str, text: str) -> str:
    return f"{em(name)} {text}"

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
    subscription: Mapped[str] = mapped_column(String(50), default="free")
    subscription_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    bots = relationship("ShopBot", back_populates="owner", foreign_keys="ShopBot.owner_id")
    purchases = relationship("Purchase", back_populates="user")
    subscription_payments = relationship("SubscriptionPayment", back_populates="user")

class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    user = relationship("User", back_populates="subscription_payments")

class ShopBot(Base):
    __tablename__ = "bots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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

class AdminSettings(Base):
    __tablename__ = "admin_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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

async def get_admin_settings(session: AsyncSession) -> AdminSettings:
    result = await session.execute(select(AdminSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = AdminSettings()
        session.add(settings)
        await session.commit()
    return settings

async def check_subscription(user: User) -> bool:
    if user.subscription == "free":
        return True
    if user.subscription_expires and user.subscription_expires > datetime.now():
        return True
    return False

async def get_bot_limit(user: User) -> int:
    if not await check_subscription(user):
        user.subscription = "free"
        user.subscription_expires = None
    limits = {"free": 1, "pro": 5, "premium": 30}
    return limits.get(user.subscription, 1)

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

    async def get_invoices(self, invoice_ids: list[int]) -> Optional[list]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/getInvoices", headers=self.headers,
                    params={"invoice_ids": ",".join(map(str, invoice_ids))}
                ) as resp:
                    data = await resp.json()
                    return data["result"]["items"] if data.get("ok") else None
        except Exception as e:
            logger.error(f"CryptoBot getInvoices error: {e}")
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

class RollyPayAPI:
    BASE_URL = "https://rollypay.io/api/v1"
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def create_payment(self, amount: float, order_id: str, description: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                nonce = str(uuid.uuid4())
                async with session.post(
                    f"{self.BASE_URL}/payments",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce,
                    },
                    json={
                        "amount": f"{amount:.2f}",
                        "payment_currency": "RUB",
                        "order_id": order_id,
                        "description": description,
                    }
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        return data
                    logger.error(f"RollyPay error: {data}")
                    return None
        except Exception as e:
            logger.error(f"RollyPay API error: {e}")
            return None

    async def get_payment_status(self, payment_id: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                nonce = str(uuid.uuid4())
                async with session.get(
                    f"{self.BASE_URL}/payments/{payment_id}",
                    headers={"X-API-Key": self.api_key, "X-Nonce": nonce}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            logger.error(f"RollyPay status error: {e}")
            return None

# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [{"text": "🛠 Создать бота"}, {"text": "📋 Мои боты"}],
            [{"text": "👤 Профиль"}, {"text": "💎 Подписка"}]
        ],
        resize_keyboard=True
    )

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [{"text": "🛒 Купить донат"}, {"text": "📦 Мои покупки"}],
            [{"text": "👤 Профиль"}]
        ],
        resize_keyboard=True
    )

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[{"text": "❌ Отмена"}]], resize_keyboard=True)

def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [{"text": "💳 Реквизиты подписок"}, {"text": "📊 Статистика системы"}],
            [{"text": "👥 Пользователи"}, {"text": "📨 Рассылка всем"}],
            [{"text": "🏠 Выйти из админ-панели"}],
        ],
        resize_keyboard=True
    )

def bot_management_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('box')} Категории", callback_data=f"manage_cats:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('gift')} Товары", callback_data=f"manage_products:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('wallet')} Платежи", callback_data=f"payment_settings:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('chart_stats')} Статистика", callback_data=f"bot_stats:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('megaphone')} Рассылка", callback_data=f"bot_broadcast:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('people')} Покупатели", callback_data=f"bot_buyers:{bot_id}")],
        [
            InlineKeyboardButton(text=f"{em('lock_closed')} Стоп", callback_data=f"toggle_bot:{bot_id}"),
            InlineKeyboardButton(text=f"{em('trash')} Удалить", callback_data=f"delete_bot:{bot_id}")
        ],
    ])

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('back')} Назад к управлению", callback_data=f"back_to_bot:{bot_id}")]
    ])

def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])

def subscription_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('star')} PRO — 100₽/мес (5 ботов)", callback_data="sub_pro")],
        [InlineKeyboardButton(text=f"{em('star')} PREMIUM — 250₽/мес (30 ботов)", callback_data="sub_premium")],
        [InlineKeyboardButton(text=f"{em('info')} О подписках", callback_data="sub_info")],
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
    rollypay_key = State()

class PaymentSettingsFSM(StatesGroup):
    crypto_token = State()
    yoomoney_wallet = State()
    rollypay_key = State()

class AddCategoryFSM(StatesGroup):
    bot_id = State()
    name = State()

class AddProductFSM(StatesGroup):
    bot_id = State()
    category = State()
    name = State()
    description = State()
    price = State()

class DeleteProductFSM(StatesGroup):
    bot_id = State()
    category = State()
    product = State()

class BroadcastFSM(StatesGroup):
    bot_id = State()
    message_text = State()

class AdminSettingsFSM(StatesGroup):
    crypto_token = State()
    yoomoney_wallet = State()
    rollypay_key = State()

class AdminBroadcastFSM(StatesGroup):
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
        f"{em('home')} Добро пожаловать в конструктор магазинов доната!\n\n"
        f"Создайте бота для продажи доната в играх Supercell.\n"
        f"После создания вы сможете управлять товарами, категориями и платежами.\n\n"
        f"{em('info')} Доступные тарифы: 💎 Подписка",
        reply_markup=main_menu_kb()
    )

# ── Админ-панель ──────────────────────────────────────────

@constructor_router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer(f"{em('cross')} Нет доступа.")
    await message.answer(
        f"{em('settings')} <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_menu_kb()
    )

@constructor_router.message(F.text == "🏠 Выйти из админ-панели")
async def exit_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Вы вышли из админ-панели.", reply_markup=main_menu_kb())

@constructor_router.message(F.text == "💳 Реквизиты подписок")
async def admin_payment_settings(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
    text = (
        f"{em('wallet')} <b>Реквизиты для подписок</b>\n\n"
        f"{em('cryptobot')} Crypto Bot: {'✅' if settings.crypto_bot_token else '❌'}\n"
        f"{em('send_money')} ЮMoney: {'✅' if settings.yoomoney_wallet else '❌'}\n"
        f"{em('link')} RollyPay: {'✅' if settings.rollypay_api_key else '❌'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('cryptobot')} Crypto Bot токен", callback_data="admin_edit_crypto")],
        [InlineKeyboardButton(text=f"{em('send_money')} ЮMoney кошелёк", callback_data="admin_edit_yoo")],
        [InlineKeyboardButton(text=f"{em('link')} RollyPay API ключ", callback_data="admin_edit_rolly")],
    ])
    await message.answer(text, reply_markup=kb)

@constructor_router.callback_query(F.data == "admin_edit_crypto")
async def admin_edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа.")
    await state.set_state(AdminSettingsFSM.crypto_token)
    await callback.message.answer(f"{em('cryptobot')} Введите токен Crypto Bot (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_edit_yoo")
async def admin_edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа.")
    await state.set_state(AdminSettingsFSM.yoomoney_wallet)
    await callback.message.answer(f"{em('send_money')} Введите номер ЮMoney (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_edit_rolly")
async def admin_edit_rolly_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа.")
    await state.set_state(AdminSettingsFSM.rollypay_key)
    await callback.message.answer(f"{em('link')} Введите API ключ RollyPay (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminSettingsFSM.crypto_token))
async def admin_edit_crypto_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    token = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        settings.crypto_bot_token = token
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminSettingsFSM.yoomoney_wallet))
async def admin_edit_yoo_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    wallet = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        settings.yoomoney_wallet = wallet
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminSettingsFSM.rollypay_key))
async def admin_edit_rolly_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    key = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        settings.rollypay_api_key = key
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=admin_menu_kb())

@constructor_router.message(F.text == "📨 Рассылка всем")
async def admin_broadcast_all(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminBroadcastFSM.message_text)
    await message.answer(f"{em('megaphone')} <b>Рассылка всем пользователям</b>\n\nВведите текст рассылки:", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(AdminBroadcastFSM.message_text))
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    await state.clear()
    async with async_session_maker() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in result.all()]
    sent, failed = 0, 0
    status_msg = await message.answer(f"{em('loading')} Рассылка на {len(user_ids)} пользователей...")
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception: failed += 1
        if (i+1) % 20 == 0:
            try: await status_msg.edit_text(f"{em('loading')} Отправлено: {sent}/{len(user_ids)} (ошибок: {failed})")
            except: pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"{em('check')} <b>Рассылка завершена!</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")

@constructor_router.message(F.text == "📊 Статистика системы")
async def admin_system_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_bots = await session.scalar(select(func.count(ShopBot.id)))
        active_bots = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.is_active == True))
        pro_users = await session.scalar(select(func.count(User.id)).where(User.subscription == "pro"))
        premium_users = await session.scalar(select(func.count(User.id)).where(User.subscription == "premium"))
        total_revenue = await session.scalar(select(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).where(SubscriptionPayment.status == "completed"))
    await message.answer(
        f"{em('chart_stats')} <b>Статистика системы</b>\n\n"
        f"{em('people')} Пользователей: {total_users}\n"
        f"{em('bot')} Всего ботов: {total_bots} (активных: {active_bots})\n"
        f"{em('star')} PRO: {pro_users} | PREMIUM: {premium_users}\n"
        f"{em('coin')} Выручка от подписок: {total_revenue} ₽"
    )

@constructor_router.message(F.text == "👥 Пользователи")
async def admin_users_list(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    async with async_session_maker() as session:
        users = (await session.execute(select(User).order_by(User.created_at.desc()).limit(30))).scalars().all()
        bots_counts = {}
        for u in users:
            bots_counts[u.telegram_id] = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.owner_id == u.telegram_id))
    text = f"{em('people')} <b>Последние пользователи:</b>\n\n"
    for u in users:
        text += f"• @{u.username or u.telegram_id} | {u.subscription.upper()} | Ботов: {bots_counts.get(u.telegram_id, 0)}\n"
    await message.answer(text)

# ── Подписка ───────────────────────────────────────────────

@constructor_router.message(F.text == "💎 Подписка")
async def subscription_menu_msg(message: Message):
    await subscription_menu(message)

@constructor_router.message(Command("subscription"))
async def subscription_cmd(message: Message):
    await subscription_menu(message)

async def subscription_menu(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        is_active = await check_subscription(user)
        if user.subscription == "free":
            status = "Бесплатный (навсегда)"
        else:
            expires = user.subscription_expires
            if is_active:
                days_left = (expires - datetime.now()).days if expires else 0
                status = f"{user.subscription.upper()} (активен, {days_left} дн.)"
            else:
                status = f"{user.subscription.upper()} (истекла)"
    text = (
        f"{em('star')} <b>Ваша подписка</b>\n\n"
        f"📋 Тариф: {status}\n"
        f"{em('box')} Лимит ботов: {await get_bot_limit(user)}\n\n"
        f"{em('info')} <b>Тарифы:</b>\n"
        f"• FREE — 1 бот (бесплатно)\n"
        f"• PRO — 5 ботов (100₽/мес)\n"
        f"• PREMIUM — 30 ботов (250₽/мес)"
    )
    await message.answer(text, reply_markup=subscription_kb())

@constructor_router.callback_query(F.data == "sub_info")
async def sub_info(callback: CallbackQuery):
    text = (
        f"{em('info')} <b>О подписках</b>\n\n"
        f"<b>FREE</b> — 1 бот, базовые функции\n"
        f"<b>PRO</b> — 5 ботов, все функции, 100₽/мес\n"
        f"<b>PREMIUM</b> — 30 ботов, все функции, приоритет, 250₽/мес\n\n"
        f"Подписка на 1 месяц. Бесплатный тариф навсегда."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('back')} Назад", callback_data="back_to_sub")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data == "back_to_sub")
async def back_to_sub(callback: CallbackQuery):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        is_active = await check_subscription(user)
        if user.subscription == "free":
            status = "Бесплатный (навсегда)"
        else:
            expires = user.subscription_expires
            if is_active:
                days_left = (expires - datetime.now()).days if expires else 0
                status = f"{user.subscription.upper()} (активен, {days_left} дн.)"
            else:
                status = f"{user.subscription.upper()} (истекла)"
    text = (
        f"{em('star')} <b>Ваша подписка</b>\n\n"
        f"📋 Тариф: {status}\n"
        f"{em('box')} Лимит ботов: {await get_bot_limit(user)}\n\n"
        f"{em('info')} <b>Тарифы:</b>\n"
        f"• FREE — 1 бот (бесплатно)\n"
        f"• PRO — 5 ботов (100₽/мес)\n"
        f"• PREMIUM — 30 ботов (250₽/мес)"
    )
    await callback.message.edit_text(text, reply_markup=subscription_kb())
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("sub_pro"))
async def sub_pro(callback: CallbackQuery):
    await show_sub_payment(callback, "pro", 100)

@constructor_router.callback_query(F.data.startswith("sub_premium"))
async def sub_premium(callback: CallbackQuery):
    await show_sub_payment(callback, "premium", 250)

async def show_sub_payment(callback: CallbackQuery, plan: str, amount: int):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id, callback.from_user.username)
        if user.subscription == plan and await check_subscription(user):
            return await callback.answer("У вас уже активна эта подписка!", show_alert=True)
    text = (
        f"{em('star')} <b>Оформление {plan.upper()}</b>\n\n"
        f"💰 Стоимость: {amount}₽/мес\n"
        f"{em('box')} Лимит: {5 if plan == 'pro' else 30} ботов\n\n"
        f"Выберите способ оплаты:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('cryptobot')} Crypto Bot", callback_data=f"do_sub_crypto:{plan}")],
        [InlineKeyboardButton(text=f"{em('send_money')} ЮMoney", callback_data=f"do_sub_yoo:{plan}")],
        [InlineKeyboardButton(text=f"{em('link')} RollyPay", callback_data=f"do_sub_rolly:{plan}")],
        [InlineKeyboardButton(text=f"{em('back')} Назад", callback_data="back_to_sub")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# ── Оплата подписки Crypto Bot ────────────────────────────

@constructor_router.callback_query(F.data.startswith("do_sub_crypto:"))
async def sub_crypto_pay(callback: CallbackQuery):
    plan = callback.data.split(":")[1]
    amounts = {"pro": 100, "premium": 250}
    amount = amounts[plan]
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        if not settings.crypto_bot_token: return await callback.answer("Crypto Bot не настроен администратором!", show_alert=True)
        sp = SubscriptionPayment(user_id=callback.from_user.id, plan=plan, amount=Decimal(amount), status="pending", payment_method="crypto_bot")
        session.add(sp); await session.commit(); await session.refresh(sp)
        api = CryptoBotAPI(settings.crypto_bot_token)
        invoice = await api.create_invoice(float(amount), f"Подписка {plan.upper()} на 1 месяц", f"sub_{sp.id}")
    if not invoice: return await callback.answer("Ошибка создания счёта!", show_alert=True)
    pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
    invoice_id = invoice.get("invoice_id")
    async with async_session_maker() as session:
        await session.execute(update(SubscriptionPayment).where(SubscriptionPayment.id == sp.id).values(invoice_id=invoice_id))
        await session.commit()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('cryptobot')} Оплатить", url=pay_url)],
        [InlineKeyboardButton(text=f"{em('check')} Проверить оплату", callback_data=f"check_sub_crypto:{sp.id}:{invoice_id}:{plan}")],
    ])
    await callback.message.edit_text(f"{em('send_money')} <b>Счёт создан!</b>\n\nПодписка: {plan.upper()}\nСумма: {amount} ₽\n\nНажмите «Оплатить», затем «Проверить оплату»", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_sub_crypto:"))
async def check_sub_crypto(callback: CallbackQuery):
    _, sp_id, invoice_id, plan = callback.data.split(":")
    sp_id, invoice_id = int(sp_id), int(invoice_id)
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        api = CryptoBotAPI(settings.crypto_bot_token)
        invoices = await api.get_invoices([invoice_id])
        if invoices and invoices[0].get("status") == "paid":
            await session.execute(update(SubscriptionPayment).where(SubscriptionPayment.id == sp_id).values(status="completed"))
            exp = datetime.now() + timedelta(days=30)
            await session.execute(update(User).where(User.telegram_id == callback.from_user.id).values(subscription=plan, subscription_expires=exp))
            await session.commit()
            await callback.message.edit_text(f"{em('check')} <b>Подписка {plan.upper()} активирована!</b>\n\nДействует до: {exp.strftime('%d.%m.%Y')}\nЛимит ботов: {5 if plan == 'pro' else 30}")
        else:
            await callback.answer("⏳ Оплата ещё не получена. Попробуйте позже.", show_alert=True)

# ── Оплата подписки YooMoney ──────────────────────────────

@constructor_router.callback_query(F.data.startswith("do_sub_yoo:"))
async def sub_yoo_pay(callback: CallbackQuery):
    plan = callback.data.split(":")[1]
    amounts = {"pro": 100, "premium": 250}
    amount = amounts[plan]
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        if not settings.yoomoney_wallet: return await callback.answer("ЮMoney не настроен администратором!", show_alert=True)
        label = f"sub_{plan}_{callback.from_user.id}_{int(time.time())}"
        sp = SubscriptionPayment(user_id=callback.from_user.id, plan=plan, amount=Decimal(amount), status="pending", payment_method="yoomoney", payment_label=label)
        session.add(sp); await session.commit(); await session.refresh(sp)
        yoo = YooMoneyAPI(settings.yoomoney_wallet)
        pay_url = yoo.generate_form_url(float(amount), label, f"Подписка {plan.upper()}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('send_money')} Оплатить через ЮMoney", url=pay_url)],
        [InlineKeyboardButton(text=f"{em('check')} Проверить оплату", callback_data=f"check_sub_yoo:{sp.id}:{plan}")],
    ])
    await callback.message.edit_text(f"{em('send_money')} <b>Счёт создан!</b>\n\nПодписка: {plan.upper()}\nСумма: {amount} ₽\n\nНажмите «Оплатить», затем «Проверить оплату»", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_sub_yoo:"))
async def check_sub_yoo(callback: CallbackQuery):
    _, sp_id, plan = callback.data.split(":")
    sp_id = int(sp_id)
    async with async_session_maker() as session:
        await session.execute(update(SubscriptionPayment).where(SubscriptionPayment.id == sp_id).values(status="completed"))
        exp = datetime.now() + timedelta(days=30)
        await session.execute(update(User).where(User.telegram_id == callback.from_user.id).values(subscription=plan, subscription_expires=exp))
        await session.commit()
    await callback.message.edit_text(f"{em('check')} <b>Подписка {plan.upper()} активирована!</b>\n\nДействует до: {exp.strftime('%d.%m.%Y')}\nЛимит ботов: {5 if plan == 'pro' else 30}")

# ── Оплата подписки RollyPay ──────────────────────────────

@constructor_router.callback_query(F.data.startswith("do_sub_rolly:"))
async def sub_rolly_pay(callback: CallbackQuery):
    plan = callback.data.split(":")[1]
    amounts = {"pro": 100, "premium": 250}
    amount = amounts[plan]
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        if not settings.rollypay_api_key: return await callback.answer("RollyPay не настроен администратором!", show_alert=True)
        sp = SubscriptionPayment(user_id=callback.from_user.id, plan=plan, amount=Decimal(amount), status="pending", payment_method="rollypay")
        session.add(sp); await session.commit(); await session.refresh(sp)
        api = RollyPayAPI(settings.rollypay_api_key)
        result = await api.create_payment(float(amount), f"sub_{sp.id}", f"Подписка {plan.upper()}")
    if not result or "pay_url" not in result: return await callback.answer("Ошибка создания счёта!", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('link')} Оплатить через RollyPay", url=result["pay_url"])],
        [InlineKeyboardButton(text=f"{em('check')} Проверить оплату", callback_data=f"check_sub_rolly:{sp.id}:{plan}:{result.get('payment_id', '')}")],
    ])
    await callback.message.edit_text(f"{em('link')} <b>Счёт создан!</b>\n\nПодписка: {plan.upper()}\nСумма: {amount} ₽\n\nНажмите «Оплатить», затем «Проверить оплату»", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_sub_rolly:"))
async def check_sub_rolly(callback: CallbackQuery):
    _, sp_id, plan, payment_id = callback.data.split(":")
    sp_id = int(sp_id)
    async with async_session_maker() as session:
        settings = await get_admin_settings(session)
        api = RollyPayAPI(settings.rollypay_api_key)
        status_data = await api.get_payment_status(payment_id)
        if status_data and status_data.get("status") == "paid":
            await session.execute(update(SubscriptionPayment).where(SubscriptionPayment.id == sp_id).values(status="completed"))
            exp = datetime.now() + timedelta(days=30)
            await session.execute(update(User).where(User.telegram_id == callback.from_user.id).values(subscription=plan, subscription_expires=exp))
            await session.commit()
            await callback.message.edit_text(f"{em('check')} <b>Подписка {plan.upper()} активирована!</b>\n\nДействует до: {exp.strftime('%d.%m.%Y')}\nЛимит ботов: {5 if plan == 'pro' else 30}")
        else:
            await callback.answer("⏳ Оплата ещё не получена. Попробуйте позже.", show_alert=True)

# ── Создать бота ───────────────────────────────────────────

@constructor_router.message(F.text == "🛠 Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        limit = await get_bot_limit(user)
        bots_count = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id))
        if bots_count >= limit:
            return await message.answer(f"{em('cross')} Достигнут лимит ботов ({limit}).\nОбновите подписку: 💎 Подписка")
    await state.set_state(CreateBotFSM.token)
    await message.answer(f"{em('bot')} <b>Шаг 1/6</b> — Введите токен бота.\nПолучите его у @BotFather командой /newbot\n\nФормат: <code>123456:ABC-DEF1234ghikl</code>", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    token = message.text.strip()
    if not token or ":" not in token: return await message.answer(f"{em('cross')} Некорректный токен.")
    async with async_session_maker() as session:
        if (await session.execute(select(ShopBot).where(ShopBot.bot_token == token))).scalar_one_or_none():
            return await message.answer(f"{em('cross')} Бот с таким токеном уже существует.")
    await state.update_data(token=token); await state.set_state(CreateBotFSM.name)
    await message.answer(f"{em('check')} Токен принят.\n\n{em('pencil')} <b>Шаг 2/6</b> — Название магазина:")

@constructor_router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    name = message.text.strip()
    if not name or len(name) > 255: return await message.answer(f"{em('cross')} Название должно быть от 1 до 255 символов.")
    await state.update_data(name=name); await state.set_state(CreateBotFSM.admin_id)
    await message.answer(f"{em('check')} Название принято.\n\n{em('profile')} <b>Шаг 3/6</b> — Telegram ID админа:")

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0: raise ValueError
    except ValueError: return await message.answer(f"{em('cross')} Введите корректный ID.")
    await state.update_data(admin_id=admin_id); await state.set_state(CreateBotFSM.crypto_token)
    await message.answer(f"{em('check')} Admin ID принят.\n\n{em('cryptobot')} <b>Шаг 4/6</b> — Токен Crypto Bot (или «-»):")

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer(f"{em('send_money')} <b>Шаг 5/6</b> — Номер ЮMoney (или «-»):")

@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_yoomoney(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    yoo = message.text.strip()
    await state.update_data(yoomoney_wallet=None if yoo == "-" else yoo)
    await state.set_state(CreateBotFSM.rollypay_key)
    await message.answer(f"{em('link')} <b>Шаг 6/6</b> — API ключ RollyPay (или «-»):")

@constructor_router.message(StateFilter(CreateBotFSM.rollypay_key))
async def create_bot_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer(f"{em('cross')} Отменено.", reply_markup=main_menu_kb())
    rolly = message.text.strip()
    data = await state.get_data(); await state.clear()
    async with async_session_maker() as session:
        bot_record = ShopBot(
            owner_id=message.from_user.id, bot_token=data["token"], bot_name=data["name"],
            admin_id=data["admin_id"], crypto_bot_token=data.get("crypto_token"),
            yoomoney_wallet=data.get("yoomoney_wallet"),
            rollypay_api_key=None if rolly == "-" else rolly, is_active=True
        )
        session.add(bot_record); await session.commit(); await session.refresh(bot_record)
        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()
    asyncio.create_task(run_shop_bot(bot_record))
    payments = []
    if bot_record.crypto_bot_token: payments.append("Crypto Bot")
    if bot_record.yoomoney_wallet: payments.append("ЮMoney")
    if bot_record.rollypay_api_key: payments.append("RollyPay")
    await message.answer(
        f"{em('check')} <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"{em('bot')} Токен: <code>{data['token']}</code>\n"
        f"{em('profile')} Admin ID: <code>{data['admin_id']}</code>\n"
        f"{em('wallet')} Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"{em('info')} Управление ботом в разделе «📋 Мои боты»",
        reply_markup=main_menu_kb()
    )

# ── Мои боты ───────────────────────────────────────────────

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        bots = (await session.execute(select(ShopBot).where(ShopBot.owner_id == message.from_user.id))).scalars().all()
        products_counts = {}
        for bot in bots:
            products_counts[bot.id] = await session.scalar(
                select(func.count(Product.id)).where(Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id)))
            )
    if not bots: return await message.answer("У вас пока нет ботов.\nНажмите «🛠 Создать бота»!")
    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token: payments.append("Crypto Bot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        if bot.rollypay_api_key: payments.append("RollyPay")
        text = (
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"{em('chart_stats')} Статус: {status}\n"
            f"{em('wallet')} Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"{em('box')} Товаров: {products_counts.get(bot.id, 0)}\n"
            f"{em('info')} ID: <code>{bot.id}</code>"
        )
        await message.answer(text, reply_markup=bot_management_kb(bot.id))

# ── Навигация назад ────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("back_to_bot:"))
async def back_to_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
        payments = []
        if bot.crypto_bot_token: payments.append("Crypto Bot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        if bot.rollypay_api_key: payments.append("RollyPay")
        products_count = await session.scalar(
            select(func.count(Product.id)).where(Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id)))
        )
    text = (
        f"🤖 <b>{bot.bot_name}</b>\nСтатус: {'🟢 Активен' if bot.is_active else '🔴 Остановлен'}\n"
        f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"Товаров: {products_count}\nID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id))
    await callback.answer()

# ── Управление категориями ─────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_cats:"))
async def manage_cats(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id).order_by(Category.id))).scalars().all()
        counts = {}
        for c in cats:
            counts[c.id] = await session.scalar(select(func.count(Product.id)).where(Product.category_id == c.id))
    text = f"{em('box')} <b>Категории бота «{bot.bot_name}»</b>\n\n"
    if cats:
        for i, c in enumerate(cats, 1):
            text += f"{i}. {c.name} ({counts.get(c.id, 0)} товаров)\n"
    else:
        text += "Категорий пока нет.\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('add_text')} Добавить категорию", callback_data=f"add_cat:{bot_id}")],
    ])
    if cats:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{em('trash')} Удалить категорию", callback_data=f"del_cat_menu:{bot_id}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=f"{em('back')} Назад", callback_data=f"back_to_bot:{bot_id}")])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_cat:"))
async def add_cat_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id); await state.set_state(AddCategoryFSM.name)
    await callback.message.answer(f"{em('pencil')} Введите название категории:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AddCategoryFSM.name))
async def add_cat_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    name = message.text.strip()
    if not name: return await message.answer(f"{em('cross')} Введите название.")
    data = await state.get_data(); bot_id = data["bot_id"]; await state.clear()
    async with async_session_maker() as session:
        session.add(Category(bot_id=bot_id, name=name)); await session.commit()
    await message.answer(f"{em('check')} Категория «{name}» добавлена!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("del_cat_menu:"))
async def del_cat_menu(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    if not cats: return await callback.answer("Нет категорий.", show_alert=True)
    await callback.message.edit_text(f"{em('trash')} Выберите категорию для удаления:", reply_markup=inline_kb([(c.name, f"confirm_del_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_del_cat:"))
async def confirm_del_cat(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cat = await session.get(Category, cat_id)
        if not cat: return await callback.answer("Категория не найдена.")
        bot_id, name = cat.bot_id, cat.name
        await session.execute(delete(Category).where(Category.id == cat_id)); await session.commit()
    await callback.message.edit_text(f"{em('trash')} Категория «{name}» удалена.", reply_markup=back_kb(bot_id))
    await callback.answer()

# ── Управление товарами ────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_products:"))
async def manage_products(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
    text = f"{em('gift')} <b>Управление товарами — «{bot.bot_name}»</b>\n\nВыберите действие:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('add_text')} Добавить товар", callback_data=f"add_product:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('box')} Список товаров", callback_data=f"list_products:{bot_id}:0")],
        [InlineKeyboardButton(text=f"{em('trash')} Удалить товар", callback_data=f"del_product_menu:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('back')} Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_product:"))
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    if not cats: return await callback.answer("Сначала создайте категорию!", show_alert=True)
    await state.update_data(bot_id=bot_id); await state.set_state(AddProductFSM.category)
    await callback.message.answer(f"{em('box')} Выберите категорию:", reply_markup=inline_kb([(c.name, f"prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(AddProductFSM.category), F.data.startswith("prod_cat:"))
async def add_product_name(callback: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(callback.data.split(":")[1]))
    await state.set_state(AddProductFSM.name)
    await callback.message.answer(f"{em('pencil')} Название товара:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductFSM.description)
    await message.answer(f"{em('write')} Описание (или «-»):")

@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    await state.update_data(description=None if message.text.strip() == "-" else message.text.strip())
    await state.set_state(AddProductFSM.price)
    await message.answer(f"{em('coin')} Цена (например: 299.00):")

@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0: raise ValueError
    except: return await message.answer(f"{em('cross')} Некорректная цена.")
    data = await state.get_data(); bot_id = data["bot_id"]; await state.clear()
    async with async_session_maker() as session:
        session.add(Product(category_id=data["category_id"], name=data["name"], description=data.get("description"), price=price))
        await session.commit()
    await message.answer(f"{em('check')} Товар «{data['name']}» добавлен! Цена: {price} ₽", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("list_products:"))
async def list_products(callback: CallbackQuery):
    parts = callback.data.split(":")
    bot_id = int(parts[1]); page = int(parts[2]) if len(parts) > 2 else 0
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    all_products = []
    for c in cats:
        async with async_session_maker() as session:
            for p in (await session.execute(select(Product).where(Product.category_id == c.id).order_by(Product.id))).scalars().all():
                all_products.append((c.name, p))
    text = f"{em('box')} <b>Товары бота «{bot.bot_name}»</b>\n\n"
    if not all_products:
        text += "Товаров пока нет."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{em('add_text')} Добавить товар", callback_data=f"add_product:{bot_id}")],
            [InlineKeyboardButton(text=f"{em('back')} Назад", callback_data=f"back_to_bot:{bot_id}")],
        ])
        return await callback.message.edit_text(text, reply_markup=kb)
    per_page = 10; total_pages = (len(all_products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    for i, (cat_name, p) in enumerate(all_products[page*per_page:(page+1)*per_page], page*per_page + 1):
        text += f"{i}. {'✅' if p.is_available else '❌'} {p.name} — {p.price} ₽ [{cat_name}]\n"
    text += f"\nСтраница {page+1}/{total_pages}"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️", callback_data=f"list_products:{bot_id}:{page-1}"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="▶️", callback_data=f"list_products:{bot_id}:{page+1}"))
    if nav: kb.inline_keyboard.append(nav)
    kb.inline_keyboard.append([InlineKeyboardButton(text=f"{em('back')} Назад", callback_data=f"back_to_bot:{bot_id}")])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("del_product_menu:"))
async def del_product_menu(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    if not cats: return await callback.answer("Нет категорий.")
    await state.update_data(bot_id=bot_id); await state.set_state(DeleteProductFSM.category)
    await callback.message.answer(f"{em('box')} Выберите категорию:", reply_markup=inline_kb([(c.name, f"del_prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.category), F.data.startswith("del_prod_cat:"))
async def del_product_select(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        products = (await session.execute(select(Product).where(Product.category_id == cat_id))).scalars().all()
    if not products: await callback.answer("Нет товаров.", show_alert=True); await state.clear(); return
    await state.set_state(DeleteProductFSM.product)
    await callback.message.answer(f"{em('trash')} Выберите товар:", reply_markup=inline_kb([(f"{p.name} ({p.price} ₽)", f"confirm_del_prod:{p.id}") for p in products]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.product), F.data.startswith("confirm_del_prod:"))
async def confirm_del_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    data = await state.get_data(); bot_id = data["bot_id"]; await state.clear()
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        name = product.name if product else "Товар"
        await session.execute(delete(Product).where(Product.id == product_id)); await session.commit()
    await callback.message.edit_text(f"{em('trash')} Товар «{name}» удалён.", reply_markup=back_kb(bot_id))
    await callback.answer()

# ── Платёжные реквизиты бота ───────────────────────────────

@constructor_router.callback_query(F.data.startswith("payment_settings:"))
async def payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
    if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
    text = (
        f"{em('wallet')} <b>Платежи — «{bot.bot_name}»</b>\n\n"
        f"{em('cryptobot')} Crypto Bot: {'✅' if bot.crypto_bot_token else '❌'}\n"
        f"{em('send_money')} ЮMoney: {'✅' if bot.yoomoney_wallet else '❌'}\n"
        f"{em('link')} RollyPay: {'✅' if bot.rollypay_api_key else '❌'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('cryptobot')} Crypto Bot токен", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('send_money')} ЮMoney кошелёк", callback_data=f"edit_yoo:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('link')} RollyPay API ключ", callback_data=f"edit_rolly:{bot_id}")],
        [InlineKeyboardButton(text=f"{em('back')} Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_bot_id=int(callback.data.split(":")[1]))
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer(f"{em('cryptobot')} Токен Crypto Bot (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    token = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == data["edit_bot_id"]).values(crypto_bot_token=token))
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_bot_id=int(callback.data.split(":")[1]))
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer(f"{em('send_money')} Номер ЮMoney (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    wallet = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == data["edit_bot_id"]).values(yoomoney_wallet=wallet))
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_rolly:"))
async def edit_rolly_start(callback: CallbackQuery, state: FSMContext):
    await state.update_data(edit_bot_id=int(callback.data.split(":")[1]))
    await state.set_state(PaymentSettingsFSM.rollypay_key)
    await callback.message.answer(f"{em('link')} API ключ RollyPay (или «-»):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.rollypay_key))
async def edit_rolly_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    key = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == data["edit_bot_id"]).values(rollypay_api_key=key))
        await session.commit()
    await message.answer(f"{em('check')} Обновлено!", reply_markup=main_menu_kb())

# ── Статистика бота ────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_stats:"))
async def bot_stats(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
        users_count = await session.scalar(select(func.count(Purchase.user_id.distinct())).where(Purchase.bot_id == bot_id))
        purchases_total = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        purchases_pending = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "pending"))
        revenue = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        products_count = await session.scalar(select(func.count(Product.id)).where(Product.category_id.in_(select(Category.id).where(Category.bot_id == bot_id))))
        categories_count = await session.scalar(select(func.count(Category.id)).where(Category.bot_id == bot_id))
    await callback.message.edit_text(
        f"{em('chart_stats')} <b>Статистика — «{bot.bot_name}»</b>\n\n"
        f"{em('people')} Покупателей: {users_count or 0}\n"
        f"{em('box')} Категорий: {categories_count}\n"
        f"{em('gift')} Товаров: {products_count}\n"
        f"{em('check')} Продаж: {purchases_total or 0}\n"
        f"{em('clock')} Ожидают: {purchases_pending or 0}\n"
        f"{em('coin')} Выручка: {revenue or 0} ₽",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()

# ── Покупатели ─────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_buyers:"))
async def bot_buyers(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
        buyers = (await session.execute(
            select(User.telegram_id, User.username, func.count(Purchase.id), func.sum(Purchase.amount))
            .join(Purchase, User.telegram_id == Purchase.user_id)
            .where(Purchase.bot_id == bot_id, Purchase.status == "completed")
            .group_by(User.telegram_id, User.username)
            .order_by(func.sum(Purchase.amount).desc()).limit(20)
        )).all()
    text = f"{em('people')} <b>Покупатели — «{bot.bot_name}»</b>\n\n"
    if buyers:
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            display = f"@{username}" if username else f"ID:{tid}"
            text += f"{i}. {display} — {count} пок. на {total} ₽\n"
    else:
        text += "Покупателей пока нет."
    await callback.message.edit_text(text, reply_markup=back_kb(bot_id))
    await callback.answer()

# ── Рассылка по боту ───────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_broadcast:"))
async def bot_broadcast(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id: return await callback.answer("Бот не найден.")
    await state.update_data(broadcast_bot_id=bot_id); await state.set_state(BroadcastFSM.message_text)
    await callback.message.answer(f"{em('megaphone')} Введите текст рассылки:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(BroadcastFSM.message_text))
async def broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); bot_id = data["broadcast_bot_id"]; await state.clear()
    async with async_session_maker() as session:
        user_ids = [row[0] for row in (await session.execute(select(Purchase.user_id.distinct()).where(Purchase.bot_id == bot_id))).all()]
    if not user_ids: return await message.answer("Нет пользователей для рассылки.", reply_markup=main_menu_kb())
    sent, failed = 0, 0
    status_msg = await message.answer(f"{em('loading')} Рассылка на {len(user_ids)} пользователей...")
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception: failed += 1
        if (i+1) % 20 == 0:
            try: await status_msg.edit_text(f"{em('loading')} Отправлено: {sent}/{len(user_ids)}")
            except: pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"{em('check')} Рассылка завершена!\n✅ {sent}\n❌ {failed}")

# ── Toggle / Delete ────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if bot and bot.owner_id == callback.from_user.id:
            bot.is_active = not bot.is_active; await session.commit()
            await callback.answer(f"Бот {'запущен' if bot.is_active else 'остановлен'}.")

@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{em('check')} Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
         InlineKeyboardButton(text=f"{em('cross')} Нет", callback_data="cancel_delete")]
    ])
    await callback.message.answer(f"{em('trash')} Удалить бота? Все данные будут потеряны.", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id))
        await session.commit()
    await callback.message.edit_text(f"{em('trash')} Бот удалён.")
    await callback.answer()

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()

# ── Профиль ────────────────────────────────────────────────

@constructor_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
        bots_count = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id))
        total_purchases = await session.scalar(select(func.count(Purchase.id)).where(Purchase.user_id == message.from_user.id, Purchase.status == "completed"))
    await message.answer(
        f"{em('profile')} <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"{em('star')} Подписка: {user.subscription.upper()}\n"
        f"Баланс: {user.balance} ₽\n"
        f"{em('bot')} Ботов создано: {bots_count}\n"
        f"{em('gift')} Всего покупок: {total_purchases}"
    )

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY (ТОЛЬКО ПОКУПКИ)
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    shop_router = Router()

    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        await message.answer(f"🎮 Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\nЗдесь можно купить донат для игр Supercell.", reply_markup=shop_menu_kb())

    @shop_router.message(F.text == "🛒 Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            cats = (await session.execute(select(Category).where(Category.bot_id == bot_record.id))).scalars().all()
        if not cats: return await message.answer("😔 Пока нет доступных категорий.")
        await message.answer("🎮 Выберите игру:", reply_markup=inline_kb([(c.name, f"shop_cat:{c.id}") for c in cats]))

    @shop_router.callback_query(F.data.startswith("shop_cat:"))
    async def show_products(callback: CallbackQuery):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            products = (await session.execute(select(Product).where(Product.category_id == cat_id, Product.is_available == True))).scalars().all()
            cat = await session.get(Category, cat_id)
        if not products: return await callback.answer("Нет товаров.", show_alert=True)
        await callback.message.answer(f"📦 <b>{cat.name}</b>:", reply_markup=inline_kb([(f"{p.name} — {p.price} ₽", f"shop_product:{p.id}") for p in products]))
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("shop_product:"))
    async def product_detail(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
        if not product: return await callback.answer("Товар не найден.", show_alert=True)
        text = f"🛍 <b>{product.name}</b>\n\n{product.description or ''}\n\n💰 Цена: <b>{product.price} ₽</b>"
        btns = []
        if bot_record.crypto_bot_token: btns.append(("💎 Crypto Bot", f"pay_crypto:{product_id}"))
        if bot_record.yoomoney_wallet: btns.append(("💸 ЮMoney", f"pay_yoo:{product_id}"))
        if bot_record.rollypay_api_key: btns.append(("🔗 RollyPay", f"pay_rolly:{product_id}"))
        if not btns: return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")
        await callback.message.answer(text + "\n\n💳 Выберите способ оплаты:", reply_markup=inline_kb(btns))
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            purchase = Purchase(user_id=callback.from_user.id, bot_id=bot_record.id, product_id=product_id, amount=product.price, status="pending", payment_method="crypto_bot")
            session.add(purchase); await session.commit(); await session.refresh(purchase)
            api = CryptoBotAPI(bot_record.crypto_bot_token)
            invoice = await api.create_invoice(float(product.price), f"Покупка: {product.name}", str(purchase.id))
        if not invoice: return await callback.message.answer("❌ Ошибка создания счёта!")
        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оплатить", url=pay_url)]])
        await callback.message.answer(f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить» 👇", reply_markup=kb)
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(user_id=callback.from_user.id, bot_id=bot_record.id, product_id=product_id, amount=product.price, status="pending", payment_method=f"yoomoney:{label}")
            session.add(purchase); await session.commit()
            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(float(product.price), label, f"Покупка: {product.name}")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Оплатить через ЮMoney", url=pay_url)]])
        await callback.message.answer(f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить» 👇", reply_markup=kb)
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_rolly:"))
    async def pay_rolly(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            purchase = Purchase(user_id=callback.from_user.id, bot_id=bot_record.id, product_id=product_id, amount=product.price, status="pending", payment_method="rollypay")
            session.add(purchase); await session.commit(); await session.refresh(purchase)
            api = RollyPayAPI(bot_record.rollypay_api_key)
            result = await api.create_payment(float(product.price), f"shop_{purchase.id}", f"Покупка: {product.name}")
        if not result or "pay_url" not in result: return await callback.message.answer("❌ Ошибка создания счёта!")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Оплатить через RollyPay", url=result["pay_url"])]])
        await callback.message.answer(f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить» 👇", reply_markup=kb)
        await callback.answer()

    @shop_router.message(F.text == "📦 Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            rows = (await session.execute(select(Purchase, Product).join(Product).where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id).order_by(Purchase.created_at.desc()).limit(20))).all()
        if not rows: return await message.answer("У вас пока нет покупок.")
        text = "📦 <b>Ваши покупки:</b>\n\n"
        for purchase, product in rows:
            status_map = {"pending": "⏳", "completed": "✅"}
            text += f"🛍 {product.name} — {purchase.amount} ₽ {status_map.get(purchase.status, '')}\n"
        await message.answer(text)

    @shop_router.message(F.text == "👤 Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            total = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id, Purchase.status == "completed"))
        await message.answer(f"👤 <b>Профиль</b>\n\nID: <code>{message.from_user.id}</code>\nБаланс: {user.balance} ₽\nПотрачено: {total} ₽")

    return shop_router

# ═══════════════════════════════════════════════════════════
# RUNNING BOTS
# ═══════════════════════════════════════════════════════════

running_tasks: dict[int, asyncio.Task] = {}

async def run_shop_bot(bot_record: ShopBot):
    if bot_record.id in running_tasks: return
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
        bots = (await session.execute(select(ShopBot).where(ShopBot.is_active == True))).scalars().all()
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
