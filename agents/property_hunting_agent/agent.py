"""
Property Hunting AI Agent using Google's Agent Development Kit (ADK)

This module implements a sequential property hunting pipeline with the following sub-agents:
1. PropertyListingAgent - Get property listings from database
2. FilterAgent - Filters listings based on user criteria
3. ScoreAgent - Ranks properties based on user preferences
4. NotificationAgent - Sends top listings to user

The main SequentialAgent orchestrates these sub-agents in sequence.
"""

from google.adk.agents import SequentialAgent

from .sub_agents.property_listing.agent import property_listing_agent
# from .sub_agents.filter.agent import filter_agent
from .sub_agents.score.agent import score_agent


def create_property_hunting_agent():
    return SequentialAgent(
        name="PropertyHuntingAgent",
        sub_agents=[property_listing_agent, score_agent],
        description="A pipeline that searches the property database for properties and scores them based on user preferences",
    )

root_agent = create_property_hunting_agent()