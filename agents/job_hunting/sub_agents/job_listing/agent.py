import os
from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Add debug output to check if .env is loaded
print("🔍 Job Hunting Agent - Checking .env variables:")
print(f"TOOLBOX_URL_PROD: {os.getenv('TOOLBOX_URL_PROD', 'NOT_FOUND')}")
print(f"TOOLBOX_URL_LOCAL: {os.getenv('TOOLBOX_URL_LOCAL', 'NOT_FOUND')}")
print(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT', 'NOT_FOUND')}")

MODEL = "gemini-2.5-flash"

prompt = """
You are a JobListingAgent responsible for retrieving job listings from a job database or API.

Your task is to:
1. Accept user queries about job openings (e.g., job title, location, remote, etc.).
2. Query the job database or API using the available toolset.
3. Return the results as a JSON array of job objects.

Example output format:
[
  {
    "title": "Software Engineer",
    "company": "TechCorp",
    "location": "Prague",
    "salary": "80000 CZK/month",
    "link": "https://example.com/job/123",
  }
]
"""

# Use environment variables instead of hardcoded URL
TOOLBOX_URL = os.getenv("TOOLBOX_URL_DEV")
print(f" Using toolbox URL: {TOOLBOX_URL}")

# Connect to your toolbox server and load the toolset for job listings
toolbox = ToolboxSyncClient(TOOLBOX_URL)
tools = toolbox.load_toolset("job-listing-toolset-bigquery")

job_listing_agent = Agent(
    model=MODEL,
    name="job_listing_agent",
    instruction=prompt,
    description="An agent that can search the job database for job listings",
    tools=tools,
    output_key="job_listings",
)
