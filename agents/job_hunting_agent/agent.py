import os
from typing import List, Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from pydantic import BaseModel, Field
from toolbox_core import ToolboxSyncClient

load_dotenv()

MODEL = "gemini-2.5-flash"


# Pydantic schema for structured job listing output
class JobListing(BaseModel):
    """Individual job listing structure"""
    job_title: str = Field(description="The position title")
    location: str = Field(description="Job location (typically Prague, Czech Republic)")
    company_name: str = Field(description="Name of the hiring company")
    employment_type: str = Field(description="Full-time, part-time, contract, hybrid, remote, etc.")
    job_overview: Optional[str] = Field(default=None, description="High-level description of the role")
    responsibilities: Optional[List[str]] = Field(default=None, description="Detailed list of job responsibilities")
    required_skills: Optional[List[str]] = Field(default=None, description="Must-have skills and qualifications")
    preferred_skills: Optional[List[str]] = Field(default=None, description="Nice-to-have skills (optional)")
    soft_skills: Optional[List[str]] = Field(default=None, description="Interpersonal and professional skills")
    qualifications: Optional[str] = Field(default=None, description="Educational and professional requirements")
    languages: Optional[List[str]] = Field(default=None, description="Language requirements")
    benefits: Optional[List[str]] = Field(default=None, description="Company benefits and perks")
    application_link: Optional[str] = Field(default=None, description="URL where users can apply for the job")


class JobSearchResponse(BaseModel):
    """Structured response containing job listings"""
    jobs: List[JobListing] = Field(description="List of job opportunities found (up to 5)")
    total_count: int = Field(description="Total number of jobs found")
    message: Optional[str] = Field(default=None, description="Optional message or summary")


prompt = """
    You are a JobHuntingAgent responsible for finding job opportunities in the Czech Republic using advanced vector search technology.

    Your task is to follow these steps:

    STEP 1: Get Job Listings Using Vector Search
    - Use the job-listing-toolset-bigquery toolbox to perform semantic vector search based on the user's query
    - The vector search will find the most semantically relevant jobs based on meaning, not just keyword matching
    - Pass the user's query directly to the toolbox - no need to modify or lowercase it
    - This will return up to 5 most relevant job opportunities based on semantic similarity

    STEP 2: Process and Structure Results
    - The toolbox returns structured job data with the following fields:
      * job_title: The position title
      * location: Job location (typically Prague, Czech Republic)
      * employment_type: Full-time, part-time, contract, hybrid, remote, etc.
      * company_name: Name of the hiring company
      * job_overview: High-level description of the role
      * responsibilities: Detailed list of job responsibilities
      * required_skills: Must-have skills and qualifications
      * preferred_skills: Nice-to-have skills (optional)
      * soft_skills: Interpersonal and professional skills
      * qualifications: Educational and professional requirements
      * languages: Language requirements
      * benefits: Company benefits and perks
      * application_link: URL where users can apply for the job (if available)
    
    STEP 3: Format the Output
    - Return your results as a JSON object matching the specified schema
    - Include ALL jobs returned (up to 5) in the "jobs" array
    - Set "total_count" to the number of jobs found
    - Include all available fields for each job listing
    - If no jobs exist, return an empty "jobs" array with total_count=0 and a helpful message

    OUTPUT FORMAT REQUIREMENTS:
    You MUST return your response as a valid JSON object with this exact structure:
    {
        "jobs": [
            {
                "job_title": "...",
                "location": "...",
                "company_name": "...",
                "employment_type": "...",
                "job_overview": "...",
                "responsibilities": ["...", "..."],
                "required_skills": ["...", "..."],
                "preferred_skills": ["...", "..."],
                "soft_skills": ["...", "..."],
                "qualifications": "...",
                "languages": ["...", "..."],
                "benefits": ["...", "..."],
                "application_link": "..." or null
            }
        ],
        "total_count": <number>,
        "message": "..." or null
    }

    Rules:
        - Use the job-listing-toolset-bigquery toolbox function for step 1
        - Pass the user's query as-is - vector search handles semantic matching automatically
        - Always return results in the specified JSON format
        - Include all available information from the toolbox response
        - If no jobs exist, return empty array with total_count=0 and a helpful message
        - Focus on jobs in the Czech Republic, particularly Prague
        - Ensure the JSON is valid and properly formatted

    Example workflow:
    1. Receive user query (e.g., "software engineer jobs in prague")
    2. Call job-listing-toolset-bigquery toolbox with the user's query
    3. Receive up to 5 structured job results
    4. Format results as JSON matching the specified schema
    5. Return the structured JSON response

    Example queries you can handle:
    - "software engineer jobs in prague"
    - "data scientist positions"
    - "remote developer opportunities"
    - "marketing jobs in czech republic"
    - "python developer with machine learning experience"
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
    Create the job hunting agent with structured output schema
    """
    return Agent(
        model=MODEL,
        name="job_hunting_agent",
        instruction=prompt,
        description="An agent that can search the job database for job opportunities",
        tools=tools,
        output_key="job_listings",  # This stores the output in state
        output_schema=JobSearchResponse,  # Structured output schema
    ) 