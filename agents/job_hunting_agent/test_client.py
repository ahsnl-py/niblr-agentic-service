#!/usr/bin/env python3
"""
Test client for Job Hunting Agent

This script tests the Job Hunting Agent by sending requests to the A2A server
and displaying the responses.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
HOST = "localhost"
PORT = 10002
BASE_URL = f"http://{HOST}:{PORT}"

# Test queries for job hunting
TEST_QUERIES = [
    "software engineer jobs in prague",
    "data scientist positions",
    "remote developer opportunities",
    "marketing jobs in czech republic",
    "python developer",
    "frontend developer",
    "devops engineer",
    "product manager",
]


async def send_message_to_agent(query: str) -> Dict[str, Any]:
    """
    Send a message to the Job Hunting Agent and return the response.
    
    Args:
        query: The job search query to send
        
    Returns:
        Dictionary containing the response data
    """
    url = f"{BASE_URL}/send_message"
    
    payload = {
        "message": {
            "role": "user",
            "parts": [{"text": query}]
        }
    }
    
    logger.info(f"Sending query: {query}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            return {"error": f"Request error: {e}"}


def extract_response_text(response_data: Dict[str, Any]) -> str:
    """
    Extract the response text from the A2A response structure.
    
    Args:
        response_data: The response data from the agent
        
    Returns:
        The extracted response text
    """
    try:
        # Navigate through the response structure
        if "response" in response_data:
            response = response_data["response"]
            
            # Check if it's a SendMessageSuccessResponse
            if "root" in response:
                root = response["root"]
                
                # Handle different response types
                if "message" in root:
                    message = root["message"]
                    if "parts" in message and message["parts"]:
                        # Extract text from parts
                        parts = message["parts"]
                        text_parts = []
                        
                        for part in parts:
                            if "root" in part:
                                part_root = part["root"]
                                if "text" in part_root:
                                    text_parts.append(part_root["text"])
                                elif "kind" in part_root and part_root["kind"] == "text":
                                    text_parts.append(part_root.get("text", ""))
                            elif "text" in part:
                                text_parts.append(part["text"])
                        
                        if text_parts:
                            return "\n".join(text_parts)
                
                # Fallback: try to extract any text content
                if "text" in root:
                    return root["text"]
        
        # If we can't extract text, return the full response for debugging
        return f"Could not extract text from response. Full response: {json.dumps(response_data, indent=2)}"
        
    except Exception as e:
        logger.error(f"Error extracting response text: {e}")
        return f"Error extracting response: {e}\nFull response: {json.dumps(response_data, indent=2)}"


async def test_job_hunting_agent():
    """
    Test the Job Hunting Agent with various queries.
    """
    logger.info("🧪 Testing Job Hunting Agent")
    logger.info(f"📍 Agent URL: {BASE_URL}")
    logger.info("=" * 60)
    
    for i, query in enumerate(TEST_QUERIES, 1):
        logger.info(f"\n🔍 Test {i}: {query}")
        logger.info("-" * 40)
        
        # Send the query to the agent
        response_data = await send_message_to_agent(query)
        
        # Check for errors
        if "error" in response_data:
            logger.error(f"❌ Error: {response_data['error']}")
            continue
        
        # Extract and display the response
        response_text = extract_response_text(response_data)
        
        if response_text:
            logger.info("✅ Response:")
            print(response_text)
        else:
            logger.warning("⚠️ No response text found")
            logger.debug(f"Full response data: {json.dumps(response_data, indent=2)}")
        
        # Add a small delay between requests
        await asyncio.sleep(1)
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 Testing completed!")


async def interactive_mode():
    """
    Run the test client in interactive mode.
    """
    logger.info("🎯 Interactive Job Hunting Agent Test")
    logger.info(f"📍 Agent URL: {BASE_URL}")
    logger.info("💡 Type 'quit' to exit")
    logger.info("=" * 60)
    
    while True:
        try:
            # Get user input
            query = input("\n🔍 Enter your job search query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                logger.info("👋 Goodbye!")
                break
            
            if not query:
                logger.warning("⚠️ Please enter a query")
                continue
            
            # Send the query to the agent
            response_data = await send_message_to_agent(query)
            
            # Check for errors
            if "error" in response_data:
                logger.error(f"❌ Error: {response_data['error']}")
                continue
            
            # Extract and display the response
            response_text = extract_response_text(response_data)
            
            if response_text:
                logger.info("✅ Response:")
                print(response_text)
            else:
                logger.warning("⚠️ No response text found")
                logger.debug(f"Full response data: {json.dumps(response_data, indent=2)}")
                
        except KeyboardInterrupt:
            logger.info("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")


def main():
    """
    Main function to run the test client.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_mode())
    else:
        asyncio.run(test_job_hunting_agent())


if __name__ == "__main__":
    main() 