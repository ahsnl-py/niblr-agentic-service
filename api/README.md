# Niblr Agentic Concierge API

REST API for the Niblr Agentic Concierge chatbot, built with FastAPI.

## Features

- RESTful API endpoints for chat interactions
- Server-Sent Events (SSE) streaming support
- Session management
- CORS enabled for React frontend integration
- Docker containerization support

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (optional, for containerized deployment)

## Environment Variables

Create a `.env` file in the root directory with:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=your-location
AGENT_ENGINE_RESOURCE_NAME=your-agent-engine-resource-name
API_PORT=8083
```

## Local Development

### Using uv

1. Install dependencies:
   ```bash
   cd api
   uv sync
   ```

2. Run the API:
   ```bash
   uv run api
   # or
   uv run python -m api
   ```

The API will be available at `http://localhost:8083`

### Using Python directly

```bash
cd api
python -m api
```

## Docker Deployment

### Build the Docker image

```bash
docker build -t niblr-agentic-api -f api/Dockerfile .
```

### Run the container

```bash
docker run -p 8083:8083 \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  -e GOOGLE_CLOUD_LOCATION=your-location \
  -e AGENT_ENGINE_RESOURCE_NAME=your-resource-name \
  -e API_PORT=8083 \
  niblr-agentic-api
```

Or use docker-compose:
```bash
cd api
docker-compose up -d
```

## API Endpoints

### `GET /`
Health check endpoint.

### `GET /health`
Health check endpoint.

### `POST /api/chat`
Main chat endpoint. Accepts a message and returns the agent's response.

**Request:**
```json
{
  "message": "Find me a 2-bedroom apartment in Praha 2",
  "session_id": "optional-session-id",
  "user_id": "optional-user-id"
}
```

**Response:**
```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "I'll help you find a 2-bedroom apartment...",
      "metadata": null
    }
  ],
  "session_id": "session-id"
}
```

### `POST /api/chat/stream`
Streaming chat endpoint using Server-Sent Events (SSE).

### `POST /api/session/new`
Create a new chat session.

**Response:**
```json
{
  "session_id": "session-id",
  "user_id": "user-id"
}
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8083/docs`
- ReDoc: `http://localhost:8083/redoc`

## Project Structure

```
api/
├── __init__.py          # Package initialization
├── __main__.py          # Main API application
├── pyproject.toml       # Project configuration and dependencies
├── Dockerfile           # Docker container definition
├── .dockerignore        # Files to exclude from Docker build
└── README.md           # This file
```

## Development

### Adding Dependencies

```bash
cd api
uv add package-name
```

### Updating Dependencies

```bash
cd api
uv sync
```

## License

Copyright 2025 Google LLC

Licensed under the Apache License, Version 2.0

