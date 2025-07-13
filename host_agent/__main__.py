"""Copyright 2025 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import asyncio
import traceback
from typing import AsyncIterator, List, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .routing_agent import root_agent as routing_agent
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default_user"
    session_id: str = "default_session"

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[Dict[str, Any]] = []
    tool_responses: List[Dict[str, Any]] = []
    error: str = None

class HealthResponse(BaseModel):
    status: str
    message: str


APP_NAME = 'routing_app'
SESSION_SERVICE = InMemorySessionService()
ROUTING_AGENT_RUNNER = Runner(
    agent=routing_agent,
    app_name=APP_NAME,
    session_service=SESSION_SERVICE,
)

# Create FastAPI app
app = FastAPI(
    title="A2A Host Agent API",
    description="API for interacting with the A2A Host Agent",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_response_from_agent(
    message: str,
    user_id: str = "default_user",
    session_id: str = "default_session"
) -> ChatResponse:
    """Get response from host agent via API."""
    try:
        # Create session if it doesn't exist
        await SESSION_SERVICE.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

        event_iterator: AsyncIterator[Event] = ROUTING_AGENT_RUNNER.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role='user', parts=[types.Part(text=message)]
            ),
        )

        final_response_text = ''
        tool_calls = []
        tool_responses = []

        async for event in event_iterator:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        tool_calls.append({
                            "name": part.function_call.name,
                            "arguments": part.function_call.model_dump(exclude_none=True)
                        })
                    elif part.function_response:
                        tool_responses.append({
                            "name": part.function_response.name,
                            "response": part.function_response.response
                        })
            
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = ''.join(
                        [p.text for p in event.content.parts if p.text]
                    )
                elif event.actions and event.actions.escalate:
                    final_response_text = f'Agent escalated: {event.error_message or "No specific message."}'
                break

        return ChatResponse(
            response=final_response_text,
            tool_calls=tool_calls,
            tool_responses=tool_responses
        )

    except Exception as e:
        print(f'Error in get_response_from_agent (Type: {type(e)}): {e}')
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while processing your request: {str(e)}"
        )


@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        message="A2A Host Agent API is running"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the host agent and get response."""
    return await get_response_from_agent(
        message=request.message,
        user_id=request.user_id,
        session_id=request.session_id
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        message="A2A Host Agent API is running"
    )


async def main():
    """Main FastAPI app."""
    print('Creating ADK session...')
    await SESSION_SERVICE.create_session(
        app_name=APP_NAME, user_id="default_user", session_id="default_session"
    )
    print('ADK session created successfully.')
    print('Launching FastAPI server...')


if __name__ == '__main__':
    asyncio.run(main())
    uvicorn.run(
        "host_agent.__main__:app",
        host="0.0.0.0",
        port=8083,
        reload=True
    )