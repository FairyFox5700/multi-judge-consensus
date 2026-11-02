"""FastAPI application: REST API + static web UI for the multi-judge consensus demo."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.consensus import multi_judge_consensus
from app.judges import ALL_JUDGES
from app.models import ConsensusResult, EvaluationRequest

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="Multi-Judge Consensus",
    description=(
        "Evaluates whether an AI agent completed a customer task correctly, using "
        "multiple LLM judges in parallel and flagging disagreement for human review."
    ),
    version="1.0.0",
)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/judges")
async def list_judges() -> dict:
    """Reports which judges are live (calling a real provider) vs demo (mock)."""
    modes = {
        "gpt-4o": "live" if settings.has_openai and not settings.force_demo_mode else "demo",
        "gpt-4o-mini": "live" if settings.has_openai and not settings.force_demo_mode else "demo",
        "claude": "live" if settings.has_anthropic and not settings.force_demo_mode else "demo",
    }
    return {
        "judges": [judge.__name__ for judge in ALL_JUDGES],
        "modes": modes,
        "review_threshold": settings.review_threshold,
    }


@app.post("/api/evaluate", response_model=ConsensusResult)
async def evaluate(request: EvaluationRequest) -> ConsensusResult:
    return await multi_judge_consensus(request)


# Serve CSS/JS assets. Mounted after the explicit routes above so "/" still returns index.html.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
