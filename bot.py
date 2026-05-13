"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL
Bothost-compatible: reads BOT_TOKEN & DATABASE_URL from env
Auto-deploy — starts immediately
Payment APIs: Crypto Pay, YooMoney, RollyPay, Lolzteam
Features: Premium emojis, subscription tiers, admin panel, full management
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
    select, func, update, delete, inspect
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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
# EMOJI CONFIG - USING STANDARD UNICODE EMOJI ONLY
# ═══════════════════════════════════════════════════════════

# Since custom emoji IDs may not be available to all bots,
# we use standard Unicode emojis that work everywhere
class Emoji:
    SETTINGS = "⚙️"
    PROFILE = "👤"
    CROWN = "👑"
    STAR = "⭐"
    SMILE = "🙂"
    CHECK = "✅"
    CROSS = "❌"
    MONEY = "💰"
    LOADING = "🔄"
    BOT = "🤖"
    BOX = "📦"
    MEGAPHONE = "📣"
    STATS = "📊"
    WALLET = "👛"
    CRYPTOBOT = "💎"
    CLOCK = "⏰"
    PARTY = "🎉"
    PENCIL = "✏️"
    TRASH = "🗑️"
    BACK = "◀️"
    INFO = "ℹ️"
    PEOPLE = "👥"
    GIFT = "🎁"
    BELL = "🔔"
    CALENDAR = "📅"
    SEND = "📤"
    ADD = "➕"
    LIST = "📋"
    REMOVE = "➖"
    TEST = "🧪"
    LOLZ = "🎮"
    HOME = "🏠"
    FIRE = "🔥"
    ROCKET = "🚀"
    EYE = "👁️"
    SHOP = "🛒"
    SUBSCRIBE = "📱"
    KEY = "🔑"
    LOCK = "🔒"
    UNLOCK = "🔓"
    CHART = "📈"
    USERS = "👥"
    ROBOT = "🤖"
    GEAR = "⚙️"
    TAG = "🏷️"
    CARD = "💳"
    COINS = "🪙"
    PACKAGE = "📦"
    TROPHY = "🏆"
    GLOBE = "🌍"
    LINK = "🔗"
    MAIL = "📧"
    PHONE = "📱"
    CAMERA = "📷"
    BOOK = "📖"
    TARGET = "🎯"
    BULB = "💡"
    TOOLS = "🛠️"
    WARNING = "⚠️"
    QUESTION = "❓"
    EXCLAMATION = "❗"
    HEART = "❤️"
    SPARKLES = "✨"
    CHART_UP = "📈"
    CHART_DOWN = "📉"
    BAR_CHART = "📊"
    PIE_CHART = "📈"
    CREDIT_CARD = "💳"
    BANK = "🏦"
    ATM = "🏧"
    RECEIPT = "🧾"
    SHOPPING_CART = "🛒"
    SHOPPING_BAGS = "🛍️"
    DELIVERY = "📦"
    GLOBE_WITH_MERIDIANS = "🌐"
    LAPTOP = "💻"
    DESKTOP = "🖥️"
    KEYBOARD = "⌨️"
    MOUSE = "🖱️"
    FLOPPY = "💾"
    CD = "💿"
    DVD = "📀"
    USB = "🔌"
    BATTERY = "🔋"
    ELECTRIC_PLUG = "🔌"
    MAGNIFYING_GLASS = "🔍"
    MAGNIFYING_GLASS_TILTED = "🔎"
    LOCKED = "🔒"
    UNLOCKED = "🔓"
    LOCKED_WITH_PEN = "🔏"
    LOCKED_WITH_KEY = "🔐"
    KEY_2 = "🔑"
    HAMMER = "🔨"
    PICK = "⛏️"
    HAMMER_AND_PICK = "⚒️"
    HAMMER_AND_WRENCH = "🛠️"
    DAGGER = "🗡️"
    CROSSED_SWORDS = "⚔️"
    GUN = "🔫"
    BOOMERANG = "🪃"
    BOW_AND_ARROW = "🏹"
    SHIELD = "🛡️"
    CARPENTRY_SAW = "🪚"
    WRENCH = "🔧"
    SCREWDRIVER = "🪛"
    NUT_AND_BOLT = "🔩"
    GEAR_2 = "⚙️"
    CLAMP = "🗜️"
    SCALES = "⚖️"
    PROBING_CANE = "🦯"
    LINK_2 = "🔗"
    CHAINS = "⛓️"
    HOOK = "🪝"
    TOOLBOX = "🧰"
    MAGNET = "🧲"
    LADDER = "🪜"
    ALEMBIC = "⚗️"
    TEST_TUBE = "🧪"
    PETRI_DISH = "🧫"
    DNA = "🧬"
    MICROSCOPE = "🔬"
    TELESCOPE = "🔭"
    SATELLITE = "📡"
    SYRINGE = "💉"
    DROP_OF_BLOOD = "🩸"
    PILL = "💊"
    ADHESIVE_BANDAGE = "🩹"
    STETHOSCOPE = "🩺"
    DOOR = "🚪"
    ELEVATOR = "🛗"
    MIRROR = "🪞"
    WINDOW = "🪟"
    BED = "🛏️"
    COUCH_AND_LAMP = "🛋️"
    CHAIR = "🪑"
    TOILET = "🚽"
    PLUNGER = "🪠"
    SHOWER = "🚿"
    BATHTUB = "🛁"
    MOUSE_TRAP = "🪤"
    RAZOR = "🪒"
    LOTION_BOTTLE = "🧴"
    SAFETY_PIN = "🧷"
    BROOM = "🧹"
    BASKET = "🧺"
    ROLL_OF_PAPER = "🧻"
    BUCKET = "🪣"
    SOAP = "🧼"
    TOOTHBRUSH = "🪥"
    SPONGE = "🧽"
    FIRE_EXTINGUISHER = "🧯"
    SHOPPING_CART_2 = "🛒"

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
    total_spent: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total_purchases: Mapped[int] = mapped_column(Integer, default=0)
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
    rollypay_terminal_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lolz_api_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lolz_merchant_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    rollypay_terminal_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lolz_api_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lolz_merchant_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    """Auto-add missing columns"""
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        
        def get_columns(connection, table_name):
            inspector = inspect(connection)
            try:
                return [col["name"] for col in inspector.get_columns(table_name)]
            except:
                return []
        
        # Migration for bots
        bots_cols = await conn.run_sync(lambda c: get_columns(c, "bots"))
        for col_name in ["rollypay_terminal_id", "rollypay_api_key", "rollypay_signing_secret", "lolz_api_token", "lolz_merchant_id"]:
            if col_name not in bots_cols:
                logger.info(f"Adding {col_name} to bots table...")
                await conn.execute(text(f"ALTER TABLE bots ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(255)"))
        
        # Migration for admin_config
        admin_cols = await conn.run_sync(lambda c: get_columns(c, "admin_config"))
        for col_name in ["rollypay_terminal_id", "rollypay_api_key", "rollypay_signing_secret", "lolz_api_token", "lolz_merchant_id"]:
            if col_name not in admin_cols:
                logger.info(f"Adding {col_name} to admin_config table...")
                await conn.execute(text(f"ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(255)"))
        if "pro_subscription_price" not in admin_cols:
            await conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS pro_subscription_price NUMERIC(10,2) DEFAULT 100.00"))
        if "premium_subscription_price" not in admin_cols:
            await conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS premium_subscription_price NUMERIC(10,2) DEFAULT 250.00"))
        
        # Migration for users
        users_cols = await conn.run_sync(lambda c: get_columns(c, "users"))
        if "subscription_tier" not in users_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'free'"))
        if "subscription_expires" not in users_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires TIMESTAMP"))
        if "total_spent" not in users_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_spent NUMERIC(12,2) DEFAULT 0.00"))
        if "total_purchases" not in users_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_purchases INTEGER DEFAULT 0"))
        
        # Migration for purchases
        pur_cols = await conn.run_sync(lambda c: get_columns(c, "purchases"))
        if "payment_id" not in pur_cols:
            await conn.execute(text("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_id VARCHAR(255)"))
    
    logger.info("Migrations completed!")

async def init_db():
    """Initialize database with migrations"""
    await run_migrations()
    
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
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    if tier != "free" and getattr(user, 'subscription_expires', None):
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
        return await self._request(
            "createInvoice",
            currency_type="fiat",
            fiat="RUB",
            amount=str(amount),
            description=description,
            payload=payload,
            paid_btn_name="callback",
            paid_btn_url="https://t.me/"
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
    
    def __init__(self, terminal_id: str, api_key: str, signing_secret: str = ""):
        self.terminal_id = terminal_id
        self.api_key = api_key
        self.signing_secret = signing_secret
    
    async def create_payment(self, amount: float, order_id: str, description: str) -> Optional[dict]:
        try:
            nonce = str(uuid.uuid4())
            payload = {
                "amount": f"{amount:.2f}",
                "payment_currency": "RUB",
                "order_id": order_id,
                "description": description,
                "terminal_id": self.terminal_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payments",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce
                    },
                    json=payload,
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

class LolzteamAPI:
    BASE_URL = "https://api.lzt.market"
    
    def __init__(self, api_token: str, merchant_id: str):
        self.api_token = api_token
        self.merchant_id = merchant_id
    
    async def create_invoice(
        self,
        amount: float,
        payment_id: str,
        comment: str,
        url_success: str = "https://t.me/"
    ) -> Optional[dict]:
        try:
            payload = {
                "currency": "rub",
                "amount": amount,
                "payment_id": payment_id,
                "comment": comment,
                "url_success": url_success,
                "merchant_id": int(self.merchant_id),
                "lifetime": 3600
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/invoice",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    if "errors" in data:
                        logger.error(f"Lolzteam API error: {data['errors']}")
                        return None
                    return data
        except Exception as e:
            logger.error(f"Lolzteam request error: {e}")
            return None
    
    async def check_invoice(self, invoice_id: int) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/invoice/{invoice_id}",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    data = await resp.json()
                    if "invoice" in data:
                        return data["invoice"].get("status")
                    return None
        except Exception as e:
            logger.error(f"Lolzteam check invoice error: {e}")
            return None

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def is_rollypay_configured(bot: ShopBot) -> bool:
    """Check if all 3 RollyPay fields are filled for bot"""
    return bool(bot.rollypay_terminal_id and bot.rollypay_api_key and bot.rollypay_signing_secret)

def is_lolz_configured(bot: ShopBot) -> bool:
    """Check if all Lolzteam fields are filled for bot"""
    return bool(bot.lolz_api_token and bot.lolz_merchant_id)

def is_rollypay_admin_configured(config: AdminConfig) -> bool:
    """Check if all 3 RollyPay fields are filled in admin"""
    return bool(config.rollypay_terminal_id and config.rollypay_api_key and config.rollypay_signing_secret)

def is_lolz_admin_configured(config: AdminConfig) -> bool:
    """Check if all Lolzteam fields are filled in admin"""
    return bool(config.lolz_api_token and config.lolz_merchant_id)

# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{Emoji.TOOLS} Создать бота"), KeyboardButton(text=f"{Emoji.LIST} Мои боты")],
            [KeyboardButton(text=f"{Emoji.CROWN} Подписка"), KeyboardButton(text=f"{Emoji.PROFILE} Профиль")],
        ],
        resize_keyboard=True
    )

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{Emoji.SHOPPING_CART} Купить донат"), KeyboardButton(text=f"{Emoji.PACKAGE} Мои покупки")],
            [KeyboardButton(text=f"{Emoji.PROFILE} Профиль")],
        ],
        resize_keyboard=True
    )

def bot_management_kb(bot_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.PACKAGE} Категории", callback_data=f"manage_cats:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.BOX} Товары", callback_data=f"manage_products:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.CREDIT_CARD} Платежи", callback_data=f"payment_settings:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.CHART} Статистика", callback_data=f"bot_stats:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.MEGAPHONE} Рассылка", callback_data=f"bot_broadcast:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.USERS} Покупатели", callback_data=f"bot_buyers:{bot_id}")],
        [InlineKeyboardButton(
            text=f"{Emoji.LOCK} Остановить" if is_active else f"{Emoji.UNLOCK} Запустить",
            callback_data=f"toggle_bot:{bot_id}"
        ), InlineKeyboardButton(text=f"{Emoji.TRASH} Удалить", callback_data=f"delete_bot:{bot_id}")],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=f"{Emoji.CROSS} Отмена")]], resize_keyboard=True)

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад к управлению", callback_data=f"back_to_bot:{bot_id}")]
    ])

def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])

def tier_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.STAR} PRO — 100₽/мес (5 ботов)", callback_data="sub_tier:pro")],
        [InlineKeyboardButton(text=f"{Emoji.CROWN} PREMIUM — 250₽/мес (30 ботов)", callback_data="sub_tier:premium")],
    ])

def payment_method_sub_kb(tier: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.CRYPTOBOT} Crypto Bot", callback_data=f"sub_pay:{tier}:crypto")],
        [InlineKeyboardButton(text=f"{Emoji.CARD} ЮMoney", callback_data=f"sub_pay:{tier}:yoomoney")],
        [InlineKeyboardButton(text=f"{Emoji.COINS} RollyPay", callback_data=f"sub_pay:{tier}:rollypay")],
        [InlineKeyboardButton(text=f"{Emoji.LOLZ} Lolzteam", callback_data=f"sub_pay:{tier}:lolz")],
    ])

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.CRYPTOBOT} Crypto Bot", callback_data="admin_crypto")],
        [InlineKeyboardButton(text=f"{Emoji.CARD} ЮMoney", callback_data="admin_yoomoney")],
        [InlineKeyboardButton(text=f"{Emoji.COINS} RollyPay", callback_data="admin_rollypay")],
        [InlineKeyboardButton(text=f"{Emoji.LOLZ} Lolzteam", callback_data="admin_lolz")],
        [InlineKeyboardButton(text=f"{Emoji.TAG} Цены подписки", callback_data="admin_prices")],
        [InlineKeyboardButton(text=f"{Emoji.CHART} Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text=f"{Emoji.MEGAPHONE} Рассылка всем", callback_data="admin_broadcast")],
    ])

def payment_method_kb(product_id: int, bot: ShopBot) -> InlineKeyboardMarkup:
    """
    Payment method keyboard for product.
    Checks all fields before showing button.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{Emoji.CRYPTOBOT} Crypto Bot",
            callback_data=f"pay_crypto:{product_id}"
        )])
    
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{Emoji.CARD} ЮMoney",
            callback_data=f"pay_yoo:{product_id}"
        )])
    
    if is_rollypay_configured(bot):
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{Emoji.COINS} RollyPay (СБП)",
            callback_data=f"pay_rolly:{product_id}"
        )])
    
    if is_lolz_configured(bot):
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{Emoji.LOLZ} Lolzteam",
            callback_data=f"pay_lolz:{product_id}"
        )])
    
    return kb

def payment_invoice_kb(pay_url: str, payment_method: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.CARD} Оплатить", url=pay_url)],
        [InlineKeyboardButton(text=f"{Emoji.LOADING} Проверить оплату", callback_data=f"check_pay:{payment_method}:{payment_id}")],
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

class AdminRollyPayFSM(StatesGroup):
    setting_type = State()
    value = State()

class AdminLolzFSM(StatesGroup):
    setting_type = State()
    value = State()

class BotRollyPayFSM(StatesGroup):
    bot_id = State()
    terminal_id = State()
    api_key = State()
    signing_secret = State()

class BotLolzFSM(StatesGroup):
    bot_id = State()
    api_token = State()
    merchant_id = State()

# ═══════════════════════════════════════════════════════════
# CONSTRUCTOR BOT ROUTER
# ═══════════════════════════════════════════════════════════

constructor_router = Router()

# ── /start ─────────────────────────────────────────────────

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    try:
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        
        await message.answer(
            f"{Emoji.ROBOT} Добро пожаловать в конструктор магазинов доната!\n\n"
            f"• Создайте бота для продажи доната в играх Supercell\n"
            f"• Управляйте товарами и категориями\n"
            f"• Принимайте платежи через CryptoBot, ЮMoney, RollyPay, Lolzteam\n\n"
            f"{Emoji.CROWN} <b>Тарифы:</b>\n"
            f"👤 Бесплатный — 1 бот (навсегда)\n"
            f"{Emoji.STAR} PRO — 5 ботов, 100₽/мес\n"
            f"{Emoji.CROWN} PREMIUM — 30 ботов, 250₽/мес",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        # Fallback with minimal message
        try:
            await message.answer(
                "Добро пожаловать в конструктор магазинов доната!\n\n"
                "• Создайте бота для продажи доната\n"
                "• Управляйте товарами и категориями\n"
                "• Принимайте платежи\n\n"
                "Тарифы:\n"
                "Бесплатный — 1 бот\n"
                "PRO — 5 ботов, 100руб/мес\n"
                "PREMIUM — 30 ботов, 250руб/мес",
                reply_markup=main_menu_kb()
            )
        except:
            await message.answer("Ошибка при запуске. Попробуйте позже.")

# ── /admin ─────────────────────────────────────────────────

@constructor_router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer(f"{Emoji.CROSS} У вас нет доступа к админ-панели.")
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    status_text = (
        f"{Emoji.GEAR} <b>Админ-панель</b>\n\n"
        f"{Emoji.CRYPTOBOT} Crypto Bot: {'✅ Настроен' if config.crypto_bot_token else '❌ Не настроен'}\n"
        f"{Emoji.CARD} ЮMoney: {'✅ Настроен' if config.yoomoney_wallet else '❌ Не настроен'}\n"
        f"{Emoji.COINS} RollyPay: {'✅ Настроен' if is_rollypay_admin_configured(config) else '❌ Не настроен'}\n"
        f"{Emoji.LOLZ} Lolzteam: {'✅ Настроен' if is_lolz_admin_configured(config) else '❌ Не настроен'}\n"
        f"{Emoji.TAG} PRO: {config.pro_subscription_price}руб | PREMIUM: {config.premium_subscription_price}руб\n\n"
        f"Выберите действие:"
    )
    await message.answer(status_text, reply_markup=admin_menu_kb())

# ── Профиль ─────────────────────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.PROFILE} Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
        total_spent = getattr(user, 'total_spent', Decimal("0.00")) or Decimal("0.00")
        total_purchases = getattr(user, 'total_purchases', 0) or 0
    
    tier_display = {"free": "👤 Бесплатный", "pro": f"{Emoji.STAR} PRO", "premium": f"{Emoji.CROWN} PREMIUM"}
    limits = {"free": "1 бот", "pro": "5 ботов", "premium": "30 ботов"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free" and getattr(user, 'subscription_expires', None):
        days_left = (user.subscription_expires - datetime.utcnow()).days
        expiry = f"\n{Emoji.CLOCK} Действует ещё {days_left} дн. (до {user.subscription_expires.strftime('%d.%m.%Y')})"
    
    await message.answer(
        f"{Emoji.PROFILE} <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📛 Username: @{message.from_user.username or '—'}\n"
        f"💎 Тариф: {tier_display.get(tier, 'Бесплатный')}{expiry}\n"
        f"{Emoji.ROBOT} Лимит ботов: {limits.get(tier, '1 бот')}\n"
        f"{Emoji.LIST} Ботов создано: {bots_count}\n"
        f"{Emoji.COINS} Баланс: {user.balance}руб\n"
        f"{Emoji.SHOPPING_CART} Всего покупок: {total_purchases}\n"
        f"{Emoji.MONEY} Потрачено всего: {total_spent}руб"
    )

# ── Подписка ────────────────────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.CROWN} Подписка")
async def subscription_menu(message: Message):
    """Step 1: show tiers"""
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        config = await get_admin_config(session)
    
    tier_display = {"free": "👤 Бесплатный", "pro": f"{Emoji.STAR} PRO", "premium": f"{Emoji.CROWN} PREMIUM"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free" and getattr(user, 'subscription_expires', None):
        days_left = (user.subscription_expires - datetime.utcnow()).days
        expiry = f"\n{Emoji.CLOCK} Осталось: {days_left} дн."
    
    await message.answer(
        f"{Emoji.CROWN} <b>Подписка</b>\n\n"
        f"Ваш тариф: {tier_display.get(tier)}{expiry}\n\n"
        f"<b>Доступные тарифы:</b>\n"
        f"👤 Бесплатный — 1 бот (навсегда)\n"
        f"{Emoji.STAR} PRO — 5 ботов, {config.pro_subscription_price}руб/мес\n"
        f"{Emoji.CROWN} PREMIUM — 30 ботов, {config.premium_subscription_price}руб/мес\n\n"
        f"<b>Выберите тариф для покупки:</b>",
        reply_markup=tier_kb()
    )

@constructor_router.callback_query(F.data.startswith("sub_tier:"))
async def sub_tier_select(callback: CallbackQuery):
    """Step 2: selected tier, show payment methods"""
    tier = callback.data.split(":")[1]
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    prices = {"pro": config.pro_subscription_price, "premium": config.premium_subscription_price}
    names = {"pro": f"{Emoji.STAR} PRO", "premium": f"{Emoji.CROWN} PREMIUM"}
    
    await callback.message.edit_text(
        f"{names.get(tier)} — {prices.get(tier)}руб/мес\n\n"
        f"<b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_sub_kb(tier)
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("sub_pay:"))
async def sub_payment_process(callback: CallbackQuery):
    """Step 3: create payment with selected method"""
    parts = callback.data.split(":")
    tier = parts[1]
    method = parts[2]
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
    
    prices = {"pro": admin_config.pro_subscription_price, "premium": admin_config.premium_subscription_price}
    amount = prices.get(tier, Decimal("100.00"))
    
    # Check credentials for selected method
    if method == "crypto" and not admin_config.crypto_bot_token:
        return await callback.answer(f"{Emoji.CROSS} Crypto Bot не настроен админом!", show_alert=True)
    
    if method == "yoomoney" and not admin_config.yoomoney_wallet:
        return await callback.answer(f"{Emoji.CROSS} ЮMoney не настроен админом!", show_alert=True)
    
    if method == "rollypay" and not is_rollypay_admin_configured(admin_config):
        return await callback.answer(f"{Emoji.CROSS} RollyPay не настроен! Нужны: Terminal ID, API Key, Signing Secret", show_alert=True)
    
    if method == "lolz" and not is_lolz_admin_configured(admin_config):
        return await callback.answer(f"{Emoji.CROSS} Lolzteam не настроен! Нужны: API Token, Merchant ID", show_alert=True)
    
    async with async_session_maker() as session:
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
        
        if method == "crypto":
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            invoice = await api.create_invoice(
                float(amount),
                f"Подписка {tier.upper()} на 1 месяц",
                f"sub_{sub.id}"
            )
            
            if invoice:
                pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
                payment_id = str(invoice.get("invoice_id", sub.id))
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer(f"{Emoji.CROSS} Ошибка создания счёта CryptoBot!", show_alert=True)
                return
        
        elif method == "yoomoney":
            yoo = YooMoneyAPI(admin_config.yoomoney_wallet)
            label = f"sub_{sub.id}"
            pay_url = yoo.generate_form_url(
                float(amount),
                label,
                f"Подписка {tier.upper()} на 1 месяц"
            )
            payment_id = label
            sub.payment_id = label
            await session.commit()
        
        elif method == "rollypay":
            api = RollyPayAPI(
                admin_config.rollypay_terminal_id,
                admin_config.rollypay_api_key,
                admin_config.rollypay_signing_secret
            )
            result = await api.create_payment(
                float(amount),
                f"sub_{sub.id}",
                f"Подписка {tier.upper()} на 1 месяц"
            )
            
            if result and result.get("pay_url"):
                pay_url = result.get("pay_url")
                payment_id = result.get("payment_id", f"sub_{sub.id}")
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer(f"{Emoji.CROSS} Ошибка создания платежа RollyPay!", show_alert=True)
                return
        
        elif method == "lolz":
            api = LolzteamAPI(admin_config.lolz_api_token, admin_config.lolz_merchant_id)
            result = await api.create_invoice(
                float(amount),
                f"sub_{sub.id}",
                f"Подписка {tier.upper()} на 1 месяц"
            )
            
            if result and result.get("invoice"):
                pay_url = result["invoice"].get("url", "")
                payment_id = str(result["invoice"].get("invoice_id", sub.id))
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer(f"{Emoji.CROSS} Ошибка создания платежа Lolzteam!", show_alert=True)
                return
    
    if pay_url:
        names = {"pro": f"{Emoji.STAR} PRO", "premium": f"{Emoji.CROWN} PREMIUM"}
        await callback.message.edit_text(
            f"{Emoji.CARD} <b>Оплата {names.get(tier)}</b>\n\n"
            f"{Emoji.MONEY} Сумма: {amount} руб\n"
            f"{Emoji.CALENDAR} Срок: 1 месяц\n"
            f"🆔 ID платежа: <code>{sub.id}</code>\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(pay_url, method, payment_id)
        )
    
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_pay:"))
async def check_payment_status(callback: CallbackQuery):
    """Check payment status (for subscriptions and purchases)"""
    parts = callback.data.split(":")
    method = parts[1]
    payment_id = parts[2]
    
    await callback.answer(f"{Emoji.LOADING} Проверяю оплату...")
    
    is_paid = False
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        sub = None
        
        # Search for subscription by various criteria
        result = await session.execute(
            select(Subscription).where(
                (Subscription.payment_id == payment_id) |
                (Subscription.id == int(payment_id) if payment_id.isdigit() else False) |
                (Subscription.payment_method.contains(payment_id))
            )
        )
        sub = result.scalar_one_or_none()
        
        if sub and sub.status == "completed":
            is_paid = True
        
        elif method == "crypto" and admin_config.crypto_bot_token:
            # Check via API
            invoice_id = None
            if payment_id.isdigit():
                invoice_id = int(payment_id)
            elif sub and sub.payment_id and sub.payment_id.isdigit():
                invoice_id = int(sub.payment_id)
            
            if invoice_id:
                api = CryptoBotAPI(admin_config.crypto_bot_token)
                status = await api.check_invoice(invoice_id)
                if status == "paid":
                    is_paid = True
        
        elif method == "rollypay" and is_rollypay_admin_configured(admin_config):
            check_id = payment_id
            if sub and sub.payment_id:
                check_id = sub.payment_id
            
            api = RollyPayAPI(
                admin_config.rollypay_terminal_id,
                admin_config.rollypay_api_key,
                admin_config.rollypay_signing_secret
            )
            result = await api.check_payment(check_id)
            if result and result.get("status") == "paid":
                is_paid = True
        
        elif method == "lolz" and is_lolz_admin_configured(admin_config):
            invoice_id = None
            if payment_id.isdigit():
                invoice_id = int(payment_id)
            elif sub and sub.payment_id and sub.payment_id.isdigit():
                invoice_id = int(sub.payment_id)
            
            if invoice_id:
                api = LolzteamAPI(admin_config.lolz_api_token, admin_config.lolz_merchant_id)
                status = await api.check_invoice(invoice_id)
                if status == "paid":
                    is_paid = True
        
        if is_paid and sub and sub.status != "completed":
            sub.status = "completed"
            user = await get_or_create_user(session, sub.user_id, None)
            user.subscription_tier = sub.tier
            user.subscription_expires = sub.expires_at
            await session.commit()
            
            names = {"pro": f"{Emoji.STAR} PRO", "premium": f"{Emoji.CROWN} PREMIUM"}
            await callback.message.answer(
                f"{Emoji.CHECK} {Emoji.PARTY} <b>Оплата подтверждена!</b>\n\n"
                f"{Emoji.PARTY} Тариф {names.get(sub.tier, sub.tier)} активирован!\n"
                f"{Emoji.CALENDAR} Действует до: {sub.expires_at.strftime('%d.%m.%Y')}"
            )
        elif is_paid and sub:
            await callback.message.answer(f"{Emoji.CHECK} Оплата уже была подтверждена ранее.")
        else:
            await callback.message.answer(
                f"{Emoji.CLOCK} <b>Оплата ещё не поступила.</b>\n\n"
                f"Попробуйте позже или обратитесь в поддержку."
            )

# ── Создать бота ───────────────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.TOOLS} Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"{Emoji.CROSS} {error_msg}")
    
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        f"{Emoji.ROBOT} <b>Шаг 1/5</b> — Введите токен бота.\n"
        f"Получите его у @BotFather командой /newbot\n\n"
        f"Формат: <code>123456:ABC-DEF1234ghikl</code>",
        reply_markup=cancel_kb()
    )

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer(f"{Emoji.CROSS} Некорректный токен. Должен быть вида: 123456:ABC-DEF")
    
    async with async_session_maker() as session:
        exists = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if exists.scalar_one_or_none():
            return await message.answer(f"{Emoji.CROSS} Бот с таким токеном уже существует в системе.")
    
    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer(
        f"{Emoji.CHECK} Токен принят.\n\n"
        f"{Emoji.PENCIL} <b>Шаг 2/5</b> — Введите название магазина:\n"
        f"Например: «Донат Brawl Stars 24/7»"
    )

@constructor_router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer(f"{Emoji.CROSS} Название должно быть от 1 до 255 символов.")
    
    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer(
        f"{Emoji.CHECK} Название принято.\n\n"
        f"{Emoji.USERS} <b>Шаг 3/5</b> — Введите Telegram ID администратора:\n"
        f"Этот пользователь будет управлять ботом из конструктора.\n"
        f"Получить ID: @getmyid_bot"
    )

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(f"{Emoji.CROSS} Введите корректный числовой Telegram ID.")
    
    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer(
        f"{Emoji.CHECK} Admin ID принят.\n\n"
        f"{Emoji.CRYPTOBOT} <b>Шаг 4/5</b> — Введите токен Crypto Bot (от @CryptoBot):\n"
        f"Или отправьте <b>-</b> чтобы пропустить."
    )

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer(
        f"{Emoji.WALLET} <b>Шаг 5/5</b> — Введите номер кошелька ЮMoney:\n"
        f"Например: 410011234567890\n"
        f"Или отправьте <b>-</b> чтобы пропустить."
    )

@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_finish(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    yoo = message.text.strip()
    data = await state.get_data()
    await state.clear()

    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"{Emoji.CROSS} {error_msg}", reply_markup=main_menu_kb())
        
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
        f"{Emoji.CHECK} <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"{Emoji.KEY} Токен: <code>{data['token']}</code>\n"
        f"👮 Admin ID: <code>{data['admin_id']}</code>\n"
        f"{Emoji.CARD} Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"{Emoji.INFO} RollyPay и Lolzteam можно настроить в управлении ботом.\n\n"
        f"{Emoji.LIST} <b>Управление ботом доступно в разделе «📋 Мои боты»</b>\n"
        f"Там вы можете: добавлять товары, настраивать категории, делать рассылки и смотреть статистику.\n\n"
        f"{Emoji.SHOPPING_CART} Сам бот уже работает — перейдите в него и нажмите /start"
    )
    await message.answer(text, reply_markup=main_menu_kb())

# ── Мои боты ─────────────────────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.LIST} Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot)
            .where(ShopBot.owner_id == message.from_user.id)
            .order_by(ShopBot.created_at.desc())
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer(
            f"{Emoji.PACKAGE} У вас пока нет созданных ботов.\n"
            f"Нажмите «{Emoji.TOOLS} Создать бота» чтобы начать!"
        )

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token:
            payments.append("CryptoBot")
        if bot.yoomoney_wallet:
            payments.append("ЮMoney")
        if is_rollypay_configured(bot):
            payments.append("RollyPay")
        if is_lolz_configured(bot):
            payments.append("Lolzteam")

        async with async_session_maker() as session:
            products_count = await session.scalar(
                select(func.count(Product.id)).where(
                    Product.category_id.in_(
                        select(Category.id).where(Category.bot_id == bot.id)
                    )
                )
            )
            total_revenue = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(Purchase.bot_id == bot.id, Purchase.status == "completed")
            )
            total_sales = await session.scalar(
                select(func.count(Purchase.id))
                .where(Purchase.bot_id == bot.id, Purchase.status == "completed")
            )
            buyers_count = await session.scalar(
                select(func.count(Purchase.user_id.distinct()))
                .where(Purchase.bot_id == bot.id, Purchase.status == "completed")
            )

        text = (
            f"{Emoji.ROBOT} <b>{bot.bot_name}</b>\n"
            f"▸ Статус: {status}\n"
            f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"▸ Товаров: {products_count} | Продаж: {total_sales}\n"
            f"▸ Покупателей: {buyers_count} | Выручка: {total_revenue or 0} руб\n"
            f"▸ ID: <code>{bot.id}</code>"
        )
        await message.answer(text, reply_markup=bot_management_kb(bot.id, bot.is_active))

# ── Навигация "Назад к управлению" ─────────────────────────

@constructor_router.callback_query(F.data.startswith("back_to_bot:"))
async def back_to_bot_management(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
    payments = []
    if bot.crypto_bot_token:
        payments.append("CryptoBot")
    if bot.yoomoney_wallet:
        payments.append("ЮMoney")
    if is_rollypay_configured(bot):
        payments.append("RollyPay")
    if is_lolz_configured(bot):
        payments.append("Lolzteam")
    
    async with async_session_maker() as session:
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(
                    select(Category.id).where(Category.bot_id == bot.id)
                )
            )
        )
        revenue = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
            .where(Purchase.bot_id == bot.id, Purchase.status == "completed")
        )
    
    text = (
        f"{Emoji.ROBOT} <b>{bot.bot_name}</b>\n"
        f"▸ Статус: {status}\n"
        f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"▸ Товаров: {products_count}\n"
        f"▸ Выручка: {revenue or 0} руб\n"
        f"▸ ID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id, bot.is_active))
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

    text = f"{Emoji.PACKAGE} <b>Категории бота «{bot.bot_name}»</b>\n\n"
    if cats:
        for i, cat in enumerate(cats, 1):
            async with async_session_maker() as session:
                products_count = await session.scalar(
                    select(func.count(Product.id)).where(Product.category_id == cat.id)
                )
            text += f"{i}. {cat.name} ({products_count} товаров)\n"
    else:
        text += "Категорий пока нет.\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.ADD} Добавить категорию", callback_data=f"add_cat:{bot_id}")],
    ])
    if cats:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{Emoji.TRASH} Удалить категорию", callback_data=f"del_cat_menu:{bot_id}")
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_cat:"))
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddCategoryFSM.name)
    await callback.message.answer(
        f"{Emoji.PENCIL} Введите название новой категории:\n"
        f"Например: «🎁 Акции» или «{Emoji.FIRE} Хиты продаж»",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AddCategoryFSM.name))
async def add_category_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer(f"{Emoji.CROSS} Название должно быть от 1 до 255 символов.")
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()

    async with async_session_maker() as session:
        session.add(Category(bot_id=bot_id, name=name))
        await session.commit()

    await message.answer(
        f"{Emoji.CHECK} Категория «{name}» добавлена!",
        reply_markup=main_menu_kb()
    )

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
        f"{Emoji.TRASH} Выберите категорию для удаления:",
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
        f"{Emoji.TRASH} Категория «{name}» удалена.",
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

    text = f"{Emoji.BOX} <b>Управление товарами — «{bot.bot_name}»</b>\n\nВыберите действие:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.ADD} Добавить товар", callback_data=f"add_product:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.LIST} Список товаров", callback_data=f"list_products:{bot_id}:0")],
        [InlineKeyboardButton(text=f"{Emoji.REMOVE} Удалить товар", callback_data=f"del_product_menu:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

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
        f"{Emoji.PACKAGE} Выберите категорию для товара:",
        reply_markup=inline_kb([(cat.name, f"prod_cat:{cat.id}") for cat in cats])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(AddProductFSM.category), F.data.startswith("prod_cat:"))
async def add_product_name(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductFSM.name)
    await callback.message.answer(
        f"{Emoji.PENCIL} Введите название товара:\nНапример: «1000 гемов»",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name:
        return await message.answer(f"{Emoji.CROSS} Введите название товара.")
    
    await state.update_data(name=name)
    await state.set_state(AddProductFSM.description)
    await message.answer(
        f"{Emoji.PENCIL} Введите описание товара:\n"
        f"Или отправьте <b>-</b> чтобы оставить без описания."
    )

@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    desc = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductFSM.price)
    await message.answer(
        f"{Emoji.MONEY} Введите цену товара в рублях:\n"
        f"Например: 299.00 или 150"
    )

@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except (ValueError, Exception):
        return await message.answer(f"{Emoji.CROSS} Некорректная цена. Пример: 299.00")

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
        f"{Emoji.CHECK} Товар «{data['name']}» добавлен!\nЦена: {price} руб",
        reply_markup=main_menu_kb()
    )

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

    text = f"{Emoji.BOX} <b>Товары бота «{bot.bot_name}»</b>\n\n"
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
            [InlineKeyboardButton(text=f"{Emoji.ADD} Добавить товар", callback_data=f"add_product:{bot_id}")],
            [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")],
        ])
        return await callback.message.edit_text(text, reply_markup=kb)

    per_page = 10
    total_pages = (len(all_products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page

    for i, (cat_name, p) in enumerate(all_products[start:end], start + 1):
        status = "✅" if p.is_available else "❌"
        text += f"{i}. {status} {p.name} — {p.price} руб [{cat_name}]\n"

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
        InlineKeyboardButton(text=f"{Emoji.BACK} К управлению", callback_data=f"back_to_bot:{bot_id}")
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

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
        f"{Emoji.PACKAGE} Выберите категорию:",
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
        f"{Emoji.TRASH} Выберите товар для удаления:",
        reply_markup=inline_kb([(f"{p.name} ({p.price} руб)", f"confirm_del_prod:{p.id}") for p in products])
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
        f"{Emoji.TRASH} Товар «{name}» удалён.",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()

# ── Платёжные реквизиты бота ──────────────────────────────

@constructor_router.callback_query(F.data.startswith("payment_settings:"))
async def payment_settings(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)

    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")

    text = (
        f"{Emoji.WALLET} <b>Платёжные реквизиты — «{bot.bot_name}»</b>\n\n"
        f"{Emoji.CRYPTOBOT} Crypto Bot: {'✅ Настроен' if bot.crypto_bot_token else '❌ Не настроен'}\n"
        f"{Emoji.CARD} ЮMoney: {'✅ Настроен' if bot.yoomoney_wallet else '❌ Не настроен'}\n"
        f"{Emoji.COINS} RollyPay: {'✅ Настроен' if is_rollypay_configured(bot) else '❌ Не настроен'}\n"
        f"{Emoji.LOLZ} Lolzteam: {'✅ Настроен' if is_lolz_configured(bot) else '❌ Не настроен'}\n\n"
        f"<i>Для RollyPay нужны: Terminal ID, API Key, Signing Secret</i>\n"
        f"<i>Для Lolzteam нужны: API Token, Merchant ID</i>\n\n"
        f"Выберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.CRYPTOBOT} Изменить Crypto Bot", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.CARD} Изменить ЮMoney", callback_data=f"edit_yoo:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.COINS} Изменить RollyPay (3 токена)", callback_data=f"edit_rolly_bot:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.LOLZ} Изменить Lolzteam (API + Merchant)", callback_data=f"edit_lolz_bot:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.TEST} Тестовая оплата", callback_data=f"test_payment:{bot_id}")],
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    await callback.message.answer(
        f"{Emoji.CRYPTOBOT} Введите новый токен Crypto Bot:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
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

    await message.answer(f"{Emoji.CHECK} Токен Crypto Bot обновлён!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer(
        f"{Emoji.CARD} Введите новый номер кошелька ЮMoney:\nИли «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
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

    await message.answer(f"{Emoji.CHECK} Кошелёк ЮMoney обновлён!", reply_markup=main_menu_kb())

# ── RollyPay для бота (3 токена) ──────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_rolly_bot:"))
async def edit_rolly_bot_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotRollyPayFSM.terminal_id)
    await callback.message.answer(
        f"{Emoji.COINS} <b>RollyPay: Terminal ID</b>\n"
        f"Введите Terminal ID (или «-» для сброса):",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(BotRollyPayFSM.terminal_id))
async def edit_rolly_bot_terminal(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(terminal_id=value)
    await state.set_state(BotRollyPayFSM.api_key)
    await message.answer(f"{Emoji.KEY} Введите API Key (или «-»):")

@constructor_router.message(StateFilter(BotRollyPayFSM.api_key))
async def edit_rolly_bot_api_key(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(api_key=value)
    await state.set_state(BotRollyPayFSM.signing_secret)
    await message.answer(f"{Emoji.LOCK} Введите Signing Secret (или «-»):")

@constructor_router.message(StateFilter(BotRollyPayFSM.signing_secret))
async def edit_rolly_bot_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    secret = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()

    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == bot_id).values(
            rollypay_terminal_id=data.get("terminal_id"),
            rollypay_api_key=data.get("api_key"),
            rollypay_signing_secret=secret
        ))
        await session.commit()

    configured = all([data.get("terminal_id"), data.get("api_key"), secret])
    status_text = f"{Emoji.CHECK} RollyPay полностью настроен!" if configured else f"{Emoji.WARNING} RollyPay сохранён, но не все поля заполнены!"
    await message.answer(status_text, reply_markup=main_menu_kb())

# ── Lolzteam для бота (2 токена) ──────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_lolz_bot:"))
async def edit_lolz_bot_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotLolzFSM.api_token)
    await callback.message.answer(
        f"{Emoji.LOLZ} <b>Lolzteam: API Token</b>\n"
        f"Введите API Token (или «-» для сброса):",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(BotLolzFSM.api_token))
async def edit_lolz_bot_token(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(api_token=value)
    await state.set_state(BotLolzFSM.merchant_id)
    await message.answer(f"{Emoji.SHOP} Введите Merchant ID (или «-»):")

@constructor_router.message(StateFilter(BotLolzFSM.merchant_id))
async def edit_lolz_bot_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    mid = None if message.text.strip() == "-" else message.text.strip()
    await state.clear()

    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == bot_id).values(
            lolz_api_token=data.get("api_token"),
            lolz_merchant_id=mid
        ))
        await session.commit()

    configured = all([data.get("api_token"), mid])
    status_text = f"{Emoji.CHECK} Lolzteam полностью настроен!" if configured else f"{Emoji.WARNING} Lolzteam сохранён, но не все поля заполнены!"
    await message.answer(status_text, reply_markup=main_menu_kb())

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
        
        # By payment methods
        crypto_sales = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.bot_id == bot_id, Purchase.status == "completed",
                Purchase.payment_method == "crypto"
            )
        )
        yoo_sales = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.bot_id == bot_id, Purchase.status == "completed",
                Purchase.payment_method == "yoo"
            )
        )
        rolly_sales = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.bot_id == bot_id, Purchase.status == "completed",
                Purchase.payment_method == "rolly"
            )
        )
        lolz_sales = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.bot_id == bot_id, Purchase.status == "completed",
                Purchase.payment_method == "lolz"
            )
        )

    text = (
        f"{Emoji.CHART} <b>Статистика — «{bot.bot_name}»</b>\n\n"
        f"{Emoji.USERS} Уникальных покупателей: {users_count or 0}\n"
        f"{Emoji.PACKAGE} Категорий: {categories_count}\n"
        f"{Emoji.BOX} Товаров: {products_count}\n"
        f"{Emoji.SHOPPING_CART} Продаж (завершено): {purchases_total or 0}\n"
        f"{Emoji.CLOCK} Продаж (ожидает): {purchases_pending or 0}\n"
        f"{Emoji.MONEY} Общая выручка: {revenue or 0} руб\n\n"
        f"<b>По методам оплаты:</b>\n"
        f"{Emoji.CRYPTOBOT} CryptoBot: {crypto_sales}\n"
        f"{Emoji.CARD} ЮMoney: {yoo_sales}\n"
        f"{Emoji.COINS} RollyPay: {rolly_sales}\n"
        f"{Emoji.LOLZ} Lolzteam: {lolz_sales}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")]
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

    text = f"{Emoji.USERS} <b>Топ покупателей — «{bot.bot_name}»</b>\n\n"
    if buyers:
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            display = f"@{username}" if username else f"ID:{tid}"
            text += f"{i}. {display}\n   {Emoji.SHOPPING_CART} {count} покупок на {total} руб\n"
    else:
        text += "Покупателей пока нет."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{Emoji.BACK} Назад", callback_data=f"back_to_bot:{bot_id}")]
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
        f"{Emoji.MEGAPHONE} Введите текст рассылки (поддерживается HTML):\n\n"
        f"<b>жирный</b>, <i>курсив</i>, <code>моно</code>\n\n"
        f"Сообщение получат все, кто делал покупки в этом боте.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(BroadcastFSM.message_text))
async def broadcast_send(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
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

    if not user_ids:
        return await message.answer(
            f"{Emoji.CROSS} Нет пользователей для рассылки.",
            reply_markup=main_menu_kb()
        )

    sent, failed = 0, 0
    status_msg = await message.answer(
        f"{Emoji.LOADING} Начинаю рассылку на {len(user_ids)} пользователей..."
    )

    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            failed += 1
        
        if (i + 1) % 10 == 0:
            await status_msg.edit_text(
                f"{Emoji.LOADING} Рассылка: {i + 1}/{len(user_ids)} "
                f"(✅ {sent} | ❌ {failed})"
            )
        
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"{Emoji.MEGAPHONE} <b>Рассылка завершена!</b>\n\n"
        f"{Emoji.CHECK} Отправлено: {sent}\n"
        f"{Emoji.CROSS} Ошибок: {failed}",
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
    kb = payment_method_kb(p.id, bot)
    
    if not kb.inline_keyboard:
        return await callback.answer("Нет настроенных платёжных систем!", show_alert=True)

    await callback.message.answer(
        f"{Emoji.TEST} <b>Тестовая оплата</b>\n\n"
        f"Товар: {p.name}\n"
        f"Цена: {p.price} руб\n\n"
        f"Выберите способ оплаты:",
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
        [InlineKeyboardButton(text=f"{Emoji.CHECK} Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
         InlineKeyboardButton(text=f"{Emoji.CROSS} Нет", callback_data="cancel_delete")]
    ])
    await callback.message.answer(
        f"{Emoji.TRASH} Вы уверены, что хотите удалить бота? Все данные будут потеряны.",
        reply_markup=kb
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_delete_bot:"))
async def confirm_delete_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        await session.execute(
            delete(ShopBot).where(ShopBot.id == bot_id, ShopBot.owner_id == callback.from_user.id)
        )
        await session.commit()
    await callback.message.edit_text(f"{Emoji.TRASH} Бот удалён.")
    await callback.answer()

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text("Отменено.")
    await callback.answer()

# ── Админ-панель ───────────────────────────────────────────

@constructor_router.callback_query(F.data == "admin_crypto")
async def admin_crypto(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="crypto")
    await callback.message.answer(f"{Emoji.CRYPTOBOT} Введите токен Crypto Bot:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_yoomoney")
async def admin_yoomoney(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="yoomoney")
    await callback.message.answer(f"{Emoji.CARD} Введите кошелёк ЮMoney:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_rollypay")
async def admin_rollypay(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminRollyPayFSM.setting_type)
    await state.update_data(setting_type="rollypay_terminal")
    await callback.message.answer(f"{Emoji.COINS} <b>RollyPay: Terminal ID</b>\nВведите Terminal ID:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_lolz")
async def admin_lolz(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminLolzFSM.setting_type)
    await state.update_data(setting_type="lolz_token")
    await callback.message.answer(f"{Emoji.LOLZ} <b>Lolzteam: API Token</b>\nВведите API Token:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminFSM.value))
async def admin_save_value(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    setting_type = data["setting_type"]
    value = message.text.strip()
    await state.clear()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if setting_type == "crypto":
            config.crypto_bot_token = value
        elif setting_type == "yoomoney":
            config.yoomoney_wallet = value
        
        await session.commit()
    
    await message.answer(f"{Emoji.CHECK} Сохранено!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminRollyPayFSM.setting_type))
async def admin_rollypay_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    st = data["setting_type"]
    value = message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if st == "rollypay_terminal":
            config.rollypay_terminal_id = value
            await session.commit()
            await state.update_data(setting_type="rollypay_api")
            await message.answer(f"{Emoji.KEY} Введите API Key:")
            return
        elif st == "rollypay_api":
            config.rollypay_api_key = value
            await session.commit()
            await state.update_data(setting_type="rollypay_secret")
            await message.answer(f"{Emoji.LOCK} Введите Signing Secret:")
            return
        elif st == "rollypay_secret":
            config.rollypay_signing_secret = value
            await session.commit()
    
    await state.clear()
    await message.answer(f"{Emoji.CHECK} RollyPay сохранён!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminLolzFSM.setting_type))
async def admin_lolz_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    st = data["setting_type"]
    value = message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if st == "lolz_token":
            config.lolz_api_token = value
            await session.commit()
            await state.update_data(setting_type="lolz_merchant")
            await message.answer(f"{Emoji.SHOP} Введите Merchant ID:")
            return
        elif st == "lolz_merchant":
            config.lolz_merchant_id = value
            await session.commit()
    
    await state.clear()
    await message.answer(f"{Emoji.CHECK} Lolzteam сохранён!", reply_markup=admin_menu_kb())

@constructor_router.callback_query(F.data == "admin_prices")
async def admin_prices(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    await state.set_state(AdminPricesFSM.price_type)
    await callback.message.answer(
        f"{Emoji.TAG} <b>Цены подписки</b>\n\n"
        f"{Emoji.STAR} PRO: {config.pro_subscription_price}руб\n"
        f"{Emoji.CROWN} PREMIUM: {config.premium_subscription_price}руб\n\n"
        f"Что меняем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Emoji.STAR} PRO", callback_data="price_pro"),
             InlineKeyboardButton(text=f"{Emoji.CROWN} PREMIUM", callback_data="price_premium")]
        ])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(AdminPricesFSM.price_type))
async def admin_price_input(callback: CallbackQuery, state: FSMContext):
    await state.update_data(price_type=callback.data)
    await state.set_state(AdminPricesFSM.value)
    name = "PRO" if callback.data == "price_pro" else "PREMIUM"
    await callback.message.answer(f"Введите новую цену для {name} (руб):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminPricesFSM.value))
async def admin_price_save(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError
    except:
        return await message.answer(f"{Emoji.CROSS} Некорректная цена.")
    
    data = await state.get_data()
    await state.clear()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        if data["price_type"] == "price_pro":
            config.pro_subscription_price = price
        else:
            config.premium_subscription_price = price
        await session.commit()
    
    await message.answer(f"{Emoji.CHECK} Цена обновлена!", reply_markup=admin_menu_kb())

@constructor_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_bots = await session.scalar(select(func.count(ShopBot.id)))
        active_bots = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.is_active == True))
        pro_users = await session.scalar(select(func.count(User.id)).where(User.subscription_tier == "pro"))
        premium_users = await session.scalar(select(func.count(User.id)).where(User.subscription_tier == "premium"))
        total_revenue = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.status == "completed")
        )
        sub_revenue = await session.scalar(
            select(func.coalesce(func.sum(Subscription.amount), 0)).where(Subscription.status == "completed")
        )
    
    await callback.message.answer(
        f"{Emoji.CHART} <b>Общая статистика</b>\n\n"
        f"{Emoji.USERS} Пользователей: {total_users}\n"
        f"{Emoji.ROBOT} Ботов всего: {total_bots} (активных: {active_bots})\n"
        f"{Emoji.STAR} PRO подписок: {pro_users}\n"
        f"{Emoji.CROWN} PREMIUM подписок: {premium_users}\n"
        f"{Emoji.MONEY} Выручка с продаж: {total_revenue or 0} руб\n"
        f"{Emoji.COINS} Выручка с подписок: {sub_revenue or 0} руб",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    await state.set_state(AdminBroadcastFSM.message_text)
    await callback.message.answer(
        f"{Emoji.MEGAPHONE} <b>Отправьте сообщение для рассылки всем пользователям.</b>\n\n"
        f"Поддерживается HTML-разметка.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AdminBroadcastFSM.message_text))
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in result.all()]
    
    sent, failed = 0, 0
    status_msg = await message.answer(
        f"{Emoji.LOADING} Рассылка на {len(user_ids)} пользователей..."
    )
    
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            failed += 1
        
        if (i + 1) % 20 == 0:
            await status_msg.edit_text(
                f"{Emoji.LOADING} Рассылка: {i + 1}/{len(user_ids)} "
                f"(отправлено: {sent}, ошибок: {failed})"
            )
            await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"{Emoji.MEGAPHONE} <b>Рассылка завершена!</b>\n\n"
        f"{Emoji.CHECK} Отправлено: {sent}\n"
        f"{Emoji.CROSS} Ошибок: {failed}"
    )

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
            f"{Emoji.LOLZ} Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат для игр Supercell.\n"
            f"Выберите действие:",
            reply_markup=shop_menu_kb()
        )

    @shop_router.message(F.text == f"{Emoji.SHOPPING_CART} Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = result.scalars().all()
        
        if not cats:
            return await message.answer("😔 Пока нет доступных категорий.")
        
        await message.answer(
            f"{Emoji.LOLZ} Выберите игру:",
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
            f"{Emoji.PACKAGE} <b>{cat.name}</b>:",
            reply_markup=inline_kb([(f"{p.name} — {p.price} руб", f"shop_product:{p.id}") for p in products])
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
            f"{Emoji.SHOPPING_BAGS} <b>{product.name}</b>\n\n"
            f"{product.description or 'Описание отсутствует'}\n\n"
            f"{Emoji.MONEY} Цена: <b>{product.price} руб</b>"
        )
        
        kb = payment_method_kb(product_id, bot_record)
        if not kb.inline_keyboard:
            return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")
        
        await callback.message.answer(text + "\n\n💳 Выберите способ оплаты:", reply_markup=kb)
        await callback.answer()

    async def process_payment(callback: CallbackQuery, product_id: int, method: str):
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer("Товар не найден.")
            
            # Credential checks
            if method == "crypto" and not bot_record.crypto_bot_token:
                return await callback.answer("❌ CryptoBot не настроен!", show_alert=True)
            if method == "yoo" and not bot_record.yoomoney_wallet:
                return await callback.answer("❌ ЮMoney не настроен!", show_alert=True)
            if method == "rolly" and not is_rollypay_configured(bot_record):
                return await callback.answer("❌ RollyPay не настроен! Нужны Terminal ID, API Key, Signing Secret", show_alert=True)
            if method == "lolz" and not is_lolz_configured(bot_record):
                return await callback.answer("❌ Lolzteam не настроен! Нужны API Token, Merchant ID", show_alert=True)
            
            purchase = Purchase(
                user_id=callback.from_user.id,
                bot_id=bot_record.id,
                product_id=product_id,
                amount=product.price,
                status="pending",
                payment_method=method
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            
            url = None
            payment_id = str(purchase.id)
            
            if method == "crypto":
                api = CryptoBotAPI(bot_record.crypto_bot_token)
                invoice = await api.create_invoice(
                    float(product.price),
                    f"Покупка: {product.name}",
                    str(purchase.id)
                )
                if invoice:
                    url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
                    payment_id = str(invoice.get("invoice_id", purchase.id))
            
            elif method == "yoo":
                label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
                yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
                url = yoo.generate_form_url(
                    float(product.price),
                    label,
                    f"Покупка: {product.name}"
                )
                payment_id = label
            
            elif method == "rolly":
                api = RollyPayAPI(
                    bot_record.rollypay_terminal_id,
                    bot_record.rollypay_api_key,
                    bot_record.rollypay_signing_secret
                )
                result = await api.create_payment(
                    float(product.price),
                    f"shop_{purchase.id}",
                    f"Покупка: {product.name}"
                )
                if result and result.get("pay_url"):
                    url = result.get("pay_url")
                    payment_id = result.get("payment_id", f"shop_{purchase.id}")
            
            elif method == "lolz":
                api = LolzteamAPI(bot_record.lolz_api_token, bot_record.lolz_merchant_id)
                result = await api.create_invoice(
                    float(product.price),
                    f"shop_{purchase.id}",
                    f"Покупка: {product.name}"
                )
                if result and result.get("invoice"):
                    url = result["invoice"].get("url", "")
                    payment_id = str(result["invoice"].get("invoice_id", purchase.id))
            
            if url:
                purchase.payment_id = payment_id
                await session.commit()
                await callback.message.answer(
                    f"{Emoji.RECEIPT} <b>Счёт создан!</b>\n\n"
                    f"Товар: {product.name}\n"
                    f"Сумма: {product.price} руб\n\n"
                    f"Нажмите «Оплатить» для перехода к оплате.",
                    reply_markup=payment_invoice_kb(url, method, payment_id)
                )
            else:
                await callback.answer("❌ Ошибка создания платежа!", show_alert=True)
        
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        await process_payment(callback, int(callback.data.split(":")[1]), "crypto")

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        await process_payment(callback, int(callback.data.split(":")[1]), "yoo")

    @shop_router.callback_query(F.data.startswith("pay_rolly:"))
    async def pay_rollypay(callback: CallbackQuery):
        await process_payment(callback, int(callback.data.split(":")[1]), "rolly")

    @shop_router.callback_query(F.data.startswith("pay_lolz:"))
    async def pay_lolzteam(callback: CallbackQuery):
        await process_payment(callback, int(callback.data.split(":")[1]), "lolz")

    @shop_router.callback_query(F.data.startswith("check_pay:"))
    async def shop_check_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        
        await callback.answer(f"{Emoji.LOADING} Проверяю оплату...")
        
        is_paid = False
        async with async_session_maker() as session:
            # Search for purchase
            result = await session.execute(
                select(Purchase).where(
                    (Purchase.payment_id == payment_id) |
                    (Purchase.payment_method.contains(payment_id)) |
                    (Purchase.id == int(payment_id) if payment_id.isdigit() else False)
                ).order_by(Purchase.id.desc())
            )
            purchase = result.scalar_one_or_none()
            
            if purchase and purchase.status == "completed":
                is_paid = True
            elif method == "crypto" and bot_record.crypto_bot_token:
                invoice_id = None
                if payment_id.isdigit():
                    invoice_id = int(payment_id)
                elif purchase and purchase.payment_id and purchase.payment_id.isdigit():
                    invoice_id = int(purchase.payment_id)
                
                if invoice_id:
                    api = CryptoBotAPI(bot_record.crypto_bot_token)
                    status = await api.check_invoice(invoice_id)
                    if status == "paid":
                        is_paid = True
            
            elif method == "rolly" and is_rollypay_configured(bot_record):
                check_id = payment_id
                if purchase and purchase.payment_id:
                    check_id = purchase.payment_id
                
                api = RollyPayAPI(
                    bot_record.rollypay_terminal_id,
                    bot_record.rollypay_api_key,
                    bot_record.rollypay_signing_secret
                )
                result = await api.check_payment(check_id)
                if result and result.get("status") == "paid":
                    is_paid = True
            
            elif method == "lolz" and is_lolz_configured(bot_record):
                invoice_id = None
                if payment_id.isdigit():
                    invoice_id = int(payment_id)
                elif purchase and purchase.payment_id and purchase.payment_id.isdigit():
                    invoice_id = int(purchase.payment_id)
                
                if invoice_id:
                    api = LolzteamAPI(bot_record.lolz_api_token, bot_record.lolz_merchant_id)
                    status = await api.check_invoice(invoice_id)
                    if status == "paid":
                        is_paid = True
            
            if is_paid and purchase and purchase.status != "completed":
                purchase.status = "completed"
                
                # Update user statistics
                user = await get_or_create_user(session, purchase.user_id, None)
                user.total_spent = (getattr(user, 'total_spent', Decimal("0.00")) or Decimal("0.00")) + purchase.amount
                user.total_purchases = (getattr(user, 'total_purchases', 0) or 0) + 1
                
                await session.commit()
                
                product = await session.get(Product, purchase.product_id)
                product_name = product.name if product else "Товар"
                
                await callback.message.answer(
                    f"{Emoji.CHECK} <b>Оплата подтверждена!</b>\n\n"
                    f"{Emoji.PARTY} Спасибо за покупку!\n"
                    f"{Emoji.SHOPPING_BAGS} {product_name}\n"
                    f"{Emoji.MONEY} {purchase.amount} руб"
                )
            elif is_paid:
                await callback.message.answer(f"{Emoji.CHECK} Оплата уже была подтверждена.")
            else:
                await callback.message.answer(
                    f"{Emoji.CLOCK} <b>Оплата ещё не поступила.</b>\n\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )

    @shop_router.message(F.text == f"{Emoji.PACKAGE} Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            rows = (await session.execute(
                select(Purchase, Product).join(Product)
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id)
                .order_by(Purchase.created_at.desc())
                .limit(20)
            )).all()
        
        if not rows:
            return await message.answer(f"{Emoji.PACKAGE} У вас пока нет покупок в этом магазине.")
        
        text = f"{Emoji.PACKAGE} <b>Ваши покупки:</b>\n\n"
        sm = {"pending": f"{Emoji.CLOCK} Ожидает", "completed": f"{Emoji.CHECK} Завершена"}
        
        total_amount = Decimal("0.00")
        completed = 0
        
        for purchase, product in rows:
            text += (
                f"{Emoji.SHOPPING_BAGS} {product.name}\n"
                f"   {Emoji.MONEY} {purchase.amount} руб | {sm.get(purchase.status, purchase.status)}\n"
                f"   {Emoji.CALENDAR} {purchase.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
            if purchase.status == "completed":
                total_amount += purchase.amount
                completed += 1
        
        text += f"━━━━━━━━━━━━━━━\n"
        text += f"{Emoji.CHART} Завершено: {completed} покупок\n"
        text += f"{Emoji.MONEY} Потрачено: {total_amount} руб"
        
        if len(text) > 4000:
            text = text[:4000] + "\n\n...(показаны последние покупки)"
        
        await message.answer(text)

    @shop_router.message(F.text == f"{Emoji.PROFILE} Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            
            # Statistics in this bot
            total_spent_bot = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id,
                    Purchase.status == "completed"
                )
            )
            purchases_count = await session.scalar(
                select(func.count(Purchase.id))
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id,
                    Purchase.status == "completed"
                )
            )
            pending_count = await session.scalar(
                select(func.count(Purchase.id))
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id,
                    Purchase.status == "pending"
                )
            )
            
            # Last purchase
            last_purchase_result = await session.execute(
                select(Purchase).where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id
                ).order_by(Purchase.created_at.desc()).limit(1)
            )
            last_purchase = last_purchase_result.scalar_one_or_none()
            
            # Overall statistics
            total_spent_all = getattr(user, 'total_spent', Decimal("0.00")) or Decimal("0.00")
            total_purchases_all = getattr(user, 'total_purchases', 0) or 0
        
        text = (
            f"{Emoji.PROFILE} <b>Профиль в «{bot_record.bot_name}»</b>\n\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"📛 @{message.from_user.username or '—'}\n"
            f"{Emoji.COINS} Баланс: {user.balance} руб\n\n"
            f"━━━ {Emoji.CHART} В этом магазине ━━━\n"
            f"{Emoji.CHECK} Завершено покупок: {purchases_count}\n"
            f"{Emoji.CLOCK} Ожидают оплаты: {pending_count}\n"
            f"{Emoji.MONEY} Потрачено здесь: {total_spent_bot} руб\n"
        )
        
        if last_purchase:
            sm = {"pending": f"{Emoji.CLOCK}", "completed": f"{Emoji.CHECK}"}
            text += (
                f"\n🕐 Последняя покупка:\n"
                f"   {sm.get(last_purchase.status, '❓')} {last_purchase.amount} руб "
                f"({last_purchase.created_at.strftime('%d.%m %H:%M')})\n"
            )
        
        text += (
            f"\n━━━ {Emoji.GLOBE} Общая статистика ━━━\n"
            f"{Emoji.SHOPPING_CART} Всего покупок: {total_purchases_all}\n"
            f"{Emoji.COINS} Потрачено всего: {total_spent_all} руб"
        )
        
        await message.answer(text)

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
    
    constructor_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # Set bot commands
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
