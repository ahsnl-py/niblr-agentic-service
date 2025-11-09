# Job Hunting AI Agent

A sophisticated job hunting AI agent built using Google's Agent Development Kit (ADK) that automates the job search process and delivers personalized job recommendations.

## Architecture

The agent follows a modular architecture:

```
agents/job_hunting_agent/
├── agent.py                    # Main job hunting agent
├── agent_executor.py           # A2A integration executor
├── __main__.py                 # Server entry point
├── test_client.py              # Test suite
└── README.md                   # This file
```

## Features

### 🔍 Job Search Capabilities
- Search job listings by title, location, or keywords
- Case-insensitive search (all keywords converted to lowercase)
- Integration with BigQuery job database via MCP server
- Mock data support for development and testing

### 🎯 Smart Query Processing
- Converts all search keywords to lowercase for better matching
- Handles various job search queries:
  - "software engineer jobs in prague"
  - "data scientist positions"
  - "remote developer opportunities"
  - "marketing jobs in czech republic"

### 🔧 Flexible Configuration
- Uses `job-listing-toolset-bigquery` toolbox from MCP server
- Configurable via environment variables
- Mock data mode for development

## Setup

### Prerequisites
- Python 3.13+
- Google Cloud credentials configured
- MCP server with `job-listing-toolset-bigquery` toolbox

### Environment Variables
```bash
# Required for Google AI
GOOGLE_API_KEY=your_api_key
# OR
GOOGLE_GENAI_USE_VERTEXAI=TRUE

# Toolbox configuration
TOOLBOX_URL_PROD=https://your-toolbox-url.com
```

### Installation
```bash
# Install dependencies
uv sync

# Run the agent server
cd agents/job_hunting_agent
uv run .
```

## Usage

### Running the Agent Server
```bash
# Default settings (localhost:10002)
uv run .

# Custom host and port
uv run . --host 0.0.0.0 --port 8080
```

### Testing the Agent
```bash
# Run automated tests
python test_client.py

# Run interactive mode
python test_client.py --interactive
```

### Deployment to cloud run
```bash
gcloud run deploy property-hunting-agent \
    --source agents/property_hunting_agent \
    --port=8080 \
    --allow-unauthenticated \
    --min 1 \
    --region <region> \
    --update-env-vars GOOGLE_CLOUD_LOCATION=<region> \
    --update-env-vars GOOGLE_CLOUD_PROJECT=<project-id> \
    --update-env-vars TOOLBOX_AUDIENCE=<toolbox-url> \
    --update-env-vars TOOLBOX_URL=<toolbox-url>
    --memory=1Gi
```

### API Endpoints
- `POST /send_message` - Send job search queries
- `GET /` - Agent information

## Data Sources

### BigQuery Integration
The agent connects to BigQuery via the MCP server using the `job-listing-toolset-bigquery` toolbox, which includes:

- `search-job-listing-by-title` - Search jobs by title
- Additional tools can be added to the toolbox

### Mock Data
For development and testing, the agent includes mock job data with:
- Software Engineer positions
- Data Scientist roles
- Product Manager opportunities
- DevOps Engineer positions
- Frontend Developer roles

## Agent Workflow

1. **Query Processing**: Converts user input to lowercase for case-insensitive search
2. **Job Search**: Uses the BigQuery toolbox to search job listings
3. **Result Formatting**: Presents results in a user-friendly format with emojis
4. **Response Delivery**: Returns formatted job listings to the user

## Future Enhancements

### Planned Sequential Tasks
- **Job Filtering**: Filter results by salary, location, company size
- **Job Scoring**: Rank jobs based on user preferences and requirements
- **Application Tracking**: Track job applications and follow-ups
- **Skill Matching**: Match user skills with job requirements
- **Salary Analysis**: Provide salary insights and comparisons

### Advanced Features
- Resume parsing and matching
- Interview preparation assistance
- Company research and insights
- Salary negotiation guidance
- Career path recommendations

## Development

### Adding New Tools
1. Add new tools to the `job-listing-toolset-bigquery` toolbox
2. Update the agent prompt to use new tools
3. Test with the test client

### Customizing the Agent
- Modify the prompt in `agent.py` for different behaviors
- Add new mock data for testing
- Extend the agent executor for additional functionality

## Troubleshooting

### Common Issues
1. **Toolbox Connection**: Ensure MCP server is running and accessible
2. **BigQuery Permissions**: Verify Google Cloud credentials and permissions
3. **Port Conflicts**: Change the default port if 10002 is in use

### Debug Mode
Enable debug logging by setting the log level:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0. 