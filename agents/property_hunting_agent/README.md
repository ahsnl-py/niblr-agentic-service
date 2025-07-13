# Property Hunting AI Agent

A sophisticated property hunting AI agent built using Google's Agent Development Kit (ADK) that automates the entire property search process from scraping listings to delivering personalized recommendations.

## Architecture

The agent follows a modular sub-agent architecture:

```
agents/property_hunting/
├── agent.py                    # Main orchestration agent
├── sub_agents/
│   ├── __init__.py            # Sub-agents package
│   ├── web_scraper/
│   │   ├── __init__.py
│   │   └── agent.py           # WebScraperAgent
│   ├── filter/
│   │   ├── __init__.py
│   │   └── agent.py           # FilterAgent
│   ├── score/
│   │   ├── __init__.py
│   │   └── agent.py           # ScoreAgent
│   └── notification/
│       ├── __init__.py
│       └── agent.py           # NotificationAgent
├── test_client.py             # Test suite
├── example.py                 # Usage example
└── README.md                  # This file
```

## Features

### 🏠 Sequential Workflow
The agent follows a 4-step sequential process:

1. **WebScraperAgent** - Scrapes property listings from real estate websites
2. **FilterAgent** - Filters listings based on user-defined criteria
3. **ScoreAgent** - Ranks properties using weighted scoring based on user preferences
4. **NotificationAgent** - Sends top 5 listings to the user via email (mocked)

### 🎯 Smart Filtering
- Budget constraints
- Bedroom requirements (min/max)
- Location preferences
- Property type filtering
- Size requirements
- Must-have amenities

### 📊 Intelligent Scoring
Properties are scored based on:
- Proximity to transport (configurable weight)
- Property size comparison
- Available amenities
- Price competitiveness
- Location desirability

### 🔧 Flexible Configuration
- Customizable user criteria
- Adjustable preference weights
- Support for multiple property websites
- Configurable listing limits

### 🏗️ Modular Design
- Each sub-agent is independent and reusable
- Easy to extend with new sub-agents
- Clear separation of concerns
- Consistent ADK patterns

## Installation

Ensure you have the Google ADK installed and configured:

```bash
pip install google-adk
```

## Quick Start

### Basic Usage

```python
from agent import run_property_hunting_pipeline, UserCriteria, UserPreferences

# Define your search criteria
criteria = UserCriteria(
    max_budget=500000,
    min_bedrooms=2,
    max_bedrooms=4,
    preferred_locations=["London", "Manchester"],
    property_type="house",
    min_square_feet=800
)

# Define your preferences for scoring
preferences = UserPreferences(
    proximity_to_transport_weight=0.3,
    size_weight=0.2,
    amenities_weight=0.2,
    price_weight=0.15,
    location_weight=0.15
)

# Run the pipeline
results = run_property_hunting_pipeline(
    site_url="rightmove.co.uk",
    user_criteria=criteria,
    user_preferences=preferences,
    max_listings=20
)

print(f"Found {len(results['top_listings'])} top properties!")
```

### Advanced Usage

```python
# Luxury property search
luxury_criteria = UserCriteria(
    max_budget=2000000,
    min_bedrooms=4,
    preferred_locations=["Kensington", "Chelsea"],
    property_type="house",
    min_square_feet=2000,
    must_have_amenities=["garden", "parking", "gym"]
)

luxury_preferences = UserPreferences(
    proximity_to_transport_weight=0.2,
    size_weight=0.3,
    amenities_weight=0.3,
    price_weight=0.1,
    location_weight=0.1
)

results = run_property_hunting_pipeline(
    site_url="zoopla.co.uk",
    user_criteria=luxury_criteria,
    user_preferences=luxury_preferences
)
```

### Using Individual Sub-Agents

You can also use individual sub-agents directly:

```python
from sub_agents import web_scraper_agent, filter_agent, score_agent, notification_agent

# Use web scraper agent directly
from google.adk.context import Context

ctx = Context()
ctx.session.state["site_url"] = "rightmove.co.uk"
result = web_scraper_agent.run(ctx)
listings = ctx.session.state.get("scraped_listings", [])
```

## Data Structures

### PropertyListing
```python
@dataclass
class PropertyListing:
    title: str
    price: str
    location: str
    link: str
    image: Optional[str] = None
    description: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    property_type: Optional[str] = None
    square_feet: Optional[int] = None
```

### UserCriteria
```python
@dataclass
class UserCriteria:
    max_budget: Optional[float] = None
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    preferred_locations: Optional[List[str]] = None
    property_type: Optional[str] = None
    min_square_feet: Optional[int] = None
    max_square_feet: Optional[int] = None
    must_have_amenities: Optional[List[str]] = None
```

### UserPreferences
```python
@dataclass
class UserPreferences:
    proximity_to_transport_weight: float = 0.3
    size_weight: float = 0.2
    amenities_weight: float = 0.2
    price_weight: float = 0.15
    location_weight: float = 0.15
```

## Sub-Agents

### WebScraperAgent
- **Location**: `sub_agents/web_scraper/agent.py`
- **Purpose**: Scrapes property listings from real estate websites
- **Tools**: `web_search`, `google_search`
- **Output**: JSON array of property listings

### FilterAgent
- **Location**: `sub_agents/filter/agent.py`
- **Purpose**: Filters listings based on user criteria
- **Tools**: None (pure logic)
- **Output**: Filtered JSON array

### ScoreAgent
- **Location**: `sub_agents/score/agent.py`
- **Purpose**: Ranks properties based on user preferences
- **Tools**: `google_search`
- **Output**: Scored and sorted JSON array

### NotificationAgent
- **Location**: `sub_agents/notification/agent.py`
- **Purpose**: Sends top listings to user
- **Tools**: None (mock email)
- **Output**: Notification confirmation

## Supported Websites

The agent can scrape from various UK property websites:
- Rightmove (rightmove.co.uk)
- Zoopla (zoopla.co.uk)
- OnTheMarket (onthemarket.com)
- And more...

## Testing

Run the test suite to see the agent in action:

```bash
cd agents/property_hunting
python test_client.py
```

The test suite includes scenarios for:
- Basic property hunting
- Luxury property search
- First-time buyer properties
- Family homes
- Investment properties

Or run the simple example:

```bash
python example.py
```

## Output Format

The pipeline returns a comprehensive results dictionary:

```python
{
    "success": True,
    "scraped_listings": [...],      # All scraped listings
    "filtered_listings": [...],     # Listings after filtering
    "scored_listings": [...],       # Listings with scores
    "top_listings": [...],          # Top 5 recommendations
    "notification_sent": True,      # Whether notification was sent
    "pipeline_duration": "2024-01-01T12:00:00"
}
```

## Customization

### Adding New Sub-Agents
1. Create a new directory in `sub_agents/`
2. Add `agent.py` with your agent definition
3. Add `__init__.py` to expose the agent
4. Update `sub_agents/__init__.py` to include the new agent
5. Update the main `agent.py` to use the new sub-agent

### Modifying Existing Sub-Agents
Each sub-agent is self-contained and can be modified independently:
- Update the prompt in the agent's `agent.py` file
- Modify tools as needed
- Test the individual agent before integrating

### Adding New Filter Criteria
Extend the `UserCriteria` dataclass and update the `FilterAgent` prompt to handle new filtering logic.

### Modifying Scoring Weights
Adjust the `UserPreferences` weights to change how properties are ranked based on your priorities.

### Supporting New Websites
Update the `WebScraperAgent` prompt to handle new property websites and their specific data structures.

## Error Handling

The pipeline includes comprehensive error handling:
- Graceful failure if scraping fails
- Fallback options for missing data
- Detailed logging for debugging
- Error reporting in results

## Performance Considerations

- Set appropriate `max_listings` to control scraping volume
- Use specific location filters to reduce search scope
- Consider caching results for repeated searches
- Monitor API rate limits for web scraping

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Follow the sub-agent pattern for new agents
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 