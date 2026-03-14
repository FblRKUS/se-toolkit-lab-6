#!/usr/bin/env python3
"""
Agent CLI - Tasks 1-2: LLM Agent with Tool Calling

Task 1: Basic LLM calling
Task 2: Documentation agent with read_file and list_files tools

Usage: uv run agent.py "Your question here"
"""

import sys
import json
import os
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv


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
    """Load LLM configuration from .env.agent.secret.
    
    Returns:
        dict: Configuration with api_key, api_base, model
        
    Exits:
        1 if configuration is missing or invalid
    """
    load_dotenv('.env.agent.secret')
    
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')
    
    if not all([api_key, api_base, model]):
        print("Error: Missing LLM configuration in .env.agent.secret", file=sys.stderr)
        print("Required: LLM_API_KEY, LLM_API_BASE, LLM_MODEL", file=sys.stderr)
        sys.exit(1)
    
    return {
        'api_key': api_key,
        'api_base': api_base,
        'model': model
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
    else:
        return f"Error: Unknown tool: {tool_name}"


def get_system_prompt() -> str:
    """Get the system prompt for the documentation agent.
    
    Returns:
        System prompt string
    """
    return """You are a helpful documentation assistant for a software engineering project.

Your task is to answer questions about the project by reading the documentation in the wiki/ directory.

Follow these steps:
1. Use list_files to discover what documentation files are available in the wiki/ directory
2. Use read_file to read relevant documentation files
3. Provide a concise answer based on the documentation
4. Include a source reference in your final answer in the format: wiki/filename.md#section-anchor

When citing sources:
- Always reference the specific wiki file that contains the answer
- Include a section anchor when possible (e.g., #resolving-merge-conflicts)
- Format: wiki/filename.md#section-anchor or just wiki/filename.md

Be concise and accurate. Only use information from the project files."""


def extract_source(answer: str) -> str:
    """Extract source reference from the answer text.
    
    Args:
        answer: LLM's answer text
        
    Returns:
        Source reference (e.g., wiki/file.md#section) or "unknown"
    """
    # Look for wiki/filename.md or wiki/filename.md#section patterns
    match = re.search(r'wiki/[\w-]+\.md(?:#[\w-]+)?', answer)
    if match:
        return match.group(0)
    return "unknown"


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
