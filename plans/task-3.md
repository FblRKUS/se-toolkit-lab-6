# Task 3 Implementation Plan: The System Agent

## Goal

Add `query_api` tool to enable the agent to query the deployed backend API for system facts and data-dependent questions.

## Key Additions to Task 2

1. **New tool**: `query_api` for HTTP requests to backend API
2. **Authentication**: Use `LMS_API_KEY` from `.env.docker.secret`
3. **Environment variables**: Read all config from env vars (no hardcoding)
4. **Updated system prompt**: Guide LLM to choose between wiki tools and API queries
5. **Benchmark**: Pass `run_eval.py` (10 local questions)

## New Tool: `query_api`

### Purpose
Send HTTP requests to the deployed backend API to answer system questions.

### Parameters
```python
{
  "method": "GET",        # HTTP method (GET, POST, etc.)
  "path": "/items/",      # API endpoint path
  "body": "{...}"         # Optional JSON request body (for POST/PUT)
}
```

### Returns
JSON string with status code and response body:
```json
{
  "status_code": 200,
  "body": {...}
}
```

### Implementation Strategy

**HTTP Client**: Use `requests` library (already in dependencies)

**Authentication**: 
- Read `LMS_API_KEY` from environment variables
- Add `Authorization: Bearer <LMS_API_KEY>` header to all requests

**Base URL**:
- Read `AGENT_API_BASE_URL` from env vars
- Default to `http://localhost:42002` if not set

**Error Handling**:
- Catch connection errors (backend not running)
- Return error information in the result JSON
- Don't crash the agent on API errors

### Tool Schema

```python
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
```

### Implementation

```python
import requests

def query_api(method: str, path: str, body: str = None) -> str:
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
        # Make request
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=body,
            timeout=30.0
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
```

## Environment Variables Configuration

### Current Setup (Task 2)
```python
load_dotenv('.env.agent.secret')
```

### Updated Setup (Task 3)
Load both `.env.agent.secret` and `.env.docker.secret`:

```python
def load_config() -> Dict[str, str]:
    """Load configuration from environment files and variables."""
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
        sys.exit(1)
    
    if not lms_api_key:
        print("Error: Missing LMS_API_KEY in .env.docker.secret", file=sys.stderr)
        sys.exit(1)
    
    return {
        'llm_api_key': api_key,
        'llm_api_base': api_base,
        'llm_model': model,
        'lms_api_key': lms_api_key,
        'agent_api_base_url': agent_api_base_url
    }
```

## Updated System Prompt

The LLM needs guidance on when to use each tool:

```python
def get_system_prompt() -> str:
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
```

## Benchmark Evaluation Strategy

### Initial Run
1. Run `uv run run_eval.py` to see which questions pass/fail
2. Record initial score and failures in this document
3. Identify patterns in failures

### Iteration Process
For each failing question:
1. Read the question type (wiki, system, data, bug, reasoning)
2. Check tool calls made - were correct tools used?
3. Check tool results - did tools return expected data?
4. Check answer format - does it match expected keywords?
5. Adjust either:
   - Tool descriptions (if wrong tool used)
   - Tool implementation (if tool errors)
   - System prompt (if answer phrasing wrong)

### Expected Question Classes

| Class | Example | Expected Tools | Success Criteria |
|-------|---------|----------------|------------------|
| Wiki lookup | "How to protect a branch?" | `list_files`, `read_file` | Answer contains wiki reference |
| System facts | "What framework?" | `query_api` or `read_file` | Answer contains "FastAPI" |
| Data queries | "How many items?" | `query_api` | Answer contains plausible number |
| Bug diagnosis | "Why does /analytics/X fail?" | `query_api`, `read_file` | Identifies the bug location |
| Reasoning | "Explain request lifecycle" | Multiple tools | Coherent multi-step explanation |

## Testing Strategy

Add 2 tests in `tests/test_task3.py`:

**Test 1: System fact question**
```python
def test_system_question_uses_query_api():
    """Test that system questions use query_api or read_file."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'What Python framework does the backend use?'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0
    output = json.loads(result.stdout.strip())
    
    # Should use either query_api or read_file
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert 'query_api' in tool_names or 'read_file' in tool_names
    
    # Answer should mention FastAPI
    assert 'fastapi' in output['answer'].lower()
```

**Test 2: Data query question**
```python
def test_data_question_uses_query_api():
    """Test that data questions use query_api."""
    result = subprocess.run(
        ['uv', 'run', 'agent.py', 'How many items are in the database?'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    assert result.returncode == 0
    output = json.loads(result.stdout.strip())
    
    # Should use query_api
    tool_names = [tc['tool'] for tc in output['tool_calls']]
    assert 'query_api' in tool_names
    
    # Should have a query to /items/
    query_calls = [tc for tc in output['tool_calls'] if tc['tool'] == 'query_api']
    assert any('/items' in tc['args']['path'] for tc in query_calls)
```

## Acceptance Criteria Checklist

- [ ] `plans/task-3.md` exists (this file)
- [ ] `agent.py` defines `query_api` tool schema
- [ ] `query_api` authenticates with `LMS_API_KEY` from environment
- [ ] All LLM config read from environment variables
- [ ] `AGENT_API_BASE_URL` read from environment (defaults to localhost:42002)
- [ ] System prompt updated to guide tool selection
- [ ] `run_eval.py` passes 10/10 local questions
- [ ] `AGENT.md` updated with Task 3 documentation (≥200 words)
- [ ] 2 regression tests for query_api exist and pass
- [ ] Git workflow followed

## Benchmark Results (to be filled after first run)

### Initial Run
```
Score: __/10
```

**Failures:**
- [ ] Question X: ...

### Iteration Log
- Iteration 1: Fixed ... → Score: __/10
- Iteration 2: Fixed ... → Score: __/10
- ...

### Final Score
```
Score: 10/10 ✓
```
