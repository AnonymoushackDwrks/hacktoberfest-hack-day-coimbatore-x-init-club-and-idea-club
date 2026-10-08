"""Autonomous tool definitions and workspace sandbox execution."""

import difflib
import fnmatch
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


IGNORED_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".gemini"}


class ToolExecutor:
    """Executes file operations and terminal commands safely within a target workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.history: List[Dict[str, Any]] = []

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve path and ensure it stays within workspace sandbox."""
        clean_path = Path(relative_path).expanduser()
        if not clean_path.is_absolute():
            resolved = (self.workspace / clean_path).resolve()
        else:
            resolved = clean_path.resolve()

        try:
            resolved.relative_to(self.workspace)
        except ValueError:
            raise PermissionError(f"Access denied: path '{relative_path}' is outside workspace '{self.workspace}'")

        return resolved

    def list_directory(self, path: str = ".", max_depth: int = 3) -> Dict[str, Any]:
        """List files and directories in workspace up to max_depth."""
        target = self._resolve_path(path)
        if not target.exists():
            return {"error": f"Path '{path}' does not exist"}

        entries: List[Dict[str, Any]] = []

        def walk(current: Path, depth: int):
            if depth > max_depth:
                return
            try:
                for item in sorted(current.iterdir()):
                    if item.name in IGNORED_DIRS or item.name.startswith("."):
                        continue
                    rel = str(item.relative_to(self.workspace)).replace("\\", "/")
                    if item.is_dir():
                        entries.append({"path": rel, "type": "directory"})
                        walk(item, depth + 1)
                    else:
                        entries.append({
                            "path": rel,
                            "type": "file",
                            "size_bytes": item.stat().st_size
                        })
            except PermissionError:
                pass

        walk(target, 1)
        return {"workspace": str(self.workspace), "total_items": len(entries), "items": entries}

    def read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> Dict[str, Any]:
        """Read text file contents with line numbering and optional range."""
        target = self._resolve_path(path)
        if not target.exists():
            return {"error": f"File '{path}' does not exist"}
        if target.is_dir():
            return {"error": f"'{path}' is a directory, not a file"}

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s = max(1, start_line or 1)
            e = min(total_lines, end_line or total_lines)

            if s > total_lines:
                return {"error": f"start_line ({s}) exceeds total lines ({total_lines})"}

            selected = lines[s - 1:e]
            numbered = [f"{s + idx}: {line}" for idx, line in enumerate(selected)]

            return {
                "path": path,
                "total_lines": total_lines,
                "start_line": s,
                "end_line": e,
                "content": "".join(numbered)
            }
        except Exception as ex:
            return {"error": f"Failed to read file '{path}': {str(ex)}"}

    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file, creating parent directories if needed."""
        target = self._resolve_path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            self.history.append({"action": "write_file", "path": path})
            return {"success": True, "path": path, "bytes_written": len(content.encode("utf-8"))}
        except Exception as ex:
            return {"error": f"Failed to write file '{path}': {str(ex)}"}

    def edit_file(self, path: str, search_pattern: str, replacement: str) -> Dict[str, Any]:
        """Perform exact search and replace in a file and generate diff."""
        target = self._resolve_path(path)
        if not target.exists():
            return {"error": f"File '{path}' does not exist"}

        try:
            with open(target, "r", encoding="utf-8") as f:
                original = f.read()

            normalized_orig = original.replace("\r\n", "\n")
            normalized_search = search_pattern.replace("\r\n", "\n")
            normalized_replace = replacement.replace("\r\n", "\n")

            if normalized_search not in normalized_orig:
                return {
                    "error": f"Search string not found in '{path}'. Please ensure exact whitespace and indentation match."
                }

            count = normalized_orig.count(normalized_search)
            if count > 1:
                return {
                    "error": f"Search pattern matched {count} times in '{path}'. Provide a more unique block of surrounding code."
                }

            updated = normalized_orig.replace(normalized_search, normalized_replace, 1)

            # Compute unified diff
            diff = list(difflib.unified_diff(
                normalized_orig.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm=""
            ))

            with open(target, "w", encoding="utf-8") as f:
                f.write(updated)

            diff_text = "".join(diff)
            self.history.append({"action": "edit_file", "path": path, "diff": diff_text})

            return {
                "success": True,
                "path": path,
                "diff": diff_text,
                "message": f"Successfully replaced code block in '{path}'"
            }
        except Exception as ex:
            return {"error": f"Failed to edit file '{path}': {str(ex)}"}

    def grep_search(self, pattern: str, directory: str = ".", is_regex: bool = False) -> Dict[str, Any]:
        """Search for text pattern or regex across workspace files."""
        target_dir = self._resolve_path(directory)
        matches: List[Dict[str, Any]] = []

        try:
            regex = re.compile(pattern if is_regex else re.escape(pattern), re.IGNORECASE)
        except Exception as ex:
            return {"error": f"Invalid regex pattern: {str(ex)}"}

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.workspace)).replace("\\", "/")
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, start=1):
                            if regex.search(line):
                                matches.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "content": line.strip()
                                })
                                if len(matches) >= 50:
                                    return {"matches": matches, "truncated": True}
                except Exception:
                    continue

        return {"matches": matches, "total_matches": len(matches), "truncated": False}

    def run_command(self, command: str, timeout: int = 45) -> Dict[str, Any]:
        """Execute a shell command inside the workspace directory."""
        try:
            # On Windows, use powershell or cmd with DEVNULL stdin to prevent handle inheritance errors
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            exit_code = proc.returncode

            self.history.append({"action": "run_command", "command": command, "exit_code": exit_code})

            return {
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "success": exit_code == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "exit_code": -1,
                "error": f"Command timed out after {timeout} seconds",
                "success": False
            }
        except Exception as ex:
            return {
                "command": command,
                "exit_code": -1,
                "error": f"Execution failed: {str(ex)}",
                "success": False
            }

    def get_git_diff(self) -> Dict[str, Any]:
        """Fetch git status and git diff in the workspace."""
        res_status = self.run_command("git status -s")
        res_diff = self.run_command("git diff")
        return {
            "status": res_status.get("stdout", ""),
            "diff": res_diff.get("stdout", "")
        }


# Standard Tool Schemas for Ollama / Function Calling
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and subdirectories in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to list (default: '.')"},
                    "max_depth": {"type": "integer", "description": "Maximum directory traversal depth (default: 3)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to read"},
                    "start_line": {"type": "integer", "description": "Optional start line number (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Optional end line number (inclusive)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of file to create or overwrite"},
                    "content": {"type": "string", "description": "Full file content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace an exact target code snippet within a file with replacement code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "search_pattern": {"type": "string", "description": "Exact text block to replace"},
                    "replacement": {"type": "string", "description": "New replacement text block"}
                },
                "required": ["path", "search_pattern", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for text or regex pattern across workspace files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern string"},
                    "directory": {"type": "string", "description": "Directory to search within (default: '.')"},
                    "is_regex": {"type": "boolean", "description": "Treat pattern as regular expression"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command (e.g. pytest, python script.py, npm test) in workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The exact shell command to run"},
                    "timeout": {"type": "integer", "description": "Execution timeout in seconds (default: 45)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Call this tool when the task has been fully accomplished and verified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Summary of actions taken, verified tests, and changes made"}
                },
                "required": ["summary"]
            }
        }
    }
]
