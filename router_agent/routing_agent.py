import json
import uuid
from typing import List
import httpx

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from .remote_agent_connection import RemoteAgentConnections

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


class RoutingAgent:
    """The Routing agent.

    This is the agent responsible for choosing which remote agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        remote_agent_addresses: List[str],
    ):
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.remote_agent_addresses = remote_agent_addresses
        self.cards: dict[str, AgentCard] = {}
        self.agents = ""
        self.a2a_client_init_status = False

    def create_agent(self) -> Agent:
        return Agent(
            model="gemini-2.5-flash",
            name='Routing_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            before_agent_callback=self.before_agent_callback,
            description=(
                "This purchasing agent orchestrates the decomposition of the user purchase request into"
                " tasks that can be performed by the seller agents."
            ),
            tools=[
                self.send_task,
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
            "session_id" in state
            and "session_active" in state
            and state["session_active"]
            and "active_agent" in state
        ):
            return {"active_agent": f"{state['active_agent']}"}
        return {"active_agent": "None"}

    async def before_agent_callback(self, callback_context: CallbackContext):
        if not self.a2a_client_init_status:
            httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout=30))
            for address in self.remote_agent_addresses:
                card_resolver = A2ACardResolver(
                    base_url=address, httpx_client=httpx_client
                )
                try:
                    card = await card_resolver.get_agent_card()
                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=card.url
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                except httpx.ConnectError:
                    print(f"ERROR: Failed to get agent card from : {address}")
            agent_info = []
            for ra in self.list_remote_agents():
                agent_info.append(json.dumps(ra))
            self.agents = "\n".join(agent_info)
            self.a2a_client_init_status = True

    async def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if "session_active" not in state or not state["session_active"]:
            if "session_id" not in state:
                state["session_id"] = str(uuid.uuid4())
            state["session_active"] = True

    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.remote_agent_connections:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            print(f"Found agent card: {card.model_dump()}")
            print("=" * 100)
            remote_agent_info.append(
                {"name": card.name, "description": card.description}
            )
        return remote_agent_info

    def send_task(self, agent_name: str, task: str, tool_context: ToolContext):
        """Sends a task to remote agent

        This will send a message to the remote agent named agent_name.

        Args:
            agent_name: The name of the agent to send the task to.
            task: The comprehensive conversation context summary
                and goal to be achieved regarding user inquiry and purchase request.
            tool_context: The tool context this method runs in.

        Yields:
            A dictionary of JSON data.
        """
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f"Agent {agent_name} not found")
        state = tool_context.state
        state["active_agent"] = agent_name
        client = self.remote_agent_connections[agent_name]
        if not client:
            raise ValueError(f"Client not available for {agent_name}")
        session_id = state["session_id"]
        task: Task
        message_id = ""
        metadata = {}
        if "input_message_metadata" in state:
            metadata.update(**state["input_message_metadata"])
            if "message_id" in state["input_message_metadata"]:
                message_id = state["input_message_metadata"]["message_id"]
        if not message_id:
            message_id = str(uuid.uuid4())

        payload = {
            "message": {
                "role": "user",
                "parts": [
                    {"type": "text", "text": task}
                ],  # Use the 'task' argument here
                "messageId": message_id,
                "contextId": session_id,
            },
        }

        message_request = SendMessageRequest(
            id=message_id, params=MessageSendParams.model_validate(payload)
        )
        send_response: SendMessageResponse = client.send_message(
            message_request=message_request
        )
        print(
            "send_response",
            send_response.model_dump_json(exclude_none=True, indent=2),
        )

        if not isinstance(send_response.root, SendMessageSuccessResponse):
            print("received non-success response. Aborting get task ")
            return None

        if not isinstance(send_response.root.result, Task):
            print("received non-task response. Aborting get task ")
            return None

        return send_response.root.result


def convert_parts(parts: list[Part], tool_context: ToolContext):
    rval = []
    for p in parts:
        rval.append(convert_part(p, tool_context))
    return rval


def convert_part(part: Part, tool_context: ToolContext):
    # Currently only support text parts
    if part.type == "text":
        return part.text

    return f"Unknown type: {part.type}"