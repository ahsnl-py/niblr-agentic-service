"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[Dict[str, Any]] = None
    structured_data: Optional[Dict[str, Any]] = None  # Structured JSON data from agent


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None  # Optional: Vertex AI agent_session_id to resume chat history
    user_id: Optional[str] = None  # Optional: deprecated, user is determined from auth token


class ChatResponse(BaseModel):
    """Chat response model."""
    messages: List[Dict[str, Any]]
    session_id: str


class StreamChunk(BaseModel):
    """Stream chunk model for SSE."""
    type: str  # "text", "tool_call", "tool_response", "complete"
    content: str
    metadata: Optional[Dict[str, Any]] = None


# Authentication models
class UserRegister(BaseModel):
    """User registration model."""
    email: str
    username: str
    password: str
    full_name: Optional[str] = None


class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User response model."""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Session management models
class SessionCreate(BaseModel):
    """Create session model."""
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionUpdate(BaseModel):
    """Update session model."""
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    """Session response model."""
    id: int
    user_id: int
    agent_session_id: str
    title: Optional[str] = None
    metadata: Optional[str] = Field(None, alias="session_metadata")  # Map session_metadata from DB to metadata in API
    created_at: datetime
    updated_at: datetime
    last_activity: datetime

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both alias and original name


class ChatMessageResponse(BaseModel):
    """Chat message response model for history.
    
    Matches the format returned by /api/chat endpoint for seamless frontend integration.
    """
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    structured_data: Optional[Dict[str, Any]] = None  # Structured JSON data (properties/jobs)

