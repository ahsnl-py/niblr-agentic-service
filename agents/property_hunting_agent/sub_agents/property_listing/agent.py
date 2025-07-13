import os
import json
from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient, auth_methods
from dotenv import load_dotenv

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
    You are a PropertyDatabaseAgent responsible for querying 
    property databases through the Toolbox Server.

    Your task is to:
    1. Receive property search queries from users
    2. Convert user queries into appropriate database queries
    3. Execute database queries using the available toolset

    Return the data as a JSON array of property objects.

    Example output format:
    [
        {
            "price": "23400",
            "location": "Pod kaštany, Praha 6 - Dejvice",
            "link": "https://example.com/property/123",
            "property_type": "1+1 Studio",
            "size": "50m2"
        }
    ]
    
    Note: Currently using mock data for development. Use the search_properties_mock function.
"""

URL = os.getenv("TOOLBOX_URL_PROD", "https://toolbox-cevoq673wa-ey.a.run.app")
headers = {
    "Authorization": auth_methods.aget_google_id_token
}
toolbox = ToolboxSyncClient(url=URL, client_headers=headers)
tools = toolbox.load_toolset("property-listing-toolset-bigquery")

# tools = [search_properties_mock]


property_listing_agent = Agent(
    model=MODEL,
    name="property_listing_agent",
    instruction=prompt,
    description="A agent that can search the property database for properties",
    tools=tools,
    output_key="property_listings",  # This stores the output in state
)
