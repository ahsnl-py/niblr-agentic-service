import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from toolbox_core import ToolboxSyncClient

from score_tool import analyze_properties

load_dotenv()

MODEL = "gemini-2.5-flash"

prompt = """
    You are a PropertyHuntingAgent responsible for finding and scoring properties in Prague.

    Your task is to follow these steps:

    STEP 1: Get Property Listings
    - Use the property-listing-toolset-bigquery toolbox to get property listings based on the user's query
    - This will return a JSON array of properties

    STEP 2: Score the Properties
    - Take the output from step 1 and pass it to the analyze_properties function
    - This function will score and rank the properties based on price, size, and location

    STEP 3: Filter the Properties
    - Take the output from step 2 and apply intelligent filtering based on the user's preferences
    - Filter by criteria such as:
        * Price range (e.g., "under 25000", "between 20000-30000")
        * Location preferences (e.g., "in Žižkov", "near metro")
        * Property type (e.g., "studio", "2+1", "apartment")
        * Size requirements (e.g., "at least 40m2", "under 60m2")
        * Any other specific requirements mentioned by the user
    - Return the filtered properties as a JSON array

    STEP 4: Return Results to User
    - Present the top 3 scored properties to the user
    - Explain why each property scored well (price, size, location factors)
    - Format the output clearly with emojis for readability

    Example workflow:
    1. Call property-listing-toolset-bigquery toolbox with user query
    2. Take that JSON result and call analyze_properties with it
    3. Apply intelligent filtering to the scored results
    4. Present the final filtered and scored results to the user

    Rules:
        - Always follow the 3-step process in order
        - Use the property-listing-toolset-bigquery toolbox function for step 1
        - Use the analyze_properties function for step 2
        - Apply intelligent filtering for step 3 based on user preferences
        - Format the final output clearly with explanations
        - If no properties exist, return a friendly error message
"""

URL = os.getenv("TOOLBOX_URL")
AUDIENCE = os.getenv("TOOLBOX_AUDIENCE", URL)


def _build_toolbox_client(url: str) -> ToolboxSyncClient:
    """
    Instantiate a Toolbox client using a synchronous Google ID token provider.
    The synchronous variant avoids the async metadata refresh path that breaks
    on Cloud Run.
    """

    if not url:
        raise ValueError("TOOLBOX_URL is not set")

    def _auth_token_provider() -> str:
        request = Request()
        token = id_token.fetch_id_token(request, AUDIENCE)
        return f"Bearer {token}"

    headers = {"Authorization": _auth_token_provider}
    return ToolboxSyncClient(url=url, client_headers=headers)


toolbox = _build_toolbox_client(URL)
tools = toolbox.load_toolset("property-listing-toolset-bigquery")
tools.append(analyze_properties)


def create_property_hunting_agent():
    """
    Create the property hunting agent
    """
    return Agent(
        model=MODEL,
        name="property_hunting_agent",
        instruction=prompt,
        description="An agent that can search the property database for property opportunities",
        tools=tools,
        output_key="property_listings",  # This stores the output in state
    )
