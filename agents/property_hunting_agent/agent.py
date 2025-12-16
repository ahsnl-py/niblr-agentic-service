import os
from typing import List, Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from toolbox_core import ToolboxSyncClient

from score_tool import analyze_properties

load_dotenv()

MODEL = "gemini-2.5-flash"


# Pydantic schema for structured property listing output
class PropertyListing(BaseModel):
    """Individual property listing structure"""
    property_id: Optional[str] = Field(default=None, description="Unique identifier for the property")
    title: Optional[str] = Field(default=None, description="Property title or headline")
    location: Optional[str] = Field(default=None, description="Property location/address")
    price: Optional[str] = Field(default=None, description="Monthly rent price")
    price_czk: Optional[float] = Field(default=None, description="Price converted to CZK")
    size_m2: Optional[float] = Field(default=None, description="Size in square meters")
    property_type: Optional[str] = Field(default=None, description="Type of property (studio, 1+kk, 2+1, etc.)")
    score: Optional[float] = Field(default=None, description="Property score from analyze_properties")
    additional_info: Optional[str] = Field(default=None, description="Additional information (utilities, fees, etc.)")
    link: Optional[str] = Field(default=None, description="Link to property listing")


class PropertySearchResponse(BaseModel):
    """Structured response containing property listings"""
    properties: List[PropertyListing] = Field(description="List of properties found (top 3 scored)")
    total_count: int = Field(description="Total number of properties found")
    message: Optional[str] = Field(default=None, description="Optional message or summary")


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
    - Select the top 3 scored properties after filtering

    STEP 4: Return Results to User
    - Return the top 3 scored properties in the specified JSON format
    - Include scoring information and explanations
    - Ensure all prices are converted to CZK

    OUTPUT FORMAT REQUIREMENTS:
    You MUST return your response as a valid JSON object with this exact structure:
    {
        "properties": [
            {
                "property_id": "...",
                "title": "...",
                "location": "...",
                "price": "...",
                "price_czk": <number>,
                "size_m2": <number>,
                "property_type": "...",
                "score": <number>,
                "additional_info": "...",
                "link": "..." or null
            }
        ],
        "total_count": <number>,
        "message": "..." or null
    }

    Rules:
        - Always follow the 4-step process in order
        - Use the property-listing-toolset-bigquery toolbox function for step 1
        - Use the analyze_properties function for step 2
        - Apply intelligent filtering for step 3 based on user preferences
        - Return top 3 properties in the specified JSON format
        - Convert all prices to CZK (price_czk field)
        - Include score from analyze_properties function
        - If no properties exist, return empty array with total_count=0 and a helpful message
        - Ensure the JSON is valid and properly formatted

    Example workflow:
    1. Call property-listing-toolset-bigquery toolbox with user query
    2. Take that JSON result and call analyze_properties with it
    3. Apply intelligent filtering to the scored results
    4. Return the final filtered and scored results as JSON matching the schema
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
    Create the property hunting agent with structured output schema
    """
    return Agent(
        model=MODEL,
        name="property_hunting_agent",
        instruction=prompt,
        description="An agent that can search the property database for property opportunities",
        tools=tools,
        output_key="property_listings",  # This stores the output in state
        output_schema=PropertySearchResponse,  # Structured output schema
    )
