"""
Telegram Bot Constructor for Supercell Donate Shops
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL
Payment APIs: Crypto Pay, YooMoney, RollyPay
Features: Premium emojis, subscription tiers, admin panel
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
    ForeignKey, select, func, update, delete, and_, or_
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
    # Emoji IDs for messages
    SETTINGS_ID = "5870982283724328568"
    PROFILE_ID = "5870994129244131212"
    PEOPLE_ID = "5870772616305839506"
    PERSON_CHECK_ID = "5891207662678317861"
    PERSON_CROSS_ID = "5893192487324880883"
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
    EYE_ID = "6037397706505195857"
    EYE_HIDDEN_ID = "6037243349675544634"
    SEND_ID = "5963103826075456248"
    DOWNLOAD_ID = "6039802767931871481"
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
    
    # HTML emoji tags for messages
    SETTINGS = '<tg-emoji emoji-id="5870982283724328568">⚙</tg-emoji>'
    PROFILE = '<tg-emoji emoji-id="5870994129244131212">👤</tg-emoji>'
    PEOPLE = '<tg-emoji emoji-id="5870772616305839506">👥</tg-emoji>'
    PERSON_CHECK = '<tg-emoji emoji-id="5891207662678317861">👤</tg-emoji>'
    PERSON_CROSS = '<tg-emoji emoji-id="5893192487324880883">👤</tg-emoji>'
    FILE = '<tg-emoji emoji-id="5870528606328852614">📁</tg-emoji>'
    SMILE = '<tg-emoji emoji-id="5870764288364252592">🙂</tg-emoji>'
    GRAPH_UP = '<tg-emoji emoji-id="5870930636742595124">📊</tg-emoji>'
    STATS = '<tg-emoji emoji-id="5870921681735781843">📊</tg-emoji>'
    HOME = '<tg-emoji emoji-id="5873147866364514353">🏘</tg-emoji>'
    LOCK_CLOSED = '<tg-emoji emoji-id="6037249452824072506">🔒</tg-emoji>'
    LOCK_OPEN = '<tg-emoji emoji-id="6037496202990194718">🔓</tg-emoji>'
    MEGAPHONE = '<tg-emoji emoji-id="6039422865189638057">📣</tg-emoji>'
    CHECK = '<tg-emoji emoji-id="5870633910337015697">✅</tg-emoji>'
    CROSS = '<tg-emoji emoji-id="5870657884844462243">❌</tg-emoji>'
    PENCIL = '<tg-emoji emoji-id="5870676941614354370">🖋</tg-emoji>'
    TRASH = '<tg-emoji emoji-id="5870875489362513438">🗑</tg-emoji>'
    BACK = '<tg-emoji emoji-id="5775896410780079073">◁</tg-emoji>'
    PAPERCLIP = '<tg-emoji emoji-id="6039451237743595514">📎</tg-emoji>'
    LINK = '<tg-emoji emoji-id="5769289093221454192">🔗</tg-emoji>'
    INFO = '<tg-emoji emoji-id="6028435952299413210">ℹ</tg-emoji>'
    BOT = '<tg-emoji emoji-id="6030400221232501136">🤖</tg-emoji>'
    EYE = '<tg-emoji emoji-id="6037397706505195857">👁</tg-emoji>'
    EYE_HIDDEN = '<tg-emoji emoji-id="6037243349675544634">👁</tg-emoji>'
    SEND = '<tg-emoji emoji-id="5963103826075456248">⬆</tg-emoji>'
    DOWNLOAD = '<tg-emoji emoji-id="6039802767931871481">⬇</tg-emoji>'
    BELL = '<tg-emoji emoji-id="6039486778597970865">🔔</tg-emoji>'
    GIFT = '<tg-emoji emoji-id="6032644646587338669">🎁</tg-emoji>'
    CLOCK = '<tg-emoji emoji-id="5983150113483134607">⏰</tg-emoji>'
    PARTY = '<tg-emoji emoji-id="6041731551845159060">🎉</tg-emoji>'
    WALLET = '<tg-emoji emoji-id="5769126056262898415">👛</tg-emoji>'
    BOX = '<tg-emoji emoji-id="5884479287171485878">📦</tg-emoji>'
    CRYPTOBOT = '<tg-emoji emoji-id="5260752406890711732">👾</tg-emoji>'
    CALENDAR = '<tg-emoji emoji-id="5890937706803894250">📅</tg-emoji>'
    TAG = '<tg-emoji emoji-id="5886285355279193209">🏷</tg-emoji>'
    MONEY = '<tg-emoji emoji-id="5904462880941545555">🪙</tg-emoji>'
    SEND_MONEY = '<tg-emoji emoji-id="5890848474563352982">🪙</tg-emoji>'
    ACCEPT_MONEY = '<tg-emoji emoji-id="5879814368572478751">🏧</tg-emoji>'
    CODE = '<tg-emoji emoji-id="5940433880585605708">🔨</tg-emoji>'
    LOADING = '<tg-emoji emoji-id="5345906554510012647">🔄</tg-emoji>'
    CROWN = '<tg-emoji emoji-id="5367404172557355066">👑</tg-emoji>'
    STAR = '<tg-emoji emoji-id="5870810157871667232">⭐</tg-emoji>'
    DIAMOND = '<tg-emoji emoji-id="5870810157871667232">💎</tg-emoji>'
    FIRE = '<tg-emoji emoji-id="5369198904321376256">🔥</tg-emoji>'
    ROCKET = '<tg-emoji emoji-id="5369198904321376256">🚀</tg-emoji>'

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
    bots = relationship("ShopBot", back_populates="owner", foreign_keys="ShopBot.owner_id")
    purchases = relationship("Purchase", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # pro, premium
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("NOW()"))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    user = relationship("User", back_populates="subscriptions")

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
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), nullable=False)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    bot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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
    
    # Ensure admin config exists
    async with async_session_maker() as session:
        admin_config = await session.execute(select(AdminConfig).limit(1))
        if not admin_config.scalar_one_or_none():
            session.add(AdminConfig())
            await session.commit()
    
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
    if user.subscription_tier != "free" and user.subscription_expires:
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
    
    limits = {"free": 1, "pro": 5, "premium": 30}
    max_bots = limits.get(user.subscription_tier, 1)
    
    if bots_count >= max_bots:
        return False, f"Достигнут лимит ботов ({max_bots}) для тарифа {user.subscription_tier}. Повысьте тариф!"
    return True, ""

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

    async def check_invoice(self, invoice_id: int) -> Optional[str]:
        """Проверка статуса счета. Возвращает статус: paid, expired, active"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/getInvoices", headers=self.headers,
                    json={"invoice_ids": [invoice_id]}
                ) as resp:
                    data = await resp.json()
                    if data.get("ok") and data["result"].get("items"):
                        return data["result"]["items"][0].get("status")
        except Exception as e:
            logger.error(f"CryptoBot check error: {e}")
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
    
    def __init__(self, api_key: str, signing_secret: str):
        self.api_key = api_key
        self.signing_secret = signing_secret
    
    def _generate_nonce(self) -> str:
        return str(uuid.uuid4())
    
    def _generate_signature(self, payload: dict) -> str:
        """Генерация подписи для вебхуков"""
        data = json.dumps(payload, sort_keys=True)
        return hmac.new(
            self.signing_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, payload: dict, signature: str) -> bool:
        """Проверка подписи вебхука"""
        expected = self._generate_signature(payload)
        return hmac.compare_digest(expected, signature)
    
    async def create_payment(self, amount: float, order_id: str, description: str) -> Optional[dict]:
        """Создание платежа"""
        try:
            nonce = self._generate_nonce()
            payload = {
                "amount": f"{amount:.2f}",
                "payment_currency": "RUB",
                "order_id": order_id,
                "description": description
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payments",
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce
                    },
                    json=payload
                ) as resp:
                    data = await resp.json()
                    return data
        except Exception as e:
            logger.error(f"RollyPay create payment error: {e}")
            return None
    
    async def check_payment(self, payment_id: str) -> Optional[dict]:
        """Проверка статуса платежа"""
        try:
            nonce = self._generate_nonce()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/payments/{payment_id}",
                    headers={
                        "X-API-Key": self.api_key,
                        "X-Nonce": nonce
                    }
                ) as resp:
                    data = await resp.json()
                    return data
        except Exception as e:
            logger.error(f"RollyPay check payment error: {e}")
            return None

# ═══════════════════════════════════════════════════════════
# KEYBOARDS (с premium emoji в icon_custom_emoji_id)
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Создать бота", icon_custom_emoji_id=Emoji.BOT_ID),
                KeyboardButton(text="Мои боты", icon_custom_emoji_id=Emoji.BOX_ID)
            ],
            [
                KeyboardButton(text="Подписка", icon_custom_emoji_id=Emoji.CROWN_ID),
                KeyboardButton(text="Профиль", icon_custom_emoji_id=Emoji.PROFILE_ID)
            ],
        ],
        resize_keyboard=True
    )

def shop_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Купить донат", icon_custom_emoji_id=Emoji.SHOP_ID),
                KeyboardButton(text="Мои покупки", icon_custom_emoji_id=Emoji.BOX_ID)
            ],
            [
                KeyboardButton(text="Профиль", icon_custom_emoji_id=Emoji.PROFILE_ID)
            ],
        ],
        resize_keyboard=True
    )

def bot_management_kb(bot_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Категории",
                callback_data=f"manage_cats:{bot_id}",
                icon_custom_emoji_id=Emoji.FILE_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Товары",
                callback_data=f"manage_products:{bot_id}",
                icon_custom_emoji_id=Emoji.BOX_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Платежи",
                callback_data=f"payment_settings:{bot_id}",
                icon_custom_emoji_id=Emoji.WALLET_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Статистика",
                callback_data=f"bot_stats:{bot_id}",
                icon_custom_emoji_id=Emoji.STATS_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Рассылка",
                callback_data=f"bot_broadcast:{bot_id}",
                icon_custom_emoji_id=Emoji.MEGAPHONE_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Покупатели",
                callback_data=f"bot_buyers:{bot_id}",
                icon_custom_emoji_id=Emoji.PEOPLE_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Остановить" if is_active else "Запустить",
                callback_data=f"toggle_bot:{bot_id}",
                icon_custom_emoji_id=Emoji.LOCK_CLOSED_ID if is_active else Emoji.LOCK_OPEN_ID
            ),
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"delete_bot:{bot_id}",
                icon_custom_emoji_id=Emoji.TRASH_ID
            ),
        ],
    ])

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена", icon_custom_emoji_id=Emoji.CROSS_ID)]],
        resize_keyboard=True
    )

def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Назад к управлению",
            callback_data=f"back_to_bot:{bot_id}",
            icon_custom_emoji_id=Emoji.BACK_ID
        )]
    ])

def subscription_kb(user_tier: str = "free") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if user_tier != "pro":
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="Купить PRO (100₽)",
                callback_data="buy_subscription:pro:crypto",
                icon_custom_emoji_id=Emoji.STAR_ID
            ),
            InlineKeyboardButton(
                text="PRO (ЮMoney)",
                callback_data="buy_subscription:pro:yoomoney",
                icon_custom_emoji_id=Emoji.WALLET_ID
            ),
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="PRO (RollyPay)",
                callback_data="buy_subscription:pro:rollypay",
                icon_custom_emoji_id=Emoji.MONEY_ID
            ),
        ])
    
    if user_tier != "premium":
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="Купить PREMIUM (250₽)",
                callback_data="buy_subscription:premium:crypto",
                icon_custom_emoji_id=Emoji.CROWN_ID
            ),
            InlineKeyboardButton(
                text="PREMIUM (ЮMoney)",
                callback_data="buy_subscription:premium:yoomoney",
                icon_custom_emoji_id=Emoji.WALLET_ID
            ),
        ])
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="PREMIUM (RollyPay)",
                callback_data="buy_subscription:premium:rollypay",
                icon_custom_emoji_id=Emoji.MONEY_ID
            ),
        ])
    
    return kb

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Crypto Bot",
                callback_data="admin_crypto",
                icon_custom_emoji_id=Emoji.CRYPTOBOT_ID
            ),
            InlineKeyboardButton(
                text="ЮMoney",
                callback_data="admin_yoomoney",
                icon_custom_emoji_id=Emoji.WALLET_ID
            ),
        ],
        [
            InlineKeyboardButton(
                text="RollyPay",
                callback_data="admin_rollypay",
                icon_custom_emoji_id=Emoji.MONEY_ID
            ),
        ],
        [
            InlineKeyboardButton(
                text="Цены подписки",
                callback_data="admin_prices",
                icon_custom_emoji_id=Emoji.TAG_ID
            ),
        ],
        [
            InlineKeyboardButton(
                text="Статистика",
                callback_data="admin_stats",
                icon_custom_emoji_id=Emoji.STATS_ID
            ),
        ],
        [
            InlineKeyboardButton(
                text="Рассылка всем",
                callback_data="admin_broadcast",
                icon_custom_emoji_id=Emoji.MEGAPHONE_ID
            ),
        ],
    ])

def payment_method_kb(bot_id: int, product_id: int, bot: ShopBot) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="Crypto Bot",
                callback_data=f"pay_crypto:{product_id}",
                icon_custom_emoji_id=Emoji.CRYPTOBOT_ID
            )
        ])
    
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="ЮMoney",
                callback_data=f"pay_yoo:{product_id}",
                icon_custom_emoji_id=Emoji.WALLET_ID
            )
        ])
    
    if bot.rollypay_api_key:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="RollyPay (СБП)",
                callback_data=f"pay_rolly:{product_id}",
                icon_custom_emoji_id=Emoji.MONEY_ID
            )
        ])
    
    return kb

def payment_invoice_kb(pay_url: str, payment_method: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Оплатить",
                url=pay_url,
                icon_custom_emoji_id=Emoji.SEND_MONEY_ID
            )
        ],
        [
            InlineKeyboardButton(
                text="Проверить оплату",
                callback_data=f"check_payment:{payment_method}:{payment_id}",
                icon_custom_emoji_id=Emoji.VERIFY_ID
            )
        ],
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
    bot_id = State()
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

# ── /start ─────────────────────────────────────────────────

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        await get_or_create_user(session, message.from_user.id, message.from_user.username)
    await message.answer(
        f"{Emoji.BOT} Добро пожаловать в конструктор магазинов доната!\n\n"
        f"Создайте бота для продажи доната в играх Supercell.\n"
        f"{Emoji.CROWN} После создания вы сможете управлять товарами, категориями и платежами.",
        reply_markup=main_menu_kb()
    )

# ── /admin ─────────────────────────────────────────────────

@constructor_router.message(Command("admin"))
async def admin_command(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer(f"{Emoji.CROSS} У вас нет доступа к админ-панели.")
    
    await message.answer(
        f"{Emoji.SETTINGS} <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_menu_kb()
    )

# ── Профиль ─────────────────────────────────────────────────

@constructor_router.message(F.text == "Профиль")
async def profile(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(ShopBot.owner_id == message.from_user.id)
        )
        total_purchases = await session.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.user_id == message.from_user.id,
                Purchase.status == "completed"
            )
        )
    
    tier_display = {"free": "Бесплатный", "pro": "PRO", "premium": "PREMIUM"}
    tier_emoji = {"free": Emoji.SMILE, "pro": Emoji.STAR, "premium": Emoji.CROWN}
    
    tier_text = tier_display.get(user.subscription_tier, "Бесплатный")
    tier_em = tier_emoji.get(user.subscription_tier, Emoji.SMILE)
    
    expiry_text = ""
    if user.subscription_expires and user.subscription_tier != "free":
        expiry_text = f"\nДействует до: {user.subscription_expires.strftime('%d.%m.%Y %H:%M')}"
    
    limits = {"free": "1 бот", "pro": "5 ботов", "premium": "30 ботов"}
    limit_text = limits.get(user.subscription_tier, "1 бот")
    
    await message.answer(
        f"{Emoji.PROFILE} <b>Профиль</b>\n\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: @{message.from_user.username or '—'}\n"
        f"Баланс: {user.balance} ₽\n"
        f"Тариф: {tier_em} {tier_text}{expiry_text}\n"
        f"Лимит ботов: {limit_text}\n"
        f"Ботов создано: {bots_count}\n"
        f"Всего покупок: {total_purchases}"
    )

# ── Подписка ───────────────────────────────────────────────

@constructor_router.message(F.text == "Подписка")
async def subscription_menu(message: Message):
    async with async_session_maker() as session:
        user = await check_subscription(session, message.from_user.id)
    
    tier_display = {"free": "Бесплатный", "pro": "PRO", "premium": "PREMIUM"}
    tier_emoji = {"free": Emoji.SMILE, "pro": Emoji.STAR, "premium": Emoji.CROWN}
    
    await message.answer(
        f"{Emoji.CROWN} <b>Подписка</b>\n\n"
        f"Текущий тариф: {tier_emoji.get(user.subscription_tier)} {tier_display.get(user.subscription_tier)}\n\n"
        f"{Emoji.SMILE} <b>Бесплатный</b> — 1 бот\n"
        f"{Emoji.STAR} <b>PRO</b> — 5 ботов, 100₽/мес\n"
        f"{Emoji.CROWN} <b>PREMIUM</b> — 30 ботов, 250₽/мес\n\n"
        f"Выберите тариф для покупки:",
        reply_markup=subscription_kb(user.subscription_tier)
    )

@constructor_router.callback_query(F.data.startswith("buy_subscription:"))
async def buy_subscription(callback: CallbackQuery):
    parts = callback.data.split(":")
    tier = parts[1]  # pro или premium
    method = parts[2]  # crypto, yoomoney или rollypay
    
    prices = {"pro": Decimal("100.00"), "premium": Decimal("250.00")}
    amount = prices.get(tier, Decimal("100.00"))
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        subscription = Subscription(
            user_id=callback.from_user.id,
            tier=tier,
            amount=amount,
            payment_method=method,
            status="pending",
            expires_at=expires_at
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)
        
        if method == "crypto":
            if not admin_config.crypto_bot_token:
                await callback.answer("Crypto Bot не настроен!", show_alert=True)
                return
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            invoice = await api.create_invoice(
                float(amount),
                f"Подписка {tier.upper()} на 1 месяц",
                f"sub_{subscription.id}"
            )
            if not invoice:
                await callback.answer("Ошибка создания счёта!", show_alert=True)
                return
            pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
            payment_id = str(invoice.get("invoice_id", subscription.id))
            subscription.payment_id = payment_id
            await session.commit()
        
        elif method == "yoomoney":
            if not admin_config.yoomoney_wallet:
                await callback.answer("ЮMoney не настроен!", show_alert=True)
                return
            yoo = YooMoneyAPI(admin_config.yoomoney_wallet)
            label = f"sub_{subscription.id}"
            pay_url = yoo.generate_form_url(float(amount), label, f"Подписка {tier.upper()} на 1 месяц")
            payment_id = label
        
        elif method == "rollypay":
            if not admin_config.rollypay_api_key:
                await callback.answer("RollyPay не настроен!", show_alert=True)
                return
            api = RollyPayAPI(admin_config.rollypay_api_key, admin_config.rollypay_signing_secret or "")
            order_id = f"sub_{subscription.id}"
            result = await api.create_payment(
                float(amount),
                order_id,
                f"Подписка {tier.upper()} на 1 месяц"
            )
            if not result or not result.get("pay_url"):
                await callback.answer("Ошибка создания платежа!", show_alert=True)
                return
            pay_url = result.get("pay_url")
            payment_id = result.get("payment_id", order_id)
            subscription.payment_id = payment_id
            await session.commit()
    
    await callback.message.answer(
        f"{Emoji.CROWN} <b>Оплата подписки {tier.upper()}</b>\n\n"
        f"Сумма: {amount} ₽\n"
        f"Срок: 1 месяц\n"
        f"ID: <code>{subscription.id}</code>\n\n"
        f"Нажмите «Оплатить» для перехода к оплате.",
        reply_markup=payment_invoice_kb(pay_url, method, payment_id)
    )
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("check_payment:"))
async def check_payment(callback: CallbackQuery):
    parts = callback.data.split(":")
    method = parts[1]
    payment_id = parts[2]
    
    await callback.answer(f"{Emoji.LOADING} Проверяю оплату...")
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        is_paid = False
        
        if method == "crypto" and admin_config.crypto_bot_token:
            api = CryptoBotAPI(admin_config.crypto_bot_token)
            status = await api.check_invoice(int(payment_id))
            if status == "paid":
                is_paid = True
        
        elif method == "yoomoney":
            # YooMoney webhook проверка
            subscription = await session.execute(
                select(Subscription).where(Subscription.payment_id == f"sub_{payment_id}")
            )
            sub = subscription.scalar_one_or_none()
            if sub and sub.status == "completed":
                is_paid = True
        
        elif method == "rollypay" and admin_config.rollypay_api_key:
            api = RollyPayAPI(admin_config.rollypay_api_key, admin_config.rollypay_signing_secret or "")
            result = await api.check_payment(payment_id)
            if result and result.get("status") == "paid":
                is_paid = True
        
        if not is_paid:
            # Проверка по subscription
            subscription = await session.execute(
                select(Subscription).where(
                    (Subscription.payment_id == payment_id) |
                    (Subscription.payment_id == f"sub_{payment_id}")
                )
            )
            sub = subscription.scalar_one_or_none()
            if sub and sub.status == "completed":
                is_paid = True
        
        if is_paid:
            # Обновляем подписку
            subscription = await session.execute(
                select(Subscription).where(
                    (Subscription.payment_id == payment_id) |
                    (Subscription.payment_id == f"sub_{payment_id}")
                )
            )
            sub = subscription.scalar_one_or_none()
            if sub and sub.status != "completed":
                sub.status = "completed"
                user = await get_or_create_user(session, sub.user_id, None)
                user.subscription_tier = sub.tier
                user.subscription_expires = sub.expires_at
                await session.commit()
            
            await callback.message.answer(
                f"{Emoji.CHECK} <b>Оплата подтверждена!</b>\n\n"
                f"Ваша подписка активирована."
            )
        else:
            await callback.message.answer(
                f"{Emoji.CLOCK} <b>Оплата ещё не поступила.</b>\n\n"
                f"Попробуйте позже или обратитесь в поддержку."
            )
    
    await callback.answer()

# ── Создать бота ───────────────────────────────────────────

@constructor_router.message(F.text == "Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(session, message.from_user.id)
        if not can_create:
            return await message.answer(f"{Emoji.CROSS} {error_msg}")
    
    await state.set_state(CreateBotFSM.token)
    await message.answer(
        f"{Emoji.BOT} <b>Шаг 1/5</b> — Введите токен бота.\n"
        f"Получите его у @BotFather командой /newbot\n\n"
        f"Формат: <code>123456:ABC-DEF1234ghikl</code>",
        reply_markup=cancel_kb()
    )

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
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
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
    name = message.text.strip()
    if not name or len(name) > 255:
        return await message.answer(f"{Emoji.CROSS} Название должно быть от 1 до 255 символов.")
    
    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    await message.answer(
        f"{Emoji.CHECK} Название принято.\n\n"
        f"{Emoji.PERSON_CHECK} <b>Шаг 3/5</b> — Введите Telegram ID администратора:\n"
        f"Этот пользователь будет управлять ботом из конструктора.\n"
        f"Получить ID: @getmyid_bot"
    )

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
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
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
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
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
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
        for game in ["Brawl Stars", "Clash of Clans", "Clash Royale"]:
            session.add(Category(bot_id=bot_record.id, name=game))
        await session.commit()

    # Launch the created bot
    asyncio.create_task(run_shop_bot(bot_record))

    payments = []
    if bot_record.crypto_bot_token:
        payments.append("Crypto Bot")
    if bot_record.yoomoney_wallet:
        payments.append("ЮMoney")
    if bot_record.rollypay_api_key:
        payments.append("RollyPay")

    text = (
        f"{Emoji.CHECK} <b>Бот «{data['name']}» создан и запущен!</b>\n\n"
        f"Токен: <code>{data['token']}</code>\n"
        f"Admin ID: <code>{data['admin_id']}</code>\n"
        f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n\n"
        f"{Emoji.INFO} <b>Управление ботом доступно в разделе «Мои боты»</b>\n"
        f"Там вы можете: добавлять товары, настраивать категории, делать рассылки и смотреть статистику.\n\n"
        f"Сам бот уже работает — перейдите в него и нажмите /start"
    )
    await message.answer(text, reply_markup=main_menu_kb())

# ── Мои боты ─────────────────────────────────────────────────

@constructor_router.message(F.text == "Мои боты")
async def my_bots(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.owner_id == message.from_user.id)
        )
        bots = result.scalars().all()

    if not bots:
        return await message.answer(
            f"{Emoji.BOX} У вас пока нет созданных ботов.\n"
            f"Нажмите «Создать бота» чтобы начать!"
        )

    for bot in bots:
        status = "Активен" if bot.is_active else "Остановлен"
        status_emoji = Emoji.LOCK_OPEN if bot.is_active else Emoji.LOCK_CLOSED
        payments = []
        if bot.crypto_bot_token:
            payments.append("Crypto Bot")
        if bot.yoomoney_wallet:
            payments.append("ЮMoney")
        if bot.rollypay_api_key:
            payments.append("RollyPay")

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

        text = (
            f"{Emoji.BOT} <b>{bot.bot_name}</b>\n"
            f"{status_emoji} Статус: {status}\n"
            f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
            f"Товаров: {products_count}\n"
            f"Выручка: {total_revenue or 0} ₽\n"
            f"ID: <code>{bot.id}</code>"
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
        
        payments = []
        if bot.crypto_bot_token: payments.append("Crypto Bot")
        if bot.yoomoney_wallet: payments.append("ЮMoney")
        if bot.rollypay_api_key: payments.append("RollyPay")
        
        products_count = await session.scalar(
            select(func.count(Product.id)).where(
                Product.category_id.in_(
                    select(Category.id).where(Category.bot_id == bot.id)
                )
            )
        )

    status = "Активен" if bot.is_active else "Остановлен"
    status_emoji = Emoji.LOCK_OPEN if bot.is_active else Emoji.LOCK_CLOSED
    text = (
        f"{Emoji.BOT} <b>{bot.bot_name}</b>\n"
        f"{status_emoji} Статус: {status}\n"
        f"Платежи: {', '.join(payments) if payments else 'не настроены'}\n"
        f"Товаров: {products_count}\n"
        f"ID: <code>{bot.id}</code>"
    )
    await callback.message.edit_text(text, reply_markup=bot_management_kb(bot_id, bot.is_active))
    await callback.answer()

# ── Платёжные реквизиты (для бота) ─────────────────────────

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
        f"{Emoji.WALLET} ЮMoney: {'✅ Настроен' if bot.yoomoney_wallet else '❌ Не настроен'}\n"
        f"{Emoji.MONEY} RollyPay: {'✅ Настроен' if bot.rollypay_api_key else '❌ Не настроен'}\n\n"
        f"Выберите действие:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Изменить Crypto Bot",
            callback_data=f"edit_crypto:{bot_id}",
            icon_custom_emoji_id=Emoji.CRYPTOBOT_ID
        )],
        [InlineKeyboardButton(
            text="Изменить ЮMoney",
            callback_data=f"edit_yoo:{bot_id}",
            icon_custom_emoji_id=Emoji.WALLET_ID
        )],
        [InlineKeyboardButton(
            text="Изменить RollyPay",
            callback_data=f"edit_rolly:{bot_id}",
            icon_custom_emoji_id=Emoji.MONEY_ID
        )],
        [InlineKeyboardButton(
            text="Тестовая оплата",
            callback_data=f"test_payment:{bot_id}",
            icon_custom_emoji_id=Emoji.SEND_MONEY_ID
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=f"back_to_bot:{bot_id}",
            icon_custom_emoji_id=Emoji.BACK_ID
        )],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@constructor_router.callback_query(F.data.startswith("edit_rolly:"))
async def edit_rolly_start(callback: CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split(":")[1])
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.rollypay_api_key)
    await callback.message.answer(
        f"{Emoji.MONEY} Введите API ключ RollyPay:\n"
        f"Или «-» чтобы удалить.",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(PaymentSettingsFSM.rollypay_api_key))
async def edit_rolly_key(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
    key = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(rollypay_api_key=key)
    await state.set_state(PaymentSettingsFSM.rollypay_secret)
    await message.answer(
        f"{Emoji.MONEY} Введите Signing Secret RollyPay:\n"
        f"Или «-» чтобы пропустить."
    )

@constructor_router.message(StateFilter(PaymentSettingsFSM.rollypay_secret))
async def edit_rolly_save(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
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

    await message.answer(f"{Emoji.CHECK} RollyPay обновлён!", reply_markup=main_menu_kb())

# ── Админ-панель ───────────────────────────────────────────

@constructor_router.callback_query(F.data == "admin_crypto")
async def admin_crypto(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="crypto")
    await callback.message.answer(
        f"{Emoji.CRYPTOBOT} Введите токен Crypto Bot для приёма платежей за подписки:",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_yoomoney")
async def admin_yoomoney(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="yoomoney")
    await callback.message.answer(
        f"{Emoji.WALLET} Введите номер кошелька ЮMoney:",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.callback_query(F.data == "admin_rollypay")
async def admin_rollypay(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="rollypay_key")
    await callback.message.answer(
        f"{Emoji.MONEY} Введите API ключ RollyPay:",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@constructor_router.message(StateFilter(AdminFSM.value))
async def admin_save_value(message: Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    data = await state.get_data()
    setting_type = data["setting_type"]
    value = message.text.strip()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if setting_type == "crypto":
            config.crypto_bot_token = value
            await message.answer(f"{Emoji.CHECK} Crypto Bot токен сохранён.")
        
        elif setting_type == "yoomoney":
            config.yoomoney_wallet = value
            await message.answer(f"{Emoji.CHECK} ЮMoney кошелёк сохранён.")
        
        elif setting_type == "rollypay_key":
            config.rollypay_api_key = value
            await state.update_data(setting_type="rollypay_secret")
            await message.answer(f"{Emoji.MONEY} Введите Signing Secret RollyPay:")
            return
        
        elif setting_type == "rollypay_secret":
            config.rollypay_signing_secret = value
            await message.answer(f"{Emoji.CHECK} RollyPay сохранён.")
        
        await session.commit()
    
    await state.clear()
    await message.answer(
        f"{Emoji.SETTINGS} <b>Админ-панель</b>",
        reply_markup=admin_menu_kb()
    )

@constructor_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_bots = await session.scalar(select(func.count(ShopBot.id)))
        total_purchases = await session.scalar(
            select(func.count(Purchase.id)).where(Purchase.status == "completed")
        )
        total_revenue = await session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
            .where(Purchase.status == "completed")
        )
        pro_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_tier == "pro")
        )
        premium_users = await session.scalar(
            select(func.count(User.id)).where(User.subscription_tier == "premium")
        )
    
    await callback.message.answer(
        f"{Emoji.STATS} <b>Общая статистика</b>\n\n"
        f"Пользователей: {total_users}\n"
        f"Ботов создано: {total_bots}\n"
        f"Продаж: {total_purchases}\n"
        f"Выручка: {total_revenue or 0} ₽\n"
        f"PRO подписок: {pro_users}\n"
        f"PREMIUM подписок: {premium_users}",
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
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())
    
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in result.all()]
    
    sent, failed = 0, 0
    status_msg = await message.answer(f"{Emoji.LOADING} Рассылка на {len(user_ids)} пользователей...")
    
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

# ── Рассылка для бота (исправленная) ───────────────────────

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
    if message.text == "Отмена":
        await state.clear()
        return await message.answer(f"{Emoji.CROSS} Отменено.", reply_markup=main_menu_kb())

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
        
        if (i + 1) % 5 == 0:
            await status_msg.edit_text(
                f"{Emoji.LOADING} Рассылка: {i + 1}/{len(user_ids)} "
                f"({Emoji.CHECK} {sent} | {Emoji.CROSS} {failed})"
            )
        
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"{Emoji.MEGAPHONE} <b>Рассылка завершена!</b>\n\n"
        f"{Emoji.CHECK} Отправлено: {sent}\n"
        f"{Emoji.CROSS} Ошибок: {failed}",
        reply_markup=main_menu_kb()
    )

# ── Прочие обработчики (toggle/delete бота) ───────────────

@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        if bot and bot.owner_id == callback.from_user.id:
            bot.is_active = not bot.is_active
            await session.commit()
            status = "запущен" if bot.is_active else "остановлен"
            await callback.answer(f"{Emoji.CHECK} Бот {status}.")
        else:
            await callback.answer(f"{Emoji.CROSS} Ошибка.")

@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    bot_id = int(callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Да, удалить",
                callback_data=f"confirm_delete_bot:{bot_id}",
                icon_custom_emoji_id=Emoji.CHECK_ID
            ),
            InlineKeyboardButton(
                text="Нет",
                callback_data="cancel_delete",
                icon_custom_emoji_id=Emoji.CROSS_ID
            ),
        ]
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
    await callback.message.edit_text(f"{Emoji.CHECK} Бот удалён.")
    await callback.answer()

@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    await callback.message.edit_text(f"{Emoji.CROSS} Отменено.")
    await callback.answer()

# ═══════════════════════════════════════════════════════════
# SHOP BOT FACTORY (с RollyPay)
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    shop_router = Router()

    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        async with async_session_maker() as session:
            await get_or_create_user(session, message.from_user.id, message.from_user.username)
        await message.answer(
            f"Добро пожаловать в <b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат для игр Supercell.\n"
            f"Выберите действие:",
            reply_markup=shop_menu_kb()
        )

    @shop_router.message(F.text == "Купить донат")
    async def buy_donate(message: Message):
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(Category.bot_id == bot_record.id)
            )
            cats = result.scalars().all()
        if not cats:
            return await message.answer(f"{Emoji.CROSS} Пока нет доступных категорий.")
        
        await message.answer(
            f"{Emoji.BOX} Выберите игру:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=c.name,
                    callback_data=f"shop_cat:{c.id}",
                    icon_custom_emoji_id=Emoji.FILE_ID
                )] for c in cats
            ])
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
            return await callback.answer(f"{Emoji.CROSS} В этой категории пока нет товаров.", show_alert=True)
        
        await callback.message.answer(
            f"{Emoji.BOX} <b>{cat.name}</b>:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{p.name} — {p.price} ₽",
                    callback_data=f"shop_product:{p.id}",
                    icon_custom_emoji_id=Emoji.SHOP_ID
                )] for p in products
            ])
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("shop_product:"))
    async def product_detail(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
        
        if not product:
            return await callback.answer(f"{Emoji.CROSS} Товар не найден.", show_alert=True)

        text = (
            f"{Emoji.BOX} <b>{product.name}</b>\n\n"
            f"{product.description or ''}\n\n"
            f"{Emoji.MONEY} Цена: <b>{product.price} ₽</b>"
        )
        
        kb = payment_method_kb(bot_record.id, product_id, bot_record)
        if not kb.inline_keyboard:
            return await callback.message.answer(text + "\n\n❌ Оплата временно недоступна.")
        
        await callback.message.answer(text + "\n\nВыберите способ оплаты:", reply_markup=kb)
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_crypto:"))
    async def pay_crypto(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer(f"{Emoji.CROSS} Товар не найден.")
            
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method="crypto_bot"
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
            return await callback.message.answer(f"{Emoji.CROSS} Ошибка создания счёта!")
        
        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        payment_id = str(invoice.get("invoice_id", purchase.id))
        purchase.payment_id = payment_id
        
        async with async_session_maker() as session:
            await session.merge(purchase)
            await session.commit()
        
        await callback.message.answer(
            f"{Emoji.MONEY} <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price} ₽\n\n"
            f"Нажмите «Оплатить»",
            reply_markup=payment_invoice_kb(pay_url, "crypto", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_yoo:"))
    async def pay_yoomoney(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer(f"{Emoji.CROSS} Товар не найден.")
            
            label = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"yoomoney:{label}"
            )
            session.add(purchase)
            await session.commit()
            
            yoo = YooMoneyAPI(bot_record.yoomoney_wallet)
            pay_url = yoo.generate_form_url(
                float(product.price), label, f"Покупка: {product.name}"
            )
        
        await callback.message.answer(
            f"{Emoji.MONEY} <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price} ₽\n\n"
            f"Нажмите «Оплатить»",
            reply_markup=payment_invoice_kb(pay_url, "yoomoney", label)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("pay_rolly:"))
    async def pay_rollypay(callback: CallbackQuery):
        product_id = int(callback.data.split(":")[1])
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            if not product:
                return await callback.answer(f"{Emoji.CROSS} Товар не найден.")
            
            order_id = f"shop_{bot_record.id}_{product_id}_{int(time.time())}"
            purchase = Purchase(
                user_id=callback.from_user.id, bot_id=bot_record.id,
                product_id=product_id, amount=product.price,
                status="pending", payment_method=f"rollypay:{order_id}"
            )
            session.add(purchase)
            await session.commit()
            
            api = RollyPayAPI(bot_record.rollypay_api_key, bot_record.rollypay_signing_secret or "")
            result = await api.create_payment(
                float(product.price),
                order_id,
                f"Покупка: {product.name}"
            )
        
        if not result or not result.get("pay_url"):
            return await callback.message.answer(f"{Emoji.CROSS} Ошибка создания платежа RollyPay!")
        
        pay_url = result.get("pay_url")
        payment_id = result.get("payment_id", order_id)
        purchase.payment_id = payment_id
        
        async with async_session_maker() as session:
            await session.merge(purchase)
            await session.commit()
        
        await callback.message.answer(
            f"{Emoji.MONEY} <b>Счёт создан!</b>\n\n"
            f"Товар: {product.name}\n"
            f"Сумма: {product.price} ₽\n\n"
            f"Нажмите «Оплатить» для перехода к оплате через СБП",
            reply_markup=payment_invoice_kb(pay_url, "rollypay", payment_id)
        )
        await callback.answer()

    @shop_router.callback_query(F.data.startswith("check_payment:"))
    async def shop_check_payment(callback: CallbackQuery):
        parts = callback.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        
        await callback.answer(f"{Emoji.LOADING} Проверяю оплату...")
        
        async with async_session_maker() as session:
            is_paid = False
            purchase = None
            
            if method == "crypto":
                api = CryptoBotAPI(bot_record.crypto_bot_token)
                status = await api.check_invoice(int(payment_id))
                if status == "paid":
                    is_paid = True
                    purchase_result = await session.execute(
                        select(Purchase).where(Purchase.payment_id == payment_id)
                    )
                    purchase = purchase_result.scalar_one_or_none()
            
            elif method == "rollypay":
                api = RollyPayAPI(bot_record.rollypay_api_key, bot_record.rollypay_signing_secret or "")
                result = await api.check_payment(payment_id)
                if result and result.get("status") == "paid":
                    is_paid = True
                    purchase_result = await session.execute(
                        select(Purchase).where(
                            (Purchase.payment_id == payment_id) |
                            (Purchase.payment_method == f"rollypay:{payment_id}")
                        )
                    )
                    purchase = purchase_result.scalar_one_or_none()
            
            if is_paid and purchase and purchase.status == "pending":
                purchase.status = "completed"
                await session.commit()
                await callback.message.answer(
                    f"{Emoji.CHECK} <b>Оплата подтверждена!</b>\n\n"
                    f"Спасибо за покупку!\n"
                    f"Товар: {purchase.product_id}"
                )
            elif is_paid and purchase:
                await callback.message.answer(
                    f"{Emoji.CHECK} <b>Оплата уже была подтверждена ранее.</b>"
                )
            else:
                await callback.message.answer(
                    f"{Emoji.CLOCK} <b>Оплата ещё не поступила.</b>\n\n"
                    f"Попробуйте позже."
                )

    @shop_router.message(F.text == "Мои покупки")
    async def my_purchases(message: Message):
        async with async_session_maker() as session:
            rows = (await session.execute(
                select(Purchase, Product).join(Product)
                .where(Purchase.user_id == message.from_user.id, Purchase.bot_id == bot_record.id)
                .order_by(Purchase.created_at.desc()).limit(20)
            )).all()
        
        if not rows:
            return await message.answer(f"{Emoji.CROSS} У вас пока нет покупок.")
        
        text = f"{Emoji.BOX} <b>Ваши покупки:</b>\n\n"
        status_map = {"pending": "⏳ Ожидает", "completed": "✅ Завершена"}
        for purchase, product in rows:
            text += f"{Emoji.SHOP} {product.name} — {purchase.amount} ₽ | {status_map.get(purchase.status, purchase.status)}\n"
        
        await message.answer(text)

    @shop_router.message(F.text == "Профиль")
    async def shop_profile(message: Message):
        async with async_session_maker() as session:
            user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
            total = await session.scalar(
                select(func.coalesce(func.sum(Purchase.amount), 0))
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id,
                    Purchase.status == "completed"
                )
            )
        
        await message.answer(
            f"{Emoji.PROFILE} <b>Профиль</b>\n\n"
            f"ID: <code>{message.from_user.id}</code>\n"
            f"Баланс: {user.balance} ₽\n"
            f"Потрачено в этом магазине: {total} ₽"
        )

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
    await constructor_bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="admin", description="Админ-панель"),
    ])
    
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
