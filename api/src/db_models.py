"""SQLAlchemy database models for User and Session."""

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base


class SubscriptionType(str, enum.Enum):
    """Subscription type enumeration."""
    FREE = "free"
    PAID = "paid"


class User(Base):
    """User model for authentication and user management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    payment_methods = relationship("PaymentMethod", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """Session model for storing chat sessions."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_session_id = Column(String, nullable=False)  # The agent engine session ID
    title = Column(String, nullable=True)  # Optional title for the session
    session_metadata = Column(Text, nullable=True)  # JSON string for additional metadata (stored as session_metadata in DB, exposed as metadata in API)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)

    # Relationship to user
    user = relationship("User", back_populates="sessions")


class Subscription(Base):
    """Subscription model for managing user credits and subscription status."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Credit fields
    credits = Column(Integer, default=10, nullable=False)  # Free tier starts with 10 credits
    
    # Subscription fields
    subscription_type = Column(SQLEnum(SubscriptionType), default=SubscriptionType.FREE, nullable=False)
    has_unlimited_credits = Column(Boolean, default=False, nullable=False)  # True for paid unlimited plan
    subscription_started_at = Column(DateTime, nullable=True)  # When subscription started
    subscription_expires_at = Column(DateTime, nullable=True)  # When subscription expires (null for lifetime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to user (one-to-one)
    user = relationship("User", back_populates="subscription")


class PaymentMethod(Base):
    """Payment method model for storing user payment information."""
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Payment provider information (e.g., Stripe payment method ID)
    provider = Column(String, nullable=False, default="stripe")  # Payment provider name
    provider_payment_method_id = Column(String, nullable=False, index=True)  # External payment method ID
    provider_customer_id = Column(String, nullable=True, index=True)  # External customer ID
    
    # Card information (only store safe, non-sensitive data)
    card_last4 = Column(String(4), nullable=False)  # Last 4 digits of card
    card_brand = Column(String, nullable=True)  # Visa, Mastercard, Amex, etc.
    card_exp_month = Column(Integer, nullable=True)  # Expiration month (1-12)
    card_exp_year = Column(Integer, nullable=True)  # Expiration year
    
    # Billing information
    billing_name = Column(String, nullable=True)  # Name on card
    billing_address_line1 = Column(String, nullable=True)
    billing_address_line2 = Column(String, nullable=True)
    billing_city = Column(String, nullable=True)
    billing_state = Column(String, nullable=True)
    billing_postal_code = Column(String, nullable=True)
    billing_country = Column(String, nullable=True)
    
    # Status
    is_default = Column(Boolean, default=False, nullable=False)  # Default payment method
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to user
    user = relationship("User", back_populates="payment_methods")


class CatalogItem(Base):
    """Catalog item model for storing saved items from agent responses."""
    __tablename__ = "catalog_items"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_item_id = Column(String(50), nullable=False)  # property_id or job_id from agent response
    catalog_name = Column(String(50), nullable=False)  # 'property', 'job', etc.
    saved_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    agent_name = Column(String(255), nullable=True)
    source_message_id = Column(Text, nullable=True)
    session_id = Column(BigInteger, nullable=True)
    
    # Relationship to user
    user = relationship("User", backref="catalog_items")

