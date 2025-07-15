# ruff: noqa: E501
# pylint: disable=logging-fstring-interpolation
import asyncio
import json
import os
import uuid

from typing import Any

import httpx

from a2a.client import A2ACardResolver
from a2a.types import (
    AgentCard,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)
from .remote_agent_connection import RemoteAgentConnections, TaskUpdateCallback
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.tool_context import ToolContext


load_dotenv()


def convert_part(part: Part, tool_context: ToolContext):
    """Convert a part to text. Only text parts are supported."""
    if part.type == 'text':
        return part.text

    return f'Unknown type: {part.type}'


def convert_parts(parts: list[Part], tool_context: ToolContext):
    """Convert parts to text."""
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def create_send_message_payload(
    text: str, task_id: str | None = None, context_id: str | None = None
) -> dict[str, Any]:
    """Helper function to create the payload for sending a task."""
    payload: dict[str, Any] = {
        'message': {
            'role': 'user',
            'parts': [{'type': 'text', 'text': text}],
            'messageId': uuid.uuid4().hex,
        },
    }

    if task_id:
        payload['message']['taskId'] = task_id

    if context_id:
        payload['message']['contextId'] = context_id
    return payload


class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''

    async def _async_init_components(
        self, remote_agent_addresses: list[str]
    ) -> None:
        """Asynchronous part of initialization."""
        # Use a single httpx.AsyncClient for all card resolutions for efficiency
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    client, address
                )  # Constructor is sync
                try:
                    card = (
                        await card_resolver.get_agent_card()
                    )  # get_agent_card is async

                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError as e:
                    print(
                        f'ERROR: Failed to get agent card from {address}: {e}'
                    )
                except Exception as e:  # Catch other potential errors
                    print(
                        f'ERROR: Failed to initialize connection for {address}: {e}'
                    )

        # Populate self.agents using the logic from original __init__ (via list_remote_agents)
        agent_info = []
        for agent_detail_dict in self.list_remote_agents():
            agent_info.append(json.dumps(agent_detail_dict))
        self.agents = '\n'.join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: list[str],
        task_callback: TaskUpdateCallback | None = None,
    ) -> 'RoutingAgent':
        """Create and asynchronously initialize an instance of the RoutingAgent."""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def create_agent(self) -> Agent:
        """Create an instance of the RoutingAgent."""
        # Change from the preview model to the stable model
        model_id = 'gemini-2.5-flash'  # ✅ Use stable model
        # model_id = 'gemini-2.5-flash-preview-04-17'  # ❌ Preview model not available
        
        print(f'Using model: {model_id}')
        return Agent(
            model=model_id,
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'Intelligent routing agent that delegates user queries to appropriate specialized agents'
            ),
            tools=[
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        """Generate the root instruction for the RoutingAgent."""
        current_agent = self.check_active_agent(context)
        return f"""
        **Role:** You are an intelligent Routing Agent that analyzes user queries and delegates them to the most appropriate specialized remote agents.

        **Core Functionality:**
        - **Query Analysis:** Analyze user requests to understand intent and required capabilities
        - **Agent Selection:** Choose the most suitable agent based on query content and agent capabilities
        - **Task Delegation:** Route requests to appropriate agents using the `send_message` function
        - **Response Coordination:** Present complete responses from remote agents to users

        **Routing Decision Framework:**

        **1. Property-Related Queries:**
        - **Keywords:** property, apartment, house, rent, buy, real estate, Prague, Czech Republic, Praha
        - **Agent:** Property Hunting Agent
        - **Examples:**
          - "Find me properties in Praha 2 with price between 20000 and 25000 CZK"
          - "I need a 2-bedroom apartment in Prague"
          - "Show me rental properties in Czech Republic"
          - "What's the real estate market like in Prague?"

        **2. Job-Related Queries:**
        - **Keywords:** job, career, employment, work, position, vacancy, hiring, CV, resume
        - **Agent:** Job Hunting Agent
        - **Examples:**
          - "Find me software developer jobs in Prague"
          - "I'm looking for marketing positions"
          - "Help me with my CV for tech jobs"

        **3. Weather-Related Queries:**
        - **Keywords:** weather, temperature, forecast, climate, rain, sunny, cold, hot
        - **Agent:** Weather Agent
        - **Examples:**
          - "What's the weather like in Prague today?"
          - "Will it rain tomorrow?"
          - "Temperature forecast for this week"

        **4. Currency-Related Queries:**
        - **Keywords:** currency, exchange rate, convert, currency conversion, currency exchange
        - **Agent:** Currency Agent
        - **Examples:**
          - "What's the exchange rate between USD and EUR?"
          - "How much is 1000 CZK in USD?"
          - "Convert 500 EUR to GBP"

        **4. Multi-Agent Scenarios:**
        - If a query requires multiple agents, delegate to the primary agent first
        - Let that agent coordinate with others if needed
        - Example: "I want to move to Prague - help me find a job and apartment"

        **Routing Rules:**

        **Priority 1: Direct Agent Matching**
        - Match query keywords to agent capabilities
        - Use exact agent names when available

        **Priority 2: Context-Based Routing**
        - Consider conversation context and previous interactions
        - Route follow-up questions to the same agent when appropriate

        **Priority 3: Default Routing**
        - If no clear match, ask user for clarification
        - Suggest available agents and their capabilities

        **Agent Communication Guidelines:**

        **Task Description Best Practices:**
        - Include all relevant context from the user's request
        - Provide specific details (location, price range, requirements)
        - Include any constraints or preferences mentioned
        - Add conversation context if relevant

        **Example Task Descriptions:**
        - "User is looking for a 2-bedroom apartment in Praha 2 with budget between 20000-25000 CZK. They prefer modern buildings with good transport connections."
        - "User needs software developer jobs in Prague. They have 3 years of experience in Python and React."

        **Response Handling:**
        - Present complete responses from remote agents
        - If an agent asks for clarification, relay that to the user
        - If an agent provides incomplete information, ask for more details
        - Maintain conversation flow and context

        **Available Agents:**
        {self.agents}

        **Currently Active Agent:** {current_agent['active_agent']}

        **Instructions for You:**
        1. **Always analyze the user's query first** - identify keywords and intent
        2. **Select the most appropriate agent** based on the routing framework above
        3. **Use the `send_message` function** with the agent name and a comprehensive task description
        4. **Include all relevant context** in the task description
        5. **Present the complete response** from the remote agent to the user
        6. **If no clear match exists**, ask the user to clarify or suggest available agents

        **Remember:** Your job is to be the intelligent router that connects users to the right specialized agents. Always prioritize user intent and provide seamless delegation.
                """

    def check_active_agent(self, context: ReadonlyContext):
        state = context.state
        if (
            'session_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'active_agent' in state
        ):
            return {'active_agent': f'{state["active_agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            if 'session_id' not in state:
                state['session_id'] = str(uuid.uuid4())
            state['session_active'] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.cards:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f'Found agent card: {card.model_dump(exclude_none=True)}')
            print('=' * 100)
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """Sends a task to a remote agent.

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive task description including user request and context.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'Agent {agent_name} not found')
        state = tool_context.state
        state['active_agent'] = agent_name
        client = self.remote_agent_connections[agent_name]

        if not client:
            raise ValueError(f'Client not available for {agent_name}')
        task_id = state['task_id'] if 'task_id' in state else str(uuid.uuid4())

        if 'context_id' in state:
            context_id = state['context_id']
        else:
            context_id = str(uuid.uuid4())

        message_id = ''
        metadata = {}
        if 'input_message_metadata' in state:
            metadata.update(**state['input_message_metadata'])
            if 'message_id' in state['input_message_metadata']:
                message_id = state['input_message_metadata']['message_id']
        if not message_id:
            message_id = str(uuid.uuid4())

        payload = {
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': task}
                ],  # Use the 'task' argument here
                'messageId': message_id,
            },
        }

        if task_id:
            payload['message']['taskId'] = task_id

        if context_id:
            payload['message']['contextId'] = context_id

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = await client.send_message(
            message_request=message_request
        )
        print(
            'send_response',
            send_response.model_dump_json(exclude_none=True, indent=2),
        )

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print('received non-success response. Aborting get task ')
            return None

        response_content = send_response.root.model_dump_json(exclude_none=True)
        json_content = json.loads(response_content)

        resp = []
        if json_content.get("result", {}).get("parts"):
            for parts in json_content["result"]["parts"]:
                if parts.get("text"):
                    resp.append(parts["text"])
        return resp


def _get_initialized_routing_agent_sync() -> Agent:
    """Synchronously creates and initializes the RoutingAgent."""

    async def _async_main() -> Agent:
        routing_agent_instance = await RoutingAgent.create(
            remote_agent_addresses=[
                os.getenv('PROPERTY_AGENT_URL', 'http://localhost:10001'),
                # os.getenv('WEATHER_AGENT_URL', 'http://localhost:10002'),
                # Add more agents as needed:
                os.getenv('CURRENCY_AGENT_URL', 'http://localhost:10003'),
                # os.getenv('WEATHER_AGENT_URL', 'http://localhost:10004'),
            ]
        )
        return routing_agent_instance.create_agent()

    try:
        return asyncio.run(_async_main())
    except RuntimeError as e:
        if 'asyncio.run() cannot be called from a running event loop' in str(e):
            print(
                f'Warning: Could not initialize RoutingAgent with asyncio.run(): {e}. '
                'This can happen if an event loop is already running (e.g., in Jupyter). '
                'Consider initializing RoutingAgent within an async function in your application.'
            )
        raise


root_agent = _get_initialized_routing_agent_sync()