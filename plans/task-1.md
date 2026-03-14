# Task 1 Implementation Plan: Call an LLM from Code

## Goal

Build a CLI program `agent.py` that takes a user question, sends it to an LLM via BotHub API, and returns a JSON response with `answer` and `tool_calls` fields.

## LLM Provider

**Provider**: BotHub (https://bothub.chat)
- **API Endpoint**: `https://bothub.chat/api/v2/openai/v1/chat/completions`
- **Model**: `qwen3-235b-a22b-2507`
- **API Key**: Stored in `.env.agent.secret` (already configured)
- **Compatibility**: OpenAI-compatible chat completions API

## Architecture

### Main Components

1. **`parse_args()`** - Parse command line arguments
   - Input: `sys.argv`
   - Output: question string
   - Error handling: Exit with code 1 if no question provided

2. **`load_config()`** - Load credentials from `.env.agent.secret`
   - Read: `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
   - Use `python-dotenv` to load environment variables

3. **`call_llm(question, api_key, api_base, model)`** - Call BotHub API
   - Build request payload with system + user messages
   - Send POST request to chat completions endpoint
   - Handle errors: timeouts, API errors, network issues
   - Return: LLM response text

4. **`format_output(answer)`** - Format JSON response
   - Structure: `{"answer": "...", "tool_calls": []}`
   - Output to stdout (print to stdout)
   - Empty `tool_calls` array for Task 1

5. **`main()`** - Orchestrate the flow
   - Parse args → Load config → Call LLM → Format output
   - Debug output to stderr only
   - Exit code 0 on success, 1 on error

### System Prompt

Minimal prompt for Task 1:
```
You are a helpful assistant. Answer the user's question concisely and accurately.
```

Will expand in Tasks 2-3 when adding tools and domain knowledge.

## Error Handling

- **No question provided**: Print usage to stderr, exit 1
- **API timeout**: 60 second timeout, exit 1 with error message to stderr
- **API errors**: Catch HTTP errors, print to stderr, exit 1
- **Invalid response**: Handle empty/malformed responses

## Testing Strategy

Create `tests/test_task1.py`:
- Run `agent.py` as subprocess with test question
- Capture stdout
- Parse JSON
- Verify:
  - Valid JSON structure
  - `answer` field exists and is non-empty string
  - `tool_calls` field exists and is empty array
  - Exit code is 0

## Dependencies

- `openai` - For OpenAI-compatible API calls
- `python-dotenv` - For loading `.env.agent.secret`
- Already in project: `pytest` for testing

## Data Flow

```
User question (CLI arg)
  ↓
parse_args()
  ↓
load_config() → .env.agent.secret
  ↓
call_llm() → BotHub API
  ↓
format_output()
  ↓
stdout: {"answer": "...", "tool_calls": []}
```

## Acceptance Criteria Checklist

- [ ] `plans/task-1.md` exists (this file)
- [ ] `agent.py` with modular functions
- [ ] `.env.agent.secret` configured (already done)
- [ ] Valid JSON output to stdout
- [ ] Debug output to stderr only
- [ ] `AGENT.md` documentation
- [ ] 1 regression test passing
- [ ] Git workflow: commit plan first, then implementation
