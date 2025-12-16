"""Functions for processing agent responses."""

import json
from typing import Dict, Any, List, Optional
from pprint import pformat

from .utils import (
    extract_json_from_text,
    extract_text_from_artifacts,
    extract_artifacts_from_task,
)


def create_agent_response(
    content: str,
    structured_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a standardized agent response dictionary.
    
    Args:
        content: The response content (text or JSON string)
        structured_data: Optional structured data dictionary
        metadata: Optional metadata dictionary. If None and structured_data exists,
                 defaults to {"title": "Agent Response"}
    
    Returns:
        Dictionary with role, content, metadata, and optionally structured_data
    """
    # Use provided metadata or default for agent responses
    if metadata is None and structured_data:
        metadata = {"title": "Agent Response"}
    elif metadata is None and not content.startswith("🤖") and not content.startswith("🛠️"):
        # Only add default metadata for actual agent responses, not delegation/tool calls
        metadata = {"title": "Agent Response"}
    
    response = {
        "role": "assistant",
        "content": content,
        "metadata": metadata
    }
    
    if structured_data:
        response["structured_data"] = structured_data
    
    return response


def process_agent_response(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process agent event and return formatted messages.
    
    Args:
        event: Event dictionary from agent stream_query
        
    Returns:
        List of formatted message dictionaries
    """
    responses = []
    
    # First, check if event has artifacts structure (like final result from get_task)
    artifacts_text = extract_text_from_artifacts(event)
    if artifacts_text:
        # Extract structured JSON from artifacts text
        structured_data = extract_json_from_text(artifacts_text)
        
        content = json.dumps(structured_data, indent=2) if structured_data else artifacts_text
        responses.append(create_agent_response(
            content=content,
            structured_data=structured_data
        ))
    
    # Process content.parts structure (from stream_query events)
    parts = event.get("content", {}).get("parts", [])
    skip_next_response = False  # Track if we should skip the next function_response (for send_task)
    
    if parts:
        for part in parts:
            if part.get("function_call"):
                func_call = part.get("function_call")
                func_name = func_call.get("name", "")
                
                # Special handling for send_task - show only agent name and task
                if func_name == "send_task":
                    func_args = func_call.get("args", {})
                    agent_name = func_args.get("agent_name", "Unknown Agent")
                    task = func_args.get("task", "")
                    
                    # Create a clean, user-friendly message
                    content = f"🤖 **{agent_name}**\n\n{task}"
                    responses.append({
                        "role": "assistant",
                        "content": content,
                        "metadata": {"title": "🔄 Delegating to Agent"}
                    })
                    skip_next_response = True  # Skip the verbose response structure
                else:
                    # For other function calls, show simplified version
                    func_name_display = func_name.replace("_", " ").title()
                    responses.append({
                        "role": "assistant",
                        "content": f"🛠️ Calling {func_name_display}...",
                        "metadata": {"title": "🛠️ Tool Call"}
                    })
            
            elif part.get("function_response"):
                # For send_task, extract artifacts from the Task object in function_response
                if skip_next_response:
                    skip_next_response = False
                    func_response = part.get("function_response", {})
                    
                    # Try to extract artifacts from the Task object
                    # The Task object might be directly in function_response or nested in various ways
                    task_obj = None
                    if isinstance(func_response, dict):
                        # Check if function_response is the Task object itself
                        if "artifacts" in func_response or "status" in func_response:
                            task_obj = func_response
                        # Check if it's nested: function_response.response.result (like send_message response)
                        elif "response" in func_response:
                            response_obj = func_response.get("response", {})
                            if isinstance(response_obj, dict):
                                result = response_obj.get("result", {})
                            if isinstance(result, dict) and ("artifacts" in result or "status" in result):
                                task_obj = result
                        # Check if it's nested: function_response.result
                        elif "result" in func_response:
                            result = func_response.get("result", {})
                            if isinstance(result, dict) and ("artifacts" in result or "status" in result):
                                task_obj = result
                        # Also check if function_response itself has nested structures we can traverse
                        # Sometimes the Task might be nested deeper
                        elif "root" in func_response:
                            root = func_response.get("root", {})
                            if isinstance(root, dict):
                                if "result" in root:
                                    result = root.get("result", {})
                                    if isinstance(result, dict) and ("artifacts" in result or "status" in result):
                                        task_obj = result
                                elif "artifacts" in root or "status" in root:
                                    task_obj = root
                    
                    # Extract artifacts from task_obj
                    artifacts_text = extract_artifacts_from_task(task_obj) if task_obj else None
                    
                    if artifacts_text:
                        # Extract structured JSON from artifacts text (works for both properties and jobs)
                        structured_data = extract_json_from_text(artifacts_text)
                        
                        content = json.dumps(structured_data, indent=2) if structured_data else artifacts_text
                        responses.append(create_agent_response(
                            content=content,
                            structured_data=structured_data
                        ))
                        continue  # Skip showing the raw function_response
                    
                    # If no artifacts found, skip silently (don't show verbose response)
                    continue
            
            elif part.get("text"):
                # Always include text parts - these contain the actual agent responses
                # This is where the property listings, job listings, and other results will appear
                text_content = part.get("text", "")
                if text_content and text_content.strip():
                    # Try to extract structured JSON from the text (handles markdown, code blocks, etc.)
                    # This works for both property_listings (with "properties") and job_listings (with "jobs")
                    structured_data = extract_json_from_text(text_content)
                    
                    # If extraction failed but text looks like it contains property/job data,
                    # check if we can find JSON elsewhere in the event
                    if not structured_data:
                        # Check if the part itself has additional data
                        part_dict = part if isinstance(part, dict) else {}
                        if "structured_output" in part_dict:
                            try:
                                structured_output = part_dict["structured_output"]
                                structured_data = json.loads(structured_output) if isinstance(structured_output, str) else structured_output
                            except (json.JSONDecodeError, TypeError):
                                pass
                    
                    # Determine content - use JSON if structured data found, otherwise use original text
                    content = json.dumps(structured_data, indent=2) if structured_data else text_content
                    
                    responses.append(create_agent_response(
                        content=content,
                        structured_data=structured_data
                    ))
            else:
                formatted_unknown = f"Unknown agent response part:\n\n```python\n{pformat(part, indent=2, width=80)}\n```"
                responses.append({
                    "role": "assistant",
                    "content": formatted_unknown,
                    "metadata": None
                })
    
    return responses

