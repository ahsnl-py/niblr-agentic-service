import vertexai
from vertexai.preview import reasoning_engines
from vertexai import agent_engines
from dotenv import load_dotenv
import os
from router_agent.agent import root_agent

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
STAGING_BUCKET = os.getenv("STAGING_BUCKET")

vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    staging_bucket=STAGING_BUCKET,
)

adk_app = reasoning_engines.AdkApp(
    agent=root_agent,
)

remote_app = agent_engines.create(
    agent_engine=adk_app,
    display_name="niblr-agent",
    requirements=[
        "google-cloud-aiplatform[agent_engines]",
        "google-adk==1.18.0",
        "a2a-sdk==0.2.16",
    ],
    extra_packages=[
        "./router_agent",
    ],
    env_vars={
        "GOOGLE_GENAI_USE_VERTEXAI": os.environ["GOOGLE_GENAI_USE_VERTEXAI"],
        "PROPERTY_HUNTING_AGENT_URL": os.environ["PROPERTY_HUNTING_AGENT_URL"],
        "JOB_HUNTING_AGENT_URL": os.environ["JOB_HUNTING_AGENT_URL"],
    },
)

print(f"Deployed remote app resource: {remote_app.resource_name}")