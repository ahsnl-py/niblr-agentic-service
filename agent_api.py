"""
FastAPI REST API endpoint for the Niblr Agentic Concierge.
This API can be consumed by a React frontend or any HTTP client.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pprint import pformat
import vertexai
from vertexai import agent_engines
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
if not PROJECT_ID or not LOCATION:
    raise ValueError(
        "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION must be set before launching the API."
    )

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Initialize FastAPI app
app = FastAPI(
    title="Niblr Agentic Concierge API",
    description="REST API for the Niblr Agentic Concierge chatbot",
    version="1.0.0"
)

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session management
USER_ID = "default_user"
REMOTE_APP = agent_engines.get(os.getenv("AGENT_ENGINE_RESOURCE_NAME"))
SESSION_ID = REMOTE_APP.create_session(user_id=USER_ID)["id"]


# Request/Response Models
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # Optional: for multi-session support
    user_id: Optional[str] = None  # Optional: for multi-user support


class ChatResponse(BaseModel):
    messages: List[Dict[str, Any]]
    session_id: str


class StreamChunk(BaseModel):
    type: str  # "text", "tool_call", "tool_response", "complete"
    content: str
    metadata: Optional[Dict[str, Any]] = None


# Helper function to process agent response
def process_agent_response(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process agent event and return formatted messages."""
    responses = []
    parts = event.get("content", {}).get("parts", [])
    
    # Track if we should skip the next function_response (for send_task)
    skip_next_response = False
    
    if parts:
        for part in parts:
            if part.get("function_call"):
                func_call = part.get("function_call")
                func_name = func_call.get("name", "")
                
                # Special handling for send_task - show only agent name and task
                if func_name == "send_task":
                    func_args = func_call.get("args", {})
                    agent_name = func_args.get("agent_name", "Unknown Agent")
                    task = func_args.get("task", "")
                    
                    # Create a clean, user-friendly message
                    content = f"🤖 **{agent_name}**\n\n{task}"
                    responses.append({
                        "role": "assistant",
                        "content": content,
                        "metadata": {"title": "🔄 Delegating to Agent"}
                    })
                    skip_next_response = True  # Skip the verbose response
                else:
                    # For other function calls, show simplified version
                    func_name_display = func_name.replace("_", " ").title()
                    responses.append({
                        "role": "assistant",
                        "content": f"🛠️ Calling {func_name_display}...",
                        "metadata": {"title": "🛠️ Tool Call"}
                    })
            
            elif part.get("function_response"):
                # For send_task, extract the actual agent response text
                if skip_next_response:
                    skip_next_response = False
                    func_response = part.get("function_response", {})
                    
                    # Try to extract the actual text response from the nested structure
                    # The response structure: response.result.artifacts[].parts[].text
                    response_text = None
                    if isinstance(func_response, dict):
                        result = func_response.get("response", {}).get("result", {})
                        if isinstance(result, dict):
                            artifacts = result.get("artifacts", [])
                            if artifacts:
                                # Get text from the first artifact's parts
                                for artifact in artifacts:
                                    parts_list = artifact.get("parts", [])
                                    for part_item in parts_list:
                                        if isinstance(part_item, dict) and "text" in part_item:
                                            response_text = part_item.get("text")
                                            break
                                    if response_text:
                                        break
                    
                    # If we found text, add it as a response
                    if response_text:
                        responses.append({
                            "role": "assistant",
                            "content": response_text,
                            "metadata": None
                        })
                    # Otherwise, skip silently (don't show verbose response)
                    continue
                
                # For other responses, show simplified version
                responses.append({
                    "role": "assistant",
                    "content": "✅ Tool execution completed",
                    "metadata": {"title": "⚡ Tool Response"}
                })
            
            elif part.get("text"):
                responses.append({
                    "role": "assistant",
                    "content": part.get("text"),
                    "metadata": None
                })
            else:
                formatted_unknown = f"Unknown agent response part:\n\n```python\n{pformat(part, indent=2, width=80)}\n```"
                responses.append({
                    "role": "assistant",
                    "content": formatted_unknown,
                    "metadata": None
                })
    
    return responses


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
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    
    Accepts a user message and returns the agent's response.
    Supports both single request-response and can be extended for streaming.
    
    Example request:
    ```json
    {
        "message": "Find me a 2-bedroom apartment in Praha 2",
        "session_id": "optional-session-id",
        "user_id": "optional-user-id"
    }
    ```
    
    Example response:
    ```json
    {
        "messages": [
            {
                "role": "assistant",
                "content": "I'll help you find a 2-bedroom apartment...",
                "metadata": null
            }
        ],
        "session_id": "session-id"
    }
    ```
    """
    try:
        # Use provided session_id or default
        session_id = request.session_id or SESSION_ID
        user_id = request.user_id or USER_ID
        
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
            # Process each event
            responses = process_agent_response(event)
            all_responses.extend(responses)
        
        # If no responses, return default
        if not all_responses:
            all_responses = [{
                "role": "assistant",
                "content": "No response from agent",
                "metadata": None
            }]
        
        return ChatResponse(
            messages=all_responses,
            session_id=session_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    
    Returns a stream of chunks as the agent processes the request.
    Useful for real-time updates in React frontend.
    
    Example usage in React:
    ```javascript
    const eventSource = new EventSource('/api/chat/stream', {
        method: 'POST',
        body: JSON.stringify({ message: 'Hello' })
    });
    
    eventSource.onmessage = (event) => {
        const chunk = JSON.parse(event.data);
        console.log(chunk);
    };
    ```
    """
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate_stream():
        try:
            session_id = request.session_id or SESSION_ID
            user_id = request.user_id or USER_ID
            
            if not request.message.strip():
                yield f"data: {json.dumps({'type': 'error', 'content': 'Message cannot be empty'})}\n\n"
                return
            
            # Stream query from agent
            for event in REMOTE_APP.stream_query(
                user_id=user_id,
                session_id=session_id,
                message=request.message,
            ):
                responses = process_agent_response(event)
                
                for response in responses:
                    chunk = StreamChunk(
                        type="text" if response.get("metadata") is None else "tool_call",
                        content=response["content"],
                        metadata=response.get("metadata")
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'complete', 'content': ''})}\n\n"
        
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


@app.post("/api/session/new")
async def create_session(user_id: Optional[str] = None):
    """
    Create a new chat session.
    
    Returns a new session_id that can be used for subsequent requests.
    """
    try:
        user_id = user_id or USER_ID
        session = REMOTE_APP.create_session(user_id=user_id)
        return {
            "session_id": session["id"],
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8083))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

