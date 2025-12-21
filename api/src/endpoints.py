"""API endpoints for the Niblr Agentic Concierge."""

import json
from typing import Optional
from datetime import datetime
from fastapi import HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .config import REMOTE_APP
from .database import get_db
from .db_models import User, Session as DBSession
from .auth import get_current_user
from .models import ChatRequest, ChatResponse, StreamChunk
from .utils import (
    extract_json_from_text,
    extract_text_from_artifacts,
    convert_event_to_dict,
)
from .response_processor import create_agent_response, process_agent_response


def register_endpoints(app):
    """Register all API endpoints with the FastAPI app."""
    
    @app.get("/")
    async def root():
        """Health check endpoint."""
        return {
            "status": "ok",
            "service": "Niblr Agentic Concierge API",
            "version": "1.0.0"
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """
        Main chat endpoint.
        
        Requires authentication. Automatically creates a new Vertex AI session if session_id is not provided.
        The session_id should be the Vertex AI agent_session_id (returned from previous chat calls or session list).
        
        When a new chat is started (no session_id), a Vertex AI session is created automatically and saved to the database.
        The returned session_id can be used to resume the conversation and access chat history.
        
        Example request (new chat):
        ```json
        {
            "message": "Find me a 2-bedroom apartment in Praha 2"
        }
        ```
        
        Example request (resume existing chat):
        ```json
        {
            "message": "What about properties in Praha 3?",
            "session_id": "700358670323548160"  // Vertex AI agent_session_id from previous response
        }
        ```
        
        Example response:
        ```json
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": "I'll help you find a 2-bedroom apartment...",
                    "metadata": {"title": "Agent Response"}
                }
            ],
            "session_id": "700358670323548160"  // Vertex AI session ID - use this to resume chat
        }
        ```
        """
        try:
            # Get or create session based on agent_session_id (Vertex AI session ID)
            db_session = None
            agent_session_id = None
            
            if request.session_id:
                # Look up session by agent_session_id (Vertex AI session ID), not database ID
                db_session = db.query(DBSession).filter(
                    DBSession.agent_session_id == request.session_id,
                    DBSession.user_id == current_user.id
                ).first()
                
                if db_session:
                    agent_session_id = db_session.agent_session_id
                    # Update last activity
                    db_session.last_activity = datetime.utcnow()
                    db.commit()
            
            # If no valid session found, create a new Vertex AI session
            if not agent_session_id:
                # Create new Vertex AI session (this is what tracks chat history)
                agent_session = REMOTE_APP.create_session(user_id=str(current_user.id))
                agent_session_id = agent_session["id"]
                
                # Generate title from first user message (first 50 characters or first sentence)
                title = None
                if request.message and request.message.strip():
                    message_stripped = request.message.strip()
                    # Use first 50 characters, or first sentence if shorter
                    if len(message_stripped) <= 50:
                        title = message_stripped
                    else:
                        # Try to find sentence break
                        sentence_end = message_stripped.find('.')
                        if sentence_end > 0 and sentence_end <= 50:
                            title = message_stripped[:sentence_end + 1]
                        else:
                            # Just use first 50 chars
                            title = message_stripped[:50].rstrip() + "..."
                
                # Save the Vertex AI session to database for user's session management
                db_session = DBSession(
                    user_id=current_user.id,
                    agent_session_id=agent_session_id,
                    title=title
                )
                db.add(db_session)
                db.commit()
                db.refresh(db_session)
            
            user_id = str(current_user.id)
            session_id = agent_session_id  # Use Vertex AI session ID for agent queries
            
            if not request.message.strip():
                raise HTTPException(status_code=400, detail="Message cannot be empty")
            
            # Track timing and metadata
            first_timestamp = None
            last_timestamp = None
            collected_metadata = {
                "usage_metadata": None,
                "agent_name": None,
                "author": None,
                "model_version": None,
            }
            
            # Collect all responses
            all_responses = []
            
            # Stream query from agent
            for event in REMOTE_APP.stream_query(
                user_id=user_id,
                session_id=session_id,
                message=request.message,
            ):
                # Convert event to dict if it's not already
                event_dict = convert_event_to_dict(event)
                
                # Track timestamps for response time calculation
                event_timestamp = event_dict.get("timestamp")
                if event_timestamp:
                    if first_timestamp is None:
                        first_timestamp = event_timestamp
                    last_timestamp = event_timestamp
                
                # Collect metadata from events
                if event_dict.get("usage_metadata") and not collected_metadata["usage_metadata"]:
                    collected_metadata["usage_metadata"] = event_dict.get("usage_metadata")
                
                if event_dict.get("author") and not collected_metadata["author"]:
                    collected_metadata["author"] = event_dict.get("author")
                
                if event_dict.get("model_version") and not collected_metadata["model_version"]:
                    collected_metadata["model_version"] = event_dict.get("model_version")
                
                # Extract agent name from artifacts (event-2.json structure)
                content_parts = event_dict.get("content", {}).get("parts", [])
                for part in content_parts:
                    func_response = part.get("function_response", {})
                    if func_response:
                        response_obj = func_response.get("response", {})
                        result = response_obj.get("result", {})
                        artifacts = result.get("artifacts", [])
                        for artifact in artifacts:
                            artifact_name = artifact.get("name")
                            if artifact_name and not collected_metadata["agent_name"]:
                                collected_metadata["agent_name"] = artifact_name
                
                # Extract content from artifacts (preserve as-is)
                artifacts_text = extract_text_from_artifacts(event_dict)
                if artifacts_text:
                    # Extract structured JSON if present, but keep original text
                    structured_data = extract_json_from_text(artifacts_text)
                    
                    # Use original artifacts text as content (preserve as-is)
                    content = artifacts_text
                    
                    response = {
                        "role": "assistant",
                        "content": content,
                    }
                    
                    if structured_data:
                        response["structured_data"] = structured_data
                    
                    all_responses.append(response)
                
                # Extract content from text parts (event-3.json structure)
                for part in content_parts:
                    if part.get("text"):
                        text_content = part.get("text", "").strip()
                        if text_content:
                            # Extract structured JSON if present
                            structured_data = extract_json_from_text(text_content)
                            
                            # Use original text as content (preserve as-is)
                            content = text_content
                            
                            response = {
                                "role": "assistant",
                                "content": content,
                            }
                            
                            if structured_data:
                                response["structured_data"] = structured_data
                            
                            all_responses.append(response)
            
            # Calculate response time if we have timestamps
            if first_timestamp and last_timestamp:
                response_time = last_timestamp - first_timestamp
                collected_metadata["response_time_seconds"] = round(response_time, 3)
            
            # If no responses, return default
            if not all_responses:
                all_responses = [{
                    "role": "assistant",
                    "content": "No response from agent",
                }]
            
            # Clean up metadata - only include non-None values
            clean_metadata = {k: v for k, v in collected_metadata.items() if v is not None}
            
            # Add metadata to all responses if we collected any
            if clean_metadata:
                for response in all_responses:
                    if response.get("metadata"):
                        # Merge with existing metadata
                        response["metadata"].update(clean_metadata)
                    else:
                        response["metadata"] = clean_metadata.copy()
            
            # Return the Vertex AI agent_session_id so user can resume chat history
            return ChatResponse(
                messages=all_responses,
                session_id=agent_session_id  # Return Vertex AI session ID for chat history
            )
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    
    @app.post("/api/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """
        Streaming chat endpoint using Server-Sent Events (SSE).
        
        Requires authentication. Automatically creates a new Vertex AI session if session_id is not provided.
        The session_id should be the Vertex AI agent_session_id to resume chat history.
        Returns a stream of chunks as the agent processes the request.
        Useful for real-time updates in React frontend.
        
        Example usage in React:
        ```javascript
        const eventSource = new EventSource('/api/chat/stream', {
            method: 'POST',
            headers: { 
                'Authorization': 'Bearer <token>',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                message: 'Hello',
                session_id: '700358670323548160'  // Optional: Vertex AI session ID
            })
        });
        
        eventSource.onmessage = (event) => {
            const chunk = JSON.parse(event.data);
            console.log(chunk);
        };
        ```
        """
        async def generate_stream():
            try:
                # Get or create session based on agent_session_id (Vertex AI session ID)
                db_session = None
                agent_session_id = None
                
                if request.session_id:
                    # Look up session by agent_session_id (Vertex AI session ID)
                    db_session = db.query(DBSession).filter(
                        DBSession.agent_session_id == request.session_id,
                        DBSession.user_id == current_user.id
                    ).first()
                    
                    if db_session:
                        agent_session_id = db_session.agent_session_id
                        db_session.last_activity = datetime.utcnow()
                        db.commit()
                
                # If no valid session found, create a new Vertex AI session
                if not agent_session_id:
                    agent_session = REMOTE_APP.create_session(user_id=str(current_user.id))
                    agent_session_id = agent_session["id"]
                    
                    # Generate title from first user message (first 50 characters or first sentence)
                    title = None
                    if request.message and request.message.strip():
                        message_stripped = request.message.strip()
                        # Use first 50 characters, or first sentence if shorter
                        if len(message_stripped) <= 50:
                            title = message_stripped
                        else:
                            # Try to find sentence break
                            sentence_end = message_stripped.find('.')
                            if sentence_end > 0 and sentence_end <= 50:
                                title = message_stripped[:sentence_end + 1]
                            else:
                                # Just use first 50 chars
                                title = message_stripped[:50].rstrip() + "..."
                    
                    # Save to database
                    db_session = DBSession(
                        user_id=current_user.id,
                        agent_session_id=agent_session_id,
                        title=title
                    )
                    db.add(db_session)
                    db.commit()
                
                user_id = str(current_user.id)
                session_id = agent_session_id  # Use Vertex AI session ID for agent queries
                
                if not request.message.strip():
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Message cannot be empty'})}\n\n"
                    return
                
                # Stream query from agent
                for event in REMOTE_APP.stream_query(
                    user_id=user_id,
                    session_id=session_id,
                    message=request.message,
                ):
                    event_dict = convert_event_to_dict(event)
                    responses = process_agent_response(event_dict)
                    
                    for response in responses:
                        chunk = StreamChunk(
                            type="text" if response.get("metadata") is None else "tool_call",
                            content=response["content"],
                            metadata=response.get("metadata")
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"
                
                # Send completion signal with session_id
                yield f"data: {json.dumps({'type': 'complete', 'content': '', 'session_id': agent_session_id})}\n\n"
            
            except Exception as e:
                error_chunk = StreamChunk(
                    type="error",
                    content=f"Error: {str(e)}",
                    metadata=None
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    # Note: Session creation is now handled by /api/sessions endpoint
    # This endpoint is deprecated - use POST /api/sessions instead

