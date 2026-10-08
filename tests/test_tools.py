"""Unit tests for OctoGemma ToolExecutor and sandbox safety."""

import os
import pytest
from pathlib import Path
from src.octogemma.tools import ToolExecutor


@pytest.fixture
def temp_workspace(tmp_path: Path):
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    (ws / "sample.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    (ws / "subfolder").mkdir()
    (ws / "subfolder" / "nested.txt").write_text("Nested data\nLine 2\n", encoding="utf-8")
    return ws


def test_list_directory(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.list_directory(".")
    assert "items" in res
    paths = [item["path"] for item in res["items"]]
    assert "sample.py" in paths
    assert "subfolder" in paths


def test_read_file(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.read_file("sample.py")
    assert "content" in res
    assert "def hello():" in res["content"]


def test_read_file_range(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.read_file("subfolder/nested.txt", start_line=2, end_line=2)
    assert "Line 2" in res["content"]
    assert "Nested data" not in res["content"]


def test_write_file(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.write_file("new_dir/test.txt", "Content here")
    assert res.get("success") is True
    assert (temp_workspace / "new_dir" / "test.txt").read_text(encoding="utf-8") == "Content here"


def test_edit_file(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.edit_file("sample.py", "return 'world'", "return 'gemini'")
    assert res.get("success") is True
    assert "diff" in res
    assert "-    return 'world'" in res["diff"]
    assert "+    return 'gemini'" in res["diff"]
    content = (temp_workspace / "sample.py").read_text(encoding="utf-8")
    assert "return 'gemini'" in content


def test_grep_search(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.grep_search("hello")
    assert len(res["matches"]) >= 1
    assert res["matches"][0]["file"] == "sample.py"


def test_sandbox_security(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    with pytest.raises(PermissionError):
        executor.read_file("../../outside.txt")


def test_run_command(temp_workspace: Path):
    executor = ToolExecutor(temp_workspace)
    res = executor.run_command("python -c \"print('Sandbox Test')\"")
    assert res["exit_code"] == 0
    assert "Sandbox Test" in res["stdout"]
