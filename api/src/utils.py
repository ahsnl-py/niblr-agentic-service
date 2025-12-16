"""Utility functions for data extraction and conversion."""

import json
import re
from typing import Dict, Any, Optional


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from text content.
    
    Handles two main cases:
    1. Plain JSON strings (most common - agents return structured JSON directly)
    2. JSON in markdown code blocks (fallback - routing agent might format as markdown)
    
    Args:
        text: Text content that may contain JSON
        
    Returns:
        Parsed JSON dictionary if found, None otherwise
    """
    if not text or not text.strip():
        return None
    
    text_stripped = text.strip()
    
    # Case 1: Try parsing the entire text as JSON (most common case now)
    # This handles when agents return pure JSON directly
    try:
        parsed = json.loads(text_stripped)
        if isinstance(parsed, dict) and ("properties" in parsed or "jobs" in parsed):
            return parsed
    except json.JSONDecodeError:
        pass
    
    # Case 2: Try to extract JSON from markdown code blocks (fallback)
    # This handles when the routing agent wraps JSON in markdown formatting
    # First, try to find JSON code blocks and extract the content
    code_block_patterns = [
        r'```json\s*(.*?)\s*```',  # JSON in code block with json tag
        r'```\s*(.*?)\s*```',      # JSON in generic code block
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            match_stripped = match.strip()
            if not match_stripped.startswith('{'):
                continue
            # Try to find the complete JSON object by counting braces
            brace_count = 0
            json_end = -1
            in_string = False
            escape_next = False
            
            for i, char in enumerate(match_stripped):
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
            
            if json_end > 0:
                try:
                    json_str = match_stripped[:json_end]
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and ("properties" in parsed or "jobs" in parsed):
                        return parsed
                except json.JSONDecodeError:
                    continue
    
    # If neither case works, return None (it's likely plain text, not JSON)
    return None


def extract_text_from_artifacts(event: Dict[str, Any]) -> Optional[str]:
    """Extract text from result.artifacts[].parts[] structure.
    
    This matches the structure returned by get_task in test_client:
    {
        "result": {
            "artifacts": [{
                "parts": [{
                    "kind": "text",
                    "text": "{...JSON...}"
                }]
            }]
        }
    }
    
    Args:
        event: Event dictionary that may contain artifacts
        
    Returns:
        Extracted text from artifacts, or None if not found
    """
    # Check for result.artifacts structure
    result = event.get("result")
    if not result:
        return None
    
    artifacts = result.get("artifacts", [])
    if not artifacts:
        return None
    
    # Extract text from all artifacts
    texts = []
    for artifact in artifacts:
        if isinstance(artifact, dict):
            parts = artifact.get("parts", [])
            for part in parts:
                if isinstance(part, dict):
                    # Check if kind is "text" and text field exists
                    if part.get("kind") == "text" and part.get("text"):
                        texts.append(part.get("text"))
                    # Also check if text exists without kind field
                    elif part.get("text") and "kind" not in part:
                        texts.append(part.get("text"))
    
    # Return the first non-empty text, or join them if multiple
    if texts:
        return "\n".join([t for t in texts if t and t.strip()])
    
    return None


def extract_artifacts_from_task(task_obj: Dict[str, Any]) -> Optional[str]:
    """Extract text from artifacts in a Task object.
    
    Args:
        task_obj: Task object dictionary that may contain artifacts
        
    Returns:
        Extracted text from artifacts, or None if not found
    """
    if not isinstance(task_obj, dict):
        return None
    
    artifacts = task_obj.get("artifacts", [])
    if not artifacts:
        return None
    
    # Extract text from artifacts
    for artifact in artifacts:
        if isinstance(artifact, dict):
            parts_list = artifact.get("parts", [])
            for part_item in parts_list:
                if isinstance(part_item, dict):
                    # Check if kind is "text" and text field exists
                    if part_item.get("kind") == "text" and part_item.get("text"):
                        return part_item.get("text")
                    # Also check if text exists without kind field
                    elif part_item.get("text") and "kind" not in part_item:
                        return part_item.get("text")
    
    return None


def convert_event_to_dict(event: Any) -> Dict[str, Any]:
    """Convert an event object to a dictionary.
    
    Args:
        event: Event object (may be dict, Pydantic model, or other)
        
    Returns:
        Dictionary representation of the event
    """
    if isinstance(event, dict):
        return event
    
    if hasattr(event, 'model_dump'):
        return event.model_dump()
    elif hasattr(event, '__dict__'):
        return event.__dict__
    else:
        return {"content": {"parts": []}}

