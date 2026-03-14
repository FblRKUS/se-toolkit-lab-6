"""
Regression tests for Task 2: The Documentation Agent

Tests that agent.py:
- Uses tools (read_file, list_files) to answer documentation questions
- Populates tool_calls array with tool usage
- Includes source field with wiki file reference
- Handles documentation questions correctly
"""

import subprocess
import json
import sys


def test_documentation_question():
    """Test agent with a documentation question that requires reading wiki files."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'How do you resolve a merge conflict?'],
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
    assert 'answer' in output, "Missing 'answer' field in output"
    assert 'source' in output, "Missing 'source' field in output"
    assert 'tool_calls' in output, "Missing 'tool_calls' field in output"
    
    # Validate answer
    assert isinstance(output['answer'], str), "'answer' must be a string"
    assert len(output['answer']) > 0, "'answer' cannot be empty"
    
    # Validate source
    assert isinstance(output['source'], str), "'source' must be a string"
    assert 'wiki/' in output['source'], "'source' should reference a wiki file"
    
    # Validate tool_calls
    assert isinstance(output['tool_calls'], list), "'tool_calls' must be a list"
    assert len(output['tool_calls']) > 0, "'tool_calls' should not be empty for documentation questions"
    
    # Check that read_file was used
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert 'read_file' in tool_names, "Agent should use 'read_file' to answer documentation questions"
    
    # Verify tool call structure
    for tool_call in output['tool_calls']:
        assert 'tool' in tool_call, "Each tool call must have 'tool' field"
        assert 'args' in tool_call, "Each tool call must have 'args' field"
        assert 'result' in tool_call, "Each tool call must have 'result' field"
        
        assert isinstance(tool_call['tool'], str), "'tool' must be a string"
        assert isinstance(tool_call['args'], dict), "'args' must be a dict"
        assert isinstance(tool_call['result'], str), "'result' must be a string"


def test_list_files_question():
    """Test agent with a question that requires listing files."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'What files are in the wiki?'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0, f"Agent exited with code {result.returncode}"
    
    output = json.loads(result.stdout.strip())
    
    # Check required fields
    assert 'answer' in output
    assert 'source' in output
    assert 'tool_calls' in output
    
    # Validate tool_calls
    assert len(output['tool_calls']) > 0, "'tool_calls' should not be empty"
    
    # Check that list_files was used
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert 'list_files' in tool_names, "Agent should use 'list_files' to list wiki files"
    
    # Verify list_files was called with wiki path
    list_files_calls = [tc for tc in output['tool_calls'] if tc['tool'] == 'list_files']
    assert len(list_files_calls) > 0, "At least one list_files call should be made"
    
    # Check that the result contains some wiki files
    for lf_call in list_files_calls:
        if lf_call['args'].get('path') == 'wiki':
            result_text = lf_call['result']
            assert 'git-workflow.md' in result_text or '.md' in result_text, \
                "list_files result should contain wiki markdown files"
            break


def test_tool_security_no_directory_traversal():
    """Test that tools reject attempts to access files outside project directory."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'Read the file at ../../../etc/passwd'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    # Agent should still succeed (return 0) but tools should deny access
    assert result.returncode == 0, "Agent should handle security violations gracefully"
    
    output = json.loads(result.stdout.strip())
    
    # If any tools were called, check that they returned errors for invalid paths
    if output['tool_calls']:
        for tool_call in output['tool_calls']:
            if '../' in str(tool_call['args'].get('path', '')):
                result_text = tool_call['result']
                assert 'Error' in result_text or 'denied' in result_text.lower(), \
                    "Tools should reject directory traversal attempts"
