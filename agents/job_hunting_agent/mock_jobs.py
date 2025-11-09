"""Mock job listings for local development and testing."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    salary: str
    description: str
    url: str
    tags: list[str]


MOCK_JOBS: tuple[JobListing, ...] = (
    JobListing(
        title="Senior Backend Engineer",
        company="Praha Tech Labs",
        location="Prague, Czech Republic",
        salary="120 000 - 150 000 CZK",
        description=(
            "Design and build resilient APIs in Python, collaborate with a cross-functional "
            "team, and mentor junior developers. Experience with GCP is a plus."
        ),
        url="https://example.com/jobs/backend-engineer",
        tags=["software engineer", "backend", "python", "gcp"],
    ),
    JobListing(
        title="Data Scientist",
        company="Czech Analytics",
        location="Prague, Czech Republic",
        salary="100 000 - 135 000 CZK",
        description=(
            "Create data products, run experiments, and help product teams make data-informed "
            "decisions. Looking for strong SQL and ML background."
        ),
        url="https://example.com/jobs/data-scientist",
        tags=["data scientist", "machine learning", "sql"],
    ),
    JobListing(
        title="Product Marketing Manager",
        company="Bohemian Startups",
        location="Brno, Czech Republic",
        salary="80 000 - 110 000 CZK",
        description=(
            "Own go-to-market messaging for a suite of B2B products. Coordinate launches, gather "
            "customer insights, and support sales enablement."
        ),
        url="https://example.com/jobs/product-marketing-manager",
        tags=["marketing", "product marketing", "b2b"],
    ),
    JobListing(
        title="Remote Frontend Engineer",
        company="EU Remote Collective",
        location="Remote (Czech Republic)",
        salary="110 000 - 140 000 CZK",
        description=(
            "Build delightful web experiences with React and TypeScript. Fully remote team "
            "collaborating across the EU timezone."
        ),
        url="https://example.com/jobs/frontend-engineer",
        tags=["frontend", "react", "remote"],
    ),
)


def _filter_jobs(query: str | None) -> Iterable[JobListing]:
    if not query:
        return MOCK_JOBS

    normalized = query.lower()
    results = [
        job
        for job in MOCK_JOBS
        if any(normalized in tag for tag in job.tags)
        or normalized in job.title.lower()
        or normalized in job.location.lower()
    ]

    return results or MOCK_JOBS


def search_jobs_mock(query: str) -> str:
    """Return mock job listings encoded as JSON."""
    jobs = _filter_jobs(query)
    return json.dumps([asdict(job) for job in jobs])

