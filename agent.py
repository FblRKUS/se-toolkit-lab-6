#!/usr/bin/env python3
"""
Agent CLI - Task 1: Call an LLM from Code

Takes a user question, sends it to BotHub API, returns JSON answer.
Usage: uv run agent.py "Your question here"
"""

import sys
import json
import os
from typing import Dict, Any
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


def call_llm(question: str, api_key: str, api_base: str, model: str) -> str:
    """Call BotHub API with the user's question.
    
    Args:
        question: User's question
        api_key: API authentication key
        api_base: API base URL
        model: Model name to use
        
    Returns:
        str: LLM's answer
        
    Exits:
        1 on API errors or timeouts
    """
    try:
        print(f"Calling LLM model: {model}", file=sys.stderr)
        
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer the user's question concisely and accurately."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            timeout=60.0
        )
        
        answer = response.choices[0].message.content
        print(f"Received answer ({len(answer)} chars)", file=sys.stderr)
        
        return answer
        
    except Exception as e:
        print(f"Error calling LLM API: {e}", file=sys.stderr)
        sys.exit(1)


def format_output(answer: str) -> Dict[str, Any]:
    """Format the answer as JSON with required fields.
    
    Args:
        answer: LLM's answer text
        
    Returns:
        dict: JSON structure with answer and tool_calls
    """
    return {
        "answer": answer,
        "tool_calls": []
    }


def main():
    """Main entry point: orchestrate the agent workflow."""
    # Parse arguments
    question = parse_args()
    print(f"Question: {question}", file=sys.stderr)
    
    # Load configuration
    config = load_config()
    
    # Call LLM
    answer = call_llm(
        question=question,
        api_key=config['api_key'],
        api_base=config['api_base'],
        model=config['model']
    )
    
    # Format and output result
    result = format_output(answer)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
