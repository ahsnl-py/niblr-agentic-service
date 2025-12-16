"""Authentication utilities for JWT tokens and password hashing.

Based on FastAPI authentication best practices from:
https://betterstack.com/community/guides/scaling-python/authentication-fastapi/
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from .database import get_db
from .db_models import User

# Load environment variables (ensure .env is loaded)
load_dotenv()

# Bcrypt configuration
BCRYPT_ROUNDS = 12

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Warn if using default secret key
if SECRET_KEY == "your-secret-key-change-this-in-production":
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Using default JWT_SECRET_KEY! This is insecure. Set JWT_SECRET_KEY in .env file.")

# OAuth2 scheme - tokenUrl should match your login endpoint
# auto_error=False allows us to handle missing tokens more gracefully
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=True)


def _prehash_password(password: str) -> bytes:
    """Pre-hash password with SHA256 to avoid bcrypt's 72-byte limit.
    
    This ensures passwords of any length can be hashed with bcrypt.
    Returns bytes (32 bytes) which is well under the 72-byte limit.
    """
    return hashlib.sha256(password.encode('utf-8')).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        # Pre-hash the plain password before verification
        prehashed = _prehash_password(plain_password)
        # Convert hashed_password string to bytes if needed
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode('utf-8')
        else:
            hashed_bytes = hashed_password
        return bcrypt.checkpw(prehashed, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password.
    
    First pre-hashes with SHA256 to avoid bcrypt's 72-byte limit,
    then hashes with bcrypt for secure storage.
    """
    # Pre-hash with SHA256 to ensure it's always under 72 bytes (32 bytes)
    prehashed = _prehash_password(password)
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(prehashed, salt)
    # Return as string for database storage
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        # Log the specific error for debugging
        import logging
        logger = logging.getLogger(__name__)
        error_msg = str(e)
        logger.warning(f"JWT verification failed: {error_msg}")
        # Check if it's a signature verification error (most common)
        if "Signature verification failed" in error_msg or "Invalid token" in error_msg:
            logger.warning(f"This usually means JWT_SECRET_KEY mismatch. Current key length: {len(SECRET_KEY) if SECRET_KEY else 0}")
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token.
    
    This follows the OAuth2 pattern from the FastAPI authentication guide.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please ensure you include 'Authorization: Bearer <token>' header.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception
    
    # Verify the token
    payload = verify_token(token)
    
    if payload is None:
        # Token is invalid or expired - provide helpful error message
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again at /api/auth/token to get a new token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user ID from token payload
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Look up user in database
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user ID in token: {user_id}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User with ID {user_id_int} not found. Token may be invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active user (alias for get_current_user)."""
    return current_user


def authenticate_user(username: str, password: str, db: Session) -> Optional[User]:
    """Authenticate a user by username/email and password.
    
    Returns the user if authentication succeeds, None otherwise.
    """
    # Find user by username or email
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    return user

