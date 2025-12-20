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
from .utils import extract_json_from_text, extract_text_from_artifacts

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
    
    agent_session_id = db_session.agent_session_id
    try:
        session_name = f"{AGENT_ENGINE_RESOURCE_NAME}/sessions/{agent_session_id}"
        REMOTE_APP.delete_session(name=session_name)
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
    
    # Try to get session info from Vertex AI
    history = []
    user_id = str(current_user.id)
    agent_session_id = db_session.agent_session_id
    
    try:
        # Try get_session method first (returns session_info with events)
        session_info = None
        if hasattr(REMOTE_APP, 'get_session'):
            try:
                session_info = REMOTE_APP.get_session(
                    user_id=user_id,
                    session_id=agent_session_id
                )
            except Exception:
                pass
        
        # Fallback: Try get_session_state if get_session doesn't exist or failed
        if not session_info and hasattr(REMOTE_APP, 'get_session_state'):
            try:
                session_state = REMOTE_APP.get_session_state(
                    user_id=user_id,
                    session_id=agent_session_id
                )
                # Check if session_state has events (might be nested)
                if isinstance(session_state, dict):
                    if "events" in session_state:
                        session_info = session_state
                    elif "session_info" in session_state:
                        session_info = session_state.get("session_info")
            except Exception:
                pass
        
        if session_info and isinstance(session_info, dict):
            # Extract events from session_info
            events = session_info.get("events", [])
            
            if events:
                # Parse each event in chronological order
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    
                    content = event.get("content", {})
                    if not isinstance(content, dict):
                        continue
                    
                    parts = content.get("parts", [])
                    role = content.get("role", "")
                    author = event.get("author", "")
                    timestamp = event.get("timestamp")
                    
                    # Convert timestamp to datetime if available
                    event_timestamp = None
                    if timestamp:
                        try:
                            event_timestamp = datetime.fromtimestamp(timestamp)
                        except (ValueError, TypeError, OSError):
                            pass
                    
                    # Process each part in the event
                    for part in parts:
                        if not isinstance(part, dict):
                            continue
                        
                        # 1. Extract user messages (text from user role)
                        if role == "user" and author == "user":
                            text = part.get("text")
                            if text and text.strip():
                                history.append(ChatMessageResponse(
                                    role="user",
                                    content=text.strip(),
                                    timestamp=event_timestamp,
                                    metadata=None
                                ))
                        
                        # 2. Extract function calls (agent delegations)
                        function_call = part.get("functionCall")
                        if function_call and isinstance(function_call, dict):
                            func_name = function_call.get("name", "")
                            func_args = function_call.get("args", {})
                            
                            # Format function call message (similar to endpoints.py)
                            if func_name == "send_task":
                                agent_name = func_args.get("agent_name", "Unknown Agent")
                                task = func_args.get("task", "")
                                history.append(ChatMessageResponse(
                                    role="assistant",
                                    content=f"🤖 **{agent_name}**\n\n{task}",
                                    timestamp=event_timestamp,
                                    metadata={"title": "🔄 Delegating to Agent"}
                                ))
                            else:
                                # Other function calls
                                func_name_display = func_name.replace("_", " ").title()
                                history.append(ChatMessageResponse(
                                    role="assistant",
                                    content=f"🛠️ Calling {func_name_display}...",
                                    timestamp=event_timestamp,
                                    metadata={"title": "🛠️ Tool Call"}
                                ))
                        
                        # 3. Extract artifact results (functionResponse with artifacts)
                        function_response = part.get("functionResponse")
                        if function_response and isinstance(function_response, dict):
                            response_data = function_response.get("response", {})
                            if isinstance(response_data, dict):
                                result = response_data.get("result", {})
                                if isinstance(result, dict):
                                    # Extract artifacts text (reuse logic from endpoints.py)
                                    artifacts_text = None
                                    
                                    artifacts = result.get("artifacts", [])
                                    if artifacts:
                                        for artifact in artifacts:
                                            if isinstance(artifact, dict):
                                                artifact_parts = artifact.get("parts", [])
                                                for artifact_part in artifact_parts:
                                                    if isinstance(artifact_part, dict):
                                                        if artifact_part.get("kind") == "text" and artifact_part.get("text"):
                                                            artifacts_text = artifact_part.get("text")
                                                            break
                                                        elif artifact_part.get("text") and "kind" not in artifact_part:
                                                            artifacts_text = artifact_part.get("text")
                                                            break
                                    
                                    if artifacts_text:
                                        # Parse JSON from artifacts (reuse extract_json_from_text)
                                        structured_data = extract_json_from_text(artifacts_text)
                                        
                                        # Format content similar to endpoints.py
                                        if structured_data:
                                            content_text = json.dumps(structured_data, indent=2)
                                            metadata = {"title": "Agent Response"}
                                        else:
                                            content_text = artifacts_text
                                            metadata = None
                                        
                                        history.append(ChatMessageResponse(
                                            role="assistant",
                                            content=content_text,
                                            timestamp=event_timestamp,
                                            metadata=metadata,
                                            structured_data=structured_data  # Include structured_data for frontend
                                        ))
                        
                            # 4. Extract final text responses (model role with text, but not function calls)
                            # Only if we haven't already captured it as artifact or function call
                            if role == "model" and author != "user":
                                text = part.get("text")
                                # Only add if it's not already captured as artifact or function call
                                if (text and text.strip() and 
                                    not part.get("functionCall") and 
                                    not part.get("functionResponse")):
                                    # Check if it contains JSON (similar to endpoints.py logic)
                                    # Check for JSON indicators first
                                    structured_data = None
                                    content_stripped = text.strip()
                                    
                                    # Similar to endpoints.py: check if content looks like JSON
                                    if '{' in content_stripped and ('"properties"' in content_stripped or '"jobs"' in content_stripped):
                                        structured_data = extract_json_from_text(content_stripped)
                                    
                                    # Format response similar to endpoints.py
                                    if structured_data:
                                        content_text = json.dumps(structured_data, indent=2)
                                        metadata = {"title": "Agent Response"}
                                    else:
                                        content_text = content_stripped
                                        # Only add metadata for actual agent responses (not short messages)
                                        if len(content_stripped) > 50 and not content_stripped.startswith("🤖") and not content_stripped.startswith("🛠️"):
                                            metadata = {"title": "Agent Response"}
                                        else:
                                            metadata = None
                                    
                                    history.append(ChatMessageResponse(
                                        role="assistant",
                                        content=content_text,
                                        timestamp=event_timestamp,
                                        metadata=metadata,
                                        structured_data=structured_data  # Include structured_data for frontend
                                    ))
        
        # If no history found, return empty list
        if not history:
            history.append(ChatMessageResponse(
                role="system",
                content="No conversation history available for this session.",
                timestamp=None,
                metadata=None
            ))
    
    except Exception as e:
        # Log error but don't fail - return error message
        history.append(ChatMessageResponse(
            role="system",
            content=f"Error retrieving history: {str(e)}",
            timestamp=None,
            metadata={"error": str(e)}
        ))
    
    # Return in the same shape as /api/chat (messages + session_id)
    return ChatResponse(
        messages=[msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in history],
        session_id=agent_session_id
    )
