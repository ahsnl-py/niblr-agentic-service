"""Utility functions for subscription and credit management."""

from sqlalchemy.orm import Session
from .db_models import User, Subscription, SubscriptionType


def ensure_user_has_subscription(user: User, db: Session) -> Subscription:
    """Ensure a user has a subscription, creating one if missing.
    
    This provides backward compatibility for users created before subscriptions were added.
    
    Args:
        user: The user object
        db: Database session
        
    Returns:
        The user's subscription (created if it didn't exist)
    """
    if user.subscription:
        return user.subscription
    
    # Create default subscription if missing
    subscription = Subscription(
        user_id=user.id,
        credits=10,  # Default 10 free credits
        subscription_type=SubscriptionType.FREE,
        has_unlimited_credits=False
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    
    # Refresh user to load the new subscription
    db.refresh(user)
    
    return subscription


def check_user_has_credits(user: User, db: Session, required_credits: int = 1) -> bool:
    """Check if user has enough credits to perform an action.
    
    Args:
        user: The user object
        db: Database session
        required_credits: Number of credits required (default: 1)
        
    Returns:
        True if user has unlimited credits or enough credits, False otherwise
    """
    subscription = ensure_user_has_subscription(user, db)
    
    if subscription.has_unlimited_credits:
        return True
    
    return subscription.credits >= required_credits


def deduct_credits(user: User, db: Session, amount: int = 1) -> bool:
    """Deduct credits from user's subscription.
    
    Args:
        user: The user object
        db: Database session
        amount: Number of credits to deduct (default: 1)
        
    Returns:
        True if credits were deducted successfully, False if insufficient credits
    """
    subscription = ensure_user_has_subscription(user, db)
    
    # Don't deduct if user has unlimited credits
    if subscription.has_unlimited_credits:
        return True
    
    # Check if user has enough credits
    if subscription.credits < amount:
        return False
    
    # Deduct credits
    subscription.credits -= amount
    db.commit()
    db.refresh(subscription)
    
    return True

