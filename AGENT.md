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

## Task 2: The Documentation Agent

### Overview

Task 2 extends the agent with tool-calling capabilities, enabling it to read project documentation and provide answers with source references.

### New Capabilities

1. **Two Tools**: `read_file` and `list_files` for navigating the wiki directory
2. **Agentic Loop**: LLM decides which tools to call, we execute them, feed results back
3. **Source Tracking**: Extract and include wiki file references in answers
4. **Tool Call History**: Record all tool calls in the JSON output

### Tools

#### `read_file(path: str) -> str`

Reads a file from the project repository.

**Parameters**:
- `path` (string) - Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns**: File contents as string, or error message if file doesn't exist

**Security**: 
- Validates path doesn't escape project directory (no `../` traversal)
- Uses `os.path.abspath()` and `startswith()` to ensure path is within project
- Returns error message for paths outside project root

**Example**:
```python
read_file("wiki/git-workflow.md")
# Returns: "# Git Workflow\n\n## Resolving merge conflicts..."
```

#### `list_files(path: str) -> str`

Lists files and directories at a given path.

**Parameters**:
- `path` (string) - Relative directory path from project root (e.g., `wiki`)

**Returns**: Newline-separated list of entries

**Security**: Same path validation as `read_file`

**Example**:
```python
list_files("wiki")
# Returns: "api.md\narchitecture.md\ngit-workflow.md\n..."
```

### Agentic Loop

The agentic loop is the core of the documentation agent:

```
1. Send question + tool schemas to LLM
   ↓
2. LLM response contains tool_calls?
   ↓
   YES → Execute each tool
      → Append results as 'tool' role messages
      → Add to conversation history
      → Go to step 1 (max 10 iterations)
   ↓
   NO → Extract final answer
      → Parse source reference from answer
      → Output JSON and exit
```

**Key Features**:
- Maximum 10 iterations to prevent infinite loops
- Tools are executed sequentially within each iteration
- Tool results are fed back to the LLM for reasoning
- Loop terminates when LLM provides a final answer (no tool calls)

**Implementation**: `agentic_loop()` function in `agent.py`

### System Prompt Strategy

Updated system prompt guides the LLM in using tools effectively:

```
You are a helpful documentation assistant for a software engineering project.

Your task is to answer questions about the project by reading the documentation 
in the wiki/ directory.

Follow these steps:
1. Use list_files to discover what documentation files are available in wiki/
2. Use read_file to read relevant documentation files
3. Provide a concise answer based on the documentation
4. Include a source reference in the format: wiki/filename.md#section-anchor

When citing sources:
- Always reference the specific wiki file that contains the answer
- Include a section anchor when possible (e.g., #resolving-merge-conflicts)
- Format: wiki/filename.md#section-anchor or just wiki/filename.md
```

### Source Extraction

The agent extracts source references from the LLM's final answer using regex:

```python
def extract_source(answer: str) -> str:
    # Look for wiki/filename.md or wiki/filename.md#section patterns
    match = re.search(r'wiki/[\w-]+\.md(?:#[\w-]+)?', answer)
    return match.group(0) if match else "unknown"
```

### Updated Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\nautochecker.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git Workflow\n\n## Resolving merge conflicts..."
    }
  ]
}
```

**Fields**:
- `answer` - LLM's final answer based on documentation
- `source` - Wiki file reference (e.g., `wiki/file.md#section`)
- `tool_calls` - Array of all tool calls made during the agentic loop

### Usage Examples

**List files in wiki**:
```bash
uv run agent.py "What files are in the wiki?"
```

**Documentation question**:
```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Testing

Tests for Task 2 in `tests/test_task2.py`:

1. **Documentation question test**: Verifies agent uses `read_file` and extracts correct source
2. **List files test**: Verifies agent uses `list_files` and returns wiki contents

Run tests:
```bash
uv run pytest tests/test_task3.py -v
```

### Lessons Learned

**Tool Description Quality Matters**: The LLM's tool selection heavily depends on clear, specific tool descriptions. Vague descriptions lead to wrong tool choices.

**Environment Variables Are Critical**: All configuration must come from environment variables. The autochecker uses different LLM providers and backend URLs during evaluation.

**Multi-step Reasoning Works**: The agentic loop successfully chains tools - querying an API to see an error, then reading source code to diagnose the bug. Max 10 iterations prevents infinite loops.

**SSL Verification**: Disabled SSL verification (`verify=False`) for local development to avoid certificate issues with localhost. Production deployments should enable proper SSL.

## Future Tasks

- **Task 4**: Add support for user authentication and authorization
