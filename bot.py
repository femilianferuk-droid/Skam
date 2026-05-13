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
    select, func, update, delete, inspect, and_, or_
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
    STATS_ID = "5870921681735781843"
    LOCK_CLOSED_ID = "6037249452824072506"
    LOCK_OPEN_ID = "6037496202990194718"
    MEGAPHONE_ID = "6039422865189638057"
    CHECK_ID = "5870633910337015697"
    CROSS_ID = "5870657884844462243"
    PENCIL_ID = "5870676941614354370"
    TRASH_ID = "5870875489362513438"
    BACK_ID = "5775896410780079073"
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
    SHOP_ID = "5373141891321699086"
    VERIFY_ID = "5774022692642492953"
    
    SETTINGS = f'<tg-emoji emoji-id="{SETTINGS_ID}">⚙</tg-emoji>'
    PROFILE = f'<tg-emoji emoji-id="{PROFILE_ID}">👤</tg-emoji>'
    CROWN = f'<tg-emoji emoji-id="{CROWN_ID}">👑</tg-emoji>'
    STAR = f'<tg-emoji emoji-id="{STAR_ID}">⭐</tg-emoji>'
    SMILE = f'<tg-emoji emoji-id="{SMILE_ID}">🙂</tg-emoji>'
    CHECK = f'<tg-emoji emoji-id="{CHECK_ID}">✅</tg-emoji>'
    CROSS = f'<tg-emoji emoji-id="{CROSS_ID}">❌</tg-emoji>'
    MONEY = f'<tg-emoji emoji-id="{MONEY_ID}">🪙</tg-emoji>'
    LOADING = f'<tg-emoji emoji-id="{LOADING_ID}">🔄</tg-emoji>'
    BOT = f'<tg-emoji emoji-id="{BOT_ID}">🤖</tg-emoji>'
    BOX = f'<tg-emoji emoji-id="{BOX_ID}">📦</tg-emoji>'
    MEGAPHONE = f'<tg-emoji emoji-id="{MEGAPHONE_ID}">📣</tg-emoji>'
    STATS = f'<tg-emoji emoji-id="{STATS_ID}">📊</tg-emoji>'
    WALLET = f'<tg-emoji emoji-id="{WALLET_ID}">👛</tg-emoji>'
    CRYPTOBOT = f'<tg-emoji emoji-id="{CRYPTOBOT_ID}">👾</tg-emoji>'
    CLOCK = f'<tg-emoji emoji-id="{CLOCK_ID}">⏰</tg-emoji>'
    PARTY = f'<tg-emoji emoji-id="{PARTY_ID}">🎉</tg-emoji>'
    PENCIL = f'<tg-emoji emoji-id="{PENCIL_ID}">🖋</tg-emoji>'
    TRASH = f'<tg-emoji emoji-id="{TRASH_ID}">🗑</tg-emoji>'
    BACK = f'<tg-emoji emoji-id="{BACK_ID}">◁</tg-emoji>'
    INFO = f'<tg-emoji emoji-id="{INFO_ID}">ℹ</tg-emoji>'
    PEOPLE = f'<tg-emoji emoji-id="{PEOPLE_ID}">👥</tg-emoji>'
    GIFT = f'<tg-emoji emoji-id="{GIFT_ID}">🎁</tg-emoji>'
    BELL = f'<tg-emoji emoji-id="{BELL_ID}">🔔</tg-emoji>'
    CALENDAR = f'<tg-emoji emoji-id="{CALENDAR_ID}">📅</tg-emoji>'
    SEND = f'<tg-emoji emoji-id="{SEND_ID}">⬆</tg-emoji>'

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
        def get_columns(connection, table_name):
            inspector = inspect(connection)
            try:
                return [col["name"] for col in inspector.get_columns(table_name)]
            except:
                return []
        
        # Миграция для bots
        bots_cols = await conn.run_sync(lambda c: get_columns(c, "bots"))
        for col_name in ["rollypay_terminal_id", "rollypay_api_key", "rollypay_signing_secret"]:
            if col_name not in bots_cols:
                logger.info(f"Adding {col_name} to bots...")
                await conn.execute(text(f"ALTER TABLE bots ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(255)"))
        
        # Миграция для admin_config
        admin_cols = await conn.run_sync(lambda c: get_columns(c, "admin_config"))
        for col_name in ["rollypay_terminal_id", "rollypay_api_key", "rollypay_signing_secret"]:
            if col_name not in admin_cols:
                logger.info(f"Adding {col_name} to admin_config...")
                await conn.execute(text(f"ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS {col_name} VARCHAR(255)"))
        if "pro_subscription_price" not in admin_cols:
            await conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS pro_subscription_price NUMERIC(10,2) DEFAULT 100.00"))
        if "premium_subscription_price" not in admin_cols:
            await conn.execute(text("ALTER TABLE admin_config ADD COLUMN IF NOT EXISTS premium_subscription_price NUMERIC(10,2) DEFAULT 250.00"))
        
        # Миграция для users
        users_cols = await conn.run_sync(lambda c: get_columns(c, "users"))
        for col_name, default in [("subscription_tier", "'free'"), ("subscription_expires", "NULL"), ("total_spent", "0.00"), ("total_purchases", "0")]:
            if col_name not in users_cols:
                logger.info(f"Adding {col_name} to users...")
                col_type = "VARCHAR(20) DEFAULT " + default if col_name == "subscription_tier" else \
                           "TIMESTAMP" if col_name == "subscription_expires" else \
                           "NUMERIC(12,2) DEFAULT " + default if col_name == "total_spent" else \
                           "INTEGER DEFAULT " + default
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
        
        # Миграция для purchases
        pur_cols = await conn.run_sync(lambda c: get_columns(c, "purchases"))
        if "payment_id" not in pur_cols:
            logger.info("Adding payment_id to purchases...")
            await conn.execute(text("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_id VARCHAR(255)"))
        
        # Создание таблиц
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Migrations completed!")

async def init_db():
    await run_migrations()
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
    if tier != "free" and hasattr(user, 'subscription_expires') and user.subscription_expires:
        if user.subscription_expires < datetime.utcnow():
            user.subscription_tier = "free"
            user.subscription_expires = None
            await session.commit()
    return user

async def can_create_bot(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    user = await check_subscription(session, user_id)
    bots_count = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.owner_id == user_id))
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
                    logger.error(f"CryptoBot error: {data}")
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
            logger.error(f"RollyPay create error: {e}")
            return None
    
    async def check_payment(self, payment_id: str) -> Optional[dict]:
        try:
            nonce = str(uuid.uuid4())
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/payments/{payment_id}",
                    headers={"X-API-Key": self.api_key, "X-Nonce": nonce},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    return await resp.json()
        except Exception as e:
            logger.error(f"RollyPay check error: {e}")
            return None

def is_rollypay_configured(bot: ShopBot) -> bool:
    """Проверяет, что все 3 поля RollyPay заполнены"""
    return bool(bot.rollypay_terminal_id and bot.rollypay_api_key and bot.rollypay_signing_secret)

def is_rollypay_admin_configured(config: AdminConfig) -> bool:
    """Проверяет, что все 3 поля RollyPay в админке заполнены"""
    return bool(config.rollypay_terminal_id and config.rollypay_api_key and config.rollypay_signing_secret)

# ═══════════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Создать бота"), KeyboardButton(text="📋 Мои боты")],
            [KeyboardButton(text="👑 Подписка"), KeyboardButton(text="👤 Профиль")],
        ],
        resize_keyboard=True
    )

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Купить донат"), KeyboardButton(text="📦 Мои покупки")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📊 Статистика")],
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
        [InlineKeyboardButton(
            text=f"{'⏸ Остановить' if is_active else '▶️ Запустить'}",
            callback_data=f"toggle_bot:{bot_id}"
        ), InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_bot:{bot_id}")],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")]
    ])

def inline_kb(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])

def tier_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ PRO — 100₽/мес (5 ботов)", callback_data="sub_tier:pro")],
        [InlineKeyboardButton(text="👑 PREMIUM — 250₽/мес (30 ботов)", callback_data="sub_tier:premium")],
    ])

def payment_method_sub_kb(tier: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👾 Crypto Bot", callback_data=f"sub_pay:{tier}:crypto")],
        [InlineKeyboardButton(text="💳 ЮMoney", callback_data=f"sub_pay:{tier}:yoomoney")],
        [InlineKeyboardButton(text="💰 RollyPay (СБП)", callback_data=f"sub_pay:{tier}:rollypay")],
    ])

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👾 Crypto Bot", callback_data="admin_crypto")],
        [InlineKeyboardButton(text="💳 ЮMoney", callback_data="admin_yoomoney")],
        [InlineKeyboardButton(text="💰 RollyPay", callback_data="admin_rollypay")],
        [InlineKeyboardButton(text="🏷 Цены подписки", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_broadcast")],
    ])

def payment_method_kb(product_id: int, bot: ShopBot) -> InlineKeyboardMarkup:
    """
    Клавиатура способов оплаты для товара.
    Проверяет ВСЕ 3 поля RollyPay перед показом кнопки.
    """
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="👾 Crypto Bot", callback_data=f"pay_crypto:{product_id}")
        ])
    
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="💳 ЮMoney", callback_data=f"pay_yoo:{product_id}")
        ])
    
    # Проверяем ВСЕ 3 поля RollyPay
    if is_rollypay_configured(bot):
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

class BotRollyPayFSM(StatesGroup):
    bot_id = State()
    terminal_id = State()
    api_key = State()
    signing_secret = State()

# ═══════════════════════════════════════════════════════════
# CONSTRUCTOR BOT ROUTER
# ═══════════════════════════════════════════════════════════

constructor_router = Router()

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        "🤖 Добро пожаловать в конструктор магазинов доната!\n\n"
        "• Создайте бота для продажи доната\n"
        "• Управляйте товарами и категориями\n"
        "• Принимайте платежи через CryptoBot, ЮMoney, RollyPay\n\n"
        "👑 Тарифы: Бесплатный (1 бот), PRO (5 ботов, 100₽/мес), PREMIUM (30 ботов, 250₽/мес)",
        reply_markup=main_menu_kb()
    )

@constructor_router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ Нет доступа к админ-панели.")
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    status = (
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👾 Crypto Bot: {'✅ Настроен' if config.crypto_bot_token else '❌ Не настроен'}\n"
        f"💳 ЮMoney: {'✅ Настроен' if config.yoomoney_wallet else '❌ Не настроен'}\n"
        f"💰 RollyPay: {'✅ Настроен' if is_rollypay_admin_configured(config) else '❌ Не настроен'}\n"
        f"🏷 PRO: {config.pro_subscription_price}₽ | PREMIUM: {config.premium_subscription_price}₽\n\n"
        f"Выберите действие:"
    )
    await message.answer(status, reply_markup=admin_menu_kb())

@constructor_router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        bots_count = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id))
        total_spent = getattr(user, 'total_spent', Decimal("0.00"))
        total_purchases = getattr(user, 'total_purchases', 0)
    
    tier_display = {"free": "👤 Бесплатный", "pro": "⭐ PRO", "premium": "👑 PREMIUM"}
    limits = {"free": "1 бот", "pro": "5 ботов", "premium": "30 ботов"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free" and getattr(user, 'subscription_expires', None):
        days_left = (user.subscription_expires - datetime.utcnow()).days
        expiry = f"\n⏰ Действует ещё {days_left} дн. (до {user.subscription_expires.strftime('%d.%m.%Y')})"
    
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📛 Username: @{message.from_user.username or '—'}\n"
        f"💎 Тариф: {tier_display.get(tier, 'Бесплатный')}{expiry}\n"
        f"🤖 Лимит ботов: {limits.get(tier, '1 бот')}\n"
        f"📋 Ботов создано: {bots_count}\n"
        f"💰 Баланс: {user.balance}₽\n"
        f"🛒 Всего покупок: {total_purchases}\n"
        f"💸 Потрачено всего: {total_spent}₽"
    )

# ── Подписка ────────────────────────────────────────────────

@constructor_router.message(F.text == "👑 Подписка")
async def subscription_menu(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        config = await get_admin_config(session)
    
    tier_display = {"free": "👤 Бесплатный", "pro": "⭐ PRO", "premium": "👑 PREMIUM"}
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free" and getattr(user, 'subscription_expires', None):
        days_left = (user.subscription_expires - datetime.utcnow()).days
        expiry = f"\n⏰ Осталось: {days_left} дн."
    
    await message.answer(
        f"👑 <b>Подписка</b>\n\n"
        f"Ваш тариф: {tier_display.get(tier)}{expiry}\n\n"
        f"<b>Доступные тарифы:</b>\n"
        f"👤 Бесплатный — 1 бот (навсегда)\n"
        f"⭐ PRO — 5 ботов, {config.pro_subscription_price}₽/мес\n"
        f"👑 PREMIUM — 30 ботов, {config.premium_subscription_price}₽/мес\n\n"
        f"<b>Выберите тариф для покупки:</b>",
        reply_markup=tier_kb()
    )

@constructor_router.callback_query(F.data.startswith("sub_tier:"))
async def sub_tier_select(callback: CallbackQuery):
    tier = callback.data.split(":")[1]
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    prices = {"pro": config.pro_subscription_price, "premium": config.premium_subscription_price}
    names = {"pro": "⭐ PRO", "premium": "👑 PREMIUM"}
    
    await callback.message.edit_text(
        f"{names.get(tier)} — {prices.get(tier)}₽/мес\n\n"
        f"<b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_sub_kb(tier)
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("sub_pay:"))
async def sub_payment_process(callback: CallbackQuery):
    parts = callback.data.split(":")
    tier = parts[1]
    method = parts[2]
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
    
    prices = {"pro": admin_config.pro_subscription_price, "premium": admin_config.premium_subscription_price}
    amount = prices.get(tier, Decimal("100.00"))
    
    # Проверка реквизитов
    if method == "crypto" and not admin_config.crypto_bot_token:
        return await callback.answer("❌ Crypto Bot не настроен админом!", show_alert=True)
    if method == "yoomoney" and not admin_config.yoomoney_wallet:
        return await callback.answer("❌ ЮMoney не настроен админом!", show_alert=True)
    if method == "rollypay" and not is_rollypay_admin_configured(admin_config):
        return await callback.answer("❌ RollyPay не настроен! Нужны: Terminal ID, API Key, Signing Secret", show_alert=True)
    
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
            invoice = await api.create_invoice(float(amount), f"Подписка {tier.upper()}", f"sub_{sub.id}")
            if invoice:
                pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
                payment_id = str(invoice.get("invoice_id", sub.id))
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer("❌ Ошибка создания счёта!", show_alert=True)
                return
        
        elif method == "yoomoney":
            yoo = YooMoneyAPI(admin_config.yoomoney_wallet)
            label = f"sub_{sub.id}"
            pay_url = yoo.generate_form_url(float(amount), label, f"Подписка {tier.upper()}")
            payment_id = label
            sub.payment_id = label
            await session.commit()
        
        elif method == "rollypay":
            api = RollyPayAPI(
                admin_config.rollypay_terminal_id,
                admin_config.rollypay_api_key,
                admin_config.rollypay_signing_secret
            )
            result = await api.create_payment(float(amount), f"sub_{sub.id}", f"Подписка {tier.upper()}")
            if result and result.get("pay_url"):
                pay_url = result.get("pay_url")
                payment_id = result.get("payment_id", f"sub_{sub.id}")
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer("❌ Ошибка создания платежа RollyPay!", show_alert=True)
                return
    
    if pay_url:
        names = {"pro": "⭐ PRO", "premium": "👑 PREMIUM"}
        await callback.message.edit_text(
            f"💳 <b>Оплата {names.get(tier)}</b>\n\n"
            f"💰 Сумма: {amount} ₽\n"
            f"📅 Срок: 1 месяц\n"
            f"🆔 ID: <code>{sub.id}</code>\n\n"
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
        
        # Ищем подписку
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
        elif method == "crypto" and admin_config.crypto_bot_token and payment_id.isdigit():
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            status = await api.check_invoice(int(payment_id))
            if status == "paid":
                is_paid = True
        elif method == "rollypay" and is_rollypay_admin_configured(admin_config):
            api = RollyPayAPI(
                admin_config.rollypay_terminal_id,
                admin_config.rollypay_api_key,
                admin_config.rollypay_signing_secret
            )
            result = await api.check_payment(payment_id)
            if result and result.get("status") == "paid":
                is_paid = True
        
        if is_paid and sub and sub.status != "completed":
            sub.status = "completed"
            user = await get_or_create_user(session, sub.user_id, None)
            user.subscription_tier = sub.tier
            user.subscription_expires = sub.expires_at
            await session.commit()
            
            names = {"pro": "⭐ PRO", "premium": "👑 PREMIUM"}
            await callback.message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"🎉 Тариф {names.get(sub.tier, sub.tier)} активирован!\n"
                f"📅 Действует до: {sub.expires_at.strftime('%d.%m.%Y')}"
            )
        elif is_paid and sub:
            await callback.message.answer("✅ Оплата уже была подтверждена ранее.")
        else:
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже или обратитесь в поддержку.")

# ── Создать бота ───────────────────────────────────────────

@constructor_router.message(F.text == "🛠 Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"❌ {error_msg}")
    
    await state.set_state(CreateBotFSM.token)
    await message.answer("🤖 <b>Шаг 1/5</b> — Введите токен бота от @BotFather:", reply_markup=cancel_kb())

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    token = message.text.strip()
    if not token or ":" not in token:
        return await message.answer("❌ Некорректный токен. Формат: 123456:ABC-DEF")
    
    async with async_session_maker() as session:
        exists = await session.execute(select(ShopBot).where(ShopBot.bot_token == token))
        if exists.scalar_one_or_none():
            return await message.answer("❌ Бот с таким токеном уже существует.")
    
    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    await message.answer("✅ Токен принят.\n\n📝 <b>Шаг 2/5</b> — Название магазина:")

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
    await message.answer("✅ Название принято.\n\n👮 <b>Шаг 3/5</b> — Telegram ID администратора:")

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0: raise ValueError
    except ValueError:
        return await message.answer("❌ Введите корректный числовой Telegram ID.")
    
    await state.update_data(admin_id=admin_id)
    await state.set_state(CreateBotFSM.crypto_token)
    await message.answer("✅ Admin ID принят.\n\n👾 <b>Шаг 4/5</b> — Токен Crypto Bot (или «-» пропустить):")

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        return await message.answer("Отменено.", reply_markup=main_menu_kb())
    
    crypto = message.text.strip()
    await state.update_data(crypto_token=None if crypto == "-" else crypto)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    await message.answer("💳 <b>Шаг 5/5</b> — Кошелёк ЮMoney (или «-» пропустить):")

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

    await message.answer(
        f"✅ <b>Бот «{data['name']}» создан!</b>\n\n"
        f"🔑 Токен: <code>{data['token']}</code>\n"
        f"👮 Admin ID: <code>{data['admin_id']}</code>\n"
        f"💳 Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"💰 RollyPay можно настроить в управлении ботом\n\n"
        f"📋 Управление — «Мои боты»",
        reply_markup=main_menu_kb()
    )

# ── Мои боты ───────────────────────────────────────────────

@constructor_router.message(F.text == "📋 Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id).order_by(ShopBot.created_at.desc())
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer("У вас пока нет ботов.\nНажмите «🛠 Создать бота»!")

    for bot in bots:
        status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
        payments = []
        if bot.crypto_bot_token: payments.append("CryptoBot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        if is_rollypay_configured(bot): payments.append("RollyPay")

        async with async_session_maker() as session:
            products_count = await session.scalar(
                select(func.count(Product.id)).where(
                    Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id))
                )
            )
            revenue = await session.scalar(
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
            f"🤖 <b>{bot.bot_name}</b>\n"
            f"▸ Статус: {status}\n"
            f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"▸ Товаров: {products_count} | Продаж: {total_sales}\n"
            f"▸ Покупателей: {buyers_count} | Выручка: {revenue or 0}₽\n"
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
    if bot.crypto_bot_token: payments.append("CryptoBot")
    if bot.yoomoney_wallet: payments.append("ЮMoney")
    if is_rollypay_configured(bot): payments.append("RollyPay")
    
    async with async_session_maker() as session:
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(select(Category.id).where(Category.bot_id == bot.id))
            )
        )
        revenue = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
            .where(Purchase.bot_id == bot.id, Purchase.status == "completed")
        )
    
    text = (
        f"🤖 <b>{bot.bot_name}</b>\n"
        f"▸ Статус: {status}\n"
        f"▸ Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"▸ Товаров: {products_count}\n"
        f"▸ Выручка: {revenue or 0}₽\n"
        f"▸ ID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id, bot.is_active))
    await callback.answer()

# ── Категории ──────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_cats:"))
async def manage_categories(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()

    text = f"📁 <b>Категории — «{bot.bot_name}»</b>\n\n"
    if cats:
        for i, cat in enumerate(cats, 1):
            async with async_session_maker() as session:
                pc = await session.scalar(select(func.count(Product.id)).where(Product.category_id == cat.id))
            text += f"{i}. {cat.name} ({pc} товаров)\n"
    else:
        text += "Нет категорий.\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_cat:{bot_id}")],
    ])
    if cats:
        kb.inline_keyboard.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_cat_menu:{bot_id}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")])

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
    await state.clear()
    async with async_session_maker() as session:
        session.add(Category(bot_id=data["bot_id"], name=name))
        await session.commit()
    await message.answer(f"✅ Категория «{name}» добавлена!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("del_cat_menu:"))
async def del_category_menu(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    if not cats:
        return await callback.answer("Нет категорий.", show_alert=True)
    await callback.message.edit_text("🗑 Выберите категорию:", reply_markup=inline_kb([(c.name, f"confirm_del_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("confirm_del_cat:"))
async def confirm_del_category(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cat = await session.get(Category, cat_id)
        if not cat: return await callback.answer("Не найдена.")
        bot_id = cat.bot_id
        name = cat.name
        await session.execute(delete(Category).where(Category.id == cat_id))
        await session.commit()
    await callback.message.edit_text(f"🗑 «{name}» удалена.", reply_markup=back_kb(bot_id))
    await callback.answer()

# ── Товары ─────────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_products:"))
async def manage_products(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_product:{bot_id}")],
        [InlineKeyboardButton(text="📋 Список", callback_data=f"list_products:{bot_id}:0")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data=f"del_product_menu:{bot_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_bot:{bot_id}")],
    ])
    await callback.message.edit_text("📦 <b>Управление товарами</b>", reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("add_product:"))
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        cats = (await session.execute(select(Category).where(Category.bot_id == bot_id))).scalars().all()
    if not cats: return await callback.answer("Создайте категорию!", show_alert=True)
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddProductFSM.category)
    await callback.message.answer("📂 Категория:", reply_markup=inline_kb([(c.name, f"prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(AddProductFSM.category), F.data.startswith("prod_cat:"))
async def add_product_name(callback: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(callback.data.split(":")[1]))
    await state.set_state(AddProductFSM.name)
    await callback.message.answer("✏️ Название товара:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductFSM.description)
    await message.answer("📝 Описание (или «-»):")

@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    desc = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddProductFSM.price)
    await message.answer("💰 Цена (299.00):")

@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0: raise ValueError
    except: return await message.answer("❌ Некорректная цена.")
    data = await state.get_data()
    await state.clear()
    async with async_session_maker() as session:
        session.add(Product(category_id=data["category_id"], name=data["name"], description=data.get("description"), price=price))
        await session.commit()
    await message.answer(f"✅ Товар «{data['name']}» добавлен! ({price}₽)", reply_markup=main_menu_kb())

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
            products = (await session.execute(select(Product).where(Product.category_id == cat.id))).scalars().all()
        for p in products: all_products.append((cat.name, p))
    
    if not all_products:
        return await callback.message.edit_text("📦 Нет товаров.", reply_markup=back_kb(bot_id))
    
    per_page = 10
    total_pages = (len(all_products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start, end = page * per_page, (page + 1) * per_page
    
    text = f"📦 <b>Товары</b>\n\n"
    for i, (cn, p) in enumerate(all_products[start:end], start + 1):
        text += f"{i}. {'✅' if p.is_available else '❌'} {p.name} — {p.price}₽ [{cn}]\n"
    text += f"\nСтр. {page + 1}/{total_pages}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️", callback_data=f"list_products:{bot_id}:{page - 1}"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="▶️", callback_data=f"list_products:{bot_id}:{page + 1}"))
    if nav: kb.inline_keyboard.append(nav)
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
    if not cats: return await callback.answer("Нет категорий.", show_alert=True)
    await callback.message.answer("📂 Категория:", reply_markup=inline_kb([(c.name, f"del_prod_cat:{c.id}") for c in cats]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.category), F.data.startswith("del_prod_cat:"))
async def del_product_select(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        products = (await session.execute(select(Product).where(Product.category_id == cat_id))).scalars().all()
    if not products: await callback.answer("Нет товаров.", show_alert=True); await state.clear(); return
    await state.set_state(DeleteProductFSM.product)
    await callback.message.answer("🗑 Выберите:", reply_markup=inline_kb([(f"{p.name} ({p.price}₽)", f"confirm_del_prod:{p.id}") for p in products]))
    await callback.answer()

@constructor_router.callback_query(StateFilter(DeleteProductFSM.product), F.data.startswith("confirm_del_prod:"))
async def confirm_del_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    await state.clear()
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        name = product.name if product else "Товар"
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.commit()
    await callback.message.edit_text(f"🗑 «{name}» удалён.", reply_markup=back_kb(data["bot_id"]))
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
        f"💳 <b>Платежи — «{bot.bot_name}»</b>\n\n"
        f"👾 Crypto Bot: {'✅ Настроен' if bot.crypto_bot_token else '❌ Не настроен'}\n"
        f"💳 ЮMoney: {'✅ Настроен' if bot.yoomoney_wallet else '❌ Не настроен'}\n"
        f"💰 RollyPay: {'✅ Настроен' if is_rollypay_configured(bot) else '❌ Не настроен'}\n\n"
        f"<i>Для RollyPay нужны: Terminal ID, API Key, Signing Secret</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👾 Crypto Bot", callback_data=f"edit_crypto:{bot_id}")],
        [InlineKeyboardButton(text="💳 ЮMoney", callback_data=f"edit_yoo:{bot_id}")],
        [InlineKeyboardButton(text="💰 RollyPay (3 токена)", callback_data=f"edit_rolly_bot:{bot_id}")],
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
    await callback.message.answer("👾 Токен Crypto Bot (или «-» удалить):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.crypto_token))
async def edit_crypto_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    token = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == data["edit_bot_id"]).values(crypto_bot_token=token))
        await session.commit()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_kb())

@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    await callback.message.answer("💳 Кошелёк ЮMoney (или «-» удалить):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.yoomoney_wallet))
async def edit_yoo_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    wallet = None if message.text.strip() == "-" else message.text.strip()
    async with async_session_maker() as session:
        await session.execute(update(ShopBot).where(ShopBot.id == data["edit_bot_id"]).values(yoomoney_wallet=wallet))
        await session.commit()
    await message.answer("✅ Обновлено!", reply_markup=main_menu_kb())

# ── RollyPay для бота (3 токена) ──────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_rolly_bot:"))
async def edit_rolly_bot_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
    
    current = ""
    if bot:
        current = (
            f"\n\n<i>Текущие настройки:</i>\n"
            f"Terminal ID: {'✅' if bot.rollypay_terminal_id else '❌'}\n"
            f"API Key: {'✅' if bot.rollypay_api_key else '❌'}\n"
            f"Signing Secret: {'✅' if bot.rollypay_signing_secret else '❌'}"
        )
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotRollyPayFSM.terminal_id)
    await callback.message.answer(
        f"💰 <b>RollyPay: Terminal ID</b>\n"
        f"Введите Terminal ID (или «-» для сброса):{current}",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(BotRollyPayFSM.terminal_id))
async def edit_rolly_bot_terminal(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(terminal_id=value)
    await state.set_state(BotRollyPayFSM.api_key)
    await message.answer("🔑 Введите API Key (или «-»):")

@constructor_router.message(StateFilter(BotRollyPayFSM.api_key))
async def edit_rolly_bot_api_key(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(api_key=value)
    await state.set_state(BotRollyPayFSM.signing_secret)
    await message.answer("🔐 Введите Signing Secret (или «-»):")

@constructor_router.message(StateFilter(BotRollyPayFSM.signing_secret))
async def edit_rolly_bot_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
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
    status_text = "✅ RollyPay полностью настроен!" if configured else "⚠️ RollyPay сохранён, но не все поля заполнены!"
    await message.answer(status_text, reply_markup=main_menu_kb())

# ── Статистика бота ───────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_stats:"))
async def bot_stats(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        users_count = await session.scalar(select(func.count(Purchase.user_id.distinct())).where(Purchase.bot_id == bot_id))
        purchases_total = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        purchases_pending = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "pending"))
        revenue = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.bot_id == bot_id, Purchase.status == "completed"))
        products_count = await session.scalar(select(func.count(Product.id)).where(Product.category_id.in_(select(Category.id).where(Category.bot_id == bot_id))))
        categories_count = await session.scalar(select(func.count(Category.id)).where(Category.bot_id == bot_id))
        
        # Статистика по методам оплаты
        crypto_sales = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed", Purchase.payment_method == "crypto_bot"))
        yoo_sales = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed", Purchase.payment_method.like("yoomoney%")))
        rolly_sales = await session.scalar(select(func.count(Purchase.id)).where(Purchase.bot_id == bot_id, Purchase.status == "completed", Purchase.payment_method.like("rollypay%")))

    await callback.message.edit_text(
        f"📊 <b>Статистика — «{bot.bot_name}»</b>\n\n"
        f"👥 Уникальных покупателей: {users_count or 0}\n"
        f"📁 Категорий: {categories_count}\n"
        f"📦 Товаров: {products_count}\n"
        f"🛒 Продаж (завершено): {purchases_total or 0}\n"
        f"⏳ Продаж (ожидает): {purchases_pending or 0}\n"
        f"💰 Общая выручка: {revenue or 0}₽\n\n"
        f"<b>По методам оплаты:</b>\n"
        f"👾 CryptoBot: {crypto_sales}\n"
        f"💳 ЮMoney: {yoo_sales}\n"
        f"💰 RollyPay: {rolly_sales}",
        reply_markup=back_kb(bot_id)
    )
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
    text = f"👥 <b>Топ покупателей</b>\n\n"
    if buyers:
        for i, (tid, username, count, total) in enumerate(buyers, 1):
            display = f"@{username}" if username else f"ID:{tid}"
            text += f"{i}. {display}\n   🛒 {count} покупок на {total}₽\n"
    else:
        text += "Покупателей нет."
    await callback.message.edit_text(text, reply_markup=back_kb(bot_id))
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("bot_broadcast:"))
async def bot_broadcast_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(broadcast_bot_id=bot_id)
    await state.set_state(BroadcastFSM.message_text)
    await callback.message.answer("📣 Введите текст рассылки (поддерживается HTML):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(BroadcastFSM.message_text))
async def broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=main_menu_kb())
    data = await state.get_data(); await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(select(Purchase.user_id.distinct()).where(Purchase.bot_id == data["broadcast_bot_id"]))
        user_ids = [row[0] for row in result.all()]
    
    if not user_ids:
        return await message.answer("Нет пользователей для рассылки.", reply_markup=main_menu_kb())
    
    sent, failed = 0, 0
    status_msg = await message.answer(f"📣 Рассылка на {len(user_ids)}...")
    
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except: failed += 1
        if (i + 1) % 10 == 0:
            await status_msg.edit_text(f"📣 {i + 1}/{len(user_ids)} (✅{sent} ❌{failed})")
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n✅ {sent} | ❌ {failed}")

# ── Тестовая оплата ────────────────────────────────────────

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
        return await callback.answer("Нет настроенных платёжных систем!", show_alert=True)

    await callback.message.answer(
        f"🧪 <b>Тестовая оплата</b>\n\n"
        f"Товар: {p.name}\n"
        f"Цена: {p.price}₽\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb
    )
    await callback.answer()

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
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_bot:{bot_id}"),
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

# ── Админ-панель ──────────────────────────────────────────

@constructor_router.callback_query(F.data == "admin_crypto")
async def admin_crypto(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="crypto")
    await callback.message.answer("👾 Токен Crypto Bot:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_yoomoney")
async def admin_yoomoney(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="yoomoney")
    await callback.message.answer("💳 Кошелёк ЮMoney:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_rollypay")
async def admin_rollypay(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    current = (
        f"\n\n<i>Текущие:</i>\n"
        f"Terminal ID: {'✅' if config.rollypay_terminal_id else '❌'}\n"
        f"API Key: {'✅' if config.rollypay_api_key else '❌'}\n"
        f"Signing Secret: {'✅' if config.rollypay_signing_secret else '❌'}"
    )
    
    await state.set_state(AdminRollyPayFSM.setting_type)
    await state.update_data(setting_type="rollypay_terminal")
    await callback.message.answer(f"💰 <b>RollyPay: Terminal ID</b>\nВведите Terminal ID:{current}", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminRollyPayFSM.setting_type))
async def admin_rollypay_process(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    if message.from_user.id not in ADMIN_IDS: return
    
    data = await state.get_data()
    st = data["setting_type"]
    value = message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if st == "rollypay_terminal":
            config.rollypay_terminal_id = value
            await session.commit()
            await state.update_data(setting_type="rollypay_api")
            await message.answer("🔑 Введите API Key:")
            return
        elif st == "rollypay_api":
            config.rollypay_api_key = value
            await session.commit()
            await state.update_data(setting_type="rollypay_secret")
            await message.answer("🔐 Введите Signing Secret:")
            return
        elif st == "rollypay_secret":
            config.rollypay_signing_secret = value
            await session.commit()
    
    await state.clear()
    await message.answer("✅ RollyPay полностью сохранён!", reply_markup=admin_menu_kb())

@constructor_router.message(StateFilter(AdminFSM.value))
async def admin_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    if message.from_user.id not in ADMIN_IDS: return
    data = await state.get_data(); await state.clear()
    st, value = data["setting_type"], message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        if st == "crypto": config.crypto_bot_token = value
        elif st == "yoomoney": config.yoomoney_wallet = value
        await session.commit()
    
    await message.answer("✅ Сохранено!", reply_markup=admin_menu_kb())

@constructor_router.callback_query(F.data == "admin_prices")
async def admin_prices(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    await state.set_state(AdminPricesFSM.price_type)
    await callback.message.answer(
        f"🏷 <b>Цены подписки</b>\n\n"
        f"PRO: {config.pro_subscription_price}₽\n"
        f"PREMIUM: {config.premium_subscription_price}₽\n\n"
        f"Что меняем?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ PRO", callback_data="price_pro"),
             InlineKeyboardButton(text="👑 PREMIUM", callback_data="price_premium")]
        ])
    )
    await callback.answer()

@constructor_router.callback_query(StateFilter(AdminPricesFSM.price_type))
async def admin_price_input(callback: CallbackQuery, state: FSMContext):
    price_type = callback.data
    await state.update_data(price_type=price_type)
    await state.set_state(AdminPricesFSM.value)
    name = "PRO" if price_type == "price_pro" else "PREMIUM"
    await callback.message.answer(f"Введите новую цену для {name} (₽):", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminPricesFSM.value))
async def admin_price_save(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.", reply_markup=admin_menu_kb())
    if message.from_user.id not in ADMIN_IDS: return
    
    try:
        price = Decimal(message.text.strip().replace(",", "."))
        if price <= 0: raise ValueError
    except: return await message.answer("❌ Некорректная цена.")
    
    data = await state.get_data()
    await state.clear()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        if data["price_type"] == "price_pro":
            config.pro_subscription_price = price
        else:
            config.premium_subscription_price = price
        await session.commit()
    
    await message.answer(f"✅ Цена обновлена!", reply_markup=admin_menu_kb())

@constructor_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_bots = await session.scalar(select(func.count(ShopBot.id)))
        total_revenue = await session.scalar(select(func.coalesce(func.sum(Purchase.amount), 0)).where(Purchase.status == "completed"))
        pro = await session.scalar(select(func.count(User.id)).where(User.subscription_tier == "pro"))
        premium = await session.scalar(select(func.count(User.id)).where(User.subscription_tier == "premium"))
        active_bots = await session.scalar(select(func.count(ShopBot.id)).where(ShopBot.is_active == True))
        total_purchases = await session.scalar(select(func.count(Purchase.id)).where(Purchase.status == "completed"))
        sub_revenue = await session.scalar(select(func.coalesce(func.sum(Subscription.amount), 0)).where(Subscription.status == "completed"))
    
    await callback.message.answer(
        f"📊 <b>Общая статистика</b>\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"🤖 Ботов: {total_bots} (активных: {active_bots})\n"
        f"⭐ PRO: {pro} | 👑 PREMIUM: {premium}\n"
        f"🛒 Всего продаж: {total_purchases}\n"
        f"💰 Выручка с продаж: {total_revenue or 0}₽\n"
        f"💎 Выручка с подписок: {sub_revenue or 0}₽",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("Нет доступа")
    await state.set_state(AdminBroadcastFSM.message_text)
    await callback.message.answer("📣 Текст для рассылки ВСЕМ пользователям:", reply_markup=cancel_kb())
    await callback.answer()

@constructor_router.message(StateFilter(AdminBroadcastFSM.message_text))
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.text == "❌ Отмена": await state.clear(); return await message.answer("Отменено.")
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
        except: failed += 1
        if (i + 1) % 20 == 0:
            await status_msg.edit_text(f"📣 {i + 1}/{len(user_ids)} (✅{sent} ❌{failed})")
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n✅ {sent} | ❌ {failed}")

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY (улучшенный профиль)
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
            cats = (await session.execute(select(Category).where(Category.bot_id == bot_record.id))).scalars().all()
        if not cats:
            return await message.answer("😔 Пока нет доступных категорий.")
        await message.answer("🎮 Выберите игру:", reply_markup=inline_kb([(c.name, f"shop_cat:{c.id}") for c in cats]))

    @shop_router.callback_query(F.data.startswith("shop_cat:"))
    async def show_products(callback: CallbackQuery):
        cat_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            products = (await session.execute(
                select(Product).where(Product.category_id == cat_id, Product.is_available == True)
            )).scalars().all()
            cat = await session.get(Category, cat_id)
        if not products:
            return await callback.answer("В этой категории пока нет товаров.", show_alert=True)
        await callback.message.answer(
            f"📦 <b>{cat.name}</b>:",
            reply_markup=inline_kb([(f"{p.name} — {p.price}₽", f"shop_product:{p.id}") for p in products])
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
            f"{product.description or 'Описание отсутствует'}\n\n"
            f"💰 Цена: <b>{product.price}₽</b>"
        )
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
            if not bot_record.crypto_bot_token: return await callback.answer("❌ Crypto Bot не настроен!", show_alert=True)
            
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method="crypto_bot"
            )
            session.add(purchase); await session.commit(); await session.refresh(purchase)
            
            api = CryptoBotAPI(bot_record.crypto_bot_token)
            invoice = await api.create_invoice(float(product.price), f"Покупка: {product.name}", str(purchase.id))
        
        if not invoice:
            return await callback.message.answer("❌ Ошибка создания счёта CryptoBot!")
        
        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        payment_id = str(invoice.get("invoice_id", purchase.id))
        
        async with async_session_maker() as session:
            await session.execute(update(Purchase).where(Purchase.id == purchase.id).values(payment_id=payment_id))
            await session.commit()
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price}₽\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(pay_url, "crypto", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            if not bot_record.yoomoney_wallet: return await callback.answer("❌ ЮMoney не настроен!", show_alert=True)
            
            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"yoomoney:{label}"
            )
            session.add(purchase); await session.commit()
            
            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(float(product.price), label, f"Покупка: {product.name}")
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price}₽\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(pay_url, "yoomoney", label)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_rolly:"))
    async def pay_rollypay(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        
        # Проверяем все 3 поля RollyPay
        if not is_rollypay_configured(bot_record):
            return await callback.answer("❌ RollyPay не настроен! Нужны: Terminal ID, API Key, Signing Secret", show_alert=True)
        
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product: return await callback.answer("Товар не найден.")
            
            order_id = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"rollypay:{order_id}"
            )
            session.add(purchase); await session.commit()
            
            api = RollyPayAPI(
                bot_record.rollypay_terminal_id,
                bot_record.rollypay_api_key,
                bot_record.rollypay_signing_secret
            )
            result = await api.create_payment(float(product.price), order_id, f"Покупка: {product.name}")
        
        if not result or not result.get("pay_url"):
            return await callback.message.answer("❌ Ошибка создания платежа RollyPay! Проверьте реквизиты.")
        
        pay_url = result.get("pay_url")
        payment_id = result.get("payment_id", order_id)
        
        async with async_session_maker() as session:
            await session.execute(update(Purchase).where(Purchase.id == purchase.id).values(payment_id=payment_id))
            await session.commit()
        
        await callback.message.answer(
            f"🧾 <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price}₽\n"
            f"Способ: RollyPay (СБП)\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(pay_url, "rollypay", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("check_pay:"))
    async def shop_check_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        
        await callback.answer("🔄 Проверяю оплату...")
        
        is_paid = False
        async with async_session_maker() as session:
            # Ищем покупку
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
            
            elif method == "crypto" and not purchase:
                # Ищем по ID счёта
                result = await session.execute(
                    select(Purchase).where(
                        Purchase.payment_id == payment_id,
                        Purchase.payment_method == "crypto_bot"
                    )
                )
                purchase = result.scalar_one_or_none()
                if purchase and bot_record.crypto_bot_token:
                    api = CryptoBotAPI(bot_record.crypto_bot_token)
                    if payment_id.isdigit():
                        status = await api.check_invoice(int(payment_id))
                        if status == "paid":
                            is_paid = True
                            purchase = purchase
            
            elif method == "rollypay" and not purchase and bot_record.rollypay_api_key:
                result = await session.execute(
                    select(Purchase).where(
                        (Purchase.payment_id == payment_id) |
                        (Purchase.payment_method.contains(payment_id))
                    )
                )
                purchase = result.scalar_one_or_none()
                if purchase:
                    api = RollyPayAPI(
                        bot_record.rollypay_terminal_id or "",
                        bot_record.rollypay_api_key,
                        bot_record.rollypay_signing_secret or ""
                    )
                    check = await api.check_payment(payment_id)
                    if check and check.get("status") == "paid":
                        is_paid = True
            
            if is_paid and purchase:
                if purchase.status != "completed":
                    purchase.status = "completed"
                    # Обновляем статистику пользователя
                    user = await get_or_create_user(session, purchase.user_id, None)
                    user.total_spent = (getattr(user, 'total_spent', Decimal("0.00")) or Decimal("0.00")) + purchase.amount
                    user.total_purchases = (getattr(user, 'total_purchases', 0) or 0) + 1
                    await session.commit()
                
                product = await session.get(Product, purchase.product_id)
                product_name = product.name if product else "Товар"
                
                await callback.message.answer(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"🎉 Спасибо за покупку!\n"
                    f"🛍 {product_name}\n"
                    f"💰 {purchase.amount}₽"
                )
            elif is_paid:
                await callback.message.answer("✅ Оплата подтверждена!")
            else:
                await callback.message.answer(
                    "⏳ <b>Оплата ещё не поступила.</b>\n\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )

    @shop_router.message(F.text == "📦 Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            rows = (await session.execute(
                select(Purchase, Product).join(Product)
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id)
                .order_by(Purchase.created_at.desc())
                .limit(20)
            )).all()
        
        if not rows:
            return await message.answer("📦 У вас пока нет покупок в этом магазине.")
        
        text = "📦 <b>Ваши покупки:</b>\n\n"
        sm = {"pending": "⏳ Ожидает", "completed": "✅ Завершена"}
        
        total_amount = Decimal("0.00")
        completed = 0
        
        for purchase, product in rows:
            text += f"🛍 {product.name}\n   💰 {purchase.amount}₽ | {sm.get(purchase.status, purchase.status)}\n   📅 {purchase.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            if purchase.status == "completed":
                total_amount += purchase.amount
                completed += 1
        
        text += f"━━━━━━━━━━━━━━━\n"
        text += f"📊 Завершено: {completed} покупок\n"
        text += f"💸 Потрачено: {total_amount}₽"
        
        if len(text) > 4000:
            text = text[:4000] + "\n\n...(показаны последние покупки)"
        
        await message.answer(text)

    @shop_router.message(F.text == "👤 Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            
            # Статистика в этом боте
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
            last_purchase = await session.execute(
                select(Purchase).where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id
                ).order_by(Purchase.created_at.desc()).limit(1)
            )
            last_p = last_purchase.scalar_one_or_none()
            
            # Общая статистика
            total_spent_all = getattr(user, 'total_spent', Decimal("0.00")) or Decimal("0.00")
            total_purchases_all = getattr(user, 'total_purchases', 0) or 0
        
        text = (
            f"👤 <b>Профиль в «{bot_record.bot_name}»</b>\n\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"📛 @{message.from_user.username or '—'}\n"
            f"💰 Баланс: {user.balance}₽\n\n"
            f"━━━ 📊 Статистика в этом магазине ━━━\n"
            f"🛒 Завершено покупок: {purchases_count}\n"
            f"⏳ Ожидают оплаты: {pending_count}\n"
            f"💸 Потрачено здесь: {total_spent_bot}₽\n"
        )
        
        if last_p:
            sm = {"pending": "⏳", "completed": "✅"}
            text += f"\n🕐 Последняя покупка:\n"
            text += f"   {sm.get(last_p.status, '❓')} {last_p.amount}₽ ({last_p.created_at.strftime('%d.%m %H:%M')})\n"
        
        text += (
            f"\n━━━ 🌍 Общая статистика ━━━\n"
            f"🛍 Всего покупок: {total_purchases_all}\n"
            f"💎 Потрачено всего: {total_spent_all}₽"
        )
        
        await message.answer(text)

    @shop_router.message(F.text == "📊 Статистика")
    async def shop_stats(message: Message):
        async with async_session_maker() as session:
            # Топ товаров
            top_products = (await session.execute(
                select(Product.name, func.count(Purchase.id), func.sum(Purchase.amount))
                .join(Purchase)
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed")
                .group_by(Product.name)
                .order_by(func.count(Purchase.id).desc())
                .limit(5)
            )).all()
            
            # Статистика по дням (последние 7 дней)
            week_ago = datetime.utcnow() - timedelta(days=7)
            week_sales = await session.scalar(
                select(func.count(Purchase.id))
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed", Purchase.created_at >= week_ago)
            )
            week_revenue = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed", Purchase.created_at >= week_ago)
            )
            
            # Методы оплаты
            method_stats = await session.execute(
                select(Purchase.payment_method, func.count(Purchase.id), func.sum(Purchase.amount))
                .where(Purchase.bot_id == bot_record.id, Purchase.status == "completed")
                .group_by(Purchase.payment_method)
            )
            methods = method_stats.all()
        
        text = f"📊 <b>Статистика «{bot_record.bot_name}»</b>\n\n"
        
        text += f"━━━ 📅 За 7 дней ━━━\n"
        text += f"🛒 Продаж: {week_sales or 0}\n"
        text += f"💰 Выручка: {week_revenue or 0}₽\n\n"
        
        if top_products:
            text += f"━━━ 🏆 Топ товаров ━━━\n"
            for i, (name, count, total) in enumerate(top_products, 1):
                text += f"{i}. {name} — {count} шт. ({total}₽)\n"
            text += "\n"
        
        if methods:
            text += f"━━━ 💳 По методам ━━━\n"
            method_names = {"crypto_bot": "👾 CryptoBot", "yoomoney": "💳 ЮMoney", "rollypay": "💰 RollyPay"}
            for method, count, total in methods:
                clean = method.split(":")[0]
                name = method_names.get(clean, clean)
                text += f"{name}: {count} продаж ({total or 0}₽)\n"
        
        await message.answer(text)

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
    
    running_tasks[bot_record.id] = asyncio.create_task(polling())

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
    try:
        await constructor_bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="admin", description="Админ-панель"),
        ])
    except: pass
    
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
