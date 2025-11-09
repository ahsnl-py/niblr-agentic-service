from .routing_agent import RoutingAgent
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

root_agent = RoutingAgent(
    remote_agent_addresses=[
        os.getenv("PROPERTY_HUNTING_AGENT_URL", "http://localhost:10001"),
        os.getenv("JOB_HUNTING_AGENT_URL", "http://localhost:10002"),
    ]
).create_agent()