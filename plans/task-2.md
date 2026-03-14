# Task 2 Implementation Plan: The Documentation Agent

## Goal

Add tool-calling capabilities to the agent from Task 1, enabling it to read project documentation and provide answers with source references.

## Key Additions to Task 1

1. **Two tools**: `read_file` and `list_files` for wiki navigation
2. **Agentic loop**: LLM calls tools → execute → feed results back → LLM decides next action
3. **Source field**: Track which wiki file/section answered the question
4. **Tool call tracking**: Record all tool calls in the JSON output

## Tools Implementation

### 1. `read_file(path: str) -> str`

**Purpose**: Read file contents from the project directory.

**Parameters**:
- `path` (string) - Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns**: File contents as string, or error message if file doesn't exist

**Security**:
- Validate path doesn't escape project directory (no `../` traversal)
- Use `os.path.abspath()` and `os.path.commonpath()` to ensure path is within project
- Return error message for invalid paths

**Implementation**:
```python
def read_file(path: str) -> str:
    # Validate path is within project
    project_root = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.abspath(os.path.join(project_root, path))
    
    if not file_path.startswith(project_root):
        return "Error: Access denied - path outside project directory"
    
    if not os.path.exists(file_path):
        return f"Error: File not found: {path}"
    
    with open(file_path, 'r') as f:
        return f.read()
```

### 2. `list_files(path: str) -> str`

**Purpose**: List files and directories at a given path.

**Parameters**:
- `path` (string) - Relative directory path from project root (e.g., `wiki`)

**Returns**: Newline-separated list of entries

**Security**: Same path validation as `read_file`

**Implementation**:
```python
def list_files(path: str) -> str:
    # Validate path
    project_root = os.path.abspath(os.path.dirname(__file__))
    dir_path = os.path.abspath(os.path.join(project_root, path))
    
    if not dir_path.startswith(project_root):
        return "Error: Access denied - path outside project directory"
    
    if not os.path.exists(dir_path):
        return f"Error: Directory not found: {path}"
    
    entries = os.listdir(dir_path)
    return '\n'.join(sorted(entries))
```

## Function Calling Schema

Define tools as OpenAI function-calling schemas:

```python
tools = [
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
```

## Agentic Loop Architecture

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

### Loop Implementation

```python
def agentic_loop(question, client, model, max_iterations=10):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    
    tool_call_history = []
    
    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS
        )
        
        message = response.choices[0].message
        
        # No tool calls = final answer
        if not message.tool_calls:
            return {
                "answer": message.content,
                "tool_calls": tool_call_history
            }
        
        # Execute tool calls
        messages.append(message)  # Add assistant response
        
        for tool_call in message.tool_calls:
            result = execute_tool(tool_call)
            tool_call_history.append({
                "tool": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments),
                "result": result
            })
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
    
    # Hit max iterations
    return {
        "answer": "Max iterations reached",
        "tool_calls": tool_call_history
    }
```

## System Prompt Strategy

Updated system prompt to guide the LLM in using tools effectively:

```
You are a helpful documentation assistant for a software engineering project.

Your task is to answer questions about the project by reading the documentation in the wiki/ directory.

Follow these steps:
1. Use list_files to discover what documentation files are available in the wiki/ directory
2. Use read_file to read relevant documentation files
3. Provide a concise answer based on the documentation
4. Include a source reference in the format: wiki/filename.md#section-anchor

When citing sources:
- Always reference the specific wiki file that contains the answer
- Include a section anchor when possible (e.g., #resolving-merge-conflicts)
- Format: wiki/filename.md#section-anchor

Be concise and accurate. Only use information from the project files.
```

## Source Field Extraction

The LLM should include source reference in its final answer. Parse it:

```python
def extract_source(answer_text):
    # Look for wiki/filename.md or wiki/filename.md#section patterns
    import re
    match = re.search(r'wiki/[\w-]+\.md(?:#[\w-]+)?', answer_text)
    return match.group(0) if match else "unknown"
```

## Output Format

Updated JSON structure:

```json
{
  "answer": "Edit the conflicting file...",
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

## Error Handling

| Error | Behavior |
|-------|----------|
| Invalid tool path (../) | Return error message, don't execute |
| File not found | Return error message to LLM |
| Max iterations (10) reached | Return best answer so far |
| No source found | Use "unknown" as source |

## Testing Strategy

Add 2 new tests in `tests/test_task2.py`:

**Test 1: Documentation question**
- Question: "How do you resolve a merge conflict?"
- Verify: `read_file` in tool_calls
- Verify: `wiki/git-workflow.md` in source
- Verify: answer contains relevant information

**Test 2: List files**
- Question: "What files are in the wiki?"
- Verify: `list_files` in tool_calls
- Verify: tool_calls has results
- Verify: answer mentions wiki files

## Code Structure Changes

### New Functions

1. `get_tool_schemas()` - Return tool definitions
2. `execute_tool(tool_call)` - Execute read_file or list_files
3. `read_file(path)` - Tool implementation
4. `list_files(path)` - Tool implementation
5. `agentic_loop(question, client, model)` - Main loop
6. `extract_source(answer)` - Parse source from answer

### Updated Functions

1. `call_llm()` - Replace with `agentic_loop()`
2. `format_output()` - Add `source` field
3. System prompt - Updated to guide tool usage

## Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists (this file)
- [ ] Tool schemas defined for `read_file` and `list_files`
- [ ] Agentic loop implemented (max 10 iterations)
- [ ] Path security validation (no directory traversal)
- [ ] `source` field in JSON output
- [ ] `tool_calls` array populated with tool usage
- [ ] `AGENT.md` updated with tool documentation
- [ ] 2 regression tests for tool-calling scenarios
- [ ] Git workflow: issue, branch, PR, review, merge
