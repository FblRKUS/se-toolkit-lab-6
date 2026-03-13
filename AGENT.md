# Agent Architecture

This document describes the implementation of the LLM-powered agent CLI built across Tasks 1-3.

## Task 1: Call an LLM from Code

### Overview

The agent is a Python CLI program that takes a user question, sends it to an LLM, and returns a JSON response.

### Architecture

The agent follows a modular design with separate functions for each responsibility:

```
User Question (CLI arg)
    ↓
parse_args() - Validate and extract question
    ↓
load_config() - Load credentials from .env.agent.secret
    ↓
call_llm() - Send request to LLM API
    ↓
format_output() - Structure JSON response
    ↓
stdout: {"answer": "...", "tool_calls": []}
```

### LLM Provider

**Provider**: BotHub (https://bothub.chat)

- **API Endpoint**: `https://bothub.chat/api/v2/openai/v1`
- **Model**: `qwen3-235b-a22b-2507`
- **Authentication**: JWT token stored in `.env.agent.secret`
- **API Compatibility**: OpenAI-compatible chat completions API

**Why BotHub?**
- OpenAI-compatible API (easy integration via `openai` Python package)
- Reliable access from any location
- Good model for general questions

### Components

#### 1. `parse_args()`
Parses command-line arguments and validates the question.

**Input**: `sys.argv`  
**Output**: Question string  
**Error handling**: Exits with code 1 if no question provided

#### 2. `load_config()`
Loads LLM configuration from `.env.agent.secret`.

**Reads**:
- `LLM_API_KEY` - API authentication token
- `LLM_API_BASE` - API endpoint URL
- `LLM_MODEL` - Model name to use

**Error handling**: Exits with code 1 if configuration is missing

#### 3. `call_llm(question, api_key, api_base, model)`
Sends the question to BotHub API and retrieves the answer.

**System prompt**:
```
You are a helpful assistant. Answer the user's question concisely and accurately.
```

**Request structure**:
- Model: Configured in `.env.agent.secret`
- Messages: System prompt + user question
- Timeout: 60 seconds

**Error handling**: Catches API errors, timeouts, network issues and exits with code 1

#### 4. `format_output(answer)`
Formats the LLM response as JSON.

**Output structure**:
```json
{
  "answer": "LLM's response text",
  "tool_calls": []
}
```

Note: `tool_calls` is empty in Task 1 (will be populated in Task 2)

#### 5. `main()`
Orchestrates the workflow by calling the above functions in sequence.

### Output Format

**stdout**: Valid JSON with `answer` and `tool_calls` fields  
**stderr**: Debug messages (question, model name, response length)  
**Exit code**: 0 on success, 1 on error

### Usage

```bash
# Basic usage
uv run agent.py "What is REST?"

# Example output
{"answer": "REST stands for Representational State Transfer...", "tool_calls": []}
```

### Configuration

Create `.env.agent.secret` from template:

```bash
cp .env.agent.example .env.agent.secret
```

Edit `.env.agent.secret`:

```env
LLM_API_KEY=your-bothub-api-key
LLM_API_BASE=https://bothub.chat/api/v2/openai/v1
LLM_MODEL=qwen3-235b-a22b-2507
```

### Dependencies

- `openai` - OpenAI-compatible API client
- `python-dotenv` - Environment variable loading
- `pytest` - Testing framework

### Error Handling

| Error | Behavior |
|-------|----------|
| No question provided | Print usage to stderr, exit 1 |
| Missing configuration | Print error to stderr, exit 1 |
| API timeout (>60s) | Print error to stderr, exit 1 |
| API error | Print error to stderr, exit 1 |
| Network error | Print error to stderr, exit 1 |

### Testing

Regression test in `tests/test_task1.py`:

- Runs `agent.py` as subprocess
- Parses stdout JSON
- Verifies `answer` and `tool_calls` fields exist
- Checks exit code is 0

Run tests:

```bash
uv run pytest tests/test_task1.py -v
```

## Future Tasks

- **Task 2**: Add tool calling capability (populate `tool_calls` array)
- **Task 3**: Implement agentic loop with tool execution
