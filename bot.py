"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL
Bothost-compatible: reads BOT_TOKEN & DATABASE_URL from env
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from urllib.parse import quote

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
    ReplyKeyboardMarkup, KeyboardButton, BotCommand
)
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, Numeric, String, Text,
    ForeignKey, select, func, update, delete, and_, or_, inspect
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
ADMIN_IDS = [7973988177]

if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("DATABASE_URL adapted for asyncpg")

if not BOT_TOKEN or not DATABASE_URL:
    logger.error("BOT_TOKEN or DATABASE_URL not set!")
    exit(1)

# ═══════════════════════════════════════════════════════════
# PREMIUM EMOJI IDs
# ═══════════════════════════════════════════════════════════

class Emoji:
    SETTINGS_ID = "5870982283724328568"
    PROFILE_ID = "5870994129244131212"
    PEOPLE_ID = "5870772616305839506"
    FILE_ID = "5870528606328852614"
    SMILE_ID = "5870764288364252592"
    GRAPH_UP_ID = "5870930636742595124"
    STATS_ID = "5870921681735781843"
    HOME_ID = "5873147866364514353"
    LOCK_CLOSED_ID = "6037249452824072506"
    LOCK_OPEN_ID = "6037496202990194718"
    MEGAPHONE_ID = "6039422865189638057"
    CHECK_ID = "5870633910337015697"
    CROSS_ID = "5870657884844462243"
    PENCIL_ID = "5870676941614354370"
    TRASH_ID = "5870875489362513438"
    BACK_ID = "5775896410780079073"
    PAPERCLIP_ID = "6039451237743595514"
    LINK_ID = "5769289093221454192"
    INFO_ID = "6028435952299413210"
    BOT_ID = "6030400221232501136"
    SEND_ID = "5963103826075456248"
    BELL_ID = "6039486778597970865"
    GIFT_ID = "6032644646587338669"
    CLOCK_ID = "5983150113483134607"
    PARTY_ID = "6041731551845159060"
    WALLET_ID = "5769126056262898415"
    BOX_ID = "5884479287171485878"
    CRYPTOBOT_ID = "5260752406890711732"
    CALENDAR_ID = "5890937706803894250"
    TAG_ID = "5886285355279193209"
    MONEY_ID = "5904462880941545555"
    SEND_MONEY_ID = "5890848474563352982"
    ACCEPT_MONEY_ID = "5879814368572478751"
    CODE_ID = "5940433880585605708"
    LOADING_ID = "5345906554510012647"
    CROWN_ID = "5367404172557355066"
    STAR_ID = "5870810157871667232"
    DIAMOND_ID = "5870810157871667232"
    FIRE_ID = "5369198904321376256"
    ROCKET_ID = "5369198904321376256"
    SHOP_ID = "5373141891321699086"
    SUBSCRIBE_ID = "6039450962865688331"
    VERIFY_ID = "5774022692642492953"
    
    SETTINGS = f'<tg-emoji emoji-id="{SETTINGS_ID}">⚙</tg-emoji>'
    PROFILE = f'<tg-emoji emoji-id="{PROFILE_ID}">👤</tg-emoji>'
    PEOPLE = f'<tg-emoji emoji-id="{PEOPLE_ID}">👥</tg-emoji>'
    FILE = f'<tg-emoji emoji-id="{FILE_ID}">📁</tg-emoji>'
    SMILE = f'<tg-emoji emoji-id="{SMILE_ID}">🙂</tg-emoji>'
    STATS = f'<tg-emoji emoji-id="{STATS_ID}">📊</tg-emoji>'
    HOME = f'<tg-emoji emoji-id="{HOME_ID}">🏘</tg-emoji>'
    LOCK_CLOSED = f'<tg-emoji emoji-id="{LOCK_CLOSED_ID}">🔒</tg-emoji>'
    LOCK_OPEN = f'<tg-emoji emoji-id="{LOCK_OPEN_ID}">🔓</tg-emoji>'
    MEGAPHONE = f'<tg-emoji emoji-id="{MEGAPHONE_ID}">📣</tg-emoji>'
    CHECK = f'<tg-emoji emoji-id="{CHECK_ID}">✅</tg-emoji>'
    CROSS = f'<tg-emoji emoji-id="{CROSS_ID}">❌</tg-emoji>'
    PENCIL = f'<tg-emoji emoji-id="{PENCIL_ID}">🖋</tg-emoji>'
    TRASH = f'<tg-emoji emoji-id="{TRASH_ID}">🗑</tg-emoji>'
    BACK = f'<tg-emoji emoji-id="{BACK_ID}">◁</tg-emoji>'
    PAPERCLIP = f'<tg-emoji emoji-id="{PAPERCLIP_ID}">📎</tg-emoji>'
    LINK = f'<tg-emoji emoji-id="{LINK_ID}">🔗</tg-emoji>'
    INFO = f'<tg-emoji emoji-id="{INFO_ID}">ℹ</tg-emoji>'
    BOT = f'<tg-emoji emoji-id="{BOT_ID}">🤖</tg-emoji>'
    SEND = f'<tg-emoji emoji-id="{SEND_ID}">⬆</tg-emoji>'
    BELL = f'<tg-emoji emoji-id="{BELL_ID}">🔔</tg-emoji>'
    GIFT = f'<tg-emoji emoji-id="{GIFT_ID}">🎁</tg-emoji>'
    CLOCK = f'<tg-emoji emoji-id="{CLOCK_ID}">⏰</tg-emoji>'
    PARTY = f'<tg-emoji emoji-id="{PARTY_ID}">🎉</tg-emoji>'
    WALLET = f'<tg-emoji emoji-id="{WALLET_ID}">👛</tg-emoji>'
    BOX = f'<tg-emoji emoji-id="{BOX_ID}">📦</tg-emoji>'
    CRYPTOBOT = f'<tg-emoji emoji-id="{CRYPTOBOT_ID}">👾</tg-emoji>'
    CALENDAR = f'<tg-emoji emoji-id="{CALENDAR_ID}">📅</tg-emoji>'
    TAG = f'<tg-emoji emoji-id="{TAG_ID}">🏷</tg-emoji>'
    MONEY = f'<tg-emoji emoji-id="{MONEY_ID}">🪙</tg-emoji>'
    SEND_MONEY = f'<tg-emoji emoji-id="{SEND_MONEY_ID}">🪙</tg-emoji>'
    ACCEPT_MONEY = f'<tg-emoji emoji-id="{ACCEPT_MONEY_ID}">🏧</tg-emoji>'
    CODE = f'<tg-emoji emoji-id="{CODE_ID}">🔨</tg-emoji>'
    LOADING = f'<tg-emoji emoji-id="{LOADING_ID}">🔄</tg-emoji>'
    CROWN = f'<tg-emoji emoji-id="{CROWN_ID}">👑</tg-emoji>'
    STAR = f'<tg-emoji emoji-id="{STAR_ID}">⭐</tg-emoji>'
    DIAMOND = f'<tg-emoji emoji-id="{DIAMOND_ID}">💎</tg-emoji>'
    FIRE = f'<tg-emoji emoji-id="{FIRE_ID}">🔥</tg-emoji>'
    ROCKET = f'<tg-emoji emoji-id="{ROCKET_ID}">🚀</tg-emoji>'

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
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")
    subscription_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class AdminConfig(Base):
    __tablename__ = "admin_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pro_subscription_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("100.00"))
    premium_subscription_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("250.00"))

class ShopBot(Base):
    __tablename__ = "bots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))

# ═══════════════════════════════════════════════════════════
# DATABASE ENGINE & MIGRATIONS
# ═══════════════════════════════════════════════════════════

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def run_migrations():
    """Автоматическое добавление недостающих колонок"""
    async with engine.begin() as conn:
        # Проверяем существующие колонки
        def get_columns(connection, table_name):
            inspector = inspect(connection)
            return [col["name"] for col in inspector.get_columns(table_name)]
        
        # Миграция для bots
        existing_cols = await conn.run_sync(lambda c: get_columns(c, "bots"))
        
        if "rollypay_api_key" not in existing_cols:
            logger.info("Adding rollypay_api_key column to bots table...")
            await conn.execute(text("ALTER TABLE bots ADD COLUMN rollypay_api_key VARCHAR(255)"))
        
        if "rollypay_signing_secret" not in existing_cols:
            logger.info("Adding rollypay_signing_secret column to bots table...")
            await conn.execute(text("ALTER TABLE bots ADD COLUMN rollypay_signing_secret VARCHAR(255)"))
        
        # Проверяем существование таблицы users
        try:
            existing_cols = await conn.run_sync(lambda c: get_columns(c, "users"))
        except Exception:
            existing_cols = []
        
        if "subscription_tier" not in existing_cols and "balance" in existing_cols:
            logger.info("Adding subscription columns to users table...")
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'free'"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires TIMESTAMP"))
        
        # Проверка purchases
        try:
            existing_cols = await conn.run_sync(lambda c: get_columns(c, "purchases"))
        except Exception:
            existing_cols = []
        
        if "payment_id" not in existing_cols and "id" in existing_cols:
            logger.info("Adding payment_id column to purchases table...")
            await conn.execute(text("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_id VARCHAR(255)"))
        
        # Проверка таблиц на существование
        def table_exists(connection, table_name):
            inspector = inspect(connection)
            return table_name in inspector.get_table_names()
        
        tables_exist = await conn.run_sync(lambda c: table_exists(c, "subscriptions"))
        if not tables_exist:
            logger.info("Creating new tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("New tables created!")
    
    logger.info("Migrations completed!")

async def init_db():
    """Initialize database with migrations"""
    await run_migrations()
    
    # Создаём таблицы, если их нет
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Ensure admin config exists
    async with async_session_maker() as session:
        admin_config = await session.execute(select(AdminConfig).limit(1))
        if not admin_config.scalar_one_or_none():
            session.add(AdminConfig())
            await session.commit()
    
    logger.info("Database ready!")

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str]) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_admin_config(session: AsyncSession) -> AdminConfig:
    result = await session.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = AdminConfig()
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config

async def check_subscription(session: AsyncSession, user_id: int) -> User:
    user = await get_or_create_user(session, user_id, None)
    if hasattr(user, 'subscription_tier') and user.subscription_tier and user.subscription_tier != "free" and user.subscription_expires:
        if user.subscription_expires < datetime.utcnow():
            user.subscription_tier = "free"
            user.subscription_expires = None
            await session.commit()
    return user

async def can_create_bot(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    user = await check_subscription(session, user_id)
    
    bots_count = await session.scalar(
        select(func.count(ShopBot.id)).where(ShopBot.owner_id == user_id)
    )
    
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    limits = {"free": 1, "pro": 5, "premium": 30}
    max_bots = limits.get(tier, 1)
    
    if bots_count >= max_bots:
        return False, f"Достигнут лимит ботов ({max_bots}) для тарифа {tier}. Повысьте тариф!"
    return True, ""

# ═══════════════════════════════════════════════════════════
# PAYMENT APIS
# ═══════════════════════════════════════════════════════════

class CryptoBotAPI:
    BASE_URL = "https://pay.crypt.bot/api"
    def __init__(self, token: str):
        self.token = token
    
    async def _request(self, method: str, **kwargs) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/{method}",
                    headers={"Crypto-Pay-API-Token": self.token},
                    json=kwargs,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]
                    logger.error(f"CryptoBot API error: {data}")
                    return None
        except Exception as e:
            logger.error(f"CryptoBot request error: {e}")
            return None
    
    async def create_invoice(self, amount: float, description: str, payload: str) -> Optional[dict]:
        return await self._request("createInvoice",
            currency_type="fiat", fiat="RUB", amount=str(amount),
            description=description, payload=payload,
            paid_btn_name="callback", paid_btn_url="https://t.me/"
        )
    
    async def check_invoice(self, invoice_id: int) -> Optional[str]:
        result = await self._request("getInvoices", invoice_ids=[invoice_id])
        if result and result.get("items"):
            return result["items"][0].get("status")
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
    
    def __init__(self, api_key: str, signing_secret: str = ""):
        self.api_key = api_key
        self.signing_secret = signing_secret
    
    async def create_payment(self, amount: float, order_id: str, description: str) -> Optional[dict]:
        try:
            nonce = str(uuid.uuid4())
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payments",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce
                    },
                    json={
                        "amount": f"{amount:.2f}",
                        "payment_currency": "RUB",
                        "order_id": order_id,
                        "description": description
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"RollyPay create payment error: {e}")
            return None
    
    async def check_payment(self, payment_id: str) -> Optional[dict]:
        try:
            nonce = str(uuid.uuid4())
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/payments/{payment_id}",
                    headers={
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"RollyPay check payment error: {e}")
            return None

# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛠 Создать бота"),
                KeyboardButton(text="📋 Мои боты")
            ],
            [
                KeyboardButton(text="👑 Подписка"),
                KeyboardButton(text="👤 Профиль")
            ],
        ],
        resize_keyboard=True
    )

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛒 Купить донат"),
                KeyboardButton(text="📦 Мои покупки")
            ],
            [
                KeyboardButton(text="👤 Профиль")
            ],
        ],
        resize_keyboard=True
    )

def bot_management_kb(bot_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📁 Категории", callback_data=f"manage_cats:{bot_id}")],
        [InlineKeyboardButton(text="📦 Товары", callback_data=f"manage_products:{bot_id}")],
        [InlineKeyboardButton(text="💳 Платежи", callback_data=f"payment_settings:{bot_id}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"bot_stats:{bot_id}")],
        [InlineKeyboardButton(text="📣 Рассылка", callback_data=f"bot_broadcast:{bot_id}")],
        [InlineKeyboardButton(text="👥 Покупатели", callback_data=f"bot_buyers:{bot_id}")],
        [
            InlineKeyboardButton(
                text=f"{'⏸ Остановить' if is_active else '▶️ Запустить'}",
                callback_data=f"toggle_bot:{bot_id}"
            ),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot_id}"),
        ],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к управлению", callback_data=f"back_to_bot:{bot_id}")]
    ])

def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])

def subscription_kb(user_tier: str = "free") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if user_tier != "pro":
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💎 Купить PRO (100₽)", callback_data="buy_sub:pro:crypto"),
            InlineKeyboardButton(text="💎 PRO ЮMoney", callback_data="buy_sub:pro:yoomoney"),
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💎 PRO RollyPay", callback_data="buy_sub:pro:rollypay"),
        ])
    
    if user_tier != "premium":
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="👑 Купить PREMIUM (250₽)", callback_data="buy_sub:premium:crypto"),
            InlineKeyboardButton(text="👑 PREMIUM ЮMoney", callback_data="buy_sub:premium:yoomoney"),
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="👑 PREMIUM RollyPay", callback_data="buy_sub:premium:rollypay"),
        ])
    
    return kb

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👾 Crypto Bot", callback_data="admin_crypto"),
            InlineKeyboardButton(text="💳 ЮMoney", callback_data="admin_yoomoney"),
        ],
        [
            InlineKeyboardButton(text="💰 RollyPay", callback_data="admin_rollypay"),
        ],
        [
            InlineKeyboardButton(text="🏷 Цены подписки", callback_data="admin_prices"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_broadcast"),
        ],
    ])

def payment_method_kb(product_id: int, bot: ShopBot) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="👾 Crypto Bot", callback_data=f"pay_crypto:{product_id}")
        ])
    
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💳 ЮMoney", callback_data=f"pay_yoo:{product_id}")
        ])
    
    if bot.rollypay_api_key:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💰 RollyPay (СБП)", callback_data=f"pay_rolly:{product_id}")
        ])
    
    return kb

def payment_invoice_kb(pay_url: str, payment_method: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay:{payment_method}:{payment_id}")],
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
    rollypay_api_key = State()
    rollypay_secret = State()

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

class AdminFSM(StatesGroup):
    setting_type = State()
    value = State()

class AdminBroadcastFSM(StatesGroup):
    message_text = State()

class AdminPricesFSM(StatesGroup):
    price_type = State()
    value = State()

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
        "• Создайте бота для продажи доната\n"
        "• Управляйте товарами и категориями\n"
        "• Принимайте платежи через CryptoBot, ЮMoney, RollyPay\n\n"
        "👑 Доступны тарифы: Бесплатный (1 бот), PRO (5 ботов, 100₽/мес), PREMIUM (30 ботов, 250₽/мес)",
        reply_markup=main_menu_kb()
    )

@constructor_router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ У вас нет доступа к админ-панели.")
    await message.answer("⚙️ <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_menu_kb())

@constructor_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
    
    tier_display = {"free": "Бесплатный", "pro": "PRO", "premium": "PREMIUM"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    tier_text = tier_display.get(tier, "Бесплатный")
    
    limits = {"free": "1 бот", "pro": "5 ботов", "premium": "30 ботов"}
    
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"Тариф: {tier_text}\n"
        f"Лимит ботов: {limits.get(tier, '1 бот')}\n"
        f"Ботов создано: {bots_count}"
    )

@constructor_router.message(F.text == "👑 Подписка")
async def subscription_menu(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
    
    tier_display = {"free": "Бесплатный", "pro": "PRO", "premium": "PREMIUM"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    await message.answer(
        f"👑 <b>Подписка</b>\n\n"
        f"Текущий тариф: {tier_display.get(tier)}\n\n"
        f"👤 <b>Бесплатный</b> — 1 бот\n"
        f"⭐ <b>PRO</b> — 5 ботов, 100₽/мес\n"
        f"👑 <b>PREMIUM</b> — 30 ботов, 250₽/мес\n\n"
        f"Выберите тариф:",
        reply_markup=subscription_kb(tier)
    )

@constructor_router.callback_query(F.data.startswith("buy_sub:"))
async def buy_subscription(callback: CallbackQuery):
    parts = callback.data.split(":")
    tier = parts[1]
    method = parts[2]
    
    prices = {"pro": Decimal("100.00"), "premium": Decimal("250.00")}
    amount = prices.get(tier, Decimal("100.00"))
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        sub = Subscription(
            user_id=callback.from_user.id,
            tier=tier,
            amount=amount,
            payment_method=method,
            status="pending",
            expires_at=expires_at
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        
        pay_url = None
        payment_id = str(sub.id)
        
        if method == "crypto" and admin_config.crypto_bot_token:
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            invoice = await api.create_invoice(float(amount), f"Подписка {tier.upper()}", f"sub_{sub.id}")
            if invoice:
                pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
                payment_id = str(invoice.get("invoice_id", sub.id))
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer("Ошибка создания счёта CryptoBot!", show_alert=True)
                return
        
        elif method == "yoomoney" and admin_config.yoomoney_wallet:
            yoo = YooMoneyAPI(admin_config.yoomoney_wallet)
            label = f"sub_{sub.id}"
            pay_url = yoo.generate_form_url(float(amount), label, f"Подписка {tier.upper()}")
            payment_id = label
            sub.payment_id = label
            await session.commit()
        
        elif method == "rollypay" and admin_config.rollypay_api_key:
            api = RollyPayAPI(admin_config.rollypay_api_key, admin_config.rollypay_signing_secret or "")
            result = await api.create_payment(float(amount), f"sub_{sub.id}", f"Подписка {tier.upper()}")
            if result and result.get("pay_url"):
                pay_url = result.get("pay_url")
                payment_id = result.get("payment_id", f"sub_{sub.id}")
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer("Ошибка создания платежа RollyPay!", show_alert=True)
                return
        else:
            await callback.answer("Платёжная система не настроена!", show_alert=True)
            return
    
    if pay_url:
        await callback.message.answer(
            f"💳 <b>Оплата подписки {tier.upper()}</b>\n\n"
            f"Сумма: {amount} ₽\nСрок: 1 месяц\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(pay_url, method, payment_id)
        )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_pay:"))
async def check_payment_status(callback: CallbackQuery):
    parts = callback.data.split(":")
    method = parts[1]
    payment_id = parts[2]
    
    await callback.answer("🔄 Проверяю оплату...")
    
    is_paid = False
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        sub = None
        
        # Поиск подписки
        result = await session.execute(
            select(Subscription).where(
                (Subscription.payment_id == payment_id) |
                (Subscription.id == int(payment_id) if payment_id.isdigit() else False)
            )
        )
        sub = result.scalar_one_or_none()
        
        if sub and sub.status == "completed":
            is_paid = True
        elif method == "crypto" and admin_config.crypto_bot_token:
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            if payment_id.isdigit():
                status = await api.check_invoice(int(payment_id))
                if status == "paid":
                    is_paid = True
        elif method == "rollypay" and admin_config.rollypay_api_key:
            api = RollyPayAPI(admin_config.rollypay_api_key, admin_config.rollypay_signing_secret or "")
            result = await api.check_payment(payment_id)
            if result and result.get("status") == "paid":
                is_paid = True
        
        if is_paid and sub and sub.status != "completed":
            sub.status = "completed"
            user = await get_or_create_user(session, sub.user_id, None)
            user.subscription_tier = sub.tier
            user.subscription_expires = sub.expires_at
            await session.commit()
            
            await callback.message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"Тариф {sub.tier.upper()} активирован до {sub.expires_at.strftime('%d.%m.%Y')}"
            )
        elif is_paid and sub:
            await callback.message.answer("✅ Оплата уже была подтверждена.")
        else:
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")

@constructor_router.message(F.text == "🛠 Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"❌ {error_msg}")
    
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        "🤖 <b>Шаг 1/5</b> — Введите токен бота.\n\n"
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
        return await message.answer("❌ Некорректный токен.")
    
    async with async_session_maker() as session:
        exists = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if exists.scalar_one_or_none():
            return await message.answer("❌ Бот с таким токеном уже существует.")
    
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
        return await message.answer("❌ Название должно быть от 1 до 255 символов.")
    
    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer("✅ Название принято.\n\n👮 <b>Шаг 3/5</b> — Введите Telegram ID администратора:")

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
        return await message.answer("❌ Введите корректный числовой Telegram ID.")
    
    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer("✅ Admin ID принят.\n\n💎 <b>Шаг 4/5</b> — Токен Crypto Bot (или «-» пропустить):")

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer("💸 <b>Шаг 5/5</b> — Кошелёк ЮMoney (или «-» пропустить):")

@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_finish(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    yoo = message.text.strip()
    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"❌ {error_msg}", reply_markup=main_menu_kb())
        
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

        for game in ["🔵 Brawl Stars", "⚔️ Clash of Clans", "👑 Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    asyncio.create_task(run_shop_bot(bot_record))

    payments = []
    if bot_record.crypto_bot_token: payments.append("Crypto Bot")
    if bot_record.yoomoney_wallet: payments.append("ЮMoney")
    if bot_record.rollypay_api_key: payments.append("RollyPay")

    await message.answer(
        f"✅ <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"Токен: <code>{data['token']}</code>\n"
        f"Admin ID: <code>{data['admin_id']}</code>\n"
        f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"📋 Управление — «Мои боты»",
        reply_markup=main_menu_kb()
    )

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id).order_by(ShopBot.created_at.desc())
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer("У вас пока нет созданных ботов.\nНажмите «🛠 Создать бота» чтобы начать!")

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token: payments.append("Crypto Bot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        if bot.rollypay_api_key: payments.append("RollyPay")

        async with async_session_maker() as session:
            products_count = await session.scalar(
                select(func.count(Product.id)).where(
                    Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id))
                )
            )

        text = (
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"▸ Статус: {status}\n"
            f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"▸ Товаров: {products_count}\n"
            f"▸ ID: <code>{bot.id}</code>"
        )
        await message.answer(text, reply_markup=bot_management_kb(bot.id, bot.is_active))

@constructor_router.callback_query(F.data.startswith("back_to_bot:"))
async def back_to_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
    payments = []
    if bot.crypto_bot_token: payments.append("Crypto Bot")
    if bot.yoomoney_wallet: payments.append("ЮMoney")
    if bot.rollypay_api_key: payments.append("RollyPay")
    
    async with async_session_maker() as session:
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id))
            )
        )
    
    text = (
        f"🤖 <b>{bot.bot_name}</b>\n"
        f"▸ Статус: {status}\n"
        f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"▸ Товаров: {products_count}\n"
        f"▸ ID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id, bot.is_active))
    await callback.answer()

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

    text = f"📁 <b>Категории бота «{bot.bot_name}»</b>\n\n"
    if cats:
        for i, cat in enumerate(cats, 1):
            async with async_session_maker() as session:
                pc = await session.scalar(select(func.count(Product.id)).where(Product.category_id == cat.id))
            text += f"{i}. {cat.name} ({pc} товаров)\n"
    else:
        text += "Категорий пока нет.\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_cat:{bot_id}")],
    ])
    if cats:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_cat_menu:{bot_id}")
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_cat:"))
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddCategoryFSM.name)
    await callback.message.answer("✏️ Введите название категории:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AddCategoryFSM.name))
async def add_category_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name:
        return await message.answer("❌ Введите название.")
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()

    async with async_session_maker() as session:
        session.add(Category(bot_id=bot_id, name=name))
        await session.commit()

    await message.answer(f"✅ Категория «{name}» добавлена!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("del_cat_menu:"))
async def del_category_menu(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    
    if not cats:
        return await callback.answer("Нет категорий.", show_alert=True)
    
    await callback.message.edit_text(
        "🗑 Выберите категорию для удаления:",
        reply_markup=inline_kb([(c.name, f"confirm_del_cat:{c.id}") for c in cats])
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
    
    await callback.message.edit_text(f"🗑 Категория «{name}» удалена.", reply_markup=back_kb(bot_id))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("manage_products:"))
async def manage_products(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_product:{bot_id}")],
        [InlineKeyboardButton(text="📋 Список", callback_data=f"list_products:{bot_id}:0")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data=f"del_product_menu:{bot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text("🛍 <b>Управление товарами</b>\nВыберите действие:", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_product:"))
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    
    if not cats:
        return await callback.answer("Сначала создайте категорию!", show_alert=True)
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddProductFSM.category)
    await callback.message.answer("📂 Выберите категорию:", reply_markup=inline_kb([(c.name, f"prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(AddProductFSM.category), F.data.startswith("prod_cat:"))
async def add_product_name(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductFSM.name)
    await callback.message.answer("✏️ Введите название товара:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductFSM.description)
    await message.answer("📝 Введите описание (или «-» пропустить):")

@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    desc = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductFSM.price)
    await message.answer("💰 Введите цену (например: 299.00):")

@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except:
        return await message.answer("❌ Некорректная цена.")

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

    await message.answer(f"✅ Товар «{data['name']}» добавлен!\nЦена: {price} ₽", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("list_products:"))
async def list_products(callback: CallbackQuery):
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()

    all_products = []
    for cat in cats:
        async with async_session_maker() as session:
            products = (await session.execute(
                select(Product).where(Product.category_id == cat.id).order_by(Product.id)
            )).scalars().all()
        for p in products:
            all_products.append((cat.name, p))

    text = f"📦 <b>Товары</b>\n\n"
    if not all_products:
        text += "Товаров нет."
        return await callback.message.edit_text(text, reply_markup=back_kb(bot_id))

    per_page = 10
    total_pages = (len(all_products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page

    for i, (cn, p) in enumerate(all_products[start:end], start + 1):
        status = "✅" if p.is_available else "❌"
        text += f"{i}. {status} {p.name} — {p.price} ₽ [{cn}]\n"

    text += f"\nСтр. {page + 1}/{total_pages}"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"list_products:{bot_id}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"list_products:{bot_id}:{page + 1}"))
    if nav:
        kb.inline_keyboard.append(nav)
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("del_product_menu:"))
async def del_product_menu(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(DeleteProductFSM.category)
    
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    
    if not cats:
        return await callback.answer("Нет категорий.", show_alert=True)
    
    await callback.message.answer("📂 Выберите категорию:", reply_markup=inline_kb([(c.name, f"del_prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.category), F.data.startswith("del_prod_cat:"))
async def del_product_select(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        products = (await session.execute(select(Product).where(Product.category_id == cat_id))).scalars().all()
    
    if not products:
        await callback.answer("Нет товаров.", show_alert=True)
        await state.clear()
        return
    
    await state.set_state(DeleteProductFSM.product)
    await callback.message.answer("🗑 Выберите товар:", reply_markup=inline_kb(
        [(f"{p.name} ({p.price}₽)", f"confirm_del_prod:{p.id}") for p in products]
    ))
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

    await callback.message.edit_text(f"🗑 Товар «{name}» удалён.", reply_markup=back_kb(bot_id))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("payment_settings:"))
async def payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)

    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")

    text = (
        f"💳 <b>Платёжные реквизиты — «{bot.bot_name}»</b>\n\n"
        f"👾 Crypto Bot: {'✅' if bot.crypto_bot_token else '❌'}\n"
        f"💳 ЮMoney: {'✅' if bot.yoomoney_wallet else '❌'}\n"
        f"💰 RollyPay: {'✅' if bot.rollypay_api_key else '❌'}\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👾 Crypto Bot", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text="💳 ЮMoney", callback_data=f"edit_yoo:{bot_id}")],
        [InlineKeyboardButton(text="💰 RollyPay", callback_data=f"edit_rolly:{bot_id}")],
        [InlineKeyboardButton(text="🧪 Тест", callback_data=f"test_payment:{bot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer("👾 Введите токен Crypto Bot (или «-» удалить):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    token = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()

    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == bot_id).values(crypto_bot_token=token))
        await session.commit()

    await message.answer("✅ Crypto Bot обновлён!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer("💳 Введите ЮMoney (или «-» удалить):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    wallet = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()

    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == bot_id).values(yoomoney_wallet=wallet))
        await session.commit()

    await message.answer("✅ ЮMoney обновлён!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_rolly:"))
async def edit_rolly_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.rollypay_api_key)
    await callback.message.answer("💰 Введите API ключ RollyPay (или «-» удалить):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.rollypay_api_key))
async def edit_rolly_key(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    key = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(rollypay_api_key=key)
    await state.set_state(PaymentSettingsFSM.rollypay_secret)
    await message.answer("🔑 Введите Signing Secret (или «-» пропустить):")

@constructor_router.message(StateFilter(PaymentSettingsFSM.rollypay_secret))
async def edit_rolly_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    api_key = data.get("rollypay_api_key")
    secret = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()

    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot).where(ShopBot.id == bot_id).values(
                rollypay_api_key=api_key,
                rollypay_signing_secret=secret
            )
        )
        await session.commit()

    await message.answer("✅ RollyPay обновлён!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("bot_stats:"))
async def bot_stats(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")

        users_count = await session.scalar(select(func.count(Purchase.user_id.distinct())).where(Purchase.bot_id == bot_id))
        purchases_total = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        revenue = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        products_count = await session.scalar(select(func.count(Product.id)).where(Product.category_id.in_(select(Category.id).where(Category.bot_id == bot_id))))
        categories_count = await session.scalar(select(func.count(Category.id)).where(Category.bot_id == bot_id))

    text = (
        f"📊 <b>Статистика — «{bot.bot_name}»</b>\n\n"
        f"👥 Покупателей: {users_count or 0}\n"
        f"📁 Категорий: {categories_count}\n"
        f"📦 Товаров: {products_count}\n"
        f"🛒 Продаж: {purchases_total or 0}\n"
        f"💰 Выручка: {revenue or 0} ₽"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(bot_id))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("bot_buyers:"))
async def bot_buyers(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.telegram_id, User.username, func.count(Purchase.id), func.sum(Purchase.amount))
            .join(Purchase, User.telegram_id == Purchase.user_id)
            .where(Purchase.bot_id == bot_id, Purchase.status == "completed")
            .group_by(User.telegram_id, User.username)
            .order_by(func.sum(Purchase.amount).desc())
            .limit(20)
        )
        buyers = result.all()

    text = f"👥 <b>Покупатели</b>\n\n"
    if buyers:
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            display = f"@{username}" if username else f"ID:{tid}"
            text += f"{i}. {display} — {count} покупок на {total} ₽\n"
    else:
        text += "Покупателей нет."

    await callback.message.edit_text(text, reply_markup=back_kb(bot_id))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("bot_broadcast:"))
async def bot_broadcast_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(broadcast_bot_id=bot_id)
    await state.set_state(BroadcastFSM.message_text)
    await callback.message.answer(
        "📣 Введите текст рассылки (поддерживается HTML):\n\n"
        "Сообщение получат все покупатели этого бота.",
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
        result = await session.execute(select(Purchase.user_id.distinct()).where(Purchase.bot_id == bot_id))
        user_ids = [row[0] for row in result.all()]

    if not user_ids:
        return await message.answer("Нет пользователей для рассылки.", reply_markup=main_menu_kb())

    sent, failed = 0, 0
    status_msg = await message.answer(f"📣 Рассылка на {len(user_ids)} пользователей...")

    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            failed += 1
        
        if (i + 1) % 10 == 0:
            await status_msg.edit_text(f"📣 Рассылка: {i + 1}/{len(user_ids)} (✅ {sent} | ❌ {failed})")
        
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n✅ {sent} | ❌ {failed}",
        reply_markup=main_menu_kb()
    )

@constructor_router.callback_query(F.data.startswith("test_payment:"))
async def test_payment(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()

    if not cats:
        return await callback.answer("Нет категорий!", show_alert=True)

    async with async_session_maker() as session:
        products = (await session.execute(
            select(Product).where(Product.category_id == cats[0].id, Product.is_available == True)
        )).scalars().all()

    if not products:
        return await callback.answer("Нет товаров!", show_alert=True)

    p = products[0]
    kb = payment_method_kb(p.id, bot)
    
    if not kb.inline_keyboard:
        return await callback.answer("Нет настроенных платежей!", show_alert=True)

    await callback.message.answer(
        f"🧪 <b>Тестовая оплата</b>\n\nТовар: {p.name}\nЦена: {p.price} ₽\n\nВыберите способ:",
        reply_markup=kb
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("pay_crypto:"))
async def do_crypto(callback: CallbackQuery):
    product_id = int(callback.data.split(":")[1])
    # ... (аналогично shop боту)

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

@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_delete_bot:{bot_id}"),
         InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")]
    ])
    await callback.message.answer("🗑 Удалить бота? Все данные будут потеряны.", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id))
        await session.commit()
    await callback.message.edit_text("🗑 Бот удалён.")

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")

# Admin handlers
@constructor_router.callback_query(F.data == "admin_crypto")
async def admin_crypto(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="crypto")
    await callback.message.answer("👾 Введите токен Crypto Bot:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_yoomoney")
async def admin_yoomoney(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="yoomoney")
    await callback.message.answer("💳 Введите ЮMoney:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_rollypay")
async def admin_rollypay(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="rollypay_key")
    await callback.message.answer("💰 Введите API ключ RollyPay:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_bots = await session.scalar(select(func.count(ShopBot.id)))
        total_revenue = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.status == "completed"))
    
    await callback.message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Пользователей: {total_users}\n"
        f"Ботов: {total_bots}\n"
        f"Выручка: {total_revenue or 0} ₽",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminBroadcastFSM.message_text)
    await callback.message.answer("📣 Отправьте сообщение для рассылки ВСЕМ пользователям:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminFSM.value))
async def admin_save_value(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS: return
    
    data = await state.get_data()
    st = data["setting_type"]
    value = message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if st == "crypto":
            config.crypto_bot_token = value
        elif st == "yoomoney":
            config.yoomoney_wallet = value
        elif st == "rollypay_key":
            config.rollypay_api_key = value
            await state.update_data(setting_type="rollypay_secret")
            await message.answer("🔑 Введите Signing Secret:")
            return
        elif st == "rollypay_secret":
            config.rollypay_signing_secret = value
        
        await session.commit()
    
    await state.clear()
    await message.answer("✅ Сохранено!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminBroadcastFSM.message_text))
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in result.all()]
    
    sent, failed = 0, 0
    status_msg = await message.answer(f"📣 Рассылка на {len(user_ids)}...")
    
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except:
            failed += 1
        if (i + 1) % 20 == 0:
            await status_msg.edit_text(f"📣 {i + 1}/{len(user_ids)} (✅{sent} ❌{failed})")
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n✅ {sent} | ❌ {failed}")

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    shop_router = Router()

    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        await message.answer(
            f"🎮 Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат для игр Supercell.\nВыберите действие:",
            reply_markup=shop_menu_kb()
        )

    @shop_router.message(F.text == "🛒 Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(select(Category).where(Category.bot_id == bot_record.id))
            cats = result.scalars().all()
        if not cats:
            return await message.answer("😔 Пока нет доступных категорий.")
        await message.answer("🎮 Выберите игру:", reply_markup=inline_kb([(c.name, f"shop_cat:{c.id}") for c in cats]))

    @shop_router.callback_query(F.data.startswith("shop_cat:"))
    async def show_products(callback: CallbackQuery):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            products_result = await session.execute(
                select(Product).where(Product.category_id == cat_id, Product.is_available == True)
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

        text = f"🛍 <b>{product.name}</b>\n\n{product.description or ''}\n\n💰 Цена: <b>{product.price} ₽</b>"
        kb = payment_method_kb(product_id, bot_record)
        if not kb.inline_keyboard:
            return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")
        await callback.message.answer(text + "\n\n💳 Выберите способ оплаты:", reply_markup=kb)
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method="crypto_bot"
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            api = CryptoBotAPI(bot_record.crypto_bot_token)
            invoice = await api.create_invoice(float(product.price), f"Покупка: {product.name}", str(purchase.id))
        
        if not invoice:
            return await callback.message.answer("❌ Ошибка создания счёта!")
        
        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        payment_id = str(invoice.get("invoice_id", purchase.id))
        
        async with async_session_maker() as session:
            await session.execute(update(Purchase).where(Purchase.id == purchase.id).values(payment_id=payment_id))
            await session.commit()
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nНажмите «Оплатить»",
            reply_markup=payment_invoice_kb(pay_url, "crypto", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"yoomoney:{label}"
            )
            session.add(purchase)
            await session.commit()
            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(float(product.price), label, f"Покупка: {product.name}")
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽",
            reply_markup=payment_invoice_kb(pay_url, "yoomoney", label)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_rolly:"))
    async def pay_rollypay(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            order_id = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"rollypay:{order_id}"
            )
            session.add(purchase)
            await session.commit()
            api = RollyPayAPI(bot_record.rollypay_api_key, bot_record.rollypay_signing_secret or "")
            result = await api.create_payment(float(product.price), order_id, f"Покупка: {product.name}")
        
        if not result or not result.get("pay_url"):
            return await callback.message.answer("❌ Ошибка создания платежа RollyPay!")
        
        pay_url = result.get("pay_url")
        payment_id = result.get("payment_id", order_id)
        
        async with async_session_maker() as session:
            await session.execute(update(Purchase).where(Purchase.id == purchase.id).values(payment_id=payment_id))
            await session.commit()
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\nТовар: {product.name}\nСумма: {product.price} ₽\n\nОплата через СБП",
            reply_markup=payment_invoice_kb(pay_url, "rollypay", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("check_pay:"))
    async def shop_check_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        
        await callback.answer("🔄 Проверяю...")
        
        is_paid = False
        async with async_session_maker() as session:
            purchase_result = await session.execute(
                select(Purchase).where(
                    (Purchase.payment_id == payment_id) |
                    (Purchase.payment_method.contains(payment_id))
                ).order_by(Purchase.id.desc())
            )
            purchase = purchase_result.scalar_one_or_none()
            
            if purchase:
                if purchase.status == "completed":
                    is_paid = True
                elif method == "crypto" and bot_record.crypto_bot_token:
                    api = CryptoBotAPI(bot_record.crypto_bot_token)
                    if payment_id.isdigit():
                        status = await api.check_invoice(int(payment_id))
                        if status == "paid":
                            is_paid = True
                elif method == "rollypay" and bot_record.rollypay_api_key:
                    api = RollyPayAPI(bot_record.rollypay_api_key, bot_record.rollypay_signing_secret or "")
                    result = await api.check_payment(payment_id)
                    if result and result.get("status") == "paid":
                        is_paid = True
                
                if is_paid and purchase.status == "pending":
                    purchase.status = "completed"
                    await session.commit()
                    await callback.message.answer(f"✅ <b>Оплата подтверждена!</b>\nСпасибо за покупку!")
                elif is_paid:
                    await callback.message.answer("✅ Оплата уже была подтверждена.")
                else:
                    await callback.message.answer("⏳ Оплата ещё не поступила.")

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
    
    try:
        await constructor_bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="admin", description="Админ-панель"),
        ])
    except:
        pass
    
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
