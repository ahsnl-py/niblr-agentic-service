# Property Hunting AI Agent

A property search agent built with Google's Agent Development Kit (ADK) that finds, scores, and presents rental opportunities in Prague.

## Architecture

```
agents/property_hunting_agent/
├── agent.py                    # Main property hunting agent
├── agent_executor.py           # A2A integration executor
├── __main__.py                 # Server entry point
├── score_tool.py               # Scoring helper tool
├── test_client.py              # Test suite / sample client
├── Dockerfile                  # Container image definition
├── pyproject.toml              # Project metadata
├── uv.lock                     # Dependency lockfile
└── README.md                   # This file
```

## Features

### 🏡 Property Search Capabilities
- Calls the `property-listing-toolset-bigquery` toolbox to locate listings.
- Converts raw toolbox results into ranked recommendations with clear explanations.
- Supports user filters such as budget, size, district, and property type.

### 📊 Smart Scoring
- Uses `score_tool.analyze_properties` to blend price, size, and district desirability.
- Encodes Prague district heuristics to highlight attractive neighborhoods.
- Returns the top-scored properties with rationale for each recommendation.

### 🔧 Flexible Configuration
- Synchronous Google ID token auth works on Cloud Run (requires `TOOLBOX_URL`/`TOOLBOX_AUDIENCE`).
- `.env` support for local development.
- Easily extendable prompt and scoring logic in `agent.py` and `score_tool.py`.

## Setup

### Prerequisites
- Python 3.12+
- Access to the `property-listing-toolset-bigquery` toolbox
- Google Cloud credentials (Application Default Credentials on Cloud Run)

### Environment Variables
```bash
# Toolbox connection
TOOLBOX_URL=http://127.0.0.1:5000
TOOLBOX_AUDIENCE=http://127.0.0.1:5000  # optional override

# Google AI (choose one path)
GOOGLE_API_KEY=your_api_key
# or
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

## Installation

```bash
uv sync
```

## Usage

### Running the Agent Server
```bash
# Default host/port (0.0.0.0:10002)
uv run .

# Custom port
uv run . --host 0.0.0.0 --port 8080
```

### Local Docker
```bash
docker build -t property-hunting-agent:local -f Dockerfile .
docker run --rm -p 8080:8080 --env-file ../.env property-hunting-agent:local
```

## Testing the Agent

```bash
python test_client.py
# optional interactive mode
python test_client.py --interactive
```

### API Endpoints
- `GET /.well-known/agent.json` – Agent metadata card
- `POST /send_message` – Submit a property search query

## Agent Workflow

1. **Query Processing** – Normalize the user request and extract key filters.
2. **Listing Retrieval** – Call the BigQuery toolbox for matching listings.
3. **Scoring** – Run `analyze_properties` to score and rank candidates.
4. **Response Delivery** – Return top options with emoji-rich explanations.
5. **State Storage** – Persist final listings in the agent state under `property_listings`.

## Deployment to Cloud Run

```bash
gcloud run deploy property-hunting-agent \
    --source agents/property_hunting_agent \
    --region <region> \
    --port 8080 \
    --allow-unauthenticated \
    --update-env-vars TOOLBOX_URL=<toolbox-url> \
    --update-env-vars TOOLBOX_AUDIENCE=<toolbox-url> \
    --memory 1Gi
```

## Troubleshooting

- **Toolbox auth errors**: Confirm `TOOLBOX_URL`/`TOOLBOX_AUDIENCE` and IAM permissions for the Cloud Run service account.
- **No listings returned**: Verify the toolbox is reachable and contains data for the query.
- **Local toolbox**: Use `TOOLBOX_URL=http://host.docker.internal:5000` when testing against a local toolbox instance.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes + add tests
4. Submit a pull request

## License

Apache License 2.0