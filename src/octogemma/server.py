"""FastAPI Web Server for OctoGemma Studio."""

import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import OctoGemmaAgent
from .config import settings
from .llm import OllamaClient
from .tools import ToolExecutor

app = FastAPI(
    title="OctoGemma Studio",
    description="Web Studio for OctoGemma Autonomous Coding Agent",
    version="0.1.0"
)

# CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

ollama_client = OllamaClient()


class RunTaskRequest(BaseModel):
    task: str
    workspace: Optional[str] = None
    model: Optional[str] = None
    max_steps: Optional[int] = 25


class PullModelRequest(BaseModel):
    model: str


@app.get("/")
async def root():
    """Serve the Web Studio SPA."""
    index_path = WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Web UI not built")
    return FileResponse(str(index_path))


@app.get("/api/health")
async def health_check():
    """Check backend and Ollama connectivity."""
    ollama_ok = await ollama_client.check_health()
    return {
        "status": "healthy",
        "ollama_connected": ollama_ok,
        "ollama_url": ollama_client.base_url,
        "workspace": str(settings.workspace_dir)
    }


@app.get("/api/models")
async def list_models():
    """Retrieve installed models from local Ollama."""
    models = await ollama_client.list_models()
    preferred = await ollama_client.get_preferred_model()
    return {
        "models": models,
        "preferred": preferred,
        "default": settings.default_model
    }


@app.post("/api/pull")
async def pull_model(req: PullModelRequest):
    """Stream model download progress via SSE."""
    async def event_generator():
        async for chunk in ollama_client.pull_model_stream(req.model):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/files")
async def get_files(path: str = "."):
    """Get workspace directory tree."""
    tools = ToolExecutor(settings.workspace_dir)
    return tools.list_directory(path=path, max_depth=4)


@app.get("/api/file")
async def get_file_content(path: str = Query(...)):
    """Read a specific file from the workspace."""
    tools = ToolExecutor(settings.workspace_dir)
    return tools.read_file(path=path)


@app.get("/api/diff")
async def get_diff():
    """Get current git diff and status."""
    tools = ToolExecutor(settings.workspace_dir)
    return tools.get_git_diff()


@app.post("/api/agent/run")
async def run_agent_stream(req: RunTaskRequest):
    """Stream autonomous agent reasoning, tool execution, and diffs via SSE."""
    ws = Path(req.workspace).resolve() if req.workspace else settings.workspace_dir
    agent = OctoGemmaAgent(
        workspace=ws,
        model=req.model,
        max_steps=req.max_steps or 25,
        ollama_client=ollama_client
    )

    async def event_generator():
        async for event in agent.run(req.task):
            payload = json.dumps(event, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
