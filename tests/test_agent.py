"""Unit tests for OctoGemma Agent logic and tool parsing."""

import json
import pytest
from pathlib import Path
from src.octogemma.agent import OctoGemmaAgent


@pytest.fixture
def agent(tmp_path: Path):
    return OctoGemmaAgent(workspace=tmp_path)


def test_parse_fallback_tool_call_markdown(agent: OctoGemmaAgent):
    text = """Let me edit the file to fix the bug.
```json
{
  "name": "edit_file",
  "arguments": {
    "path": "test.py",
    "search_pattern": "foo",
    "replacement": "bar"
  }
}
```
"""
    call = agent._parse_fallback_tool_call(text)
    assert call is not None
    assert call["name"] == "edit_file"
    assert call["arguments"]["path"] == "test.py"


def test_parse_fallback_tool_call_xml(agent: OctoGemmaAgent):
    text = """Thinking about what to run...
<tool_call>
{"name": "run_command", "arguments": {"command": "pytest tests/"}}
</tool_call>
"""
    call = agent._parse_fallback_tool_call(text)
    assert call is not None
    assert call["name"] == "run_command"
    assert call["arguments"]["command"] == "pytest tests/"


def test_parse_fallback_tool_call_inline(agent: OctoGemmaAgent):
    text = '{"name": "read_file", "arguments": {"path": "main.py"}}'
    call = agent._parse_fallback_tool_call(text)
    assert call is not None
    assert call["name"] == "read_file"
    assert call["arguments"]["path"] == "main.py"


def test_execute_tool_finish(agent: OctoGemmaAgent):
    res = agent.execute_tool("finish_task", {"summary": "Fixed calculations"})
    assert res["success"] is True
    assert res["summary"] == "Fixed calculations"
