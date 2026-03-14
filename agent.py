#!/usr/bin/env python3
"""
Agent CLI - Tasks 1-3: LLM Agent with Tool Calling

Task 1: Basic LLM calling
Task 2: Documentation agent with read_file and list_files tools
Task 3: System agent with query_api tool for backend API queries

Usage: uv run agent.py "Your question here"
"""

import sys
import json
import os
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import requests


def parse_args() -> str:
    """Parse command line arguments and return the question.
    
    Returns:
        str: User's question
        
    Exits:
        1 if no question provided
    """
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    if not question.strip():
        print("Error: Question cannot be empty", file=sys.stderr)
        sys.exit(1)
    
    return question


def load_config() -> Dict[str, str]:
    """Load configuration from environment files and variables.
    
    Returns:
        dict: Configuration with LLM and backend API settings
        
    Exits:
        1 if configuration is missing or invalid
    """
    # Load both env files (order matters - later ones override)
    load_dotenv('.env.agent.secret')
    load_dotenv('.env.docker.secret')
    
    # LLM configuration
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')
    
    # Backend API configuration
    lms_api_key = os.getenv('LMS_API_KEY')
    agent_api_base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
    
    # Validate required variables
    if not all([api_key, api_base, model]):
        print("Error: Missing LLM configuration", file=sys.stderr)
        print("Required: LLM_API_KEY, LLM_API_BASE, LLM_MODEL", file=sys.stderr)
        sys.exit(1)
    
    if not lms_api_key:
        print("Warning: LMS_API_KEY not set, query_api will not work", file=sys.stderr)
    
    return {
        'api_key': api_key,
        'api_base': api_base,
        'model': model,
        'lms_api_key': lms_api_key,
        'agent_api_base_url': agent_api_base_url
    }


# Tool implementations

def read_file(path: str) -> str:
    """Read a file from the project repository.
    
    Args:
        path: Relative path from project root
        
    Returns:
        File contents or error message
    """
    project_root = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.abspath(os.path.join(project_root, path))
    
    # Security: prevent directory traversal
    if not file_path.startswith(project_root):
        return f"Error: Access denied - path outside project directory"
    
    if not os.path.exists(file_path):
        return f"Error: File not found: {path}"
    
    if not os.path.isfile(file_path):
        return f"Error: Not a file: {path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root
        
    Returns:
        Newline-separated list of entries or error message
    """
    project_root = os.path.abspath(os.path.dirname(__file__))
    dir_path = os.path.abspath(os.path.join(project_root, path))
    
    # Security: prevent directory traversal
    if not dir_path.startswith(project_root):
        return f"Error: Access denied - path outside project directory"
    
    if not os.path.exists(dir_path):
        return f"Error: Directory not found: {path}"
    
    if not os.path.isdir(dir_path):
        return f"Error: Not a directory: {path}"
    
    try:
        entries = os.listdir(dir_path)
        return '\n'.join(sorted(entries))
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: Optional[str] = None) -> str:
    """Query the backend API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., /items/)
        body: Optional JSON request body
        
    Returns:
        JSON string with status_code and body
    """
    # Get configuration from environment
    api_base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')
    api_key = os.getenv('LMS_API_KEY')
    
    if not api_key:
        return json.dumps({
            "status_code": 0,
            "body": "Error: LMS_API_KEY not set in environment"
        })
    
    # Build full URL
    url = api_base_url.rstrip('/') + path
    
    # Prepare headers
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Make request (disable SSL verification for local development)
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=body,
            timeout=30.0,
            verify=False
        )
        
        # Parse response body
        try:
            body_json = response.json()
        except:
            body_json = response.text
        
        return json.dumps({
            "status_code": response.status_code,
            "body": body_json
        }, ensure_ascii=False)
        
    except requests.exceptions.ConnectionError:
        return json.dumps({
            "status_code": 0,
            "body": f"Error: Cannot connect to {url}. Is the backend running?"
        })
    except Exception as e:
        return json.dumps({
            "status_code": 0,
            "body": f"Error: {str(e)}"
        })


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get OpenAI function-calling schemas for available tools.
    
    Returns:
        List of tool schemas
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read contents of a file from the project repository. Use this to find documentation, code, or configuration files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root, e.g. 'wiki/git-workflow.md'"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to discover what documentation is available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root, e.g. 'wiki'"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Query the deployed backend API to get system facts or data. Use this for questions about: framework, ports, database content, analytics, scores, items. Returns HTTP status code and response body.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method: GET, POST, PUT, DELETE",
                            "enum": ["GET", "POST", "PUT", "DELETE"]
                        },
                        "path": {
                            "type": "string",
                            "description": "API endpoint path starting with /, e.g. '/items/' or '/analytics/completion-rate?lab=lab-04'"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests"
                        }
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Execute a tool by name with given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        
    Returns:
        Tool execution result as string
    """
    if tool_name == "read_file":
        return read_file(tool_args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(tool_args.get("path", ""))
    elif tool_name == "query_api":
        return query_api(
            method=tool_args.get("method", "GET"),
            path=tool_args.get("path", "/"),
            body=tool_args.get("body")
        )
    else:
        return f"Error: Unknown tool: {tool_name}"


def get_system_prompt() -> str:
    """Get the system prompt for the system agent.
    
    Returns:
        System prompt string
    """
    return """You are a helpful assistant for a software engineering project.

You have access to three types of tools:

1. **query_api** - Query the deployed backend API
   - Use for: system facts (framework, ports), database content (items, scores), analytics data
   - Examples: "How many items?", "What framework?", "Get completion rate for lab-04"
   
2. **read_file** - Read files from the project repository
   - Use for: source code inspection, configuration files, implementation details
   - Examples: "Show the Item model", "Read docker-compose.yml", "Find the bug in routes.py"
   
3. **list_files** - List directory contents
   - Use for: discovering available wiki documentation, exploring project structure
   - Examples: "What wiki files exist?", "List files in backend/"

**Strategy for answering questions:**

1. **System/data questions** → Use query_api first
   - "How many items?" → GET /items/ and count
   - "What framework?" → GET /docs or read backend source code
   - "Get analytics for lab-04" → GET /analytics/completion-rate?lab=lab-04

2. **Documentation questions** → Use list_files + read_file
   - "How to resolve merge conflicts?" → read wiki/git-workflow.md
   - "How to set up Docker?" → read wiki/docker.md

3. **Code/implementation questions** → Use read_file on source
   - "Show the database model" → read backend/models.py
   - "Find the bug in endpoint X" → read backend/routes/X.py

4. **Multi-step questions** → Chain tools
   - "Why does /analytics/X fail?" → query_api to see error → read_file to find bug

Always include a source reference when answering from wiki (format: wiki/file.md#section).

Be concise and accurate."""


def extract_source(answer: str) -> str:
    """Extract source reference from the answer text.
    
    Args:
        answer: LLM's answer text
        
    Returns:
        Source reference (e.g., wiki/file.md#section) or empty string
    """
    # Look for wiki/filename.md or wiki/filename.md#section patterns
    match = re.search(r'wiki/[\w-]+\.md(?:#[\w-]+)?', answer)
    if match:
        return match.group(0)
    # Source is optional for system questions
    return ""


def agentic_loop(question: str, api_key: str, api_base: str, model: str, max_iterations: int = 10) -> Dict[str, Any]:
    """Run the agentic loop: LLM calls tools, we execute them, repeat until answer.
    
    Args:
        question: User's question
        api_key: API authentication key
        api_base: API base URL
        model: Model name to use
        max_iterations: Maximum number of tool call iterations
        
    Returns:
        Dict with answer, source, and tool_calls
        
    Exits:
        1 on API errors
    """
    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": question}
        ]
        
        tool_call_history = []
        tools = get_tool_schemas()
        
        print(f"Starting agentic loop (max {max_iterations} iterations)", file=sys.stderr)
        
        for iteration in range(max_iterations):
            print(f"Iteration {iteration + 1}", file=sys.stderr)
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                timeout=60.0
            )
            
            message = response.choices[0].message
            
            # No tool calls = final answer
            if not message.tool_calls:
                print(f"Final answer received ({len(message.content)} chars)", file=sys.stderr)
                return {
                    "answer": message.content,
                    "source": extract_source(message.content),
                    "tool_calls": tool_call_history
                }
            
            # Execute tool calls
            print(f"Executing {len(message.tool_calls)} tool call(s)", file=sys.stderr)
            messages.append(message)  # Add assistant message with tool calls
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                print(f"  Tool: {tool_name}, Args: {tool_args}", file=sys.stderr)
                
                # Execute tool
                result = execute_tool(tool_name, tool_args)
                result_preview = result[:100] + "..." if len(result) > 100 else result
                print(f"  Result: {result_preview}", file=sys.stderr)
                
                # Record in history
                tool_call_history.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        
        # Hit max iterations
        print(f"Max iterations ({max_iterations}) reached", file=sys.stderr)
        return {
            "answer": "Maximum iterations reached without final answer.",
            "source": "unknown",
            "tool_calls": tool_call_history
        }
        
    except Exception as e:
        print(f"Error in agentic loop: {e}", file=sys.stderr)
        sys.exit(1)


def format_output(answer: str, source: str, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Format the answer as JSON with required fields.
    
    Args:
        answer: LLM's answer text
        source: Source reference (e.g., wiki/file.md#section)
        tool_calls: List of tool calls made
        
    Returns:
        dict: JSON structure with answer, source, and tool_calls
    """
    return {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }


def main():
    """Main entry point: orchestrate the agent workflow."""
    # Parse arguments
    question = parse_args()
    print(f"Question: {question}", file=sys.stderr)
    
    # Load configuration
    config = load_config()
    print(f"Using model: {config['model']}", file=sys.stderr)
    
    # Run agentic loop
    result_data = agentic_loop(
        question=question,
        api_key=config['api_key'],
        api_base=config['api_base'],
        model=config['model']
    )
    
    # Format and output result
    result = format_output(
        answer=result_data['answer'],
        source=result_data['source'],
        tool_calls=result_data['tool_calls']
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
