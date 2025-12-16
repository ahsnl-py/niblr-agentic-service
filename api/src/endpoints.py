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
                
                # Check if event has result.artifacts structure (like test_client response)
                # This is the final result structure with artifacts
                artifacts_text = extract_text_from_artifacts(event_dict)
                if artifacts_text:
                    # Extract structured JSON from artifacts text
                    structured_data = extract_json_from_text(artifacts_text)
                    
                    content = json.dumps(structured_data, indent=2) if structured_data else artifacts_text
                    all_responses.append(create_agent_response(
                        content=content,
                        structured_data=structured_data
                    ))
                
                # Check if event has state/output_key with structured data
                # The agent stores structured output in state under output_key
                event_state = None
                if isinstance(event_dict, dict):
                    event_state = event_dict.get("state", {})
                else:
                    # Try to get state from original event object
                    if hasattr(event, 'state'):
                        state_obj = event.state
                    if isinstance(state_obj, dict):
                        event_state = state_obj
                    elif hasattr(state_obj, '__dict__'):
                        event_state = state_obj.__dict__
                    elif hasattr(state_obj, 'model_dump'):
                        event_state = state_obj.model_dump()
                
                if event_state:
                    # Check for property_listings or job_listings in state
                    property_listings = event_state.get("property_listings") if isinstance(event_state, dict) else None
                    job_listings = event_state.get("job_listings") if isinstance(event_state, dict) else None
                    
                    if property_listings or job_listings:
                        # Found structured data in state - use it instead of text
                        structured_data = property_listings if property_listings else job_listings
                        # Convert to dict if it's a string
                        if isinstance(structured_data, str):
                            try:
                                structured_data = json.loads(structured_data)
                            except json.JSONDecodeError:
                                pass
                        
                        if isinstance(structured_data, dict):
                            # Add structured response - this is the actual JSON from the agent
                            all_responses.append(create_agent_response(
                                content=json.dumps(structured_data, indent=2),
                                structured_data=structured_data
                            ))
                
                # Process each event - make sure we capture all responses
                # Process content.parts for intermediate messages (like delegation messages)
                event_responses = process_agent_response(event_dict)
                if event_responses:
                    # Filter out duplicate text responses if we already have artifacts
                    if artifacts_text:
                        # Keep only non-text responses (like delegation messages with metadata)
                        # and responses that don't match the artifacts text
                        filtered_responses = []
                        for r in event_responses:
                            content = r.get("content", "").strip()
                            # Keep if it has metadata (delegation/tool call messages)
                            if r.get("metadata") is not None:
                                filtered_responses.append(r)
                            # Keep if it's different from artifacts_text (to avoid duplicates)
                            elif content and content != artifacts_text.strip():
                                # Also check if it's not the same JSON
                                try:
                                    if json.loads(content) != extract_json_from_text(artifacts_text):
                                        filtered_responses.append(r)
                                except (json.JSONDecodeError, ValueError):
                                    # Not JSON, so keep if different text
                                    filtered_responses.append(r)
                        
                        if filtered_responses:
                            all_responses.extend(filtered_responses)
                    else:
                        all_responses.extend(event_responses)
            
            # After streaming completes, try to get state from the session
            # The agent stores structured output in state under output_key
            try:
                # Try to get session state if available
                if hasattr(REMOTE_APP, 'get_session_state'):
                    session_state = REMOTE_APP.get_session_state(user_id=user_id, session_id=session_id)
                    if session_state:
                        property_listings = session_state.get("property_listings")
                        job_listings = session_state.get("job_listings")
                        
                        if property_listings or job_listings:
                            structured_data = property_listings if property_listings else job_listings
                            if isinstance(structured_data, str):
                                try:
                                    structured_data = json.loads(structured_data)
                                except json.JSONDecodeError:
                                    pass
                            
                            if isinstance(structured_data, dict):
                                # Replace or add structured response
                                # Remove any existing markdown responses and add JSON
                                all_responses = [
                                    r for r in all_responses 
                                    if r.get("metadata") is not None or not r.get("content", "").startswith("Here are")
                                ]
                                all_responses.append(create_agent_response(
                                    content=json.dumps(structured_data, indent=2),
                                    structured_data=structured_data
                                ))
            except Exception:
                # If we can't access session state, continue with what we have
                pass
            
            # Filter and prioritize responses
            # Remove short intermediate messages and prioritize structured data
            filtered_responses = []
            has_structured_response = False
            
            for response in all_responses:
                content = response.get("content", "")
                metadata = response.get("metadata")
                
                # Always keep delegation messages and tool calls (they have metadata)
                if metadata is not None:
                    filtered_responses.append(response)
                # Always keep responses with structured_data (final JSON response - works for both properties and jobs)
                elif response.get("structured_data"):
                    filtered_responses.append(response)
                    has_structured_response = True
                # Check if content contains JSON indicators - re-extract if needed
                # This handles both property listings ("properties") and job listings ("jobs")
                elif '{' in content and ('"properties"' in content or '"jobs"' in content):
                    # This looks like a JSON response, make sure we extract it
                    structured_data = extract_json_from_text(content)
                    if structured_data:
                        response["structured_data"] = structured_data
                        # Ensure metadata is set for agent responses
                        if not response.get("metadata"):
                            response["metadata"] = {"title": "Agent Response"}
                        filtered_responses.append(response)
                        has_structured_response = True
                    else:
                        # Even if extraction failed, keep it if it looks like JSON
                        # This ensures we don't lose job listings or property listings
                        filtered_responses.append(response)
                # Keep longer text responses that might be final responses
                elif len(content.strip()) > 50:
                    filtered_responses.append(response)
                # If we don't have structured data yet, keep shorter responses too (they might contain JSON)
                elif not has_structured_response and len(content.strip()) > 10:
                    filtered_responses.append(response)
            
            # Use filtered responses if we filtered any out
            if filtered_responses:
                all_responses = filtered_responses
            
            # If no responses, return default
            if not all_responses:
                all_responses = [create_agent_response(
                    content="No response from agent",
                    metadata=None
                )]
            
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

