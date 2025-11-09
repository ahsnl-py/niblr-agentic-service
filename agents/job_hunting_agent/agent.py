import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from toolbox_core import ToolboxSyncClient

load_dotenv()

MODEL = "gemini-2.5-flash"

prompt = """
    You are a JobHuntingAgent responsible for finding job opportunities in the Czech Republic.

    Your task is to follow these steps:

    STEP 1: Get Job Listings
    - Use the job-listing-toolset-bigquery toolbox to get job listings based on the user's query
    - IMPORTANT: Convert all search keywords to lowercase for better matching
    - This will return a JSON array of job opportunities

    STEP 2: Process and Present Results
    - Take the output from step 1 and present the job listings to the user
    - Format the results clearly with job title, company, location, and salary information
    - Include relevant details like job descriptions when available
    - Present the results in a user-friendly format with emojis for readability

    Rules:
        - Always convert search keywords to lowercase before using them in searches
        - Use the job-listing-toolset-bigquery toolbox function for step 1
        - Format the final output clearly with job details
        - If no jobs exist, return a friendly error message
        - Focus on jobs in the Czech Republic, particularly Prague
        - Include salary information when available
        - Provide direct links to job applications when possible

    Example workflow:
    1. Convert user query to lowercase
    2. Call job-listing-toolset-bigquery toolbox with the lowercase query
    3. Present the job results in a clear, organized format

    Example queries you can handle:
    - "software engineer jobs in prague"
    - "data scientist positions"
    - "remote developer opportunities"
    - "marketing jobs in czech republic"
"""

URL = os.getenv("TOOLBOX_URL")
AUDIENCE = os.getenv("TOOLBOX_AUDIENCE", URL)


def _build_toolbox_client(url: str) -> ToolboxSyncClient:
    """
    Instantiate a Toolbox client using a synchronous Google ID token provider.
    The synchronous variant avoids the async metadata refresh path that breaks
    on Cloud Run.
    """

    if url is None:
        raise ValueError("TOOLBOX_URL is not set")

    def _auth_token_provider() -> str:
        request = Request()
        token = id_token.fetch_id_token(request, AUDIENCE)
        return f"Bearer {token}"

    headers = {"Authorization": _auth_token_provider}
    return ToolboxSyncClient(url=url, client_headers=headers)


toolbox = _build_toolbox_client(URL)
tools = toolbox.load_toolset("job-listing-toolset-bigquery")

def create_job_hunting_agent():
    """
    Create the job hunting agent
    """
    return Agent(
        model=MODEL,
        name="job_hunting_agent",
        instruction=prompt,
        description="An agent that can search the job database for job opportunities",
        tools=tools,
        output_key="job_listings",  # This stores the output in state
    ) 