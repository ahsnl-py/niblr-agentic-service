"""Session management endpoints."""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from .database import get_db
from .db_models import User, Session as DBSession
from .models import (
    SessionCreate,
    SessionUpdate,
    SessionResponse,
    ChatMessageResponse,
    ChatResponse,
)
from .auth import get_current_user
from .config import REMOTE_APP, AGENT_ENGINE_RESOURCE_NAME, PROJECT_ID, LOCATION
from .utils import parse_session_info_to_messages

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def find_session_by_agent_id(
    agent_session_id: str,
    user_id: int,
    db: Session
) -> Optional[DBSession]:
    """Find a session by Vertex AI agent_session_id.
    
    Args:
        agent_session_id: Vertex AI session ID (string)
        user_id: User ID to filter by
        db: Database session
        
    Returns:
        DBSession if found, None otherwise
    """
    return db.query(DBSession).filter(
        DBSession.agent_session_id == agent_session_id,
        DBSession.user_id == user_id
    ).first()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session."""
    # Create agent engine session
    agent_session = REMOTE_APP.create_session(user_id=str(current_user.id))
    agent_session_id = agent_session["id"]
    
    # Create database session record
    db_session = DBSession(
        user_id=current_user.id,
        agent_session_id=agent_session_id,
        title=session_data.title,
        session_metadata=json.dumps(session_data.metadata) if session_data.metadata else None
    )
    
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    
    return db_session


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """List all sessions for the current user."""
    sessions = db.query(DBSession).filter(
        DBSession.user_id == current_user.id
    ).order_by(
        DBSession.last_activity.desc()
    ).offset(skip).limit(limit).all()
    
    return sessions


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific session by Vertex AI agent_session_id.
    
    Args:
        session_id: Vertex AI session ID (e.g., "4726576737192771584")
    """
    db_session = find_session_by_agent_id(session_id, current_user.id, db)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return db_session


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    session_data: SessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a session (e.g., change title or metadata).
    
    Args:
        session_id: Vertex AI session ID
    """
    db_session = find_session_by_agent_id(session_id, current_user.id, db)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update fields
    if session_data.title is not None:
        db_session.title = session_data.title
    if session_data.metadata is not None:
        db_session.session_metadata = json.dumps(session_data.metadata)
    
    db_session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_session)
    
    return db_session


@router.post("/{session_id}/save", response_model=SessionResponse)
async def save_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save/update a session's last activity timestamp.
    
    Args:
        session_id: Vertex AI session ID
    """
    db_session = find_session_by_agent_id(session_id, current_user.id, db)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update last activity
    db_session.last_activity = datetime.utcnow()
    db.commit()
    db.refresh(db_session)
    
    return db_session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a session from both Vertex AI and the database.
    
    Uses the Vertex AI Agent Engine Sessions API as documented:
    https://docs.cloud.google.com/agent-builder/agent-engine/sessions/manage-sessions-api#delete_a_session
    
    Args:
        session_id: Vertex AI session ID
    """
    db_session = find_session_by_agent_id(session_id, current_user.id, db)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    try:
        REMOTE_APP.delete_session(
            user_id=str(current_user.id),
            session_id=session_id)

    except Exception:
        # Silently fail - Vertex AI session deletion failure shouldn't prevent database cleanup
        pass
    
    # Delete from database (always attempt, even if Vertex AI deletion failed)
    db.delete(db_session)
    db.commit()
    
    return None


@router.get("/{session_id}/history", response_model=ChatResponse)
async def get_session_history(
    session_id: str,  # agent_session_id
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history from Vertex AI session.
    
    Parses the session events to extract:
    - User messages (questions/requests)
    - Function calls (agent delegations)
    - Artifact results (structured JSON responses)
    
    Args:
        session_id: Vertex AI agent_session_id
        
    Returns:
        List of chat messages in chronological order
    """
    # Find session in database
    db_session = find_session_by_agent_id(session_id, current_user.id, db)
    
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    user_id = str(current_user.id)
    agent_session_id = db_session.agent_session_id
    
    # Try get_session method first (returns session_info with events)
    session_info = REMOTE_APP.get_session(
        user_id=user_id,
        session_id=agent_session_id
    )

    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    messages = parse_session_info_to_messages(session_info)

    # Return in the same shape as /api/chat (messages + session_id)
    return ChatResponse(
        messages=messages,
        session_id=agent_session_id
    )
