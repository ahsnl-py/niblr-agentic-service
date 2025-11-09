import gradio as gr

from typing import List, Dict, Any
from pprint import pformat
import vertexai
from vertexai import agent_engines
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
if not PROJECT_ID or not LOCATION:
    raise ValueError(
        "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION must be set before launching the UI."
    )

vertexai.init(project=PROJECT_ID, location=LOCATION)

USER_ID = "default_user"

REMOTE_APP = agent_engines.get(os.getenv("AGENT_ENGINE_RESOURCE_NAME"))
SESSION_ID = REMOTE_APP.create_session(user_id=USER_ID)["id"]


async def get_response_from_agent(
    message: str,
    history: List[Dict[str, Any]],
) -> str:
    """Send the message to the backend and get a response.

    Args:
        message: Text content of the message.
        history: List of previous message dictionaries in the conversation.

    Returns:
        Text response from the backend service.
    """
    # try:

    default_response = "No response from agent"

    responses = []

    for event in REMOTE_APP.stream_query(
        user_id=USER_ID,
        session_id=SESSION_ID,
        message=message,
    ):
        parts = event.get("content", {}).get("parts", [])
        if parts:
            for part in parts:
                if part.get("function_call"):
                    formatted_call = f"```python\n{pformat(part.get('function_call'), indent=2, width=80)}\n```"
                    responses.append(
                        gr.ChatMessage(
                            role="assistant",
                            content=f"{part.get('function_call').get('name')}:\n{formatted_call}",
                            metadata={"title": "🛠️ Tool Call"},
                        )
                    )
                elif part.get("function_response"):
                    formatted_response = f"```python\n{pformat(part.get('function_response'), indent=2, width=80)}\n```"

                    responses.append(
                        gr.ChatMessage(
                            role="assistant",
                            content=formatted_response,
                            metadata={"title": "⚡ Tool Response"},
                        )
                    )
                elif part.get("text"):
                    responses.append(
                        gr.ChatMessage(
                            role="assistant",
                            content=part.get("text"),
                        )
                    )
                else:
                    formatted_unknown_parts = f"Unknown agent response part:\n\n```python\n{pformat(part, indent=2, width=80)}\n```"

                    responses.append(
                        gr.ChatMessage(
                            role="assistant",
                            content=formatted_unknown_parts,
                        )
                    )

    if not responses:
        yield default_response

    yield responses


if __name__ == "__main__":
    demo = gr.ChatInterface(
        get_response_from_agent,
        title="Niblr Agentic Concierge",
        description="This assistant can help you to find the best agent for your needs.",
        type="messages",
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=8080,
    )