import os
import json
from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient, auth_methods
from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-2.5-flash"

# Mock job data for development
MOCK_JOBS = [
    {
        "title": "Software Engineer",
        "company": "TechCorp",
        "location": "Prague, Czech Republic",
        "salary": "80000 CZK/month",
        "link": "https://example.com/job/123",
        "description": "Full-stack development with Python and React"
    },
    {
        "title": "Data Scientist",
        "company": "DataAnalytics Inc",
        "location": "Prague, Czech Republic",
        "salary": "90000 CZK/month",
        "link": "https://example.com/job/124",
        "description": "Machine learning and data analysis"
    },
    {
        "title": "Product Manager",
        "company": "StartupXYZ",
        "location": "Prague, Czech Republic",
        "salary": "75000 CZK/month",
        "link": "https://example.com/job/125",
        "description": "Product strategy and roadmap management"
    },
    {
        "title": "DevOps Engineer",
        "company": "CloudTech",
        "location": "Prague, Czech Republic",
        "salary": "85000 CZK/month",
        "link": "https://example.com/job/126",
        "description": "Infrastructure and deployment automation"
    },
    {
        "title": "Frontend Developer",
        "company": "WebSolutions",
        "location": "Prague, Czech Republic",
        "salary": "70000 CZK/month",
        "link": "https://example.com/job/127",
        "description": "React and Vue.js development"
    }
]

def search_jobs_mock(query: str) -> str:
    """
    Mock function to search jobs based on query
    For development purposes when BigQuery is not available
    """
    # Simple keyword matching - convert to lowercase for case-insensitive search
    query_lower = query.lower()
    filtered_jobs = []
    
    for job in MOCK_JOBS:
        # Check if query matches title, company, location, or description
        if (query_lower in job["title"].lower() or 
            query_lower in job["company"].lower() or
            query_lower in job["location"].lower() or
            query_lower in job["description"].lower()):
            filtered_jobs.append(job)
    
    # If no matches, return all jobs
    if not filtered_jobs:
        filtered_jobs = MOCK_JOBS
    
    return json.dumps(filtered_jobs)
    

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

URL = os.getenv("TOOLBOX_URL_DEV", "https://toolbox-cevoq673wa-ey.a.run.app")
headers = {
    "Authorization": auth_methods.aget_google_id_token
}
toolbox = ToolboxSyncClient(url=URL, client_headers=headers)
tools = toolbox.load_toolset("job-listing-toolset-bigquery")

# For development, you can use mock data instead
# tools = [search_jobs_mock]

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