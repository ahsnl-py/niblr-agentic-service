# Quick Start Guide

## Local Development

1. **Install dependencies:**
   ```bash
   cd api
   uv sync
   ```

2. **Set up environment variables:**
   Create a `.env` file in the root directory with:
   ```env
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=your-location
   AGENT_ENGINE_RESOURCE_NAME=your-resource-name
   API_PORT=8083
   ```

3. **Run the API:**
   ```bash
   uv run api
   ```

   The API will be available at `http://localhost:8083`

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t niblr-agentic-api -f api/Dockerfile .

# Run the container
docker run -p 8083:8083 \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  -e GOOGLE_CLOUD_LOCATION=your-location \
  -e AGENT_ENGINE_RESOURCE_NAME=your-resource-name \
  niblr-agentic-api
```

### Using Docker Compose

```bash
cd api
# Make sure .env file exists in root directory (../.env)
docker-compose up -d
```

## Testing the API

```bash
# Health check
curl http://localhost:8083/health

# Send a chat message
curl -X POST http://localhost:8083/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8083/docs
- ReDoc: http://localhost:8083/redoc

