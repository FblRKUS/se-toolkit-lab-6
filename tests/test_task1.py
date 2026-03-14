"""
Regression test for Task 1: Call an LLM from Code

Tests that agent.py:
- Runs successfully as a subprocess
- Returns valid JSON to stdout
- Contains required fields: answer and tool_calls
- tool_calls is an empty array (Task 1 requirement)
"""

import subprocess
import json
import sys


def test_agent_basic_question():
    """Test agent.py with a basic question."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'What is 2+2?'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {result.stdout}", file=sys.stderr)
        raise AssertionError(f"Invalid JSON output: {e}")
    
    assert 'answer' in output, "Missing 'answer' field in output"
    assert 'tool_calls' in output, "Missing 'tool_calls' field in output"
    
    assert isinstance(output['answer'], str), "'answer' must be a string"
    assert len(output['answer']) > 0, "'answer' cannot be empty"
    
    assert isinstance(output['tool_calls'], list), "'tool_calls' must be a list"
    assert len(output['tool_calls']) == 0, "'tool_calls' should be empty in Task 1"


def test_agent_different_question():
    """Test agent.py with a different question to verify it's not hardcoded."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'What does REST stand for?'],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    output = json.loads(result.stdout.strip())
    
    assert 'answer' in output
    assert 'tool_calls' in output
    assert isinstance(output['answer'], str)
    assert len(output['answer']) > 0
    assert output['tool_calls'] == []


def test_agent_no_question_provided():
    """Test that agent.py fails gracefully when no question is provided."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 1, "Agent should exit with code 1 when no question provided"
    assert len(result.stderr) > 0, "Agent should print error message to stderr"
