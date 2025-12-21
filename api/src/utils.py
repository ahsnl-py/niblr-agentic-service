"""Utility functions for data extraction and conversion."""

import json
import re
from typing import Dict, Any, Optional, List


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


def parse_session_info_to_messages(session_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse session_info from Vertex AI and format messages with metadata.
    
    Parses events from session_info.json format and formats agent responses
    according to agent-response-sample.json format while preserving conversation history.
    
    Args:
        session_info: Session info dictionary from REMOTE_APP.get_session()
        
    Returns:
        List of formatted message dictionaries with:
        - User messages: role="user", content, timestamp
        - Agent messages: role="assistant", content, structured_data, metadata
    """
    if not session_info or not isinstance(session_info, dict):
        return []
    
    events = session_info.get("events", [])
    if not events:
        return []
    
    messages = []
    first_timestamp = None
    last_timestamp = None
    collected_metadata = {
        "usage_metadata": None,
        "agent_name": None,
        "author": None,
        "model_version": None,
    }
    
    # Track agent response boundaries (for calculating response time)
    agent_response_start = None
    agent_response_end = None
    
    # Track artifact content (fallback if no model text found)
    artifact_content = None
    artifact_structured = None
    
    for event in events:
        if not isinstance(event, dict):
            continue
        
        content = event.get("content", {})
        if not isinstance(content, dict):
            continue
        
        parts = content.get("parts", [])
        role = content.get("role", "")
        author = event.get("author", "")
        timestamp = event.get("timestamp")
        usage_metadata = event.get("usageMetadata") or event.get("usage_metadata")
        model_version = event.get("modelVersion") or event.get("model_version")
        
        # Track timestamps
        if timestamp:
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp
        
        # Collect metadata from events (only from agent events, not user)
        if author != "user":
            if usage_metadata and not collected_metadata["usage_metadata"]:
                collected_metadata["usage_metadata"] = usage_metadata
            
            if author and not collected_metadata["author"]:
                collected_metadata["author"] = author
            
            if model_version and not collected_metadata["model_version"]:
                collected_metadata["model_version"] = model_version
        
        # Process each part
        for part in parts:
            if not isinstance(part, dict):
                continue
            
            # 1. Extract user messages (preserve as-is)
            if role == "user" and author == "user":
                text = part.get("text")
                if text and text.strip():
                    messages.append({
                        "role": "user",
                        "content": text.strip(),
                        "timestamp": timestamp
                    })
            
            # 2. Extract agent name from function_response artifacts (for metadata)
            # Note: functionResponse can appear in both "user" role (response to routing agent) 
            # and "model" role events
            function_response = part.get("functionResponse")
            if function_response and isinstance(function_response, dict):
                response_data = function_response.get("response", {})
                if isinstance(response_data, dict):
                    result = response_data.get("result", {})
                    if isinstance(result, dict):
                        artifacts = result.get("artifacts", [])
                        for artifact in artifacts:
                            if isinstance(artifact, dict):
                                artifact_name = artifact.get("name")
                                if artifact_name and not collected_metadata["agent_name"]:
                                    collected_metadata["agent_name"] = artifact_name
                                
                                # Extract artifacts text (raw JSON from artifacts)
                                artifact_parts = artifact.get("parts", [])
                                for artifact_part in artifact_parts:
                                    if isinstance(artifact_part, dict):
                                        artifact_text = artifact_part.get("text")
                                        if artifact_text and artifact_text.strip():
                                            # Mark agent response start (first artifact)
                                            if agent_response_start is None and timestamp:
                                                agent_response_start = timestamp
                                            
                                            # Store artifact text for later use (if no model text found)
                                            # We'll use this as fallback content
                                            if artifact_content is None:
                                                artifact_content = artifact_text
                                                artifact_structured = extract_json_from_text(artifact_text)
                                            
                                            # Mark agent response end (last artifact)
                                            if timestamp:
                                                agent_response_end = timestamp
            
            # 3. Extract text from agent responses (model role) - this is the final formatted response
            # Prioritize this over artifacts as it's the formatted output
            if role == "model" and author != "user":
                text = part.get("text")
                if text and text.strip():
                    # Mark agent response start
                    if agent_response_start is None and timestamp:
                        agent_response_start = timestamp
                    
                    # Extract structured JSON
                    structured_data = extract_json_from_text(text)
                    
                    # Format as agent response (this is the primary response)
                    agent_message = {
                        "role": "assistant",
                        "content": text.strip(),  # Preserve as-is (formatted markdown JSON)
                    }
                    
                    if structured_data:
                        agent_message["structured_data"] = structured_data
                    
                    messages.append(agent_message)
                    
                    # Mark agent response end
                    if timestamp:
                        agent_response_end = timestamp
                    
                    # Clear artifact content since we have model text (prioritize model text)
                    artifact_content = None
                    artifact_structured = None
    
    # If we have artifact content but no model text, use artifact as fallback
    if artifact_content:
        agent_message = {
            "role": "assistant",
            "content": artifact_content,  # Preserve as-is (raw JSON)
        }
        
        if artifact_structured:
            agent_message["structured_data"] = artifact_structured
        
        messages.append(agent_message)
    
    # Calculate response time if we have agent response boundaries
    if agent_response_start and agent_response_end:
        response_time = agent_response_end - agent_response_start
        collected_metadata["response_time_seconds"] = round(response_time, 3)
    elif first_timestamp and last_timestamp:
        # Fallback: use first to last timestamp
        response_time = last_timestamp - first_timestamp
        collected_metadata["response_time_seconds"] = round(response_time, 3)
    
    # Clean up metadata - only include non-None values
    clean_metadata = {k: v for k, v in collected_metadata.items() if v is not None}
    
    # Add metadata to all agent responses
    if clean_metadata:
        for message in messages:
            if message.get("role") == "assistant":
                message["metadata"] = clean_metadata.copy()
    
    return messages

