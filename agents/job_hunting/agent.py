"""
Job Hunting AI Agent using Google's Agent Development Kit (ADK)

This module implements a sequential job hunting pipeline with the following sub-agents:
1. JobListingAgent - Get job listings from database
2. FilterAgent - Filters job listings based on user criteria
3. ScoreAgent - Ranks jobs based on user preferences

The main SequentialAgent orchestrates these sub-agents in sequence.
"""

from google.adk.agents import SequentialAgent

from .sub_agents.job_listing.agent import job_listing_agent
# from .sub_agents.filter.agent import filter_agent
# from .sub_agents.score.agent import score_agent

root_agent = SequentialAgent(
    name="JobHuntingAgentPipeline",
    sub_agents=[job_listing_agent],
    description="A pipeline that searches the job database for job opportunities",
)