from . import property_listing, score, filter

# Create a root_agent for the sub_agents directory
# This allows ADK to run the sub_agents as a standalone agent
from .property_listing import property_listing_agent as root_agent