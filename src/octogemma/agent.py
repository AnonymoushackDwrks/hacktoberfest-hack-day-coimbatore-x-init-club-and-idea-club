"""Autonomous Agent Engine with ReAct, Tool-Calling, and Self-Healing capabilities."""

import json
import logging
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from .config import settings
from .llm import OllamaClient
from .tools import AGENT_TOOLS, ToolExecutor

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are OctoGemma, an elite autonomous software engineering agent.
Your mission is to understand user objectives, explore codebases, autonomously fix bugs, implement features, run tests, and self-repair errors.

### AVAILABLE TOOLS:
You can invoke the following tools to interact with the workspace:
1. `list_directory`: List files and subdirectories.
   Arguments: `{"path": ".", "max_depth": 3}`
2. `read_file`: Read file contents with line numbers.
   Arguments: `{"path": "relative/path/to/file.py", "start_line": 1, "end_line": 100}`
3. `write_file`: Create or overwrite a file.
   Arguments: `{"path": "file.py", "content": "..."}`
4. `edit_file`: Replace an exact code block within a file with replacement code.
   Arguments: `{"path": "file.py", "search_pattern": "exact existing code", "replacement": "new replacement code"}`
5. `grep_search`: Search text or regex across the workspace.
   Arguments: `{"pattern": "def my_func", "directory": "."}`
6. `run_command`: Execute a shell command in the workspace (e.g. pytest, python script.py).
   Arguments: `{"command": "pytest examples/demo_repo", "timeout": 45}`
7. `finish_task`: Call when the objective is verified and complete.
   Arguments: `{"summary": "Summary of verified changes made."}`

### HOW TO INVOKE A TOOL:
Whenever you want to take an action, explain your reasoning, then output a JSON tool call block:
```json
{
  "name": "tool_name",
  "arguments": {
    "param": "value"
  }
}
```

### RULES:
1. Read or inspect code first before editing.
2. When fixing bugs, run tests (`run_command`) to confirm the failure and verify the fix.
3. If an error or test failure occurs, inspect the traceback and self-heal your code.
4. When all tests pass, invoke `finish_task`.
"""


class AgentEvent:
    """Agent lifecycle event yielded during execution."""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.type = event_type
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, **self.data}


class OctoGemmaAgent:
    """Autonomous Coding Agent Engine."""

    def __init__(
        self,
        workspace: Optional[Path] = None,
        model: Optional[str] = None,
        max_steps: Optional[int] = None,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.workspace = (workspace or settings.workspace_dir).resolve()
        self.tools = ToolExecutor(self.workspace)
        self.client = ollama_client or OllamaClient()
        self.model = model or settings.default_model
        self.max_steps = max_steps or settings.max_steps
        self.messages: List[Dict[str, Any]] = []

    def _parse_fallback_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse tool calls if the model printed JSON or XML in text rather than native schema."""
        # 1. Check XML-style <tool_call>...</tool_call>
        xml_match = re.search(r"<tool_call>[\s\n]*({.*?})[\s\n]*</tool_call>", text, re.DOTALL)
        if xml_match:
            try:
                return json.loads(xml_match.group(1))
            except Exception:
                pass

        # 2. Check markdown ```json ... ``` blocks
        code_blocks = re.findall(r"```(?:json)?\s*({[\s\S]*?})\s*```", text)
        for block in code_blocks:
            try:
                parsed = json.loads(block)
                if ("name" in parsed or "tool" in parsed or "action" in parsed):
                    return {
                        "name": parsed.get("name") or parsed.get("tool") or parsed.get("action"),
                        "arguments": parsed.get("arguments") or parsed.get("parameters") or parsed.get("args") or parsed.get("action_input") or {}
                    }
                # Check format {"tool_name": {args}}
                for tname in ("read_file", "edit_file", "write_file", "run_command", "list_directory", "grep_search", "finish_task"):
                    if tname in parsed and isinstance(parsed[tname], dict):
                        return {"name": tname, "arguments": parsed[tname]}
            except Exception:
                continue

        # 3. Check inline JSON with {"name": "...", "arguments": ...}
        inline_match = re.search(r'\{\s*"(?:name|tool|action)"\s*:\s*"([a-zA-Z0-9_]+)"\s*,\s*"(?:arguments|parameters|args|action_input)"\s*:\s*(\{.*?\})\s*\}', text, re.DOTALL)
        if inline_match:
            try:
                return {
                    "name": inline_match.group(1),
                    "arguments": json.loads(inline_match.group(2))
                }
            except Exception:
                pass

        # 4. Check "Action: tool_name\nAction Input: {...}" pattern
        action_match = re.search(r'Action:\s*([a-zA-Z0-9_]+)\s*\n+Action Input:\s*({[\s\S]*?})', text)
        if action_match:
            try:
                return {
                    "name": action_match.group(1).strip(),
                    "arguments": json.loads(action_match.group(2))
                }
            except Exception:
                pass

        # 5. Check if entire text or trailing block is valid JSON object
        raw_json_match = re.search(r'({[\s\S]*})', text)
        if raw_json_match:
            try:
                parsed = json.loads(raw_json_match.group(1))
                if "name" in parsed:
                    return {
                        "name": parsed["name"],
                        "arguments": parsed.get("arguments", parsed.get("args", {}))
                    }
            except Exception:
                pass

        # 6. Check markdown bash / shell code blocks (e.g. ```bash \n pytest ... \n ```)
        bash_match = re.search(r"```(?:bash|sh|shell|zsh|powershell|cmd)?\s*\n+([\s\S]*?)\n*```", text)
        if bash_match:
            cmd = bash_match.group(1).strip()
            if cmd and not cmd.startswith("{") and not cmd.startswith("def ") and not cmd.startswith("class ") and not cmd.startswith("import "):
                first_line = cmd.split("\n")[0].strip()
                if first_line in ("ls", "dir", "ls -la", "ls -l"):
                    return {"name": "list_directory", "arguments": {"path": "."}}
                return {"name": "run_command", "arguments": {"command": first_line}}

        # 7. Check explicit inline pytest commands
        if "pytest" in text.lower():
            p_match = re.search(r"`(pytest[a-zA-Z0-9_\-\.\/ ]*)`", text, re.IGNORECASE)
            if p_match:
                return {"name": "run_command", "arguments": {"command": p_match.group(1).strip()}}

        return None

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool invocation to ToolExecutor."""
        try:
            if name == "list_directory":
                return self.tools.list_directory(
                    path=args.get("path", "."),
                    max_depth=int(args.get("max_depth", 3))
                )
            elif name == "read_file":
                return self.tools.read_file(
                    path=args["path"],
                    start_line=args.get("start_line"),
                    end_line=args.get("end_line")
                )
            elif name == "write_file":
                return self.tools.write_file(
                    path=args["path"],
                    content=args["content"]
                )
            elif name == "edit_file":
                return self.tools.edit_file(
                    path=args["path"],
                    search_pattern=args["search_pattern"],
                    replacement=args["replacement"]
                )
            elif name == "grep_search":
                return self.tools.grep_search(
                    pattern=args["pattern"],
                    directory=args.get("directory", "."),
                    is_regex=bool(args.get("is_regex", False))
                )
            elif name == "run_command":
                return self.tools.run_command(
                    command=args["command"],
                    timeout=int(args.get("timeout", 45))
                )
            elif name == "finish_task":
                return {"success": True, "summary": args.get("summary", "Task completed.")}
            else:
                return {"error": f"Unknown tool: '{name}'"}
        except Exception as ex:
            return {"error": f"Tool execution error: {str(ex)}"}

    async def run(self, user_instruction: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute autonomous agent loop and stream lifecycle events."""
        # 1. Determine active model
        active_model = await self.client.get_preferred_model(self.model)
        yield AgentEvent("agent_started", {
            "model": active_model,
            "workspace": str(self.workspace),
            "instruction": user_instruction,
            "max_steps": self.max_steps
        }).to_dict()

        # 2. Initialize conversation messages
        self.messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User Objective:\n{user_instruction}\n\nWorkspace Directory: {self.workspace}\nPlease resolve the task autonomously. Verify your solution with tests/commands before calling finish_task."
            }
        ]

        step = 0
        task_completed = False
        consecutive_failures = 0

        while step < self.max_steps and not task_completed:
            step += 1
            yield AgentEvent("step_start", {"step": step, "max_steps": self.max_steps}).to_dict()

            # Call LLM
            try:
                response = await self.client.chat(
                    model=active_model,
                    messages=self.messages,
                    tools=AGENT_TOOLS,
                    temperature=0.2
                )
            except Exception as ex:
                yield AgentEvent("error", {"message": f"LLM communication error: {str(ex)}"}).to_dict()
                return

            assistant_msg = response.get("message", {})
            raw_content = assistant_msg.get("content", "") or ""
            native_tool_calls = assistant_msg.get("tool_calls", [])

            # Emit thoughts
            if raw_content:
                yield AgentEvent("thought", {"thought": raw_content, "step": step}).to_dict()

            # Record assistant turn in context
            self.messages.append(assistant_msg)

            # Determine tool call to execute
            tool_name: Optional[str] = None
            tool_args: Dict[str, Any] = {}

            if native_tool_calls:
                call_info = native_tool_calls[0]
                func = call_info.get("function", {})
                tool_name = func.get("name")
                tool_args = func.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}
            else:
                # Attempt fallback parsing from raw text
                fallback = self._parse_fallback_tool_call(raw_content)
                if fallback:
                    tool_name = fallback.get("name")
                    tool_args = fallback.get("arguments", {})

            # If no tool was chosen by model
            if not tool_name:
                # If model finished in text without calling finish_task
                if any(w in raw_content.lower() for w in ("completed", "finished", "all tests pass", "mission accomplished")):
                    yield AgentEvent("task_finished", {
                        "step": step,
                        "summary": raw_content,
                        "verified": True
                    }).to_dict()
                    task_completed = True
                    break
                elif step == 1:
                    # In step 1, if model was conversational or gave advice, auto-kickstart workspace inspection
                    tool_name = "list_directory"
                    tool_args = {"path": "."}
                else:
                    # Nudge model strictly to output a tool call
                    self.messages.append({
                        "role": "user",
                        "content": "Action required: You must execute an action now using JSON syntax, for example:\n```json\n{\"name\": \"run_command\", \"arguments\": {\"command\": \"pytest examples/demo_repo\"}}\n```"
                    })
                    continue

            # Check if finished
            if tool_name == "finish_task":
                summary = tool_args.get("summary", raw_content or "Task completed.")
                yield AgentEvent("task_finished", {
                    "step": step,
                    "summary": summary,
                    "verified": True
                }).to_dict()
                task_completed = True
                break

            # Announce tool call
            yield AgentEvent("tool_call", {
                "step": step,
                "tool": tool_name,
                "arguments": tool_args
            }).to_dict()

            # Execute tool
            tool_result = self.execute_tool(tool_name, tool_args)

            # If it was an edit/write, emit diff event
            if tool_name == "edit_file" and tool_result.get("success"):
                yield AgentEvent("diff_updated", {
                    "path": tool_result.get("path"),
                    "diff": tool_result.get("diff")
                }).to_dict()

            # Check for command failure or tool errors to trigger self-healing alert
            is_failure = False
            if "error" in tool_result:
                is_failure = True
            elif tool_name == "run_command" and not tool_result.get("success"):
                is_failure = True

            if is_failure:
                consecutive_failures += 1
                yield AgentEvent("self_healing_triggered", {
                    "step": step,
                    "tool": tool_name,
                    "reason": tool_result.get("error") or tool_result.get("stderr") or "Command failed",
                    "attempt": consecutive_failures
                }).to_dict()
            else:
                consecutive_failures = 0

            # Yield tool result
            yield AgentEvent("tool_result", {
                "step": step,
                "tool": tool_name,
                "result": tool_result
            }).to_dict()

            # Append tool result to context messages
            tool_result_str = json.dumps(tool_result, ensure_ascii=False)
            if native_tool_calls:
                self.messages.append({
                    "role": "tool",
                    "content": tool_result_str
                })
            else:
                self.messages.append({
                    "role": "user",
                    "content": f"[Observation from tool '{tool_name}']:\n{tool_result_str}\n\nPlease analyze this result and decide your next action or tool call. If the task is verified and complete, call finish_task."
                })

        if not task_completed and step >= self.max_steps:
            yield AgentEvent("step_limit_reached", {
                "step": step,
                "message": f"Agent reached maximum execution steps ({self.max_steps})."
            }).to_dict()
