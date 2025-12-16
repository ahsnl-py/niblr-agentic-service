"""Configuration and initialization for the API."""

import os
from dotenv import load_dotenv
import vertexai
from vertexai import agent_engines

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

if not PROJECT_ID or not LOCATION:
    raise ValueError(
        "GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION must be set before launching the API."
    )

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Get agent engine resource name with validation
AGENT_ENGINE_RESOURCE_NAME = os.getenv("AGENT_ENGINE_RESOURCE_NAME")
if not AGENT_ENGINE_RESOURCE_NAME:
    raise ValueError(
        "AGENT_ENGINE_RESOURCE_NAME environment variable is not set. "
        "Please set it in your .env file or environment."
    )

# Validate resource name format
if not (AGENT_ENGINE_RESOURCE_NAME.startswith("projects/") and 
        ("/agentEngines/" in AGENT_ENGINE_RESOURCE_NAME or "/reasoningEngines/" in AGENT_ENGINE_RESOURCE_NAME)):
    raise ValueError(
        f"Invalid AGENT_ENGINE_RESOURCE_NAME format: {AGENT_ENGINE_RESOURCE_NAME}\n"
        f"Expected format: projects/{{project_id}}/locations/{{location}}/agentEngines/{{id}} or "
        f"projects/{{project_id}}/locations/{{location}}/reasoningEngines/{{id}}"
    )

try:
    REMOTE_APP = agent_engines.get(AGENT_ENGINE_RESOURCE_NAME)
except ValueError as e:
    raise ValueError(
        f"Failed to get agent engine with resource name: {AGENT_ENGINE_RESOURCE_NAME}\n"
        f"Error: {str(e)}\n"
        f"Please verify that:\n"
        f"1. The agent engine exists and is deployed\n"
        f"2. You have the correct permissions\n"
        f"3. The resource name format is correct"
    ) from e

