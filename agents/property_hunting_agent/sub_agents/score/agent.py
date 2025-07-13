"""
Score Sub-Agent for Property Hunting

This agent is responsible for ranking property listings based on user preferences.
"""

from google.adk.agents import Agent
import json

MODEL = "gemini-2.5-flash"

DISTRICT_DATA = {
  "districts": {
    "Praha 1": {
      "desirability_score": 100,
      "average_rent_per_m2": 450,
      "pros": ["Historic center", "Best location", "Prestigious"],
      "cons": ["Expensive", "Touristy", "Noisy"]
    },
    "Praha 2": {
      "desirability_score": 90,
      "average_rent_per_m2": 400,
      "pros": ["Vinohrady/Nové Město", "Upscale cafes", "Expat-friendly"],
      "cons": ["Still pricey", "Limited parking"]
    },
    "Praha 6": {
      "desirability_score": 85,
      "average_rent_per_m2": 380,
      "pros": ["Dejvice/Bubeneč", "Diplomatic area", "Quiet & green"],
      "cons": ["Far from center", "Fewer nightlife options"]
    },
    "Praha 7": {
      "desirability_score": 80,
      "average_rent_per_m2": 350,
      "pros": ["Holešovice", "Trendy", "Good transport"],
      "cons": ["Rapidly gentrifying", "Some industrial areas"]
    },
    "Praha 5": {
      "desirability_score": 75,
      "average_rent_per_m2": 340,
      "pros": ["Anděl/Smíchov", "Business hub", "Metro access"],
      "cons": ["Crowded", "Tourists near Vyšehrad"]
    },
    "Praha 3": {
      "desirability_score": 70,
      "average_rent_per_m2": 320,
      "pros": ["Žižkov", "Affordable", "Lively bars"],
      "cons": ["Grittier", "Noise at night"]
    },
    "Praha 4": {
      "desirability_score": 65,
      "average_rent_per_m2": 300,
      "pros": ["Pankrác/Budějovická", "Good for families"],
      "cons": ["Suburban feel", "Longer commute"]
    },
    "Praha 8": {
      "desirability_score": 60,
      "average_rent_per_m2": 290,
      "pros": ["Karlín (rising)", "New developments"],
      "cons": ["Libeň still rough", "Flood risk areas"]
    },
    "Praha 9": {
      "desirability_score": 50,
      "average_rent_per_m2": 270,
      "pros": ["Cheap", "Spacious"],
      "cons": ["Far from center", "Industrial zones"]
    },
    "Praha 10": {
      "desirability_score": 45,
      "average_rent_per_m2": 260,
      "pros": ["Residential", "Parks"],
      "cons": ["Boring", "Weak public transport"]
    }
  },
  "notes": {
    "source": "Based on 2024 rental market trends, expat forums, and real estate reports",
    "scaling": "Desirability score (0-100) considers prestige, prices, safety, and amenities",
    "adjustments": "Fine-tune scores for specific streets (e.g., Žižkov's 'Riegerovy sady' > 'Malešická')"
  }
}

def analyze_properties(property_list_json: str) -> str:
    """
    property_list_json: A JSON string representing a list of property dictionaries.
    Returns: A JSON string of the scored properties.
    """
    property_list = json.loads(property_list_json)
    scored_properties = []
    
    for prop in property_list:
        # Extract district (e.g., "Praha 3 - Žižkov" → "Praha 3")
        location = prop.get("location", "")
        district = location.split(",")[-1].strip().split(" - ")[0] if location else "Unknown"
        
        # Get location score (default to 50 if district not found)
        location_score = DISTRICT_DATA["districts"].get(district, {}).get("desirability_score", 50)
        
        # Parse price and size
        try:
            price = float(prop.get("price", "0"))
            size_str = prop.get("size", "0m2").replace("m2", "").strip()
            size = float(size_str) if size_str else 0
            price_per_m2 = price / size if size > 0 else 0
        except (ValueError, ZeroDivisionError):
            price_per_m2 = 0
            size = 0
        
        # Normalize scores (0-100)
        # Price score: Lower price/m² = higher score
        max_price_per_m2 = 1000  # Adjust based on your data range
        price_score = max(0, 100 - (price_per_m2 / max_price_per_m2 * 100)) if price_per_m2 > 0 else 50
        
        # Size score: Larger size = higher score
        max_size = 50  # Adjust based on your data range
        size_score = min(100, (size / max_size) * 100) if size > 0 else 50
        
        # Weighted total
        total_score = (
            0.4 * price_score +
            0.3 * size_score +
            0.3 * location_score
        )
        
        scored_prop = {
            **prop,
            "total_score": round(total_score, 1),
            "price_score": round(price_score, 1),
            "size_score": round(size_score, 1),
            "location_score": location_score,
            "district": district
        }
        scored_properties.append(scored_prop)
    
    # Rank by total_score (descending)
    ranked_properties = sorted(scored_properties, key=lambda x: -x["total_score"])
    
    # Return top 3 + explanations
    top_3_properties = ranked_properties[:3]
    return json.dumps(top_3_properties)

SCORE_AGENT_PROMPT = """
You are a Prague real estate assistant. Your task is:
    1. Load the provided list of properties from the previous agent.
    2. Calculate each property's score using the `analyze_properties` function.
    3. Rank properties from highest to lowest score.
    4. Show the top 3 best-value properties with details.
    5. Explain why they scored well (price, size, location).

**Properties from PropertyListingAgent:**
{property_listings}

Rules:
    - Always validate input data (e.g., missing price/size).
    - If no properties exist, return a friendly error.
    - Format output clearly with emojis for readability.
    - Use the analyze_properties function to score the properties.
"""

score_agent = Agent(
    model=MODEL,
    name="score_agent",
    instruction=SCORE_AGENT_PROMPT,
    output_key="scored_listings",  # This stores the output in state
    tools=[analyze_properties],
) 