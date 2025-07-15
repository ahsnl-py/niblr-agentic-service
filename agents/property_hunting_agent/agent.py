import os
import json
from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient, auth_methods
from dotenv import load_dotenv
from .score_tool import analyze_properties

load_dotenv()

MODEL = "gemini-2.5-flash"

# Mock property data for development
MOCK_PROPERTIES = [
    {
        "price": "23400",
        "location": "Pod kaštany, Praha 6 - Dejvice",
        "link": "https://example.com/property/123",
        "property_type": "1+1 Studio",
        "size": "50m2"
    },
    {
        "price": "18900",
        "location": "Malešická, Praha 3 - Žižkov",
        "link": "https://example.com/property/124",
        "property_type": "1+KK Studio",
        "size": "40m2"
    },
    {
        "price": "28500",
        "location": "Vinohradská, Praha 2 - Vinohrady",
        "link": "https://example.com/property/125",
        "property_type": "2+1 Apartment",
        "size": "65m2"
    },
    {
        "price": "32000",
        "location": "Anděl, Praha 5 - Smíchov",
        "link": "https://example.com/property/126",
        "property_type": "2+1 Apartment",
        "size": "70m2"
    },
    {
        "price": "19500",
        "location": "Žižkov, Praha 3 - Žižkov",
        "link": "https://example.com/property/127",
        "property_type": "1+1 Studio",
        "size": "35m2"
    }
]

def search_properties_mock(query: str) -> str:
    """
    Mock function to search properties based on query
    For development purposes when BigQuery is not available
    """
    # Simple keyword matching
    query_lower = query.lower()
    filtered_properties = []
    
    for prop in MOCK_PROPERTIES:
        # Check if query matches location, property type, or price range
        if (query_lower in prop["location"].lower() or 
            query_lower in prop["property_type"].lower() or
            query_lower in prop["price"]):
            filtered_properties.append(prop)
    
    # If no matches, return all properties
    if not filtered_properties:
        filtered_properties = MOCK_PROPERTIES
    
    return json.dumps(filtered_properties)
    

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

URL = os.getenv("TOOLBOX_URL_PROD", "https://toolbox-cevoq673wa-ey.a.run.app")
headers = {
    "Authorization": auth_methods.aget_google_id_token
}
toolbox = ToolboxSyncClient(url=URL, client_headers=headers)
tools = toolbox.load_toolset("property-listing-toolset-bigquery")

# tools = [search_properties_mock, analyze_properties]
tools.append(analyze_properties)

def create_property_hunting_agent():
    """
    Create the property hunting agent
    """
    return Agent(
        model=MODEL,
        name="property_listing_agent",
        instruction=prompt,
        description="A agent that can search the property database for properties",
        tools=tools,
        output_key="property_listings",  # This stores the output in state
    )
