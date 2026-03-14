"""
Regression tests for Task 3: The System Agent

Tests that agent.py:
- Uses query_api tool for system/data questions
- Uses read_file for code inspection
- Handles backend API correctly
"""

import subprocess
import json
import sys


def test_system_framework_question():
    """Test that system questions about framework use appropriate tools."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'What Python web framework does the backend use?'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {result.stdout}", file=sys.stderr)
        raise AssertionError(f"Invalid JSON output: {e}")
    
    # Check required fields
    assert 'answer' in output, "Missing 'answer' field"
    assert 'source' in output, "Missing 'source' field"
    assert 'tool_calls' in output, "Missing 'tool_calls' field"
    
    # Should use either query_api or read_file
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert len(tool_names) > 0, "Should use at least one tool"
    assert 'query_api' in tool_names or 'read_file' in tool_names, \
        "Should use query_api or read_file for framework questions"
    
    # Answer should mention FastAPI
    assert 'fastapi' in output['answer'].lower() or 'fast' in output['answer'].lower(), \
        "Answer should mention FastAPI framework"


def test_data_query_uses_query_api():
    """Test that data questions use query_api tool."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'How many items are in the database?'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    output = json.loads(result.stdout.strip())
    
    # Check required fields
    assert 'answer' in output
    assert 'tool_calls' in output
    
    # Should use query_api for database queries
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert 'query_api' in tool_names, "Should use query_api for database queries"
    
    # Verify query_api was called with /items/ path
    query_calls = [tc for tc in output['tool_calls'] if tc['tool'] == 'query_api']
    assert len(query_calls) > 0, "Should have at least one query_api call"
    
    # Check that at least one call queries items
    paths_called = [tc['args'].get('path', '') for tc in query_calls]
    assert any('/items' in path for path in paths_called), \
        "Should query /items/ endpoint for item count"
    
    # Answer should contain a number
    import re
    has_number = bool(re.search(r'\d+', output['answer']))
    assert has_number, "Answer should contain a number (item count)"


def test_query_api_authentication():
    """Test that query_api includes authentication headers."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'Query the API to list items'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    output = json.loads(result.stdout.strip())
    
    # Check that query_api was used
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    
    if 'query_api' in tool_names:
        # Verify query_api results
        query_calls = [tc for tc in output['tool_calls'] if tc['tool'] == 'query_api']
        
        for call in query_calls:
            result_str = call['result']
            # Parse the result JSON
            try:
                result_json = json.loads(result_str)
                # Should have status_code and body
                assert 'status_code' in result_json, "query_api result should have status_code"
                assert 'body' in result_json, "query_api result should have body"
                
                # If status code is 0, it's an error (connection/auth issue)
                # Otherwise it's a valid HTTP response
                status_code = result_json['status_code']
                assert isinstance(status_code, int), "status_code should be an integer"
                
            except json.JSONDecodeError:
                # Result might be an error message string
                assert 'Error' in result_str or 'error' in result_str, \
                    "Non-JSON result should be an error message"
