"""
Telegram Bot Constructor for Supercell Donate Shops & Feedback Bots
Stack: aiogram 3.x, SQLAlchemy 2.0 (async), PostgreSQL
Bothost-compatible: reads BOT_TOKEN & DATABASE_URL from env
Auto-deploy — starts immediately
Payment APIs: Crypto Pay, YooMoney, RollyPay
Features: Donate shops, Feedback bots, Premium emojis, subscription tiers, admin panel
Channel: @vestcreatorsktgk
"""

# ═══════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════

import asyncio
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
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    select,
    func,
    update,
    delete,
    inspect
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import text


# ═══════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# ENVIRONMENT CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Get bot token from environment variables (Bothost compatible)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Admin user IDs who can access the admin panel
ADMIN_IDS = [7973988177]

# Channel for instructions and support
CHANNEL_USERNAME = "@vestcreatorsktgk"
CHANNEL_URL = "https://t.me/vestcreatorsktgk"

# Adapt PostgreSQL URL for asyncpg driver if needed
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    if "+asyncpg" not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1
        )
        logger.info("DATABASE_URL adapted for asyncpg driver")

# Validate required environment variables
if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is not set!")
    exit(1)

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable is not set!")
    exit(1)

logger.info("Configuration loaded successfully")
logger.info(f"Channel: {CHANNEL_USERNAME}")
logger.info(f"Admin IDs: {ADMIN_IDS}")


# ═══════════════════════════════════════════════════════════
# EMOJI CLASS
# ═══════════════════════════════════════════════════════════

class Emoji:
    """
    Standard Unicode emojis that work everywhere without Premium.
    Using Unicode characters instead of custom emoji IDs for compatibility.
    """
    
    # ── Navigation and UI Elements ──────────────────────────
    
    SETTINGS = "⚙️"          # Settings/Configuration
    PROFILE = "👤"            # Profile/User
    BACK = "◀️"              # Back/Return
    HOME = "🏠"              # Home
    ADD = "➕"               # Add/Create
    REMOVE = "➖"            # Remove/Delete
    LIST = "📋"              # List/Menu
    CHECK = "✅"             # Checkmark/Success
    CROSS = "❌"             # Cross/Error/Cancel
    LOADING = "🔄"           # Loading/Processing
    WARNING = "⚠️"          # Warning/Caution
    INFO = "ℹ️"             # Information
    QUESTION = "❓"          # Question/Help
    PENCIL = "✏️"           # Edit/Pencil
    TRASH = "🗑️"           # Delete/Trash
    KEY = "🔑"               # Key/Token
    LOCK = "🔒"              # Lock/Closed
    UNLOCK = "🔓"            # Unlock/Open
    EYE = "👁️"             # Eye/Visible
    GEAR = "⚙️"             # Gear/Settings
    TOOLS = "🛠️"           # Tools
    CHANNEL = "📢"           # Channel/Announcement
    SEND = "📤"              # Send/Forward
    ROCKET = "🚀"            # Rocket/Launch
    
    # ── Users and Profiles ──────────────────────────────────
    
    USERS = "👥"             # Users/People
    PEOPLE = "👥"            # People/Group
    ROBOT = "🤖"             # Robot/Bot
    BOT = "🤖"               # Bot
    CROWN = "👑"             # Crown/Premium
    STAR = "⭐"              # Star/Pro
    SMILE = "🙂"             # Smile
    
    # ── Commerce and Money ──────────────────────────────────
    
    MONEY = "💰"             # Money
    COINS = "🪙"            # Coins
    CARD = "💳"              # Credit Card
    CREDIT_CARD = "💳"       # Credit Card (alias)
    BANK = "🏦"              # Bank
    WALLET = "👛"            # Wallet
    RECEIPT = "🧾"           # Receipt/Invoice
    SHOPPING_CART = "🛒"     # Shopping Cart
    SHOPPING_BAGS = "🛍️"   # Shopping Bags
    SHOP = "🛒"              # Shop (alias)
    
    # ── Payment Systems ─────────────────────────────────────
    
    CRYPTOBOT = "💎"         # Crypto Bot
    
    # ── Communication ───────────────────────────────────────
    
    MEGAPHONE = "📣"         # Megaphone/Broadcast
    BELL = "🔔"              # Bell/Notification
    MAIL = "📧"              # Mail/Message
    PHONE = "📱"             # Phone/Contact
    FEEDBACK = "💬"          # Feedback/Chat
    REPLY = "↩️"            # Reply
    FORWARD = "➡️"          # Forward
    
    # ── Content and Items ───────────────────────────────────
    
    BOX = "📦"               # Box/Package
    PACKAGE = "📦"           # Package (alias)
    GIFT = "🎁"              # Gift
    TAG = "🏷️"             # Tag/Label
    DELIVERY = "📦"          # Delivery (alias)
    
    # ── Time and Date ───────────────────────────────────────
    
    CLOCK = "⏰"             # Clock/Time
    CALENDAR = "📅"          # Calendar/Date
    
    # ── Statistics and Analytics ────────────────────────────
    
    STATS = "📊"             # Statistics
    CHART = "📈"             # Chart
    CHART_UP = "📈"          # Chart Up
    CHART_DOWN = "📉"        # Chart Down
    BAR_CHART = "📊"         # Bar Chart
    
    # ── Celebration and Emotions ────────────────────────────
    
    PARTY = "🎉"             # Party/Celebration
    TROPHY = "🏆"            # Trophy/Award
    SPARKLES = "✨"          # Sparkles
    HEART = "❤️"            # Heart
    FIRE = "🔥"              # Fire/Hot
    
    # ── Gaming ──────────────────────────────────────────────
    
    LOLZ = "🎮"              # Gaming
    
    # ── Technology ──────────────────────────────────────────
    
    GLOBE = "🌍"             # Globe/World
    LINK = "🔗"              # Link
    LAPTOP = "💻"            # Laptop
    MAGNIFYING_GLASS = "🔍"  # Search
    MICROSCOPE = "🔬"        # Microscope
    TELESCOPE = "🔭"         # Telescope
    SATELLITE = "📡"         # Satellite
    SUBSCRIBE = "📱"         # Subscribe
    TEST = "🧪"              # Test
    TEST_TUBE = "🧪"         # Test Tube


# ═══════════════════════════════════════════════════════════
# DATABASE MODELS
# ═══════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


class User(Base):
    """
    User model - stores information about registered users
    and their subscription status
    """
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False
    )
    
    username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    balance: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00")
    )
    
    subscription_tier: Mapped[str] = mapped_column(
        String(20),
        default="free"
    )
    
    subscription_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00")
    )
    
    total_purchases: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


class Subscription(Base):
    """
    Subscription model - tracks subscription payments
    """
    
    __tablename__ = "subscriptions"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )


class AdminConfig(Base):
    """
    Admin configuration model - stores global payment settings
    """
    
    __tablename__ = "admin_config"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_terminal_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    pro_subscription_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("100.00")
    )
    
    premium_subscription_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("250.00")
    )


class ShopBot(Base):
    """
    Bot model - can be either 'shop' or 'feedback' type
    """
    
    __tablename__ = "bots"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    bot_token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )
    
    bot_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    bot_type: Mapped[str] = mapped_column(
        String(20),
        default="shop"
    )
    
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    crypto_bot_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    yoomoney_wallet: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_terminal_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_api_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    rollypay_signing_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    welcome_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    support_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    feedback_button_text: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    feedback_button_reply: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


class Category(Base):
    """
    Product category model for shop bots
    """
    
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    bot_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


class Product(Base):
    """
    Product model for shop bots
    """
    
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    category_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    auto_deliver_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=-1
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


class Purchase(Base):
    """
    Purchase model for tracking shop purchases
    """
    
    __tablename__ = "purchases"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    bot_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    product_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending"
    )
    
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    
    payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    
    delivered_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


class FeedbackMessage(Base):
    """
    Feedback message model for feedback bots
    """
    
    __tablename__ = "feedback_messages"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    bot_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    admin_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    
    message_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    reply_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    is_replied: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("NOW()")
    )


# ═══════════════════════════════════════════════════════════
# DATABASE ENGINE AND SESSION FACTORY
# ═══════════════════════════════════════════════════════════

# Create async engine for PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ═══════════════════════════════════════════════════════════
# DATABASE MIGRATIONS
# ═══════════════════════════════════════════════════════════

async def run_migrations():
    """
    Run database migrations to add missing columns.
    This ensures backward compatibility when updating the bot.
    """
    
    logger.info("Running database migrations...")
    
    async with engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        
        def get_columns(connection, table_name):
            """
            Get list of column names for a given table.
            Returns empty list if table doesn't exist.
            """
            inspector = inspect(connection)
            try:
                return [
                    col["name"]
                    for col in inspector.get_columns(table_name)
                ]
            except Exception:
                return []
        
        # ── Migrate bots table ──────────────────────────────
        
        bots_columns = await conn.run_sync(
            lambda c: get_columns(c, "bots")
        )
        
        bot_column_definitions = [
            ("rollypay_terminal_id", "VARCHAR(255)"),
            ("rollypay_api_key", "VARCHAR(255)"),
            ("rollypay_signing_secret", "VARCHAR(255)"),
            ("welcome_message", "TEXT"),
            ("support_username", "VARCHAR(255)"),
            ("bot_type", "VARCHAR(20) DEFAULT 'shop'"),
            ("feedback_button_text", "VARCHAR(255)"),
            ("feedback_button_reply", "TEXT"),
        ]
        
        for col_name, col_type in bot_column_definitions:
            if col_name not in bots_columns:
                logger.info(
                    f"Adding column '{col_name}' to 'bots' table..."
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE bots "
                        f"ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
        
        # ── Migrate products table ──────────────────────────
        
        products_columns = await conn.run_sync(
            lambda c: get_columns(c, "products")
        )
        
        product_column_definitions = [
            ("auto_deliver_text", "TEXT"),
            ("quantity", "INTEGER DEFAULT -1"),
        ]
        
        for col_name, col_type in product_column_definitions:
            if col_name not in products_columns:
                logger.info(
                    f"Adding column '{col_name}' to 'products' table..."
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE products "
                        f"ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
        
        # ── Migrate purchases table ─────────────────────────
        
        purchases_columns = await conn.run_sync(
            lambda c: get_columns(c, "purchases")
        )
        
        purchase_column_definitions = [
            ("payment_id", "VARCHAR(255)"),
            ("delivered_text", "TEXT"),
        ]
        
        for col_name, col_type in purchase_column_definitions:
            if col_name not in purchases_columns:
                logger.info(
                    f"Adding column '{col_name}' to 'purchases' table..."
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE purchases "
                        f"ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
        
        # ── Migrate admin_config table ──────────────────────
        
        admin_columns = await conn.run_sync(
            lambda c: get_columns(c, "admin_config")
        )
        
        admin_column_definitions = [
            ("rollypay_terminal_id", "VARCHAR(255)"),
            ("rollypay_api_key", "VARCHAR(255)"),
            ("rollypay_signing_secret", "VARCHAR(255)"),
        ]
        
        for col_name, col_type in admin_column_definitions:
            if col_name not in admin_columns:
                logger.info(
                    f"Adding column '{col_name}' to 'admin_config' table..."
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE admin_config "
                        f"ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
        
        if "pro_subscription_price" not in admin_columns:
            logger.info(
                "Adding column 'pro_subscription_price' to "
                "'admin_config' table..."
            )
            await conn.execute(
                text(
                    "ALTER TABLE admin_config "
                    "ADD COLUMN IF NOT EXISTS "
                    "pro_subscription_price NUMERIC(10,2) DEFAULT 100.00"
                )
            )
        
        if "premium_subscription_price" not in admin_columns:
            logger.info(
                "Adding column 'premium_subscription_price' to "
                "'admin_config' table..."
            )
            await conn.execute(
                text(
                    "ALTER TABLE admin_config "
                    "ADD COLUMN IF NOT EXISTS "
                    "premium_subscription_price NUMERIC(10,2) DEFAULT 250.00"
                )
            )
        
        # ── Migrate users table ─────────────────────────────
        
        users_columns = await conn.run_sync(
            lambda c: get_columns(c, "users")
        )
        
        users_column_definitions = [
            ("subscription_tier", "VARCHAR(20) DEFAULT 'free'"),
            ("subscription_expires", "TIMESTAMP"),
            ("total_spent", "NUMERIC(12,2) DEFAULT 0.00"),
            ("total_purchases", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_type in users_column_definitions:
            if col_name not in users_columns:
                logger.info(
                    f"Adding column '{col_name}' to 'users' table..."
                )
                await conn.execute(
                    text(
                        f"ALTER TABLE users "
                        f"ADD COLUMN IF NOT EXISTS "
                        f"{col_name} {col_type}"
                    )
                )
    
    logger.info("All database migrations completed successfully!")


# ═══════════════════════════════════════════════════════════
# DATABASE INITIALIZATION
# ═══════════════════════════════════════════════════════════

async def init_db():
    """
    Initialize the database:
    1. Run migrations to ensure all columns exist
    2. Create default admin configuration if not exists
    """
    
    logger.info("Initializing database...")
    
    await run_migrations()
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(AdminConfig).limit(1)
        )
        admin_config = result.scalar_one_or_none()
        
        if not admin_config:
            logger.info("Creating default admin configuration...")
            session.add(AdminConfig())
            await session.commit()
    
    logger.info("Database initialization complete!")


# ═══════════════════════════════════════════════════════════
# DATABASE HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None
) -> User:
    """
    Get existing user from database or create a new one.
    
    Args:
        session: Database session
        telegram_id: User's Telegram ID
        username: User's Telegram username (optional)
    
    Returns:
        User object
    """
    
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.info(f"Creating new user: telegram_id={telegram_id}")
        user = User(
            telegram_id=telegram_id,
            username=username
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def get_admin_config(session: AsyncSession) -> AdminConfig:
    """
    Get or create admin configuration.
    
    Args:
        session: Database session
    
    Returns:
        AdminConfig object
    """
    
    result = await session.execute(
        select(AdminConfig).limit(1)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        config = AdminConfig()
        session.add(config)
        await session.commit()
        await session.refresh(config)
    
    return config


async def check_subscription(
    session: AsyncSession,
    user_id: int
) -> User:
    """
    Check if user's subscription is still valid.
    If expired, reset to free tier.
    
    Args:
        session: Database session
        user_id: User's Telegram ID
    
    Returns:
        User object with updated subscription status
    """
    
    user = await get_or_create_user(session, user_id, None)
    
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    if tier != "free":
        expires = getattr(user, 'subscription_expires', None)
        if expires and expires < datetime.utcnow():
            logger.info(
                f"Subscription expired for user {user_id}. "
                f"Resetting to free tier."
            )
            user.subscription_tier = "free"
            user.subscription_expires = None
            await session.commit()
    
    return user


async def can_create_bot(
    session: AsyncSession,
    user_id: int
) -> tuple[bool, str]:
    """
    Check if user can create more bots based on their subscription tier.
    
    Args:
        session: Database session
        user_id: User's Telegram ID
    
    Returns:
        Tuple of (can_create: bool, error_message: str)
    """
    
    user = await check_subscription(session, user_id)
    
    bots_count = await session.scalar(
        select(func.count(ShopBot.id)).where(
            ShopBot.owner_id == user_id
        )
    )
    
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    limits = {
        "free": 1,
        "pro": 5,
        "premium": 30
    }
    
    max_bots = limits.get(tier, 1)
    
    if bots_count >= max_bots:
        return False, (
            f"Достигнут лимит ботов ({max_bots}) "
            f"для тарифа {tier}. Повысьте тариф!"
        )
    
    return True, ""


# ═══════════════════════════════════════════════════════════
# PAYMENT API CLASSES
# ═══════════════════════════════════════════════════════════

class CryptoBotAPI:
    """
    Crypto Bot payment API integration.
    Uses Crypto Pay API for creating and checking invoices.
    """
    
    BASE_URL = "https://pay.crypt.bot/api"
    
    def __init__(self, token: str):
        """
        Initialize CryptoBot API with token.
        
        Args:
            token: Crypto Bot API token from @CryptoBot
        """
        self.token = token
    
    async def _request(
        self,
        method: str,
        **kwargs
    ) -> Optional[dict]:
        """
        Make a request to the Crypto Bot API.
        
        Args:
            method: API method name
            **kwargs: Additional parameters for the request
        
        Returns:
            API response data or None on error
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/{method}",
                    headers={
                        "Crypto-Pay-API-Token": self.token
                    },
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
    
    async def create_invoice(
        self,
        amount: float,
        description: str,
        payload: str
    ) -> Optional[dict]:
        """
        Create a payment invoice.
        
        Args:
            amount: Payment amount in RUB
            description: Invoice description
            payload: Custom payload for the invoice
        
        Returns:
            Invoice data or None on error
        """
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
    
    async def check_invoice(
        self,
        invoice_id: int
    ) -> Optional[str]:
        """
        Check the status of an invoice.
        
        Args:
            invoice_id: ID of the invoice to check
        
        Returns:
            Invoice status ("paid", "active", etc.) or None on error
        """
        result = await self._request(
            "getInvoices",
            invoice_ids=[invoice_id]
        )
        
        if result and result.get("items"):
            return result["items"][0].get("status")
        
        return None


class YooMoneyAPI:
    """
    YooMoney payment API integration.
    Generates payment form URLs for YooMoney payments.
    """
    
    def __init__(self, wallet: str):
        """
        Initialize YooMoney API with wallet number.
        
        Args:
            wallet: YooMoney wallet number
        """
        self.wallet = wallet
    
    def generate_form_url(
        self,
        amount: float,
        label: str,
        comment: str
    ) -> str:
        """
        Generate a YooMoney payment form URL.
        
        Args:
            amount: Payment amount in RUB
            label: Payment label/identifier
            comment: Payment comment/description
        
        Returns:
            URL for the YooMoney payment form
        """
        return (
            f"https://yoomoney.ru/quickpay/confirm.xml?"
            f"receiver={self.wallet}"
            f"&quickpay-form=button"
            f"&targets={quote(comment)}"
            f"&sum={amount}"
            f"&label={label}"
            f"&successURL="
        )


class RollyPayAPI:
    """
    RollyPay payment API integration.
    Supports SBP (Fast Payment System) payments.
    """
    
    BASE_URL = "https://rollypay.io/api/v1"
    
    def __init__(
        self,
        terminal_id: str,
        api_key: str,
        signing_secret: str = ""
    ):
        """
        Initialize RollyPay API.
        
        Args:
            terminal_id: Terminal ID from RollyPay
            api_key: API key from RollyPay
            signing_secret: Signing secret from RollyPay
        """
        self.terminal_id = terminal_id
        self.api_key = api_key
        self.signing_secret = signing_secret
    
    async def create_payment(
        self,
        amount: float,
        order_id: str,
        description: str
    ) -> Optional[dict]:
        """
        Create a payment.
        
        Args:
            amount: Payment amount in RUB
            order_id: Unique order identifier
            description: Payment description
        
        Returns:
            Payment data or None on error
        """
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
    
    async def check_payment(
        self,
        payment_id: str
    ) -> Optional[dict]:
        """
        Check the status of a payment.
        
        Args:
            payment_id: ID of the payment to check
        
        Returns:
            Payment status data or None on error
        """
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
# PAYMENT CONFIGURATION HELPERS
# ═══════════════════════════════════════════════════════════

def is_rollypay_configured(bot: ShopBot) -> bool:
    """
    Check if RollyPay is fully configured for a bot.
    All three fields must be set: terminal_id, api_key, signing_secret.
    
    Args:
        bot: ShopBot object to check
    
    Returns:
        True if RollyPay is fully configured, False otherwise
    """
    return bool(
        bot.rollypay_terminal_id
        and bot.rollypay_api_key
        and bot.rollypay_signing_secret
    )


def is_rollypay_admin_configured(config: AdminConfig) -> bool:
    """
    Check if RollyPay is fully configured in admin panel.
    
    Args:
        config: AdminConfig object to check
    
    Returns:
        True if RollyPay is fully configured, False otherwise
    """
    return bool(
        config.rollypay_terminal_id
        and config.rollypay_api_key
        and config.rollypay_signing_secret
    )


# ═══════════════════════════════════════════════════════════
# KEYBOARD BUILDERS
# ═══════════════════════════════════════════════════════════

def main_menu_kb() -> ReplyKeyboardMarkup:
    """
    Main menu keyboard for the constructor bot.
    
    Returns:
        ReplyKeyboardMarkup with main menu buttons
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=f"{Emoji.TOOLS} Создать бота"
                ),
                KeyboardButton(
                    text=f"{Emoji.LIST} Мои боты"
                )
            ],
            [
                KeyboardButton(
                    text=f"{Emoji.CROWN} Подписка"
                ),
                KeyboardButton(
                    text=f"{Emoji.PROFILE} Профиль"
                )
            ],
        ],
        resize_keyboard=True
    )


def shop_menu_kb() -> ReplyKeyboardMarkup:
    """
    Menu keyboard for shop-type child bots.
    
    Returns:
        ReplyKeyboardMarkup with shop menu buttons
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=f"{Emoji.SHOPPING_CART} Купить донат"
                ),
                KeyboardButton(
                    text=f"{Emoji.PACKAGE} Мои покупки"
                )
            ],
            [
                KeyboardButton(
                    text=f"{Emoji.PROFILE} Профиль"
                ),
                KeyboardButton(
                    text=f"{Emoji.PHONE} Поддержка"
                )
            ],
        ],
        resize_keyboard=True
    )


def feedback_menu_kb(bot: ShopBot) -> ReplyKeyboardMarkup:
    """
    Menu keyboard for feedback-type child bots.
    Includes optional feedback button if configured.
    
    Args:
        bot: ShopBot object with feedback settings
    
    Returns:
        ReplyKeyboardMarkup with feedback menu buttons
    """
    keyboard = []
    
    if bot.support_username:
        keyboard.append([
            KeyboardButton(
                text=f"{Emoji.PHONE} Поддержка"
            )
        ])
    
    keyboard.append([
        KeyboardButton(
            text=f"{Emoji.PROFILE} Профиль"
        )
    ])
    
    if bot.feedback_button_text:
        keyboard.append([
            KeyboardButton(
                text=bot.feedback_button_text
            )
        ])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


def bot_management_kb(
    bot_id: int,
    is_active: bool = True,
    bot_type: str = "shop"
) -> InlineKeyboardMarkup:
    """
    Bot management inline keyboard.
    Different options for shop and feedback bots.
    
    Args:
        bot_id: ID of the bot
        is_active: Whether the bot is currently active
        bot_type: Type of bot ("shop" or "feedback")
    
    Returns:
        InlineKeyboardMarkup with management buttons
    """
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot_type == "shop":
        # Shop bot management options
        kb.inline_keyboard.extend([
            [
                InlineKeyboardButton(
                    text=f"{Emoji.PACKAGE} Категории",
                    callback_data=f"manage_cats:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BOX} Товары",
                    callback_data=f"manage_products:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CREDIT_CARD} Платежи",
                    callback_data=f"payment_settings:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CHART} Статистика",
                    callback_data=f"bot_stats:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.MEGAPHONE} Рассылка",
                    callback_data=f"bot_broadcast:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.USERS} Покупатели",
                    callback_data=f"bot_buyers:{bot_id}"
                )
            ],
        ])
    else:
        # Feedback bot management options
        kb.inline_keyboard.extend([
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CHART} Статистика",
                    callback_data=f"bot_stats:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.MAIL} Сообщения",
                    callback_data=f"feedback_messages:{bot_id}"
                )
            ],
        ])
    
    # Common management options
    toggle_text = (
        f"{Emoji.LOCK} Остановить"
        if is_active
        else f"{Emoji.UNLOCK} Запустить"
    )
    
    kb.inline_keyboard.extend([
        [
            InlineKeyboardButton(
                text=f"{Emoji.GEAR} Настройки",
                callback_data=f"bot_settings:{bot_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=toggle_text,
                callback_data=f"toggle_bot:{bot_id}"
            ),
            InlineKeyboardButton(
                text=f"{Emoji.TRASH} Удалить",
                callback_data=f"delete_bot:{bot_id}"
            ),
        ],
    ])
    
    return kb


def cancel_kb() -> ReplyKeyboardMarkup:
    """
    Cancel button for FSM states.
    
    Returns:
        ReplyKeyboardMarkup with cancel button
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"{Emoji.CROSS} Отмена")]
        ],
        resize_keyboard=True
    )


def back_kb(bot_id: int) -> InlineKeyboardMarkup:
    """
    Back button to return to bot management.
    
    Args:
        bot_id: ID of the bot
    
    Returns:
        InlineKeyboardMarkup with back button
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BACK} Назад к управлению",
                    callback_data=f"back_to_bot:{bot_id}"
                )
            ]
        ]
    )


def inline_kb(
    buttons: list[tuple[str, str]]
) -> InlineKeyboardMarkup:
    """
    Create an inline keyboard from a list of (text, callback_data) tuples.
    
    Args:
        buttons: List of (text, callback_data) tuples
    
    Returns:
        InlineKeyboardMarkup with one button per row
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data)]
            for text, data in buttons
        ]
    )


def tier_kb() -> InlineKeyboardMarkup:
    """
    Subscription tier selection keyboard.
    
    Returns:
        InlineKeyboardMarkup with tier options
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.STAR} PRO — 100₽/мес (5 ботов)",
                    callback_data="sub_tier:pro"
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        f"{Emoji.CROWN} PREMIUM — "
                        f"250₽/мес (30 ботов)"
                    ),
                    callback_data="sub_tier:premium"
                )
            ],
        ]
    )


def payment_method_sub_kb(tier: str) -> InlineKeyboardMarkup:
    """
    Payment method selection keyboard for subscriptions.
    
    Args:
        tier: Subscription tier ("pro" or "premium")
    
    Returns:
        InlineKeyboardMarkup with payment method options
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CRYPTOBOT} Crypto Bot",
                    callback_data=f"sub_pay:{tier}:crypto"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CARD} ЮMoney",
                    callback_data=f"sub_pay:{tier}:yoomoney"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.COINS} RollyPay",
                    callback_data=f"sub_pay:{tier}:rollypay"
                )
            ],
        ]
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    """
    Admin panel main keyboard.
    
    Returns:
        InlineKeyboardMarkup with admin options
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CRYPTOBOT} Crypto Bot",
                    callback_data="admin_crypto"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CARD} ЮMoney",
                    callback_data="admin_yoomoney"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.COINS} RollyPay",
                    callback_data="admin_rollypay"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.TAG} Цены подписки",
                    callback_data="admin_prices"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CHART} Статистика",
                    callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.MEGAPHONE} Рассылка всем",
                    callback_data="admin_broadcast"
                )
            ],
        ]
    )


def payment_method_kb(
    product_id: int,
    bot: ShopBot
) -> InlineKeyboardMarkup:
    """
    Payment method selection keyboard for a product.
    Only shows methods that are configured for the bot.
    
    Args:
        product_id: ID of the product
        bot: ShopBot object with payment configuration
    
    Returns:
        InlineKeyboardMarkup with available payment methods
    """
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if bot.crypto_bot_token:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{Emoji.CRYPTOBOT} Crypto Bot",
                callback_data=f"pay_crypto:{product_id}"
            )
        ])
    
    if bot.yoomoney_wallet:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{Emoji.CARD} ЮMoney",
                callback_data=f"pay_yoo:{product_id}"
            )
        ])
    
    if is_rollypay_configured(bot):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{Emoji.COINS} RollyPay",
                callback_data=f"pay_rolly:{product_id}"
            )
        ])
    
    return kb


def payment_invoice_kb(
    pay_url: str,
    method: str,
    payment_id: str
) -> InlineKeyboardMarkup:
    """
    Payment invoice keyboard with pay and check buttons.
    
    Args:
        pay_url: URL for payment
        method: Payment method name
        payment_id: ID of the payment
    
    Returns:
        InlineKeyboardMarkup with pay and check buttons
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CARD} Оплатить",
                    url=pay_url
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.LOADING} Проверить оплату",
                    callback_data=f"check_pay:{method}:{payment_id}"
                )
            ],
        ]
    )


def payment_settings_menu_kb(bot_id: int) -> InlineKeyboardMarkup:
    """
    Payment settings menu keyboard with channel link for instructions.
    
    Args:
        bot_id: ID of the bot
    
    Returns:
        InlineKeyboardMarkup with payment settings options
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CRYPTOBOT} Crypto Bot",
                    callback_data=f"edit_crypto:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CARD} ЮMoney",
                    callback_data=f"edit_yoo:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.COINS} RollyPay (3 токена)",
                    callback_data=f"edit_rolly_bot:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.TEST} Тестовая оплата",
                    callback_data=f"test_payment:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        f"{Emoji.CHANNEL} Инструкции: "
                        f"{CHANNEL_USERNAME}"
                    ),
                    url=CHANNEL_URL
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BACK} Назад",
                    callback_data=f"back_to_bot:{bot_id}"
                )
            ],
        ]
    )


def bot_settings_kb(
    bot_id: int,
    bot_type: str = "shop"
) -> InlineKeyboardMarkup:
    """
    Bot settings keyboard.
    Different options for shop and feedback bots.
    
    Args:
        bot_id: ID of the bot
        bot_type: Type of bot ("shop" or "feedback")
    
    Returns:
        InlineKeyboardMarkup with settings options
    """
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.PENCIL} Приветствие",
                    callback_data=f"edit_welcome:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.PHONE} Поддержка",
                    callback_data=f"edit_support:{bot_id}"
                )
            ],
        ]
    )
    
    if bot_type == "feedback":
        kb.inline_keyboard.insert(
            1,
            [
                InlineKeyboardButton(
                    text=f"{Emoji.KEY} Кнопка обратной связи",
                    callback_data=f"edit_feedback_button:{bot_id}"
                )
            ]
        )
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"{Emoji.BACK} Назад",
            callback_data=f"back_to_bot:{bot_id}"
        )
    ])
    
    return kb


# ═══════════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════════

class CreateBotFSM(StatesGroup):
    """States for the bot creation wizard"""
    bot_type = State()       # Choose bot type (shop/feedback)
    token = State()           # Enter bot token
    name = State()            # Enter bot name
    admin_id = State()        # Enter admin Telegram ID
    crypto_token = State()    # Enter CryptoBot token (shop only)
    yoomoney_wallet = State() # Enter YooMoney wallet (shop only)


class PaymentSettingsFSM(StatesGroup):
    """States for editing payment settings"""
    crypto_token = State()    # Edit CryptoBot token
    yoomoney_wallet = State() # Edit YooMoney wallet


class AddCategoryFSM(StatesGroup):
    """States for adding a new category"""
    bot_id = State()          # Bot ID
    name = State()            # Category name


class AddProductFSM(StatesGroup):
    """States for adding a new product"""
    bot_id = State()          # Bot ID
    category = State()        # Selected category
    name = State()            # Product name
    description = State()     # Product description
    price = State()           # Product price
    auto_deliver = State()    # Auto-delivery text


class DeleteProductFSM(StatesGroup):
    """States for deleting a product"""
    bot_id = State()          # Bot ID
    category = State()        # Selected category
    product = State()         # Selected product


class EditDeliverFSM(StatesGroup):
    """States for editing delivery text"""
    product_id = State()      # Product ID
    text = State()            # New delivery text


class BroadcastFSM(StatesGroup):
    """States for sending broadcast messages"""
    bot_id = State()          # Bot ID
    message_text = State()    # Broadcast message text


class AdminFSM(StatesGroup):
    """States for admin settings"""
    setting_type = State()    # Type of setting (crypto/yoomoney)
    value = State()           # Setting value


class AdminBroadcastFSM(StatesGroup):
    """States for admin broadcast"""
    message_text = State()    # Broadcast message text


class AdminPricesFSM(StatesGroup):
    """States for editing subscription prices"""
    price_type = State()      # PRO or PREMIUM
    value = State()           # New price value


class AdminRollyPayFSM(StatesGroup):
    """States for admin RollyPay setup"""
    setting_type = State()    # Current setting step
    value = State()           # Setting value


class BotRollyPayFSM(StatesGroup):
    """States for bot RollyPay setup"""
    bot_id = State()          # Bot ID
    terminal_id = State()     # Terminal ID
    api_key = State()         # API Key
    signing_secret = State()  # Signing Secret


class BotSettingsFSM(StatesGroup):
    """States for bot general settings"""
    bot_id = State()          # Bot ID
    welcome_message = State() # Welcome message
    support_username = State()# Support username


class FeedbackButtonFSM(StatesGroup):
    """States for feedback button settings"""
    bot_id = State()          # Bot ID
    button_text = State()     # Button text
    button_reply = State()    # Button reply text


class ReplyFeedbackFSM(StatesGroup):
    """States for replying to feedback messages"""
    message_id = State()      # Message ID to reply to
    reply_text = State()      # Reply text
    bot_token = State()       # Bot token for sending reply


# ═══════════════════════════════════════════════════════════
# CONSTRUCTOR BOT ROUTER - COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════

constructor_router = Router()


# ── /start Command Handler ──────────────────────────────────

@constructor_router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handle /start command.
    Shows welcome message with available features and tariffs.
    """
    try:
        async with async_session_maker() as session:
            await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username
            )
        
        welcome_text = (
            f"{Emoji.ROBOT} Добро пожаловать в конструктор ботов!\n\n"
            f"• Создайте магазин доната для игр Supercell\n"
            f"• Создайте бота обратной связи\n"
            f"• Принимайте платежи через CryptoBot, ЮMoney, RollyPay\n"
            f"• Настраивайте автоматическую выдачу товаров\n\n"
            f"{Emoji.CHANNEL} Инструкции: {CHANNEL_USERNAME}\n\n"
            f"{Emoji.CROWN} <b>Тарифы:</b>\n"
            f"👤 Бесплатный — 1 бот (навсегда)\n"
            f"{Emoji.STAR} PRO — 5 ботов, 100₽/мес\n"
            f"{Emoji.CROWN} PREMIUM — 30 ботов, 250₽/мес"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=main_menu_kb()
        )
    
    except Exception as e:
        logger.error(f"Error in cmd_start handler: {e}")
        try:
            await message.answer(
                "Добро пожаловать в конструктор ботов!\n\n"
                "• Создайте магазин доната\n"
                "• Создайте бота обратной связи\n"
                "• Принимайте платежи\n\n"
                "Тарифы:\n"
                "Бесплатный — 1 бот\n"
                "PRO — 5 ботов\n"
                "PREMIUM — 30 ботов",
                reply_markup=main_menu_kb()
            )
        except Exception:
            await message.answer(
                "Ошибка при запуске. Попробуйте позже."
            )


# ── /admin Command Handler ──────────────────────────────────

@constructor_router.message(Command("admin"))
async def admin_cmd(message: Message):
    """
    Handle /admin command.
    Shows admin panel with global settings.
    """
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer(
            f"{Emoji.CROSS} У вас нет доступа к админ-панели."
        )
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    crypto_status = "✅" if config.crypto_bot_token else "❌"
    yoo_status = "✅" if config.yoomoney_wallet else "❌"
    rolly_status = (
        "✅" if is_rollypay_admin_configured(config) else "❌"
    )
    
    admin_text = (
        f"{Emoji.GEAR} <b>Админ-панель</b>\n\n"
        f"{Emoji.CRYPTOBOT} Crypto Bot: {crypto_status}\n"
        f"{Emoji.CARD} ЮMoney: {yoo_status}\n"
        f"{Emoji.COINS} RollyPay: {rolly_status}\n"
        f"{Emoji.TAG} PRO: {config.pro_subscription_price}руб | "
        f"PREMIUM: {config.premium_subscription_price}руб\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(admin_text, reply_markup=admin_menu_kb())


# ── Profile Button Handler ──────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.PROFILE} Профиль")
async def profile(message: Message):
    """
    Show user profile with statistics.
    """
    async with async_session_maker() as session:
        user = await check_subscription(
            session, message.from_user.id
        )
        
        bots_count = await session.scalar(
            select(func.count(ShopBot.id)).where(
                ShopBot.owner_id == message.from_user.id
            )
        )
        
        total_spent = (
            getattr(user, 'total_spent', Decimal("0.00"))
            or Decimal("0.00")
        )
        
        total_purchases = (
            getattr(user, 'total_purchases', 0) or 0
        )
    
    tier_display = {
        "free": "👤 Бесплатный",
        "pro": f"{Emoji.STAR} PRO",
        "premium": f"{Emoji.CROWN} PREMIUM"
    }
    
    limits = {
        "free": "1 бот",
        "pro": "5 ботов",
        "premium": "30 ботов"
    }
    
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free":
        expires = getattr(user, 'subscription_expires', None)
        if expires:
            days_left = (expires - datetime.utcnow()).days
            expiry = (
                f"\n{Emoji.CLOCK} Действует ещё {days_left} дн. "
                f"(до {expires.strftime('%d.%m.%Y')})"
            )
    
    profile_text = (
        f"{Emoji.PROFILE} <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📛 Username: @{message.from_user.username or '—'}\n"
        f"💎 Тариф: {tier_display.get(tier, 'Бесплатный')}"
        f"{expiry}\n"
        f"{Emoji.ROBOT} Лимит ботов: "
        f"{limits.get(tier, '1 бот')}\n"
        f"{Emoji.LIST} Ботов создано: {bots_count}\n"
        f"{Emoji.COINS} Баланс: {user.balance}руб\n"
        f"{Emoji.SHOPPING_CART} Всего покупок: {total_purchases}\n"
        f"{Emoji.MONEY} Потрачено всего: {total_spent}руб"
    )
    
    await message.answer(profile_text)


# ── Subscription Button Handler ─────────────────────────────

@constructor_router.message(F.text == f"{Emoji.CROWN} Подписка")
async def subscription_menu(message: Message):
    """
    Show subscription options and current tier.
    """
    async with async_session_maker() as session:
        user = await check_subscription(
            session, message.from_user.id
        )
        config = await get_admin_config(session)
    
    tier_display = {
        "free": "👤 Бесплатный",
        "pro": f"{Emoji.STAR} PRO",
        "premium": f"{Emoji.CROWN} PREMIUM"
    }
    
    tier = getattr(user, 'subscription_tier', 'free') or 'free'
    
    expiry = ""
    if tier != "free":
        expires = getattr(user, 'subscription_expires', None)
        if expires:
            days_left = (expires - datetime.utcnow()).days
            expiry = f"\n{Emoji.CLOCK} Осталось: {days_left} дн."
    
    sub_text = (
        f"{Emoji.CROWN} <b>Подписка</b>\n\n"
        f"Ваш тариф: {tier_display.get(tier)}{expiry}\n\n"
        f"<b>Доступные тарифы:</b>\n"
        f"👤 Бесплатный — 1 бот (навсегда)\n"
        f"{Emoji.STAR} PRO — 5 ботов, "
        f"{config.pro_subscription_price}руб/мес\n"
        f"{Emoji.CROWN} PREMIUM — 30 ботов, "
        f"{config.premium_subscription_price}руб/мес\n\n"
        f"<b>Выберите тариф для покупки:</b>"
    )
    
    await message.answer(sub_text, reply_markup=tier_kb())


# ── Subscription Tier Selection ─────────────────────────────

@constructor_router.callback_query(F.data.startswith("sub_tier:"))
async def sub_tier_select(callback: CallbackQuery):
    """
    Handle tier selection - show payment methods.
    """
    tier = callback.data.split(":")[1]
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    prices = {
        "pro": config.pro_subscription_price,
        "premium": config.premium_subscription_price
    }
    
    names = {
        "pro": f"{Emoji.STAR} PRO",
        "premium": f"{Emoji.CROWN} PREMIUM"
    }
    
    await callback.message.edit_text(
        f"{names.get(tier)} — {prices.get(tier)}руб/мес\n\n"
        f"<b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_sub_kb(tier)
    )
    await callback.answer()


# ── Subscription Payment Processing ─────────────────────────

@constructor_router.callback_query(F.data.startswith("sub_pay:"))
async def sub_payment_process(callback: CallbackQuery):
    """
    Process subscription payment with selected method.
    """
    parts = callback.data.split(":")
    tier = parts[1]
    method = parts[2]
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
    
    prices = {
        "pro": admin_config.pro_subscription_price,
        "premium": admin_config.premium_subscription_price
    }
    amount = prices.get(tier, Decimal("100.00"))
    
    # Validate payment method configuration
    if method == "crypto" and not admin_config.crypto_bot_token:
        return await callback.answer(
            f"{Emoji.CROSS} Crypto Bot не настроен!",
            show_alert=True
        )
    
    if method == "yoomoney" and not admin_config.yoomoney_wallet:
        return await callback.answer(
            f"{Emoji.CROSS} ЮMoney не настроен!",
            show_alert=True
        )
    
    if (
        method == "rollypay"
        and not is_rollypay_admin_configured(admin_config)
    ):
        return await callback.answer(
            f"{Emoji.CROSS} RollyPay не настроен!",
            show_alert=True
        )
    
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
                pay_url = (
                    invoice.get("pay_url")
                    or invoice.get("bot_invoice_url", "")
                )
                payment_id = str(
                    invoice.get("invoice_id", sub.id)
                )
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer(
                    f"{Emoji.CROSS} Ошибка создания счёта!",
                    show_alert=True
                )
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
                payment_id = result.get(
                    "payment_id", f"sub_{sub.id}"
                )
                sub.payment_id = payment_id
                await session.commit()
            else:
                await callback.answer(
                    f"{Emoji.CROSS} Ошибка создания платежа!",
                    show_alert=True
                )
                return
    
    if pay_url:
        names = {
            "pro": f"{Emoji.STAR} PRO",
            "premium": f"{Emoji.CROWN} PREMIUM"
        }
        
        await callback.message.edit_text(
            f"{Emoji.CARD} <b>Оплата {names.get(tier)}</b>\n\n"
            f"{Emoji.MONEY} Сумма: {amount} руб\n"
            f"{Emoji.CALENDAR} Срок: 1 месяц\n"
            f"🆔 ID платежа: <code>{sub.id}</code>\n\n"
            f"Нажмите «Оплатить» для перехода к оплате.",
            reply_markup=payment_invoice_kb(
                pay_url, method, payment_id
            )
        )
    
    await callback.answer()


# ── Payment Status Check ────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("check_pay:"))
async def check_payment_status(callback: CallbackQuery):
    """
    Check payment status for subscriptions.
    """
    parts = callback.data.split(":")
    method = parts[1]
    payment_id = parts[2]
    
    await callback.answer(f"{Emoji.LOADING} Проверяю оплату...")
    
    is_paid = False
    
    async with async_session_maker() as session:
        admin_config = await get_admin_config(session)
        
        # Find subscription
        result = await session.execute(
            select(Subscription).where(
                (Subscription.payment_id == payment_id)
                | (
                    Subscription.id == int(payment_id)
                    if payment_id.isdigit()
                    else False
                )
                | (
                    Subscription.payment_method.contains(
                        payment_id
                    )
                )
            )
        )
        sub = result.scalar_one_or_none()
        
        # Already completed
        if sub and sub.status == "completed":
            is_paid = True
        
        # Check via CryptoBot API
        elif method == "crypto" and admin_config.crypto_bot_token:
            invoice_id = None
            if payment_id.isdigit():
                invoice_id = int(payment_id)
            elif (
                sub
                and sub.payment_id
                and sub.payment_id.isdigit()
            ):
                invoice_id = int(sub.payment_id)
            
            if invoice_id:
                api = CryptoBotAPI(admin_config.crypto_bot_token)
                status = await api.check_invoice(invoice_id)
                if status == "paid":
                    is_paid = True
        
        # Check via RollyPay API
        elif (
            method == "rollypay"
            and is_rollypay_admin_configured(admin_config)
        ):
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
        
        # Confirm payment if paid
        if is_paid and sub and sub.status != "completed":
            sub.status = "completed"
            
            user = await get_or_create_user(
                session, sub.user_id, None
            )
            user.subscription_tier = sub.tier
            user.subscription_expires = sub.expires_at
            
            await session.commit()
            
            names = {
                "pro": f"{Emoji.STAR} PRO",
                "premium": f"{Emoji.CROWN} PREMIUM"
            }
            
            success_text = (
                f"{Emoji.CHECK} {Emoji.PARTY} "
                f"<b>Оплата подтверждена!</b>\n\n"
                f"{Emoji.PARTY} Тариф "
                f"{names.get(sub.tier, sub.tier)} активирован!\n"
                f"{Emoji.CALENDAR} Действует до: "
                f"{sub.expires_at.strftime('%d.%m.%Y')}"
            )
            
            await callback.message.answer(success_text)
        
        elif is_paid and sub:
            await callback.message.answer(
                f"{Emoji.CHECK} Оплата уже была подтверждена ранее."
            )
        else:
            await callback.message.answer(
                f"{Emoji.CLOCK} <b>Оплата ещё не поступила.</b>\n\n"
                f"Попробуйте позже или обратитесь в поддержку."
            )


# ── Create Bot Wizard - Step 1: Choose Type ─────────────────

@constructor_router.message(F.text == f"{Emoji.TOOLS} Создать бота")
async def create_bot_start(message: Message, state: FSMContext):
    """
    Start bot creation wizard.
    First step: choose bot type (shop or feedback).
    """
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(
            session, message.from_user.id
        )
        if not can_create:
            return await message.answer(
                f"{Emoji.CROSS} {error_msg}"
            )
    
    await state.set_state(CreateBotFSM.bot_type)
    
    type_text = (
        f"{Emoji.ROBOT} <b>Выберите тип бота:</b>\n\n"
        f"{Emoji.SHOPPING_CART} <b>Донат магазин</b> — "
        f"продажа доната с приёмом платежей\n"
        f"{Emoji.FEEDBACK} <b>Обратная связь</b> — "
        f"бот для приёма сообщений от пользователей"
    )
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        f"{Emoji.SHOPPING_CART} "
                        f"Донат магазин"
                    ),
                    callback_data="bot_type:shop"
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        f"{Emoji.FEEDBACK} "
                        f"Обратная связь"
                    ),
                    callback_data="bot_type:feedback"
                )
            ],
        ]
    )
    
    await message.answer(type_text, reply_markup=kb)


# ── Create Bot Wizard - Bot Type Selected ───────────────────

@constructor_router.callback_query(
    StateFilter(CreateBotFSM.bot_type),
    F.data.startswith("bot_type:")
)
async def create_bot_type_selected(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Handle bot type selection and proceed to token input.
    """
    bot_type = callback.data.split(":")[1]
    await state.update_data(bot_type=bot_type)
    await state.set_state(CreateBotFSM.token)
    
    total_steps = "5" if bot_type == "shop" else "3"
    
    step_text = (
        f"{Emoji.ROBOT} <b>Шаг 1/{total_steps}</b> — "
        f"Введите токен бота.\n"
        f"Получите его у @BotFather командой /newbot\n\n"
        f"Формат: <code>123456:ABC-DEF1234ghikl</code>"
    )
    
    await callback.message.answer(
        step_text, reply_markup=cancel_kb()
    )
    await callback.answer()


# ── Create Bot Wizard - Step 2: Token ───────────────────────

@constructor_router.message(StateFilter(CreateBotFSM.token))
async def create_bot_token(message: Message, state: FSMContext):
    """
    Handle bot token input and validation.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    token = message.text.strip()
    
    if not token or ":" not in token:
        return await message.answer(
            f"{Emoji.CROSS} Некорректный токен. "
            f"Должен быть вида: 123456:ABC-DEF"
        )
    
    # Check if token already exists
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(ShopBot.bot_token == token)
        )
        if result.scalar_one_or_none():
            return await message.answer(
                f"{Emoji.CROSS} Бот с таким токеном "
                f"уже существует в системе."
            )
    
    await state.update_data(token=token)
    await state.set_state(CreateBotFSM.name)
    
    await message.answer(
        f"{Emoji.CHECK} Токен принят.\n\n"
        f"{Emoji.PENCIL} <b>Шаг 2</b> — "
        f"Введите название бота:\n"
        f"Например: «Донат Brawl Stars 24/7»"
    )


# ── Create Bot Wizard - Step 3: Name ────────────────────────

@constructor_router.message(StateFilter(CreateBotFSM.name))
async def create_bot_name(message: Message, state: FSMContext):
    """
    Handle bot name input.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    name = message.text.strip()
    
    if not name or len(name) > 255:
        return await message.answer(
            f"{Emoji.CROSS} Название должно быть "
            f"от 1 до 255 символов."
        )
    
    await state.update_data(name=name)
    await state.set_state(CreateBotFSM.admin_id)
    
    await message.answer(
        f"{Emoji.CHECK} Название принято.\n\n"
        f"{Emoji.USERS} <b>Шаг 3</b> — "
        f"Введите Telegram ID администратора:\n"
        f"Этот пользователь будет управлять ботом.\n"
        f"Получить ID: @getmyid_bot"
    )


# ── Create Bot Wizard - Step 4: Admin ID ────────────────────

@constructor_router.message(StateFilter(CreateBotFSM.admin_id))
async def create_bot_admin(message: Message, state: FSMContext):
    """
    Handle admin ID input.
    For feedback bots, this is the last step.
    For shop bots, proceed to payment setup.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0:
            raise ValueError
    except ValueError:
        return await message.answer(
            f"{Emoji.CROSS} Введите корректный числовой "
            f"Telegram ID."
        )
    
    await state.update_data(admin_id=admin_id)
    
    data = await state.get_data()
    
    if data.get("bot_type") == "feedback":
        # Feedback bots don't need payment setup
        await finish_bot_creation(message, state)
    else:
        # Shop bots need payment tokens
        await state.set_state(CreateBotFSM.crypto_token)
        await message.answer(
            f"{Emoji.CHECK} Admin ID принят.\n\n"
            f"{Emoji.CRYPTOBOT} <b>Шаг 4/5</b> — "
            f"Введите токен Crypto Bot (от @CryptoBot):\n"
            f"Или отправьте <b>-</b> чтобы пропустить."
        )


# ── Create Bot Wizard - Step 5a: CryptoBot Token ────────────

@constructor_router.message(StateFilter(CreateBotFSM.crypto_token))
async def create_bot_crypto(message: Message, state: FSMContext):
    """
    Handle CryptoBot token input (shop bots only).
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    crypto = message.text.strip()
    crypto_token = None if crypto == "-" else crypto
    
    await state.update_data(crypto_token=crypto_token)
    await state.set_state(CreateBotFSM.yoomoney_wallet)
    
    await message.answer(
        f"{Emoji.WALLET} <b>Шаг 5/5</b> — "
        f"Введите номер кошелька ЮMoney:\n"
        f"Например: 410011234567890\n"
        f"Или отправьте <b>-</b> чтобы пропустить."
    )


# ── Create Bot Wizard - Step 5b: YooMoney Wallet ────────────

@constructor_router.message(StateFilter(CreateBotFSM.yoomoney_wallet))
async def create_bot_finish(message: Message, state: FSMContext):
    """
    Handle YooMoney wallet input and finish bot creation.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    yoo = message.text.strip()
    yoomoney_wallet = None if yoo == "-" else yoo
    
    await state.update_data(yoomoney_wallet=yoomoney_wallet)
    await finish_bot_creation(message, state)


# ── Bot Creation Finalization ───────────────────────────────

async def finish_bot_creation(message: Message, state: FSMContext):
    """
    Finalize bot creation:
    - Save bot to database
    - Create default categories for shop bots
    - Start the child bot
    """
    data = await state.get_data()
    await state.clear()
    
    async with async_session_maker() as session:
        can_create, error_msg = await can_create_bot(
            session, message.from_user.id
        )
        if not can_create:
            return await message.answer(
                f"{Emoji.CROSS} {error_msg}",
                reply_markup=main_menu_kb()
            )
        
        bot_type = data.get("bot_type", "shop")
        
        bot_record = ShopBot(
            owner_id=message.from_user.id,
            bot_token=data["token"],
            bot_name=data["name"],
            bot_type=bot_type,
            admin_id=data["admin_id"],
            crypto_bot_token=data.get("crypto_token"),
            yoomoney_wallet=data.get("yoomoney_wallet"),
            is_active=True
        )
        
        session.add(bot_record)
        await session.commit()
        await session.refresh(bot_record)
        
        # Create default categories for shop bots
        if bot_type == "shop":
            default_games = [
                "🔵 Brawl Stars",
                "⚔️ Clash of Clans",
                "👑 Clash Royale"
            ]
            for game in default_games:
                session.add(
                    Category(bot_id=bot_record.id, name=game)
                )
            await session.commit()
    
    # Start the child bot
    asyncio.create_task(run_shop_bot(bot_record))
    
    type_name = (
        "Донат магазин" if bot_type == "shop"
        else "Обратная связь"
    )
    
    success_text = (
        f"{Emoji.CHECK} <b>Бот создан и запущен!</b>\n\n"
        f"Тип: {type_name}\n"
        f"Название: {data['name']}\n"
        f"ID: <code>{bot_record.id}</code>\n\n"
        f"Управление в разделе «{Emoji.LIST} Мои боты»\n"
        f"Инструкции: {CHANNEL_USERNAME}"
    )
    
    await message.answer(success_text, reply_markup=main_menu_kb())


# ── My Bots List ────────────────────────────────────────────

@constructor_router.message(F.text == f"{Emoji.LIST} Мои боты")
async def my_bots(message: Message):
    """
    Show list of user's bots with management options.
    """
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
        
        if bot.bot_type == "shop":
            type_icon = Emoji.SHOPPING_CART
            type_name = "Магазин"
        else:
            type_icon = Emoji.FEEDBACK
            type_name = "Обратная связь"
        
        info_lines = [
            f"▸ Статус: {status}",
            f"▸ Тип: {type_icon} {type_name}",
        ]
        
        if bot.bot_type == "shop":
            async with async_session_maker() as session:
                products_count = await session.scalar(
                    select(func.count(Product.id)).where(
                        Product.category_id.in_(
                            select(Category.id).where(
                                Category.bot_id == bot.id
                            )
                        )
                    )
                )
                
                revenue = await session.scalar(
                    select(
                        func.coalesce(
                            func.sum(Purchase.amount), 0
                        )
                    ).where(
                        Purchase.bot_id == bot.id,
                        Purchase.status == "completed"
                    )
                )
                
                sales = await session.scalar(
                    select(func.count(Purchase.id)).where(
                        Purchase.bot_id == bot.id,
                        Purchase.status == "completed"
                    )
                )
            
            info_lines.extend([
                f"▸ Товаров: {products_count} | Продаж: {sales}",
                f"▸ Выручка: {revenue or 0} руб",
            ])
        else:
            async with async_session_maker() as session:
                msg_count = await session.scalar(
                    select(func.count(FeedbackMessage.id))
                    .where(FeedbackMessage.bot_id == bot.id)
                )
            
            info_lines.append(
                f"▸ Сообщений: {msg_count}"
            )
        
        info_lines.append(f"▸ ID: <code>{bot.id}</code>")
        
        bot_text = (
            f"{Emoji.ROBOT} <b>{bot.bot_name}</b>\n"
            + "\n".join(info_lines)
        )
        
        await message.answer(
            bot_text,
            reply_markup=bot_management_kb(
                bot.id, bot.is_active, bot.bot_type
            )
        )


# ── Back to Bot Management ──────────────────────────────────

@constructor_router.callback_query(F.data.startswith("back_to_bot:"))
async def back_to_bot(callback: CallbackQuery):
    """
    Navigate back to bot management view.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    status = "🟢 Активен" if bot.is_active else "🔴 Остановлен"
    
    if bot.bot_type == "shop":
        type_icon = Emoji.SHOPPING_CART
        type_name = "Магазин"
    else:
        type_icon = Emoji.FEEDBACK
        type_name = "Обратная связь"
    
    info_lines = [
        f"▸ Статус: {status}",
        f"▸ Тип: {type_icon} {type_name}",
    ]
    
    if bot.bot_type == "shop":
        async with async_session_maker() as session:
            products_count = await session.scalar(
                select(func.count(Product.id)).where(
                    Product.category_id.in_(
                        select(Category.id).where(
                            Category.bot_id == bot.id
                        )
                    )
                )
            )
        info_lines.append(f"▸ Товаров: {products_count}")
    
    info_lines.append(f"▸ ID: <code>{bot.id}</code>")
    
    bot_text = (
        f"{Emoji.ROBOT} <b>{bot.bot_name}</b>\n"
        + "\n".join(info_lines)
    )
    
    await callback.message.edit_text(
        bot_text,
        reply_markup=bot_management_kb(
            bot_id, bot.is_active, bot.bot_type
        )
    )
    await callback.answer()


# ── Bot Settings Menu ───────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_settings:"))
async def bot_settings(callback: CallbackQuery):
    """
    Show bot settings menu.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    welcome_status = (
        "✅ Настроено" if bot.welcome_message
        else "❌ По умолчанию"
    )
    support_status = (
        f"@{bot.support_username}"
        if bot.support_username
        else "не указана"
    )
    
    settings_text = (
        f"{Emoji.GEAR} <b>Настройки бота «{bot.bot_name}»</b>\n\n"
        f"📝 Приветственное сообщение: {welcome_status}\n"
        f"📞 Поддержка: {support_status}"
    )
    
    if bot.bot_type == "feedback":
        btn_status = (
            bot.feedback_button_text or "не задана"
        )
        reply_status = (
            "✅ Настроен" if bot.feedback_button_reply
            else "❌ Не настроен"
        )
        settings_text += (
            f"\n🔘 Кнопка: {btn_status}\n"
            f"💬 Ответ кнопки: {reply_status}"
        )
    
    settings_text += "\n\nВыберите действие:"
    
    await callback.message.edit_text(
        settings_text,
        reply_markup=bot_settings_kb(bot_id, bot.bot_type)
    )
    await callback.answer()


# ── Edit Welcome Message ────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_welcome:"))
async def edit_welcome_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing welcome message.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotSettingsFSM.welcome_message)
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        current = (
            bot.welcome_message
            or "Не задано (используется стандартное)"
        )
    
    await callback.message.answer(
        f"{Emoji.PENCIL} <b>Изменение приветствия</b>\n\n"
        f"Текущее: {current[:200]}...\n\n"
        f"Введите новое сообщение (или «-» для сброса):\n"
        f"<i>Поддерживается HTML-разметка</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(BotSettingsFSM.welcome_message)
)
async def edit_welcome_save(message: Message, state: FSMContext):
    """
    Save welcome message.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()
    
    welcome = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(welcome_message=welcome)
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Приветственное сообщение обновлено!",
        reply_markup=main_menu_kb()
    )


# ── Edit Support Username ───────────────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_support:"))
async def edit_support_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing support username.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotSettingsFSM.support_username)
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        current = (
            f"@{bot.support_username}"
            if bot.support_username
            else "не указан"
        )
    
    await callback.message.answer(
        f"{Emoji.PHONE} <b>Изменение поддержки</b>\n\n"
        f"Текущий: {current}\n\n"
        f"Введите username поддержки (без @) "
        f"или «-» для удаления:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(BotSettingsFSM.support_username)
)
async def edit_support_save(message: Message, state: FSMContext):
    """
    Save support username.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()
    
    support = (
        None if message.text.strip() == "-"
        else message.text.strip().replace("@", "")
    )
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(support_username=support)
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Поддержка обновлена!",
        reply_markup=main_menu_kb()
    )


# ── Feedback Button Settings ────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("edit_feedback_button:")
)
async def edit_feedback_button_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing feedback button settings.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(FeedbackButtonFSM.button_text)
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        current_text = bot.feedback_button_text or "не задана"
        current_reply = bot.feedback_button_reply or "не задан"
    
    await callback.message.answer(
        f"{Emoji.KEY} <b>Настройка кнопки обратной связи</b>\n\n"
        f"Текущий текст кнопки: {current_text}\n"
        f"Текущий ответ: {current_reply[:100]}...\n\n"
        f"Введите текст кнопки (или «-» для удаления):",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(FeedbackButtonFSM.button_text)
)
async def edit_feedback_button_save(
    message: Message,
    state: FSMContext
):
    """
    Save feedback button text and ask for reply text.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    
    btn_text = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    if btn_text:
        await state.update_data(button_text=btn_text)
        await state.set_state(FeedbackButtonFSM.button_reply)
        
        await message.answer(
            f"{Emoji.PENCIL} Введите текст ответа "
            f"после нажатия кнопки:\n"
            f"(или «-» для пропуска)\n\n"
            f"<i>Поддерживается HTML-разметка</i>"
        )
    else:
        await state.clear()
        
        async with async_session_maker() as session:
            await session.execute(
                update(ShopBot)
                .where(ShopBot.id == bot_id)
                .values(
                    feedback_button_text=None,
                    feedback_button_reply=None
                )
            )
            await session.commit()
        
        await message.answer(
            f"{Emoji.CHECK} Кнопка обратной связи удалена!",
            reply_markup=main_menu_kb()
        )


@constructor_router.message(
    StateFilter(FeedbackButtonFSM.button_reply)
)
async def edit_feedback_button_reply_save(
    message: Message,
    state: FSMContext
):
    """
    Save feedback button reply text.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    
    btn_reply = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    await state.clear()
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(
                feedback_button_text=data["button_text"],
                feedback_button_reply=btn_reply
            )
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Кнопка обратной связи настроена!",
        reply_markup=main_menu_kb()
    )


# ── Feedback Messages List ──────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("feedback_messages:")
)
async def feedback_messages(callback: CallbackQuery):
    """
    Show feedback messages for admin to reply.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        messages_result = await session.execute(
            select(FeedbackMessage)
            .where(FeedbackMessage.bot_id == bot_id)
            .order_by(FeedbackMessage.created_at.desc())
            .limit(20)
        )
        messages = messages_result.scalars().all()
    
    if not messages:
        return await callback.answer(
            "Нет сообщений.", show_alert=True
        )
    
    for msg in messages:
        status = (
            "✅ Отвечено" if msg.is_replied
            else "⏳ Ожидает ответа"
        )
        
        msg_text = (
            f"{Emoji.MAIL} <b>Сообщение #{msg.id}</b>\n"
            f"👤 От: <code>{msg.user_id}</code>\n"
            f"📅 {msg.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📝 {msg.message_text[:300]}\n"
            f"📌 Статус: {status}"
        )
        
        if msg.reply_text:
            msg_text += f"\n💬 Ответ: {msg.reply_text[:200]}"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        
        if not msg.is_replied:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{Emoji.REPLY} Ответить",
                    callback_data=f"reply_feedback:{msg.id}"
                )
            ])
        
        await callback.message.answer(msg_text, reply_markup=kb)
    
    await callback.answer()


# ── Reply to Feedback Message ───────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("reply_feedback:")
)
async def reply_feedback_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start replying to a feedback message.
    """
    msg_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        fb_msg = await session.get(FeedbackMessage, msg_id)
        if fb_msg:
            bot = await session.get(ShopBot, fb_msg.bot_id)
            await state.update_data(
                message_id=msg_id,
                bot_token=bot.bot_token if bot else None
            )
    
    await state.set_state(ReplyFeedbackFSM.reply_text)
    
    await callback.message.answer(
        f"{Emoji.REPLY} Введите текст ответа пользователю:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(ReplyFeedbackFSM.reply_text)
)
async def reply_feedback_send(
    message: Message,
    state: FSMContext
):
    """
    Send reply to feedback message via child bot.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    msg_id = data["message_id"]
    bot_token = data.get("bot_token")
    await state.clear()
    
    async with async_session_maker() as session:
        fb_msg = await session.get(FeedbackMessage, msg_id)
        
        if not fb_msg:
            return await message.answer("Сообщение не найдено.")
        
        # Save reply
        fb_msg.reply_text = message.text
        fb_msg.is_replied = True
        await session.commit()
        
        # Send reply via child bot
        if bot_token:
            try:
                child_bot = Bot(
                    token=bot_token,
                    default=DefaultBotProperties(
                        parse_mode=ParseMode.HTML
                    )
                )
                
                reply_text = (
                    f"{Emoji.REPLY} <b>Ответ от поддержки:</b>\n\n"
                    f"{message.text}"
                )
                
                await child_bot.send_message(
                    fb_msg.user_id, reply_text
                )
                
                await child_bot.session.close()
                
                await message.answer(
                    f"{Emoji.CHECK} Ответ отправлен пользователю "
                    f"через дочерний бот!"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to send reply via child bot: {e}"
                )
                await message.answer(
                    f"{Emoji.CROSS} Ошибка отправки через "
                    f"дочерний бот: {e}"
                )
        else:
            await message.answer(
                f"{Emoji.WARNING} Токен бота не найден. "
                f"Ответ сохранён, но не отправлен."
            )


# ── Category Management ─────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("manage_cats:"))
async def manage_categories(callback: CallbackQuery):
    """
    Show category management menu.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        cats_result = await session.execute(
            select(Category)
            .where(Category.bot_id == bot_id)
            .order_by(Category.id)
        )
        cats = cats_result.scalars().all()
    
    text = (
        f"{Emoji.PACKAGE} <b>Категории бота "
        f"«{bot.bot_name}»</b>\n\n"
    )
    
    if cats:
        for i, cat in enumerate(cats, 1):
            async with async_session_maker() as session:
                products_count = await session.scalar(
                    select(func.count(Product.id)).where(
                        Product.category_id == cat.id
                    )
                )
            text += (
                f"{i}. {cat.name} "
                f"({products_count} товаров)\n"
            )
    else:
        text += "Категорий пока нет.\n"
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.ADD} Добавить категорию",
                    callback_data=f"add_cat:{bot_id}"
                )
            ],
        ]
    )
    
    if cats:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{Emoji.TRASH} Удалить категорию",
                callback_data=f"del_cat_menu:{bot_id}"
            )
        ])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"{Emoji.BACK} Назад",
            callback_data=f"back_to_bot:{bot_id}"
        )
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@constructor_router.callback_query(F.data.startswith("add_cat:"))
async def add_category_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start adding a new category.
    """
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
    """
    Save new category.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    name = message.text.strip()
    
    if not name or len(name) > 255:
        return await message.answer(
            f"{Emoji.CROSS} Название должно быть "
            f"от 1 до 255 символов."
        )
    
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
    """
    Show category deletion menu.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()
    
    if not cats:
        return await callback.answer(
            "Нет категорий для удаления.", show_alert=True
        )
    
    await callback.message.edit_text(
        f"{Emoji.TRASH} Выберите категорию для удаления:",
        reply_markup=inline_kb([
            (cat.name, f"confirm_del_cat:{cat.id}")
            for cat in cats
        ])
    )
    await callback.answer()


@constructor_router.callback_query(
    F.data.startswith("confirm_del_cat:")
)
async def confirm_del_category(callback: CallbackQuery):
    """
    Confirm and delete category.
    """
    cat_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        cat = await session.get(Category, cat_id)
        
        if not cat:
            return await callback.answer("Категория не найдена.")
        
        bot_id = cat.bot_id
        name = cat.name
        
        await session.execute(
            delete(Category).where(Category.id == cat_id)
        )
        await session.commit()
    
    await callback.message.edit_text(
        f"{Emoji.TRASH} Категория «{name}» удалена.",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()


# ── Product Management ──────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("manage_products:")
)
async def manage_products(callback: CallbackQuery):
    """
    Show product management menu.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    text = (
        f"{Emoji.BOX} <b>Управление товарами — "
        f"«{bot.bot_name}»</b>\n\n"
        f"Выберите действие:"
    )
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.ADD} Добавить товар",
                    callback_data=f"add_product:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.LIST} Список товаров",
                    callback_data=f"list_products:{bot_id}:0"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.REMOVE} Удалить товар",
                    callback_data=f"del_product_menu:{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BACK} Назад",
                    callback_data=f"back_to_bot:{bot_id}"
                )
            ],
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@constructor_router.callback_query(F.data.startswith("add_product:"))
async def add_product_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start adding a new product.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()
    
    if not cats:
        return await callback.answer(
            "Сначала создайте категорию!", show_alert=True
        )
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AddProductFSM.category)
    
    await callback.message.answer(
        f"{Emoji.PACKAGE} Выберите категорию для товара:",
        reply_markup=inline_kb([
            (cat.name, f"prod_cat:{cat.id}")
            for cat in cats
        ])
    )
    await callback.answer()


@constructor_router.callback_query(
    StateFilter(AddProductFSM.category),
    F.data.startswith("prod_cat:")
)
async def add_product_name(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Select category and ask for product name.
    """
    cat_id = int(callback.data.split(":")[1])
    
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductFSM.name)
    
    await callback.message.answer(
        f"{Emoji.PENCIL} Введите название товара:\n"
        f"Например: «1000 гемов»",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(StateFilter(AddProductFSM.name))
async def add_product_desc(message: Message, state: FSMContext):
    """
    Handle product name and ask for description.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    name = message.text.strip()
    
    if not name:
        return await message.answer(
            f"{Emoji.CROSS} Введите название товара."
        )
    
    await state.update_data(name=name)
    await state.set_state(AddProductFSM.description)
    
    await message.answer(
        f"{Emoji.PENCIL} Введите описание товара:\n"
        f"Или отправьте <b>-</b> чтобы оставить "
        f"без описания."
    )


@constructor_router.message(StateFilter(AddProductFSM.description))
async def add_product_price(message: Message, state: FSMContext):
    """
    Handle description and ask for price.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    desc = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    await state.update_data(description=desc)
    await state.set_state(AddProductFSM.price)
    
    await message.answer(
        f"{Emoji.MONEY} Введите цену товара в рублях:\n"
        f"Например: 299.00 или 150"
    )


@constructor_router.message(StateFilter(AddProductFSM.price))
async def add_product_deliver(message: Message, state: FSMContext):
    """
    Handle price and ask for delivery text.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    try:
        price = Decimal(
            message.text.strip().replace(",", ".")
        )
        if price <= 0:
            raise ValueError
    except (ValueError, Exception):
        return await message.answer(
            f"{Emoji.CROSS} Некорректная цена. "
            f"Пример: 299.00"
        )
    
    await state.update_data(price=price)
    await state.set_state(AddProductFSM.auto_deliver)
    
    await message.answer(
        f"{Emoji.GIFT} <b>Текст автоматической выдачи</b>\n\n"
        f"Введите текст, который получит покупатель "
        f"после оплаты.\n"
        f"Или «-» если товар без автоматической выдачи.\n\n"
        f"<i>Поддерживается HTML-разметка</i>\n"
        f"<i>Пример: «Спасибо за покупку! "
        f"Ваш код: ABC123»</i>"
    )


@constructor_router.message(StateFilter(AddProductFSM.auto_deliver))
async def add_product_save(message: Message, state: FSMContext):
    """
    Save the new product.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    deliver_text = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    data = await state.get_data()
    await state.clear()
    
    async with async_session_maker() as session:
        product = Product(
            category_id=data["category_id"],
            name=data["name"],
            description=data.get("description"),
            price=data["price"],
            auto_deliver_text=deliver_text,
            is_available=True
        )
        session.add(product)
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Товар «{data['name']}» добавлен!\n"
        f"Цена: {data['price']} руб\n"
        f"Автовыдача: "
        f"{'✅ Настроена' if deliver_text else '❌ Отсутствует'}",
        reply_markup=main_menu_kb()
    )


# ── Edit Delivery Text ──────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("edit_deliver:"))
async def edit_deliver_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing delivery text.
    """
    product_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        
        if not product:
            return await callback.answer("Товар не найден.")
    
    await state.update_data(product_id=product_id)
    await state.set_state(EditDeliverFSM.text)
    
    current = product.auto_deliver_text or "не задан"
    
    await callback.message.answer(
        f"{Emoji.PENCIL} <b>Изменение текста выдачи</b>\n\n"
        f"Товар: {product.name}\n"
        f"Цена: {product.price} руб\n"
        f"Текущий текст:\n<code>{current[:500]}</code>\n\n"
        f"Введите новый текст (или «-» для удаления):\n"
        f"<i>Поддерживается HTML-разметка</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(StateFilter(EditDeliverFSM.text))
async def edit_deliver_save(message: Message, state: FSMContext):
    """
    Save delivery text.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    product_id = data["product_id"]
    await state.clear()
    
    text = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    async with async_session_maker() as session:
        await session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(auto_deliver_text=text)
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Текст выдачи обновлён!",
        reply_markup=main_menu_kb()
    )


# ── Toggle Product Availability ─────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("toggle_product:")
)
async def toggle_product(callback: CallbackQuery):
    """
    Toggle product availability (show/hide).
    """
    product_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        
        if product:
            product.is_available = not product.is_available
            await session.commit()
            
            status = (
                "включен ✅" if product.is_available
                else "отключен ❌"
            )
            await callback.answer(f"Товар {status}.")
        else:
            await callback.answer("Товар не найден.")


# ── List Products with Management ───────────────────────────

@constructor_router.callback_query(
    F.data.startswith("list_products:")
)
async def list_products(callback: CallbackQuery):
    """
    Show product list with management buttons.
    """
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()
    
    all_products = []
    for cat in cats:
        async with async_session_maker() as session:
            prod_result = await session.execute(
                select(Product)
                .where(Product.category_id == cat.id)
                .order_by(Product.id)
            )
            products = prod_result.scalars().all()
        for p in products:
            all_products.append((cat.name, p))
    
    if not all_products:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{Emoji.ADD} Добавить товар",
                        callback_data=f"add_product:{bot_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{Emoji.BACK} Назад",
                        callback_data=f"back_to_bot:{bot_id}"
                    )
                ],
            ]
        )
        return await callback.message.edit_text(
            "Товаров пока нет.", reply_markup=kb
        )
    
    per_page = 5
    total_pages = (
        (len(all_products) + per_page - 1) // per_page
    )
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        bot_name = bot.bot_name if bot else "Неизвестный"
    
    text = (
        f"{Emoji.BOX} <b>Товары бота «{bot_name}»</b>\n"
        f"Страница {page + 1}/{total_pages}\n\n"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    for i, (cat_name, p) in enumerate(
        all_products[start:end], start + 1
    ):
        status = "✅" if p.is_available else "❌"
        auto = " 🤖" if p.auto_deliver_text else ""
        
        text += (
            f"{i}. {status}{auto} <b>{p.name}</b>\n"
            f"   💰 {p.price} руб | 📁 {cat_name}\n"
        )
        
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{Emoji.PENCIL} Выдача",
                callback_data=f"edit_deliver:{p.id}"
            ),
            InlineKeyboardButton(
                text=(
                    f"{'❌ Скрыть' if p.is_available else '✅ Показать'}"
                ),
                callback_data=f"toggle_product:{p.id}"
            ),
            InlineKeyboardButton(
                text=f"{Emoji.TRASH}",
                callback_data=f"confirm_del_product:{p.id}"
            )
        ])
    
    # Navigation buttons
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"list_products:{bot_id}:{page - 1}"
            )
        )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=f"list_products:{bot_id}:{page + 1}"
            )
        )
    if nav:
        kb.inline_keyboard.append(nav)
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"{Emoji.ADD} Добавить",
            callback_data=f"add_product:{bot_id}"
        ),
        InlineKeyboardButton(
            text=f"{Emoji.BACK} Назад",
            callback_data=f"back_to_bot:{bot_id}"
        )
    ])
    
    await callback.message.edit_text(
        text, reply_markup=kb, parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ── Delete Product ──────────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("del_product_menu:")
)
async def del_product_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Show product deletion menu.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        cats_result = await session.execute(
            select(Category).where(Category.bot_id == bot_id)
        )
        cats = cats_result.scalars().all()
    
    if not cats:
        return await callback.answer(
            "Нет категорий.", show_alert=True
        )
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(DeleteProductFSM.category)
    
    await callback.message.answer(
        f"{Emoji.PACKAGE} Выберите категорию:",
        reply_markup=inline_kb([
            (cat.name, f"del_prod_cat:{cat.id}")
            for cat in cats
        ])
    )
    await callback.answer()


@constructor_router.callback_query(
    StateFilter(DeleteProductFSM.category),
    F.data.startswith("del_prod_cat:")
)
async def del_product_select(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Select product to delete.
    """
    cat_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        prod_result = await session.execute(
            select(Product).where(
                Product.category_id == cat_id
            )
        )
        products = prod_result.scalars().all()
    
    if not products:
        await callback.answer(
            "В этой категории нет товаров.",
            show_alert=True
        )
        await state.clear()
        return
    
    await state.set_state(DeleteProductFSM.product)
    
    await callback.message.answer(
        f"{Emoji.TRASH} Выберите товар для удаления:",
        reply_markup=inline_kb([
            (
                f"{p.name} ({p.price} руб)",
                f"confirm_del_prod:{p.id}"
            )
            for p in products
        ])
    )
    await callback.answer()


@constructor_router.callback_query(
    StateFilter(DeleteProductFSM.product),
    F.data.startswith("confirm_del_prod:")
)
async def confirm_del_product_by_id(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Confirm and delete product (from menu).
    """
    product_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    bot_id = data["bot_id"]
    await state.clear()
    
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        name = product.name if product else "Товар"
        
        await session.execute(
            delete(Product).where(Product.id == product_id)
        )
        await session.commit()
    
    await callback.message.edit_text(
        f"{Emoji.TRASH} Товар «{name}» удалён.",
        reply_markup=back_kb(bot_id)
    )
    await callback.answer()


@constructor_router.callback_query(
    F.data.startswith("confirm_del_product:")
)
async def confirm_del_product_direct(callback: CallbackQuery):
    """
    Direct product deletion from list.
    """
    product_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        product = await session.get(Product, product_id)
        
        if not product:
            return await callback.answer("Товар не найден.")
        
        name = product.name
        
        cat = await session.get(
            Category, product.category_id
        )
        bot_id = cat.bot_id if cat else 0
        
        await session.execute(
            delete(Product).where(Product.id == product_id)
        )
        await session.commit()
    
    await callback.answer(f"Товар «{name}» удалён.")
    
    if bot_id:
        await callback.message.edit_text(
            f"{Emoji.TRASH} Товар «{name}» удалён.",
            reply_markup=back_kb(bot_id)
        )


# ── Payment Settings ────────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("payment_settings:")
)
async def payment_settings(callback: CallbackQuery):
    """
    Show payment settings menu for a shop bot.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
    
    if not bot or bot.owner_id != callback.from_user.id:
        return await callback.answer("Бот не найден.")
    
    crypto_status = (
        "✅ Настроен" if bot.crypto_bot_token
        else "❌ Не настроен"
    )
    yoo_status = (
        "✅ Настроен" if bot.yoomoney_wallet
        else "❌ Не настроен"
    )
    rolly_status = (
        "✅ Настроен" if is_rollypay_configured(bot)
        else "❌ Не настроен"
    )
    
    payment_text = (
        f"{Emoji.WALLET} <b>Платёжные реквизиты — "
        f"«{bot.bot_name}»</b>\n\n"
        f"{Emoji.CRYPTOBOT} Crypto Bot: {crypto_status}\n"
        f"{Emoji.CARD} ЮMoney: {yoo_status}\n"
        f"{Emoji.COINS} RollyPay: {rolly_status}\n\n"
        f"<i>Для RollyPay нужны: Terminal ID, API Key, "
        f"Signing Secret</i>\n"
        f"<i>Инструкции: {CHANNEL_USERNAME}</i>\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=payment_settings_menu_kb(bot_id)
    )
    await callback.answer()


@constructor_router.callback_query(F.data.startswith("edit_crypto:"))
async def edit_crypto_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing CryptoBot token.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.crypto_token)
    
    await callback.message.answer(
        f"{Emoji.CRYPTOBOT} Введите новый токен Crypto Bot:\n"
        f"Или «-» чтобы удалить.\n\n"
        f"Инструкции: {CHANNEL_USERNAME}",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(PaymentSettingsFSM.crypto_token)
)
async def edit_crypto_save(message: Message, state: FSMContext):
    """
    Save CryptoBot token.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    await state.clear()
    
    token = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(crypto_bot_token=token)
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Токен Crypto Bot обновлён!",
        reply_markup=main_menu_kb()
    )


@constructor_router.callback_query(F.data.startswith("edit_yoo:"))
async def edit_yoo_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start editing YooMoney wallet.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(edit_bot_id=bot_id)
    await state.set_state(PaymentSettingsFSM.yoomoney_wallet)
    
    await callback.message.answer(
        f"{Emoji.CARD} Введите новый номер кошелька ЮMoney:\n"
        f"Или «-» чтобы удалить.\n\n"
        f"Инструкции: {CHANNEL_USERNAME}",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(PaymentSettingsFSM.yoomoney_wallet)
)
async def edit_yoo_save(message: Message, state: FSMContext):
    """
    Save YooMoney wallet.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["edit_bot_id"]
    await state.clear()
    
    wallet = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(yoomoney_wallet=wallet)
        )
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Кошелёк ЮMoney обновлён!",
        reply_markup=main_menu_kb()
    )


# ── RollyPay Bot Setup ──────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("edit_rolly_bot:")
)
async def edit_rolly_bot_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start RollyPay setup for a bot.
    """
    bot_id = int(callback.data.split(":")[1])
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(BotRollyPayFSM.terminal_id)
    
    await callback.message.answer(
        f"{Emoji.COINS} <b>RollyPay: Terminal ID</b>\n"
        f"Введите Terminal ID (или «-» для сброса):\n\n"
        f"Инструкции: {CHANNEL_USERNAME}",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(BotRollyPayFSM.terminal_id)
)
async def edit_rolly_bot_terminal(
    message: Message,
    state: FSMContext
):
    """
    Handle Terminal ID input.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    value = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    await state.update_data(terminal_id=value)
    await state.set_state(BotRollyPayFSM.api_key)
    
    await message.answer(
        f"{Emoji.KEY} Введите API Key (или «-»):"
    )


@constructor_router.message(
    StateFilter(BotRollyPayFSM.api_key)
)
async def edit_rolly_bot_api_key(
    message: Message,
    state: FSMContext
):
    """
    Handle API Key input.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    value = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    await state.update_data(api_key=value)
    await state.set_state(BotRollyPayFSM.signing_secret)
    
    await message.answer(
        f"{Emoji.LOCK} Введите Signing Secret (или «-»):"
    )


@constructor_router.message(
    StateFilter(BotRollyPayFSM.signing_secret)
)
async def edit_rolly_bot_save(
    message: Message,
    state: FSMContext
):
    """
    Save RollyPay settings.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["bot_id"]
    
    secret = (
        None if message.text.strip() == "-"
        else message.text.strip()
    )
    
    await state.clear()
    
    async with async_session_maker() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == bot_id)
            .values(
                rollypay_terminal_id=data.get("terminal_id"),
                rollypay_api_key=data.get("api_key"),
                rollypay_signing_secret=secret
            )
        )
        await session.commit()
    
    configured = all([
        data.get("terminal_id"),
        data.get("api_key"),
        secret
    ])
    
    status_text = (
        f"{Emoji.CHECK} RollyPay полностью настроен!"
        if configured
        else (
            f"{Emoji.WARNING} RollyPay сохранён, "
            f"но не все поля заполнены!"
        )
    )
    
    await message.answer(
        status_text, reply_markup=main_menu_kb()
    )


# ── Statistics ──────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_stats:"))
async def bot_stats(callback: CallbackQuery):
    """
    Show bot statistics.
    Different stats for shop and feedback bots.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        if bot.bot_type == "shop":
            # Shop bot statistics
            users_count = await session.scalar(
                select(
                    func.count(Purchase.user_id.distinct())
                ).where(Purchase.bot_id == bot_id)
            )
            
            purchases_done = await session.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.bot_id == bot_id,
                    Purchase.status == "completed"
                )
            )
            
            purchases_pending = await session.scalar(
                select(func.count(Purchase.id)).where(
                    Purchase.bot_id == bot_id,
                    Purchase.status == "pending"
                )
            )
            
            revenue = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(Purchase.amount), 0
                    )
                ).where(
                    Purchase.bot_id == bot_id,
                    Purchase.status == "completed"
                )
            )
            
            products_count = await session.scalar(
                select(func.count(Product.id)).where(
                    Product.category_id.in_(
                        select(Category.id).where(
                            Category.bot_id == bot_id
                        )
                    )
                )
            )
            
            categories_count = await session.scalar(
                select(func.count(Category.id)).where(
                    Category.bot_id == bot_id
                )
            )
            
            stats_text = (
                f"{Emoji.CHART} <b>Статистика — "
                f"«{bot.bot_name}»</b>\n\n"
                f"{Emoji.USERS} Покупателей: "
                f"{users_count or 0}\n"
                f"{Emoji.PACKAGE} Категорий: "
                f"{categories_count}\n"
                f"{Emoji.BOX} Товаров: {products_count}\n"
                f"{Emoji.SHOPPING_CART} Продаж: "
                f"{purchases_done or 0} "
                f"(ожидает: {purchases_pending or 0})\n"
                f"{Emoji.MONEY} Выручка: "
                f"{revenue or 0} руб"
            )
        else:
            # Feedback bot statistics
            total_msgs = await session.scalar(
                select(func.count(FeedbackMessage.id))
                .where(FeedbackMessage.bot_id == bot_id)
            )
            
            replied_msgs = await session.scalar(
                select(func.count(FeedbackMessage.id))
                .where(
                    FeedbackMessage.bot_id == bot_id,
                    FeedbackMessage.is_replied == True
                )
            )
            
            unique_users = await session.scalar(
                select(
                    func.count(
                        FeedbackMessage.user_id.distinct()
                    )
                ).where(FeedbackMessage.bot_id == bot_id)
            )
            
            stats_text = (
                f"{Emoji.CHART} <b>Статистика — "
                f"«{bot.bot_name}»</b>\n\n"
                f"{Emoji.USERS} Уникальных пользователей: "
                f"{unique_users or 0}\n"
                f"{Emoji.MAIL} Всего сообщений: "
                f"{total_msgs}\n"
                f"{Emoji.CHECK} Отвечено: "
                f"{replied_msgs or 0}\n"
                f"{Emoji.CLOCK} Ожидает ответа: "
                f"{(total_msgs or 0) - (replied_msgs or 0)}"
            )
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BACK} Назад",
                    callback_data=f"back_to_bot:{bot_id}"
                )
            ]
        ]
    )
    
    await callback.message.edit_text(
        stats_text, reply_markup=kb
    )
    await callback.answer()


# ── Buyers List ─────────────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("bot_buyers:"))
async def bot_buyers(callback: CallbackQuery):
    """
    Show top buyers list for shop bot.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
        
        result = await session.execute(
            select(
                User.telegram_id,
                User.username,
                func.count(Purchase.id),
                func.sum(Purchase.amount)
            )
            .join(
                Purchase,
                User.telegram_id == Purchase.user_id
            )
            .where(
                Purchase.bot_id == bot_id,
                Purchase.status == "completed"
            )
            .group_by(
                User.telegram_id, User.username
            )
            .order_by(
                func.sum(Purchase.amount).desc()
            )
            .limit(20)
        )
        buyers = result.all()
    
    text = (
        f"{Emoji.USERS} <b>Топ покупателей — "
        f"«{bot.bot_name}»</b>\n\n"
    )
    
    if buyers:
        for i, (tid, username, count, total) in enumerate(
            buyers, 1
        ):
            display = (
                f"@{username}" if username
                else f"ID:{tid}"
            )
            text += (
                f"{i}. {display}\n"
                f"   {Emoji.SHOPPING_CART} {count} "
                f"покупок на {total} руб\n"
            )
    else:
        text += "Покупателей пока нет."
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.BACK} Назад",
                    callback_data=f"back_to_bot:{bot_id}"
                )
            ]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ── Broadcast ───────────────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("bot_broadcast:")
)
async def bot_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Start broadcast message creation for shop bot.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if not bot or bot.owner_id != callback.from_user.id:
            return await callback.answer("Бот не найден.")
    
    await state.update_data(broadcast_bot_id=bot_id)
    await state.set_state(BroadcastFSM.message_text)
    
    await callback.message.answer(
        f"{Emoji.MEGAPHONE} Введите текст рассылки "
        f"(поддерживается HTML):\n\n"
        f"<b>жирный</b>, <i>курсив</i>, <code>моно</code>\n\n"
        f"Сообщение получат все, кто делал покупки "
        f"в этом боте.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(BroadcastFSM.message_text)
)
async def broadcast_send(message: Message, state: FSMContext):
    """
    Send broadcast message to all buyers of a shop bot.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    data = await state.get_data()
    bot_id = data["broadcast_bot_id"]
    await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Purchase.user_id.distinct()).where(
                Purchase.bot_id == bot_id
            )
        )
        user_ids = [row[0] for row in result.all()]
    
    if not user_ids:
        return await message.answer(
            f"{Emoji.CROSS} Нет пользователей для рассылки.",
            reply_markup=main_menu_kb()
        )
    
    sent = 0
    failed = 0
    
    status_msg = await message.answer(
        f"{Emoji.LOADING} Начинаю рассылку на "
        f"{len(user_ids)} пользователей..."
    )
    
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(
                uid, message.text
            )
            sent += 1
        except Exception:
            failed += 1
        
        if (i + 1) % 10 == 0:
            await status_msg.edit_text(
                f"{Emoji.LOADING} Рассылка: "
                f"{i + 1}/{len(user_ids)} "
                f"(✅ {sent} | ❌ {failed})"
            )
        
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(
        f"{Emoji.MEGAPHONE} <b>Рассылка завершена!</b>\n\n"
        f"{Emoji.CHECK} Отправлено: {sent}\n"
        f"{Emoji.CROSS} Ошибок: {failed}",
        reply_markup=main_menu_kb()
    )


# ── Test Payment ────────────────────────────────────────────

@constructor_router.callback_query(
    F.data.startswith("test_payment:")
)
async def test_payment(callback: CallbackQuery):
    """
    Create a test payment for a shop bot.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        cats_result = await session.execute(
            select(Category).where(
                Category.bot_id == bot_id
            )
        )
        cats = cats_result.scalars().all()
    
    if not cats:
        return await callback.answer(
            "Нет категорий. Создайте товары!",
            show_alert=True
        )
    
    async with async_session_maker() as session:
        products_result = await session.execute(
            select(Product).where(
                Product.category_id == cats[0].id,
                Product.is_available == True
            )
        )
        products = products_result.scalars().all()
    
    if not products:
        return await callback.answer(
            "Нет товаров в категории.",
            show_alert=True
        )
    
    p = products[0]
    kb = payment_method_kb(p.id, bot)
    
    if not kb.inline_keyboard:
        return await callback.answer(
            "Нет настроенных платёжных систем!",
            show_alert=True
        )
    
    await callback.message.answer(
        f"{Emoji.TEST} <b>Тестовая оплата</b>\n\n"
        f"Товар: {p.name}\n"
        f"Цена: {p.price} руб\n\n"
        f"Выберите способ оплаты:",
        reply_markup=kb
    )
    await callback.answer()


# ── Toggle / Delete Bot ─────────────────────────────────────

@constructor_router.callback_query(F.data.startswith("toggle_bot:"))
async def toggle_bot(callback: CallbackQuery):
    """
    Toggle bot active/inactive status.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        bot = await session.get(ShopBot, bot_id)
        
        if bot and bot.owner_id == callback.from_user.id:
            bot.is_active = not bot.is_active
            await session.commit()
            
            status = (
                "запущен" if bot.is_active
                else "остановлен"
            )
            await callback.answer(f"Бот {status}.")
        else:
            await callback.answer("Ошибка.")


@constructor_router.callback_query(F.data.startswith("delete_bot:"))
async def delete_bot_confirm(callback: CallbackQuery):
    """
    Confirm bot deletion.
    """
    bot_id = int(callback.data.split(":")[1])
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CHECK} Да, удалить",
                    callback_data=(
                        f"confirm_delete_bot:{bot_id}"
                    )
                ),
                InlineKeyboardButton(
                    text=f"{Emoji.CROSS} Нет",
                    callback_data="cancel_delete"
                )
            ]
        ]
    )
    
    await callback.message.answer(
        f"{Emoji.TRASH} Вы уверены, что хотите удалить "
        f"бота? Все данные будут потеряны.",
        reply_markup=kb
    )
    await callback.answer()


@constructor_router.callback_query(
    F.data.startswith("confirm_delete_bot:")
)
async def confirm_delete_bot(callback: CallbackQuery):
    """
    Delete bot permanently.
    """
    bot_id = int(callback.data.split(":")[1])
    
    async with async_session_maker() as session:
        await session.execute(
            delete(ShopBot).where(
                ShopBot.id == bot_id,
                ShopBot.owner_id == callback.from_user.id
            )
        )
        await session.commit()
    
    await callback.message.edit_text(
        f"{Emoji.TRASH} Бот удалён."
    )
    await callback.answer()


@constructor_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    """
    Cancel bot deletion.
    """
    await callback.message.edit_text("Отменено.")
    await callback.answer()


# ── Admin Panel: CryptoBot Settings ─────────────────────────

@constructor_router.callback_query(F.data == "admin_crypto")
async def admin_crypto(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: set CryptoBot token.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="crypto")
    
    await callback.message.answer(
        f"{Emoji.CRYPTOBOT} Введите токен Crypto Bot:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.callback_query(F.data == "admin_yoomoney")
async def admin_yoomoney(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: set YooMoney wallet.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    await state.set_state(AdminFSM.value)
    await state.update_data(setting_type="yoomoney")
    
    await callback.message.answer(
        f"{Emoji.CARD} Введите кошелёк ЮMoney:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.callback_query(F.data == "admin_rollypay")
async def admin_rollypay(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: set RollyPay.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    await state.set_state(AdminRollyPayFSM.setting_type)
    await state.update_data(setting_type="rollypay_terminal")
    
    await callback.message.answer(
        f"{Emoji.COINS} <b>RollyPay: Terminal ID</b>\n"
        f"Введите Terminal ID:",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(StateFilter(AdminFSM.value))
async def admin_save_value(
    message: Message,
    state: FSMContext
):
    """
    Admin: save setting value.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=admin_menu_kb()
        )
    
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
    
    await message.answer(
        f"{Emoji.CHECK} Сохранено!",
        reply_markup=admin_menu_kb()
    )


@constructor_router.message(
    StateFilter(AdminRollyPayFSM.setting_type)
)
async def admin_rollypay_save(
    message: Message,
    state: FSMContext
):
    """
    Admin: save RollyPay settings step by step.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=admin_menu_kb()
        )
    
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
            await state.update_data(
                setting_type="rollypay_api"
            )
            await message.answer(
                f"{Emoji.KEY} Введите API Key:"
            )
            return
        
        elif st == "rollypay_api":
            config.rollypay_api_key = value
            await session.commit()
            await state.update_data(
                setting_type="rollypay_secret"
            )
            await message.answer(
                f"{Emoji.LOCK} Введите Signing Secret:"
            )
            return
        
        elif st == "rollypay_secret":
            config.rollypay_signing_secret = value
            await session.commit()
    
    await state.clear()
    await message.answer(
        f"{Emoji.CHECK} RollyPay сохранён!",
        reply_markup=admin_menu_kb()
    )


# ── Admin Panel: Prices ─────────────────────────────────────

@constructor_router.callback_query(F.data == "admin_prices")
async def admin_prices(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: edit subscription prices.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
    
    await state.set_state(AdminPricesFSM.price_type)
    
    await callback.message.answer(
        f"{Emoji.TAG} <b>Цены подписки</b>\n\n"
        f"{Emoji.STAR} PRO: "
        f"{config.pro_subscription_price}руб\n"
        f"{Emoji.CROWN} PREMIUM: "
        f"{config.premium_subscription_price}руб\n\n"
        f"Что меняем?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{Emoji.STAR} PRO",
                        callback_data="price_pro"
                    ),
                    InlineKeyboardButton(
                        text=f"{Emoji.CROWN} PREMIUM",
                        callback_data="price_premium"
                    )
                ]
            ]
        )
    )
    await callback.answer()


@constructor_router.callback_query(
    StateFilter(AdminPricesFSM.price_type)
)
async def admin_price_input(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: input new price.
    """
    await state.update_data(price_type=callback.data)
    await state.set_state(AdminPricesFSM.value)
    
    name = (
        "PRO" if callback.data == "price_pro"
        else "PREMIUM"
    )
    
    await callback.message.answer(
        f"Введите новую цену для {name} (руб):",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(AdminPricesFSM.value)
)
async def admin_price_save(
    message: Message,
    state: FSMContext
):
    """
    Admin: save new price.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=admin_menu_kb()
        )
    
    try:
        price = Decimal(
            message.text.strip().replace(",", ".")
        )
        if price <= 0:
            raise ValueError
    except Exception:
        return await message.answer(
            f"{Emoji.CROSS} Некорректная цена."
        )
    
    data = await state.get_data()
    await state.clear()
    
    async with async_session_maker() as session:
        config = await get_admin_config(session)
        
        if data["price_type"] == "price_pro":
            config.pro_subscription_price = price
        else:
            config.premium_subscription_price = price
        
        await session.commit()
    
    await message.answer(
        f"{Emoji.CHECK} Цена обновлена!",
        reply_markup=admin_menu_kb()
    )


# ── Admin Panel: Statistics ─────────────────────────────────

@constructor_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """
    Admin: show global statistics.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    async with async_session_maker() as session:
        total_users = await session.scalar(
            select(func.count(User.id))
        )
        
        total_bots = await session.scalar(
            select(func.count(ShopBot.id))
        )
        
        active_bots = await session.scalar(
            select(func.count(ShopBot.id)).where(
                ShopBot.is_active == True
            )
        )
        
        pro_users = await session.scalar(
            select(func.count(User.id)).where(
                User.subscription_tier == "pro"
            )
        )
        
        premium_users = await session.scalar(
            select(func.count(User.id)).where(
                User.subscription_tier == "premium"
            )
        )
        
        total_revenue = await session.scalar(
            select(
                func.coalesce(
                    func.sum(Purchase.amount), 0
                )
            ).where(Purchase.status == "completed")
        )
        
        sub_revenue = await session.scalar(
            select(
                func.coalesce(
                    func.sum(Subscription.amount), 0
                )
            ).where(Subscription.status == "completed")
        )
    
    stats_text = (
        f"{Emoji.CHART} <b>Общая статистика</b>\n\n"
        f"{Emoji.USERS} Пользователей: {total_users}\n"
        f"{Emoji.ROBOT} Ботов: {total_bots} "
        f"(активных: {active_bots})\n"
        f"{Emoji.STAR} PRO: {pro_users} | "
        f"{Emoji.CROWN} PREMIUM: {premium_users}\n"
        f"{Emoji.MONEY} Продажи: "
        f"{total_revenue or 0} руб\n"
        f"{Emoji.COINS} Подписки: "
        f"{sub_revenue or 0} руб"
    )
    
    await callback.message.answer(
        stats_text, reply_markup=admin_menu_kb()
    )
    await callback.answer()


# ── Admin Panel: Global Broadcast ───────────────────────────

@constructor_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Admin: start global broadcast.
    """
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Нет доступа")
    
    await state.set_state(AdminBroadcastFSM.message_text)
    
    await callback.message.answer(
        f"{Emoji.MEGAPHONE} <b>Отправьте сообщение "
        f"для рассылки всем пользователям.</b>\n\n"
        f"Поддерживается HTML-разметка.",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@constructor_router.message(
    StateFilter(AdminBroadcastFSM.message_text)
)
async def admin_broadcast_send(
    message: Message,
    state: FSMContext
):
    """
    Admin: send global broadcast.
    """
    if message.text == f"{Emoji.CROSS} Отмена":
        await state.clear()
        return await message.answer(
            "Отменено.", reply_markup=main_menu_kb()
        )
    
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.clear()
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(User.telegram_id)
        )
        user_ids = [row[0] for row in result.all()]
    
    sent = 0
    failed = 0
    
    status_msg = await message.answer(
        f"{Emoji.LOADING} Рассылка на "
        f"{len(user_ids)} пользователей..."
    )
    
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(
                uid, message.text
            )
            sent += 1
        except Exception:
            failed += 1
        
        if (i + 1) % 20 == 0:
            await status_msg.edit_text(
                f"{Emoji.LOADING} Рассылка: "
                f"{i + 1}/{len(user_ids)} "
                f"(отправлено: {sent}, ошибок: {failed})"
            )
        
        await asyncio.sleep(0.1)
    
    await status_msg.edit_text(
        f"{Emoji.MEGAPHONE} <b>Рассылка завершена!</b>\n\n"
        f"{Emoji.CHECK} Отправлено: {sent}\n"
        f"{Emoji.CROSS} Ошибок: {failed}"
    )


# ═══════════════════════════════════════════════════════════
# SHOP BOT ROUTER
# ═══════════════════════════════════════════════════════════

def create_shop_router(bot_record: ShopBot) -> Router:
    """
    Create router for shop-type child bot.
    Handles product browsing, payments, purchases, profile.
    """
    shop_router = Router()
    
    # ── /start Handler ──────────────────────────────────────
    
    @shop_router.message(CommandStart())
    async def shop_start(message: Message):
        """
        Handle /start in shop bot.
        Shows welcome message and main menu.
        """
        async with async_session_maker() as session:
            await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username
            )
        
        welcome = bot_record.welcome_message or (
            f"{Emoji.LOLZ} Добро пожаловать в "
            f"<b>{bot_record.bot_name}</b>!\n\n"
            f"Здесь можно купить донат "
            f"для игр Supercell.\n"
            f"Выберите действие:"
        )
        
        await message.answer(
            welcome,
            reply_markup=shop_menu_kb()
        )
    
    
    # ── Buy Donate Handler ──────────────────────────────────
    
    @shop_router.message(
        F.text == f"{Emoji.SHOPPING_CART} Купить донат"
    )
    async def buy_donate(message: Message):
        """
        Show game categories for purchase.
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(Category).where(
                    Category.bot_id == bot_record.id
                )
            )
            cats = result.scalars().all()
        
        if not cats:
            return await message.answer(
                "😔 Пока нет доступных категорий."
            )
        
        await message.answer(
            f"{Emoji.LOLZ} Выберите игру:",
            reply_markup=inline_kb([
                (c.name, f"shop_cat:{c.id}")
                for c in cats
            ])
        )
    
    
    # ── Show Products in Category ───────────────────────────
    
    @shop_router.callback_query(F.data.startswith("shop_cat:"))
    async def show_products(callback: CallbackQuery):
        """
        Show products in selected category.
        """
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
            return await callback.answer(
                "В этой категории пока нет товаров.",
                show_alert=True
            )
        
        await callback.message.answer(
            f"{Emoji.PACKAGE} <b>{cat.name}</b>:",
            reply_markup=inline_kb([
                (
                    f"{p.name} — {p.price} руб",
                    f"shop_product:{p.id}"
                )
                for p in products
            ])
        )
        await callback.answer()
    
    
    # ── Product Detail ──────────────────────────────────────
    
    @shop_router.callback_query(
        F.data.startswith("shop_product:")
    )
    async def product_detail(callback: CallbackQuery):
        """
        Show product details with payment options.
        """
        product_id = int(callback.data.split(":")[1])
        
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
        
        if not product or not product.is_available:
            return await callback.answer(
                "Товар недоступен.", show_alert=True
            )
        
        text = (
            f"{Emoji.SHOPPING_BAGS} <b>{product.name}</b>"
            f"\n\n"
            f"{product.description or 'Описание отсутствует'}"
            f"\n\n"
            f"{Emoji.MONEY} Цена: <b>{product.price} руб</b>"
        )
        
        kb = payment_method_kb(product_id, bot_record)
        
        if not kb.inline_keyboard:
            return await callback.message.answer(
                text + "\n\n❌ Оплата временно недоступна."
            )
        
        await callback.message.answer(
            text + "\n\n💳 Выберите способ оплаты:",
            reply_markup=kb
        )
        await callback.answer()
    
    
    # ── Process Payment ─────────────────────────────────────
    
    async def process_payment(
        callback: CallbackQuery,
        product_id: int,
        method: str
    ):
        """
        Create payment for a product.
        
        Args:
            callback: Callback query
            product_id: Product ID
            method: Payment method (crypto/yoo/rolly)
        """
        async with async_session_maker() as session:
            product = await session.get(Product, product_id)
            
            if not product or not product.is_available:
                return await callback.answer("Товар недоступен.")
            
            # Validate payment method configuration
            if (
                method == "crypto"
                and not bot_record.crypto_bot_token
            ):
                return await callback.answer(
                    "❌ CryptoBot не настроен!",
                    show_alert=True
                )
            
            if (
                method == "yoo"
                and not bot_record.yoomoney_wallet
            ):
                return await callback.answer(
                    "❌ ЮMoney не настроен!",
                    show_alert=True
                )
            
            if (
                method == "rolly"
                and not is_rollypay_configured(bot_record)
            ):
                return await callback.answer(
                    "❌ RollyPay не настроен!",
                    show_alert=True
                )
            
            # Create purchase record
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
                api = CryptoBotAPI(
                    bot_record.crypto_bot_token
                )
                invoice = await api.create_invoice(
                    float(product.price),
                    f"Покупка: {product.name}",
                    str(purchase.id)
                )
                
                if invoice:
                    url = (
                        invoice.get("pay_url")
                        or invoice.get("bot_invoice_url", "")
                    )
                    payment_id = str(
                        invoice.get("invoice_id", purchase.id)
                    )
            
            elif method == "yoo":
                label = (
                    f"shop_{bot_record.id}_"
                    f"{product_id}_{int(time.time())}"
                )
                yoo = YooMoneyAPI(
                    bot_record.yoomoney_wallet
                )
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
                    payment_id = result.get(
                        "payment_id",
                        f"shop_{purchase.id}"
                    )
            
            if url:
                purchase.payment_id = payment_id
                await session.commit()
                
                await callback.message.answer(
                    f"{Emoji.RECEIPT} <b>Счёт создан!</b>\n\n"
                    f"Товар: {product.name}\n"
                    f"Сумма: {product.price} руб\n\n"
                    f"Нажмите «Оплатить» для перехода "
                    f"к оплате.",
                    reply_markup=payment_invoice_kb(
                        url, method, payment_id
                    )
                )
            else:
                await callback.answer(
                    "❌ Ошибка создания платежа!",
                    show_alert=True
                )
        
        await callback.answer()
    
    
    # ── Payment Method Handlers ─────────────────────────────
    
    @shop_router.callback_query(
        F.data.startswith("pay_crypto:")
    )
    async def pay_crypto(callback: CallbackQuery):
        """Handle CryptoBot payment"""
        product_id = int(callback.data.split(":")[1])
        await process_payment(callback, product_id, "crypto")
    
    
    @shop_router.callback_query(
        F.data.startswith("pay_yoo:")
    )
    async def pay_yoomoney(callback: CallbackQuery):
        """Handle YooMoney payment"""
        product_id = int(callback.data.split(":")[1])
        await process_payment(callback, product_id, "yoo")
    
    
    @shop_router.callback_query(
        F.data.startswith("pay_rolly:")
    )
    async def pay_rollypay(callback: CallbackQuery):
        """Handle RollyPay payment"""
        product_id = int(callback.data.split(":")[1])
        await process_payment(callback, product_id, "rolly")
    
    
    # ── Check Payment Status ────────────────────────────────
    
    @shop_router.callback_query(
        F.data.startswith("check_pay:")
    )
    async def shop_check_payment(callback: CallbackQuery):
        """
        Check payment status in shop bot.
        Confirms payment and triggers auto-delivery.
        """
        parts = callback.data.split(":")
        method = parts[1]
        payment_id = parts[2]
        
        await callback.answer(
            f"{Emoji.LOADING} Проверяю оплату..."
        )
        
        is_paid = False
        
        async with async_session_maker() as session:
            # Find purchase
            result = None
            if payment_id.isdigit():
                result = await session.execute(
                    select(Purchase).where(
                        (Purchase.payment_id == payment_id)
                        | (Purchase.id == int(payment_id))
                    ).order_by(Purchase.id.desc())
                )
            else:
                result = await session.execute(
                    select(Purchase)
                    .where(Purchase.payment_id == payment_id)
                    .order_by(Purchase.id.desc())
                )
            
            purchase = (
                result.scalar_one_or_none()
                if result else None
            )
            
            # Already completed
            if purchase and purchase.status == "completed":
                is_paid = True
            
            # Check via CryptoBot
            elif (
                method == "crypto"
                and bot_record.crypto_bot_token
            ):
                invoice_id = None
                if payment_id.isdigit():
                    invoice_id = int(payment_id)
                elif (
                    purchase
                    and purchase.payment_id
                    and purchase.payment_id.isdigit()
                ):
                    invoice_id = int(purchase.payment_id)
                
                if invoice_id:
                    api = CryptoBotAPI(
                        bot_record.crypto_bot_token
                    )
                    status = await api.check_invoice(
                        invoice_id
                    )
                    if status == "paid":
                        is_paid = True
            
            # Check via RollyPay
            elif (
                method == "rolly"
                and is_rollypay_configured(bot_record)
            ):
                check_id = (
                    purchase.payment_id
                    if purchase and purchase.payment_id
                    else payment_id
                )
                
                api = RollyPayAPI(
                    bot_record.rollypay_terminal_id,
                    bot_record.rollypay_api_key,
                    bot_record.rollypay_signing_secret
                )
                result_check = await api.check_payment(
                    check_id
                )
                
                if (
                    result_check
                    and result_check.get("status") == "paid"
                ):
                    is_paid = True
            
            # Process payment confirmation
            if (
                is_paid
                and purchase
                and purchase.status != "completed"
            ):
                purchase.status = "completed"
                
                # Get product for auto-delivery
                product = await session.get(
                    Product, purchase.product_id
                )
                
                # Update user statistics
                user = await get_or_create_user(
                    session,
                    purchase.user_id,
                    None
                )
                
                current_spent = (
                    getattr(
                        user, 'total_spent',
                        Decimal("0.00")
                    )
                    or Decimal("0.00")
                )
                current_purchases = (
                    getattr(
                        user, 'total_purchases', 0
                    )
                    or 0
                )
                
                user.total_spent = (
                    current_spent + purchase.amount
                )
                user.total_purchases = (
                    current_purchases + 1
                )
                
                await session.commit()
                
                product_name = (
                    product.name if product else "Товар"
                )
                
                # Send confirmation
                await callback.message.answer(
                    f"{Emoji.CHECK} "
                    f"<b>Оплата подтверждена!</b>\n\n"
                    f"{Emoji.PARTY} Спасибо за покупку!\n"
                    f"{Emoji.SHOPPING_BAGS} {product_name}\n"
                    f"{Emoji.MONEY} {purchase.amount} руб"
                )
                
                # Auto-delivery
                if product and product.auto_deliver_text:
                    try:
                        delivery_text = (
                            f"{Emoji.GIFT} "
                            f"<b>Ваш заказ:</b>\n\n"
                            f"Товар: {product.name}\n\n"
                            f"{product.auto_deliver_text}"
                        )
                        
                        await (
                            callback.message.bot
                            .send_message(
                                purchase.user_id,
                                delivery_text
                            )
                        )
                        
                        purchase.delivered_text = (
                            product.auto_deliver_text
                        )
                        await session.commit()
                        
                    except Exception as e:
                        logger.error(
                            f"Failed to deliver product "
                            f"{product.id}: {e}"
                        )
                        
                        # Notify admin about delivery failure
                        try:
                            alert_text = (
                                f"{Emoji.WARNING} "
                                f"<b>Ошибка выдачи!</b>\n"
                                f"Покупка #{purchase.id}\n"
                                f"Товар: {product.name}\n"
                                f"Покупатель: "
                                f"{purchase.user_id}\n"
                                f"Ошибка: {str(e)}"
                            )
                            await (
                                callback.message.bot
                                .send_message(
                                    bot_record.admin_id,
                                    alert_text
                                )
                            )
                        except Exception:
                            pass
                
                # Support info
                if bot_record.support_username:
                    await callback.message.answer(
                        f"{Emoji.PHONE} По вопросам: "
                        f"@{bot_record.support_username}"
                    )
            
            elif is_paid:
                await callback.message.answer(
                    f"{Emoji.CHECK} Оплата уже была "
                    f"подтверждена."
                )
            else:
                await callback.message.answer(
                    f"{Emoji.CLOCK} <b>Оплата ещё "
                    f"не поступила.</b>\n\n"
                    f"Попробуйте позже или обратитесь "
                    f"в поддержку."
                )
    
    
    # ── My Purchases ────────────────────────────────────────
    
    @shop_router.message(
        F.text == f"{Emoji.PACKAGE} Мои покупки"
    )
    async def my_purchases(message: Message):
        """
        Show user's purchase history in this shop.
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(Purchase, Product)
                .join(
                    Product,
                    Purchase.product_id == Product.id
                )
                .where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.bot_id == bot_record.id
                )
                .order_by(Purchase.created_at.desc())
                .limit(20)
            )
            rows = result.all()
        
        if not rows:
            return await message.answer(
                f"{Emoji.PACKAGE} У вас пока нет "
                f"покупок в этом магазине."
            )
        
        text = f"{Emoji.PACKAGE} <b>Ваши покупки:</b>\n\n"
        
        status_map = {
            "pending": f"{Emoji.CLOCK} Ожидает",
            "completed": f"{Emoji.CHECK} Завершена"
        }
        
        total_amount = Decimal("0.00")
        completed = 0
        
        for purchase, product in rows:
            text += (
                f"{Emoji.SHOPPING_BAGS} {product.name}\n"
                f"   {Emoji.MONEY} {purchase.amount} руб | "
                f"{status_map.get(purchase.status, purchase.status)}\n"
                f"   {Emoji.CALENDAR} "
                f"{purchase.created_at.strftime('%d.%m.%Y %H:%M')}"
                f"\n\n"
            )
            
            if purchase.status == "completed":
                total_amount += purchase.amount
                completed += 1
        
        text += (
            f"━━━━━━━━━━━━━━━\n"
            f"{Emoji.CHART} Завершено: {completed} покупок\n"
            f"{Emoji.MONEY} Потрачено: {total_amount} руб"
        )
        
        if len(text) > 4000:
            text = (
                text[:4000]
                + "\n\n...(показаны последние покупки)"
            )
        
        await message.answer(text)
    
    
    # ── Profile ─────────────────────────────────────────────
    
    @shop_router.message(F.text == f"{Emoji.PROFILE} Профиль")
    async def shop_profile(message: Message):
        """
        Show user profile in shop context.
        """
        async with async_session_maker() as session:
            user = await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username
            )
            
            total_spent_bot = await session.scalar(
                select(
                    func.coalesce(
                        func.sum(Purchase.amount), 0
                    )
                )
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
            
            total_spent_all = (
                getattr(
                    user, 'total_spent', Decimal("0.00")
                )
                or Decimal("0.00")
            )
            
            total_purchases_all = (
                getattr(user, 'total_purchases', 0) or 0
            )
        
        text = (
            f"{Emoji.PROFILE} <b>Профиль в "
            f"«{bot_record.bot_name}»</b>\n\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"📛 @{message.from_user.username or '—'}\n"
            f"{Emoji.COINS} Баланс: {user.balance} руб\n\n"
            f"━━━ {Emoji.CHART} В этом магазине ━━━\n"
            f"{Emoji.CHECK} Завершено: {purchases_count}\n"
            f"{Emoji.CLOCK} Ожидают: {pending_count}\n"
            f"{Emoji.MONEY} Потрачено: "
            f"{total_spent_bot} руб\n\n"
            f"━━━ {Emoji.GLOBE} Общая статистика ━━━\n"
            f"{Emoji.SHOPPING_CART} Всего: "
            f"{total_purchases_all}\n"
            f"{Emoji.COINS} Потрачено: "
            f"{total_spent_all} руб"
        )
        
        if bot_record.support_username:
            text += (
                f"\n\n{Emoji.PHONE} Поддержка: "
                f"@{bot_record.support_username}"
            )
        
        await message.answer(text)
    
    
    # ── Support ─────────────────────────────────────────────
    
    @shop_router.message(F.text == f"{Emoji.PHONE} Поддержка")
    async def shop_support(message: Message):
        """
        Show support contact information.
        """
        if bot_record.support_username:
            await message.answer(
                f"{Emoji.PHONE} <b>Поддержка</b>\n\n"
                f"По всем вопросам обращайтесь:\n"
                f"@{bot_record.support_username}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Написать в поддержку",
                                url=(
                                    f"https://t.me/"
                                    f"{bot_record.support_username}"
                                )
                            )
                        ]
                    ]
                )
            )
        else:
            await message.answer(
                f"{Emoji.PHONE} Поддержка пока "
                f"не настроена."
            )
    
    return shop_router


# ═══════════════════════════════════════════════════════════
# FEEDBACK BOT ROUTER
# ═══════════════════════════════════════════════════════════

def create_feedback_router(bot_record: ShopBot) -> Router:
    """
    Create router for feedback-type child bot.
    Handles message forwarding to admin and reply delivery.
    """
    fb_router = Router()
    
    # ── /start Handler ──────────────────────────────────────
    
    @fb_router.message(CommandStart())
    async def fb_start(message: Message):
        """
        Handle /start in feedback bot.
        Shows welcome message with feedback instructions.
        """
        async with async_session_maker() as session:
            await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username
            )
        
        welcome = bot_record.welcome_message or (
            f"{Emoji.FEEDBACK} <b>{bot_record.bot_name}</b>"
            f"\n\n"
            f"Отправьте ваше сообщение, "
            f"и администратор ответит вам."
        )
        
        kb = feedback_menu_kb(bot_record)
        
        await message.answer(welcome, reply_markup=kb)
    
    
    # ── Profile Handler ─────────────────────────────────────
    
    @fb_router.message(F.text == f"{Emoji.PROFILE} Профиль")
    async def fb_profile(message: Message):
        """
        Show user profile in feedback bot.
        """
        async with async_session_maker() as session:
            user = await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username
            )
            
            msg_count = await session.scalar(
                select(func.count(FeedbackMessage.id))
                .where(
                    FeedbackMessage.bot_id == bot_record.id,
                    FeedbackMessage.user_id == message.from_user.id
                )
            )
            
            replied_count = await session.scalar(
                select(func.count(FeedbackMessage.id))
                .where(
                    FeedbackMessage.bot_id == bot_record.id,
                    FeedbackMessage.user_id == message.from_user.id,
                    FeedbackMessage.is_replied == True
                )
            )
        
        text = (
            f"{Emoji.PROFILE} <b>Профиль</b>\n\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"📛 @{message.from_user.username or '—'}\n"
            f"📝 Сообщений: {msg_count}\n"
            f"✅ Отвечено: {replied_count}"
        )
        
        if bot_record.support_username:
            text += (
                f"\n\n{Emoji.PHONE} Поддержка: "
                f"@{bot_record.support_username}"
            )
        
        await message.answer(text)
    
    
    # ── Support Handler ─────────────────────────────────────
    
    @fb_router.message(F.text == f"{Emoji.PHONE} Поддержка")
    async def fb_support(message: Message):
        """
        Show support contact in feedback bot.
        """
        if bot_record.support_username:
            await message.answer(
                f"{Emoji.PHONE} <b>Поддержка</b>\n\n"
                f"По вопросам: "
                f"@{bot_record.support_username}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Написать",
                                url=(
                                    f"https://t.me/"
                                    f"{bot_record.support_username}"
                                )
                            )
                        ]
                    ]
                )
            )
        else:
            await message.answer(
                f"{Emoji.PHONE} Поддержка не настроена."
            )
    
    
    # ── Main Message Handler ────────────────────────────────
    
    @fb_router.message()
    async def handle_feedback_message(message: Message):
        """
        Handle ANY message in feedback bot.
        - Menu buttons are ignored
        - Feedback button gets custom reply
        - Regular messages get standard confirmation
        """
        
        # Ignore menu buttons
        if message.text in [
            f"{Emoji.PROFILE} Профиль",
            f"{Emoji.PHONE} Поддержка"
        ]:
            return
        
        # Ignore reply commands
        if message.text and message.text.startswith("/reply_"):
            return
        
        # Check if feedback button was pressed
        is_feedback_button = (
            bot_record.feedback_button_text
            and message.text == bot_record.feedback_button_text
        )
        
        async with async_session_maker() as session:
            # Save feedback message to database
            fb_msg = FeedbackMessage(
                bot_id=bot_record.id,
                user_id=message.from_user.id,
                admin_id=bot_record.admin_id,
                message_text=message.text or "[медиа]"
            )
            session.add(fb_msg)
            await session.commit()
            await session.refresh(fb_msg)
            
            # Forward message to admin
            try:
                admin_text = (
                    f"{Emoji.MAIL} <b>Новое сообщение "
                    f"#{fb_msg.id}</b>\n"
                    f"👤 От: <code>{message.from_user.id}</code>"
                )
                
                if message.from_user.username:
                    admin_text += (
                        f"\n📛 @{message.from_user.username}"
                    )
                
                admin_text += (
                    f"\n📝 {(message.text or '[медиа]')[:1000]}"
                    f"\n\n📌 Бот: {bot_record.bot_name} "
                    f"(ID: {bot_record.id})"
                    f"\n\nОтветить через панель управления ботом"
                )
                
                await message.bot.send_message(
                    bot_record.admin_id,
                    admin_text
                )
                
                logger.info(
                    f"Feedback #{fb_msg.id} forwarded to admin "
                    f"{bot_record.admin_id}"
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to forward message to admin: {e}"
                )
        
        # Send reply to user
        if is_feedback_button and bot_record.feedback_button_reply:
            # Custom reply for feedback button
            await message.answer(bot_record.feedback_button_reply)
        else:
            # Standard confirmation for regular messages
            await message.answer(
                f"{Emoji.CHECK} Ваше сообщение #{fb_msg.id} "
                f"отправлено! Администратор ответит "
                f"в ближайшее время."
            )
    
    return fb_router


# ═══════════════════════════════════════════════════════════
# BOT RUNNER
# ═══════════════════════════════════════════════════════════

# Dictionary to track running bot tasks
running_tasks: dict[int, asyncio.Task] = {}


async def run_shop_bot(bot_record: ShopBot):
    """
    Start a child bot (shop or feedback type).
    
    Args:
        bot_record: ShopBot database record
    """
    if bot_record.id in running_tasks:
        logger.warning(
            f"Bot {bot_record.id} is already running"
        )
        return
    
    # Create bot instance
    bot = Bot(
        token=bot_record.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Create dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    
    # Include appropriate router based on bot type
    if bot_record.bot_type == "shop":
        dp.include_router(create_shop_router(bot_record))
    else:
        dp.include_router(create_feedback_router(bot_record))
    
    async def polling():
        """Polling function for the bot"""
        logger.info(
            f"Bot '{bot_record.bot_name}' "
            f"(id={bot_record.id}, "
            f"type={bot_record.bot_type}) started"
        )
        try:
            await dp.start_polling(
                bot,
                allowed_updates=[
                    "message",
                    "callback_query"
                ]
            )
        except Exception as e:
            logger.error(
                f"Bot {bot_record.id} error: {e}"
            )
        finally:
            await bot.session.close()
    
    # Start polling in background task
    task = asyncio.create_task(polling())
    running_tasks[bot_record.id] = task


async def start_all_active_bots():
    """
    Start all active bots on application launch.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(ShopBot).where(
                ShopBot.is_active == True
            )
        )
        bots = result.scalars().all()
    
    logger.info(
        f"Starting {len(bots)} active bots..."
    )
    
    for bot_record in bots:
        await run_shop_bot(bot_record)
        await asyncio.sleep(0.5)  # Small delay between starts
    
    logger.info("All active bots started!")


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

async def main():
    """
    Main entry point for the constructor bot.
    1. Initialize database
    2. Start all active child bots
    3. Start the constructor bot
    """
    
    logger.info("=" * 50)
    logger.info("Starting Bot Constructor...")
    logger.info("=" * 50)
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Create constructor bot
    logger.info("Creating constructor bot...")
    constructor_bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Set bot commands
    try:
        await constructor_bot.set_my_commands([
            BotCommand(
                command="start",
                description="Главное меню"
            ),
            BotCommand(
                command="admin",
                description="Админ-панель"
            ),
        ])
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.warning(
            f"Failed to set bot commands: {e}"
        )
    
    # Setup dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(constructor_router)
    
    # Start all active child bots
    await start_all_active_bots()
    
    logger.info("Constructor bot is starting...")
    logger.info("=" * 50)
    
    # Start polling
    try:
        await dp.start_polling(
            constructor_bot,
            allowed_updates=[
                "message",
                "callback_query"
            ]
        )
    finally:
        # Graceful shutdown
        logger.info("Shutting down...")
        
        await constructor_bot.session.close()
        
        # Cancel all running child bot tasks
        for task in running_tasks.values():
            task.cancel()
        
        # Wait for tasks to finish
        await asyncio.gather(
            *running_tasks.values(),
            return_exceptions=True
        )
        
        # Close database connection
        await engine.dispose()
        
        logger.info("Shutdown complete.")


# ═══════════════════════════════════════════════════════════
# APPLICATION START
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Entry point when running directly.
    Uses asyncio.run() for proper async execution.
    """
    asyncio.run(main())
