# MCP Server Local Deployment Guide

This guide provides step-by-step instructions for deploying the Model Context Protocol (MCP) server locally for development and testing.

## Overview

The MCP server provides tools and toolboxes that can be used by AI agents to interact with external data sources, particularly BigQuery for job and property listings.

## Prerequisites

### Required Software
- **Node.js** (v18 or higher) - for MCP Inspector
- **Python** (3.13+) - for the MCP server
- **uv** - Python package manager
- **Google Cloud CLI** - for BigQuery access

### Required Accounts & Permissions
- Google Cloud Project with BigQuery enabled
- Service account with BigQuery permissions
- Google Cloud credentials configured locally

## Installation

### 1. Install Node.js Dependencies
```bash
# Install MCP Inspector globally
npm install -g @modelcontextprotocol/inspector
```

### 2. Install Python Dependencies
```bash
# Navigate to the project root
cd /Users/ahsanulnasahsanulnas/git/niblr-agentic-service-a2a

# Install dependencies using uv
uv sync
```

### 3. Configure Google Cloud Credentials
```bash
# Authenticate with Google Cloud
gcloud auth login

# Set the project
gcloud config set project niblr-agentic-service

# Create and download service account key (if needed)
gcloud iam service-accounts create mcp-server-sa \
    --display-name="MCP Server Service Account"

gcloud projects add-iam-policy-binding niblr-agentic-service \
    --member="serviceAccount:mcp-server-sa@niblr-agentic-service.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"

gcloud iam service-accounts keys create mcp-server-key.json \
    --iam-account=mcp-server-sa@niblr-agentic-service.iam.gserviceaccount.com

# Set the credentials
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/mcp-server-key.json"
```

## Deployment Steps

### Step 1: Start MCP Inspector (Optional but Recommended)

The MCP Inspector provides a web interface to test and debug your MCP server.

```bash
# Start the MCP Inspector
npx @modelcontextprotocol/inspector
```

This will:
- Start a web server (usually on `http://localhost:3000`)
- Provide a UI to test MCP tools and toolboxes
- Show real-time logs and responses

**Note**: Keep this running in a separate terminal window for debugging.

### Step 2: Start the MCP Server

```bash
# Navigate to the project root
cd /Users/ahsanulnasahsanulnas/git/niblr-agentic-service-a2a

# Start the MCP server with the tools configuration
./toolbox --tools-file "/Users/ahsanulnasahsanulnas/git/niblr-agentic-service-a2a/tools.yaml"
```

This command:
- Starts the MCP server using the `tools.yaml` configuration
- Loads all defined tools and toolsets
- Makes the server available for agent connections

## Configuration Files

### tools.yaml
The main configuration file that defines:
- **Sources**: BigQuery connections
- **Tools**: Individual SQL queries for data access
- **Toolsets**: Grouped collections of tools

#### Key Sections:

**Sources:**
```yaml
source-bigquery-eu:
  kind: bigquery
  project: niblr-agentic-service
  location: europe-west3
```

**Tools:**
```yaml
search-job-listing-by-title:
  kind: bigquery-sql
  source: source-bigquery-eu
  description: Search for job listings by title from BigQuery.
  parameters:
    - name: title
      type: string
      description: The title of the job to search for.
  statement: |
    SELECT *
    FROM `niblr-agentic-service.interm_layer.job_listing_view` 
    WHERE LOWER(title) LIKE CONCAT('%', @title, '%')
    LIMIT 10
```

**Toolsets:**
```yaml
job-listing-toolset-bigquery:
  - search-job-listing-by-title
  - search-job-listing-by-location
  - search-job-listing-by-company-name
```

## Available Tools

### Job Listing Tools
- `search-job-listing-by-title` - Search jobs by title
- `search-job-listing-by-location` - Search jobs by location
- `search-job-listing-by-company-name` - Search jobs by company

### Property Listing Tools
- `search-property-listing-by-location` - Search properties by location
- `search-property-listing-by-price-range` - Search properties by price range
- `search-property-listing-by-size-range` - Search properties by size range
- `search-property-listing-by-apartment-type` - Search properties by apartment type

## Testing the Deployment

### 1. Using MCP Inspector
1. Open `http://localhost:3000` in your browser
2. Connect to your MCP server
3. Test individual tools and toolsets
4. View logs and responses in real-time

### 2. Using Python Agents
```bash
# Test with job hunting agent
cd agents/job_hunting_agent
uv run .

# In another terminal, test the agent
python test_client.py --interactive
```

### 3. Using curl (Advanced)
```bash
# Test a specific tool
curl -X POST http://localhost:8080/tools/search-job-listing-by-title \
  -H "Content-Type: application/json" \
  -d '{"title": "software engineer"}'
```

## Environment Variables

### Required Variables
```bash
# Google Cloud Project
export GOOGLE_CLOUD_PROJECT="niblr-agentic-service"

# Google Cloud Credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# MCP Server Configuration
export PORT=8080
export HOST="0.0.0.0"
```

### Optional Variables
```bash
# Debug logging
export LOG_LEVEL="DEBUG"

# Custom BigQuery location
export BIGQUERY_LOCATION="europe-west3"
```

## Troubleshooting

### Common Issues

#### 1. Permission Denied Errors
```bash
# Check if credentials are properly set
echo $GOOGLE_APPLICATION_CREDENTIALS

# Verify service account permissions
gcloud projects get-iam-policy niblr-agentic-service \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:mcp-server-sa@niblr-agentic-service.iam.gserviceaccount.com"
```

#### 2. Port Already in Use
```bash
# Check what's using the port
lsof -i :8080

# Kill the process or use a different port
export PORT=8081
```

#### 3. BigQuery Dataset Not Found
```bash
# Verify the dataset exists
bq ls niblr-agentic-service:interm_layer

# Check table structure
bq show niblr-agentic-service:interm_layer.job_listing_view
```

#### 4. MCP Inspector Connection Issues
```bash
# Check if MCP server is running
curl http://localhost:8080/health

# Verify the server is accessible
netstat -an | grep 8080
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"

# Start server with verbose output
./toolbox --tools-file tools.yaml --verbose
```

## Development Workflow

### 1. Adding New Tools
1. Edit `tools.yaml` to add new tool definitions
2. Test the tool using MCP Inspector
3. Update agent prompts to use new tools
4. Test with agents

### 2. Modifying Existing Tools
1. Update the SQL statement in `tools.yaml`
2. Restart the MCP server
3. Test changes with MCP Inspector
4. Verify agent functionality

### 3. Adding New Data Sources
1. Add new source configuration in `tools.yaml`
2. Create tools that reference the new source
3. Update toolsets to include new tools
4. Test with MCP Inspector

## Monitoring and Logs

### Server Logs
The MCP server provides detailed logging:
- Tool execution logs
- BigQuery query logs
- Error messages and stack traces
- Performance metrics

### Health Checks
```bash
# Check server health
curl http://localhost:8080/health

# Check available tools
curl http://localhost:8080/tools
```

## Security Considerations

### Service Account Permissions
- Use least privilege principle
- Grant only necessary BigQuery permissions
- Regularly rotate service account keys

### Network Security
- Use localhost for development
- Implement proper authentication for production
- Use HTTPS in production environments

### Data Access
- Limit query results with `LIMIT` clauses
- Implement row-level security in BigQuery
- Audit data access regularly

## Production Deployment

For production deployment, consider:
- Using Cloud Run or similar containerized deployment
- Implementing proper authentication and authorization
- Setting up monitoring and alerting
- Using managed service accounts
- Implementing rate limiting

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review MCP server logs
3. Test with MCP Inspector
4. Verify BigQuery permissions and data access

## Additional Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Google Cloud IAM](https://cloud.google.com/iam/docs)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp) 